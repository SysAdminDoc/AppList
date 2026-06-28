"""Application scanner engine — discovers installed software from multiple sources."""

import codecs
import hashlib
import json
import os
import re
import struct
import subprocess
import sys
import winreg
from datetime import datetime, timedelta
from pathlib import Path
from time import monotonic
from typing import Callable, Dict, List, Optional, Tuple

from .models import Application, ScanDiagnostic
from .constants import REGISTRY_PATHS

try:
    from windowsprefetch import Prefetch
except ImportError:
    Prefetch = None  # type: ignore[assignment]


FILETIME_EPOCH = datetime(1601, 1, 1)
USERASSIST_ROOT = r"Software\Microsoft\Windows\CurrentVersion\Explorer\UserAssist"
HASH_CACHE_FILENAME = "wingetlist-sha-cache.json"
HASH_SKIP_EXECUTABLE_PARTS = (
    "unins",
    "uninstall",
    "setup",
    "install",
    "update",
    "crash",
    "helper",
    "service",
)


class ApplicationScanner:
    """Core engine for scanning installed applications from multiple sources."""

    def __init__(self, progress_callback=None, status_callback=None):
        self.progress_callback = progress_callback
        self.status_callback = status_callback
        self.applications: List[Application] = []
        self.scan_diagnostics: List[ScanDiagnostic] = []
        self.seen_apps: set = set()
        self._cancelled = False
        self._active_diagnostic: Optional[ScanDiagnostic] = None

    def cancel(self):
        """Cancel the scanning operation."""
        self._cancelled = True

    def _update_progress(self, value: float, maximum: float = 100):
        if self.progress_callback:
            self.progress_callback(value, maximum)

    def _update_status(self, status: str):
        if self.status_callback:
            self.status_callback(status)

    def _log_warning(self, message: str):
        if self._active_diagnostic is not None:
            self._active_diagnostic.warnings.append(message)
        print(f"Warning: {message}", file=sys.stderr)

    def _record_skipped_source(self, source: str):
        self.scan_diagnostics.append(ScanDiagnostic(source=source, status="skipped"))

    def _run_diagnostic_step(
        self,
        source: str,
        scanner: Callable[[], List[Application]],
    ) -> List[Application]:
        diagnostic = ScanDiagnostic(source=source, status="running")
        self.scan_diagnostics.append(diagnostic)
        previous_diagnostic = self._active_diagnostic
        self._active_diagnostic = diagnostic
        started = monotonic()
        try:
            rows = scanner()
        except Exception as e:
            diagnostic.status = "failed"
            diagnostic.warnings.append(str(e))
            print(f"Warning: {source} scan failed: {e}", file=sys.stderr)
            rows = []
        finally:
            diagnostic.duration_seconds = round(monotonic() - started, 3)
            self._active_diagnostic = previous_diagnostic

        diagnostic.row_count = len(rows)
        if diagnostic.status == "running":
            diagnostic.status = "warning" if diagnostic.warnings else "ok"
        return rows

    def _normalize_name(self, name: str) -> str:
        """Normalize application name for deduplication."""
        return re.sub(r'[^\w]', '', name.lower())

    def _format_size(self, size_kb: int) -> str:
        """Format size in KB to human-readable string."""
        if size_kb <= 0:
            return ""
        if size_kb < 1024:
            return f"{size_kb} KB"
        elif size_kb < 1024 * 1024:
            return f"{size_kb / 1024:.1f} MB"
        else:
            return f"{size_kb / (1024 * 1024):.2f} GB"

    def _parse_install_date(self, date_str: str) -> str:
        """Parse install date from various formats."""
        if not date_str:
            return ""
        try:
            if len(date_str) == 8 and date_str.isdigit():
                return f"{date_str[:4]}-{date_str[4:6]}-{date_str[6:]}"
            return date_str
        except (TypeError, ValueError):
            return date_str

    def _filetime_to_string(self, filetime: int) -> str:
        """Convert a Windows FILETIME integer to AppList's timestamp string."""
        if filetime <= 0:
            return ""
        try:
            dt = FILETIME_EPOCH + timedelta(microseconds=filetime / 10)
        except (OverflowError, ValueError):
            return ""

        now = datetime.now()
        if dt.year < 1990 or dt > now + timedelta(days=2):
            return ""
        return dt.strftime("%Y-%m-%d %H:%M:%S")

    def _parse_datetime_string(self, value: str) -> str:
        """Normalize parser timestamps to AppList's timestamp string."""
        if not value:
            return ""
        cleaned = str(value).strip().replace("T", " ").replace("Z", "")
        for fmt in ("%Y-%m-%d %H:%M:%S.%f", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
            try:
                return datetime.strptime(cleaned[:26], fmt).strftime("%Y-%m-%d %H:%M:%S")
            except ValueError:
                continue
        return ""

    def _timestamp_key(self, value: str) -> datetime:
        parsed = self._parse_datetime_string(value)
        if not parsed:
            return FILETIME_EPOCH
        return datetime.strptime(parsed, "%Y-%m-%d %H:%M:%S")

    def _newer_timestamp(self, current: str, candidate: str) -> str:
        candidate = self._parse_datetime_string(candidate)
        if not candidate:
            return current
        if not current:
            return candidate
        return candidate if self._timestamp_key(candidate) > self._timestamp_key(current) else current

    def _extract_userassist_timestamp(self, payload: bytes) -> str:
        """Read the last-run FILETIME from UserAssist binary payloads."""
        if not isinstance(payload, (bytes, bytearray)):
            return ""
        for offset in (60, 8):
            if len(payload) < offset + 8:
                continue
            timestamp = self._filetime_to_string(struct.unpack_from("<Q", payload, offset)[0])
            if timestamp:
                return timestamp
        return ""

    def _strip_userassist_prefix(self, decoded_name: str) -> str:
        value = decoded_name.strip("\x00 ")
        for prefix in ("UEME_RUNPATH:", "UEME_RUNPIDL:", "UEME_CTLCUACOUNT:", "UEME_CTLSESSION:"):
            if value.upper().startswith(prefix):
                return value[len(prefix):]
        return value

    def _candidate_keys(self, value: str) -> set:
        """Return normalized matching keys for an app name, path, executable, or ID."""
        if not value:
            return set()

        raw = os.path.expandvars(str(value).strip().strip('"').strip("'"))
        if not raw:
            return set()

        cleaned = re.sub(r"^\[(?:Folder|Store)\]\s*", "", raw, flags=re.IGNORECASE)
        normalized_path = cleaned.replace("/", "\\")
        pieces = {raw, cleaned}

        for token in re.split(r"[!|]", cleaned):
            if token.strip():
                pieces.add(token.strip())

        basename = os.path.basename(normalized_path.rstrip("\\"))
        if basename:
            pieces.add(basename)
            stem, _ = os.path.splitext(basename)
            if stem:
                pieces.add(stem)

        if "." in cleaned and "\\" not in cleaned:
            pieces.add(cleaned.split(".")[-1])

        return {self._normalize_name(piece) for piece in pieces if self._normalize_name(piece)}

    def _record_last_used(self, mapping: Dict[str, str], candidates: set, timestamp: str):
        for key in candidates:
            mapping[key] = self._newer_timestamp(mapping.get(key, ""), timestamp)

    def _build_userassist_last_used_map(self) -> Dict[str, str]:
        """Build normalized app/path keys from UserAssist launch history."""
        last_used: Dict[str, str] = {}
        try:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, USERASSIST_ROOT, 0, winreg.KEY_READ) as root:
                guid_count = winreg.QueryInfoKey(root)[0]
                for guid_index in range(guid_count):
                    if self._cancelled:
                        break
                    guid_name = winreg.EnumKey(root, guid_index)
                    try:
                        with winreg.OpenKey(root, f"{guid_name}\\Count", 0, winreg.KEY_READ) as count_key:
                            value_count = winreg.QueryInfoKey(count_key)[1]
                            for value_index in range(value_count):
                                try:
                                    raw_name, payload, _ = winreg.EnumValue(count_key, value_index)
                                except OSError:
                                    continue
                                timestamp = self._extract_userassist_timestamp(payload)
                                if not timestamp:
                                    continue
                                decoded_name = codecs.decode(raw_name, "rot_13")
                                clean_name = self._strip_userassist_prefix(decoded_name)
                                self._record_last_used(last_used, self._candidate_keys(clean_name), timestamp)
                    except (FileNotFoundError, OSError, PermissionError):
                        continue
        except (FileNotFoundError, OSError, PermissionError, AttributeError) as e:
            self._log_warning(f"UserAssist last-used data could not be scanned: {e}")
        return last_used

    def _build_prefetch_last_used_map(self) -> Dict[str, str]:
        """Build normalized executable keys from Windows Prefetch files."""
        last_used: Dict[str, str] = {}
        if Prefetch is None:
            self._log_warning("Prefetch parser is not installed; last-used Prefetch data skipped.")
            return last_used

        prefetch_dir = Path(os.environ.get("WINDIR", r"C:\Windows")) / "Prefetch"
        try:
            pf_files = list(prefetch_dir.glob("*.pf"))
        except (OSError, PermissionError) as e:
            self._log_warning(f"Prefetch last-used data could not be scanned: {e}")
            return last_used

        failed = 0
        for pf_path in pf_files:
            if self._cancelled:
                break
            try:
                parsed = Prefetch(str(pf_path))
                timestamp = ""
                for raw_timestamp in getattr(parsed, "timestamps", []) or []:
                    timestamp = self._newer_timestamp(timestamp, str(raw_timestamp))
                if not timestamp:
                    continue

                executable_name = str(getattr(parsed, "executableName", "") or "")
                fallback_name = pf_path.name.split("-")[0]
                self._record_last_used(
                    last_used,
                    self._candidate_keys(executable_name) | self._candidate_keys(fallback_name),
                    timestamp,
                )
            except (OSError, PermissionError, struct.error, UnicodeDecodeError, ValueError, IndexError):
                failed += 1

        if failed:
            self._log_warning(f"{failed} Prefetch files could not be parsed.")
        return last_used

    def _application_last_used_candidates(self, app: Application) -> set:
        candidates = set()
        for value in (app.name, app.install_location, app.winget_id):
            candidates.update(self._candidate_keys(value))

        if app.install_location and os.path.isdir(app.install_location):
            try:
                for child in os.listdir(app.install_location):
                    if child.lower().endswith(".exe"):
                        candidates.update(self._candidate_keys(child))
            except (OSError, PermissionError):
                pass
        return candidates

    def _apply_last_used_dates(self):
        """Enrich collected applications with best-effort last-used timestamps."""
        if not self.applications:
            return

        self._update_status("Phase 8/9: Reading last-used activity...")
        self._update_progress(84)

        userassist_map = self._build_userassist_last_used_map()
        self._update_progress(88)
        prefetch_map = self._build_prefetch_last_used_map()
        if not userassist_map and not prefetch_map:
            return

        for app in self.applications:
            last_used = ""
            for candidate in self._application_last_used_candidates(app):
                last_used = self._newer_timestamp(last_used, userassist_map.get(candidate, ""))
                last_used = self._newer_timestamp(last_used, prefetch_map.get(candidate, ""))
            app.last_used_date = last_used

    def _hash_cache_path(self) -> Path:
        appdata = os.environ.get("APPDATA")
        base_dir = Path(appdata) / "AppList" if appdata else Path.home() / ".applist"
        return base_dir / HASH_CACHE_FILENAME

    def _load_hash_cache(self) -> Dict[str, Dict[str, object]]:
        cache_path = self._hash_cache_path()
        try:
            if not cache_path.is_file():
                return {}
            with open(cache_path, encoding="utf-8") as f:
                data = json.load(f)
            return data if isinstance(data, dict) else {}
        except (OSError, json.JSONDecodeError, TypeError) as e:
            self._log_warning(f"Hash cache could not be read: {e}")
            return {}

    def _save_hash_cache(self, cache: Dict[str, Dict[str, object]]):
        cache_path = self._hash_cache_path()
        try:
            cache_path.parent.mkdir(parents=True, exist_ok=True)
            with open(cache_path, "w", encoding="utf-8") as f:
                json.dump(cache, f, indent=2, sort_keys=True)
        except OSError as e:
            self._log_warning(f"Hash cache could not be saved: {e}")

    def _hash_file_sha256(self, filepath: str) -> str:
        digest = hashlib.sha256()
        with open(filepath, "rb") as f:
            for chunk in iter(lambda: f.read(1024 * 1024), b""):
                digest.update(chunk)
        return digest.hexdigest()

    def _get_cached_sha256(self, filepath: str, cache: Dict[str, Dict[str, object]]) -> tuple:
        try:
            resolved = str(Path(filepath).resolve())
            stat = os.stat(resolved)
        except OSError:
            return "", False

        cached = cache.get(resolved)
        if (
            isinstance(cached, dict)
            and cached.get("size") == stat.st_size
            and cached.get("mtime") == stat.st_mtime
            and isinstance(cached.get("sha256"), str)
        ):
            return str(cached["sha256"]), False

        try:
            sha256_hash = self._hash_file_sha256(resolved)
        except OSError as e:
            self._log_warning(f"Could not hash {resolved}: {e}")
            return "", False

        cache[resolved] = {
            "sha256": sha256_hash,
            "size": stat.st_size,
            "mtime": stat.st_mtime,
            "cached_at": datetime.now().isoformat(timespec="seconds"),
        }
        return sha256_hash, True

    def _list_executables(self, location: str) -> List[str]:
        if not location:
            return []
        expanded = os.path.expandvars(location.strip().strip('"'))
        if os.path.isfile(expanded) and expanded.lower().endswith(".exe"):
            return [expanded]
        if not os.path.isdir(expanded):
            return []

        executables: List[str] = []
        child_dirs: List[str] = []
        try:
            with os.scandir(expanded) as entries:
                for entry in entries:
                    try:
                        if entry.is_file() and entry.name.lower().endswith(".exe"):
                            executables.append(entry.path)
                        elif entry.is_dir():
                            child_dirs.append(entry.path)
                    except OSError:
                        continue
        except (OSError, PermissionError):
            return []

        if executables:
            return executables

        for child_dir in child_dirs[:20]:
            try:
                with os.scandir(child_dir) as entries:
                    for entry in entries:
                        if entry.is_file() and entry.name.lower().endswith(".exe"):
                            executables.append(entry.path)
            except (OSError, PermissionError):
                continue
        return executables

    def _score_executable_candidate(self, app: Application, executable_path: str) -> float:
        name = os.path.basename(executable_path)
        stem, _ = os.path.splitext(name)
        stem_key = self._normalize_name(stem)
        app_keys = self._candidate_keys(app.name)
        score = 0.0

        if stem_key in app_keys:
            score += 100
        elif any(stem_key and (stem_key in key or key in stem_key) for key in app_keys):
            score += 55

        lowered = name.lower()
        if any(part in lowered for part in HASH_SKIP_EXECUTABLE_PARTS):
            score -= 35
        else:
            score += 15

        try:
            score += min(os.path.getsize(executable_path) / (1024 * 1024), 25)
        except OSError:
            pass
        return score

    def _find_primary_executable(self, app: Application) -> str:
        candidates = []
        if app.executable_path:
            candidates.extend(self._list_executables(app.executable_path))
        candidates.extend(self._list_executables(app.install_location))
        if not candidates:
            return ""
        deduped = sorted(set(candidates), key=lambda path: self._score_executable_candidate(app, path), reverse=True)
        return deduped[0] if deduped else ""

    def _apply_virustotal_hashes(self):
        """Hash primary executables and attach VirusTotal report URLs."""
        if not self.applications:
            return

        self._update_status("Phase 9/9: Hashing executable files...")
        self._update_progress(92)

        cache = self._load_hash_cache()
        cache_changed = False
        failures = 0
        total = len(self.applications)

        for index, app in enumerate(self.applications):
            if self._cancelled:
                break
            executable_path = self._find_primary_executable(app)
            if not executable_path:
                continue

            sha256_hash, changed = self._get_cached_sha256(executable_path, cache)
            if not sha256_hash:
                failures += 1
                continue

            cache_changed = cache_changed or changed
            app.executable_path = executable_path
            app.sha256_hash = sha256_hash
            app.virustotal_url = f"https://www.virustotal.com/gui/file/{sha256_hash}"

            if index % 10 == 0:
                self._update_progress(92 + (index / max(total, 1)) * 7)

        if cache_changed:
            self._save_hash_cache(cache)
        if failures:
            self._log_warning(f"{failures} executable hashes could not be calculated.")

    def _get_registry_value(self, key, value_name: str, default: str = "") -> str:
        """Safely get a registry value."""
        try:
            value, _ = winreg.QueryValueEx(key, value_name)
            return str(value) if value else default
        except (FileNotFoundError, OSError):
            return default

    def scan_registry(self) -> List[Application]:
        """Scan Windows Registry for installed applications."""
        apps = []
        total_paths = len(REGISTRY_PATHS)

        for idx, (hive, path, source_name) in enumerate(REGISTRY_PATHS):
            if self._cancelled:
                break

            self._update_status(f"Scanning registry: {source_name}...")
            self._update_progress((idx / total_paths) * 20)

            try:
                arch = "64-bit" if "WOW6432Node" not in path else "32-bit"
                if source_name == "HKCU":
                    arch = "User"

                access_flag = winreg.KEY_READ
                if "WOW6432Node" not in path and hive == winreg.HKEY_LOCAL_MACHINE:
                    access_flag |= winreg.KEY_WOW64_64KEY

                with winreg.OpenKey(hive, path, 0, access_flag) as key:
                    subkey_count = winreg.QueryInfoKey(key)[0]

                    for i in range(subkey_count):
                        if self._cancelled:
                            break
                        try:
                            subkey_name = winreg.EnumKey(key, i)
                            with winreg.OpenKey(key, subkey_name, 0, access_flag) as subkey:
                                name = self._get_registry_value(subkey, "DisplayName")

                                if not name:
                                    continue

                                # Skip system components and updates
                                system_component = self._get_registry_value(subkey, "SystemComponent")
                                if system_component == "1":
                                    continue

                                parent_name = self._get_registry_value(subkey, "ParentDisplayName")
                                if parent_name:
                                    continue

                                # Deduplicate
                                norm_name = self._normalize_name(name)
                                if norm_name in self.seen_apps:
                                    continue
                                self.seen_apps.add(norm_name)

                                # Build full registry path
                                hive_name = "HKEY_LOCAL_MACHINE" if hive == winreg.HKEY_LOCAL_MACHINE else "HKEY_CURRENT_USER"
                                full_reg_path = f"{hive_name}\\{path}\\{subkey_name}"

                                # Get size
                                size_kb = 0
                                try:
                                    size_kb = int(self._get_registry_value(subkey, "EstimatedSize", "0"))
                                except ValueError:
                                    pass

                                app = Application(
                                    name=name,
                                    publisher=self._get_registry_value(subkey, "Publisher"),
                                    version=self._get_registry_value(subkey, "DisplayVersion"),
                                    install_date=self._parse_install_date(
                                        self._get_registry_value(subkey, "InstallDate")
                                    ),
                                    install_location=self._get_registry_value(subkey, "InstallLocation"),
                                    uninstall_registry_key=full_reg_path,
                                    uninstall_command=self._get_registry_value(subkey, "UninstallString"),
                                    estimated_size=self._format_size(size_kb),
                                    source=source_name,
                                    architecture=arch,
                                    app_type="Desktop",
                                )
                                apps.append(app)

                        except (OSError, PermissionError):
                            continue

            except (FileNotFoundError, OSError, PermissionError) as e:
                self._log_warning(f"Registry source {source_name} could not be scanned: {e}")
                continue

        return apps

    def scan_store_apps(self) -> List[Application]:
        """Scan Microsoft Store / UWP applications."""
        apps = []
        self._update_status("Scanning Microsoft Store apps...")
        self._update_progress(22)

        try:
            # Use PowerShell to get AppX packages
            cmd = [
                "powershell", "-NoProfile", "-Command",
                "Get-AppxPackage | Select-Object Name, Publisher, Version, InstallLocation, PackageFullName | ConvertTo-Json"
            ]

            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=60,
                creationflags=subprocess.CREATE_NO_WINDOW
            )

            if result.returncode == 0 and result.stdout.strip():
                packages = json.loads(result.stdout)
                if not isinstance(packages, list):
                    packages = [packages]

                total = len(packages)
                for idx, pkg in enumerate(packages):
                    if self._cancelled:
                        break

                    self._update_progress(22 + (idx / total) * 12)

                    name = pkg.get("Name", "")
                    if not name:
                        continue

                    # Skip framework packages
                    if any(x in name.lower() for x in [".net", "vclibs", "framework", "microsoft.ui"]):
                        continue

                    # Create friendly name
                    display_name = name.split(".")[-1] if "." in name else name
                    display_name = re.sub(r'([a-z])([A-Z])', r'\1 \2', display_name)

                    norm_name = self._normalize_name(display_name)
                    if norm_name in self.seen_apps:
                        continue
                    self.seen_apps.add(norm_name)

                    publisher = pkg.get("Publisher", "")
                    # Clean up publisher string
                    if publisher:
                        pub_match = re.search(r'CN=([^,]+)', publisher)
                        if pub_match:
                            publisher = pub_match.group(1)

                    app = Application(
                        name=f"[Store] {display_name}",
                        publisher=publisher,
                        version=pkg.get("Version", ""),
                        install_location=pkg.get("InstallLocation", ""),
                        uninstall_registry_key="",
                        uninstall_command=f"Remove-AppxPackage {pkg.get('PackageFullName', '')}",
                        source="Microsoft Store",
                        architecture="UWP",
                        app_type="Store App",
                    )
                    apps.append(app)

        except (FileNotFoundError, subprocess.TimeoutExpired, subprocess.SubprocessError,
                json.JSONDecodeError, OSError, TypeError) as e:
            self._log_warning(f"Microsoft Store scan failed: {e}")

        return apps

    def scan_program_files(self) -> List[Application]:
        """Scan Program Files directories for additional applications."""
        apps = []
        self._update_status("Scanning Program Files directories...")
        self._update_progress(36)

        program_dirs = [
            os.environ.get("ProgramFiles", r"C:\Program Files"),
            os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)"),
            os.path.join(os.environ.get("LOCALAPPDATA", ""), "Programs"),
        ]

        total_dirs = len(program_dirs)

        for dir_idx, program_dir in enumerate(program_dirs):
            if self._cancelled:
                break
            if not os.path.exists(program_dir):
                continue

            try:
                subdirs = os.listdir(program_dir)
                for sub_idx, subdir in enumerate(subdirs):
                    if self._cancelled:
                        break

                    self._update_progress(36 + ((dir_idx * len(subdirs) + sub_idx) / (total_dirs * max(len(subdirs), 1))) * 14)

                    full_path = os.path.join(program_dir, subdir)
                    if not os.path.isdir(full_path):
                        continue

                    # Skip common system/framework folders
                    skip_folders = [
                        "common files", "windows", "microsoft", "internet explorer",
                        "windowsapps", "modifiablewindowsapps", "reference assemblies"
                    ]
                    if subdir.lower() in skip_folders:
                        continue

                    norm_name = self._normalize_name(subdir)
                    if norm_name in self.seen_apps:
                        continue

                    # Check if folder contains executables
                    has_exe = False
                    exe_path = ""
                    try:
                        for item in os.listdir(full_path):
                            if item.lower().endswith('.exe'):
                                has_exe = True
                                exe_path = os.path.join(full_path, item)
                                break
                    except PermissionError:
                        continue

                    if not has_exe:
                        continue

                    self.seen_apps.add(norm_name)

                    # Determine architecture from path
                    arch = "32-bit" if "x86" in program_dir.lower() else "64-bit"

                    app = Application(
                        name=f"[Folder] {subdir}",
                        install_location=full_path,
                        executable_path=exe_path,
                        source="Program Files Scan",
                        architecture=arch,
                        app_type="Desktop (Unregistered)",
                    )
                    apps.append(app)

            except (PermissionError, OSError):
                continue

        return apps

    def scan_chocolatey(self) -> List[Application]:
        """Scan Chocolatey installed packages from %PROGRAMDATA%\\chocolatey\\lib\\."""
        apps: List[Application] = []
        choco_lib = os.path.join(
            os.environ.get("ProgramData", r"C:\ProgramData"), "chocolatey", "lib"
        )
        if not os.path.isdir(choco_lib):
            return apps

        self._update_status("Scanning Chocolatey packages...")
        self._update_progress(52)

        try:
            pkg_dirs = [d for d in os.listdir(choco_lib) if os.path.isdir(os.path.join(choco_lib, d))]
        except OSError as e:
            self._log_warning(f"Chocolatey package directory could not be listed: {e}")
            return apps

        for pkg_dir in pkg_dirs:
            if self._cancelled:
                break
            norm = self._normalize_name(pkg_dir)
            if norm in self.seen_apps:
                continue

            pkg_path = os.path.join(choco_lib, pkg_dir)
            name = pkg_dir
            version = ""
            publisher = ""

            # Parse .nuspec for metadata
            try:
                nuspec_files = [f for f in os.listdir(pkg_path) if f.endswith(".nuspec")]
            except OSError as e:
                self._log_warning(f"Could not list Chocolatey metadata for {pkg_dir}: {e}")
                nuspec_files = []
            if nuspec_files:
                nuspec_path = os.path.join(pkg_path, nuspec_files[0])
                try:
                    import xml.etree.ElementTree as ET
                    tree = ET.parse(nuspec_path)
                    root = tree.getroot()
                    ns = root.tag.split("}")[0].lstrip("{") if "}" in root.tag else ""
                    prefix = f"{{{ns}}}" if ns else ""
                    meta = root.find(f"{prefix}metadata")
                    if meta is not None:
                        id_el = meta.find(f"{prefix}id")
                        ver_el = meta.find(f"{prefix}version")
                        auth_el = meta.find(f"{prefix}authors")
                        if id_el is not None and id_el.text:
                            name = id_el.text.strip()
                        if ver_el is not None and ver_el.text:
                            version = ver_el.text.strip()
                        if auth_el is not None and auth_el.text:
                            publisher = auth_el.text.strip()
                except (OSError, ET.ParseError, AttributeError) as e:
                    self._log_warning(f"Could not read Chocolatey metadata for {pkg_dir}: {e}")

            self.seen_apps.add(norm)
            apps.append(Application(
                name=name,
                version=version,
                publisher=publisher,
                install_location=pkg_path,
                source="Chocolatey",
                app_type="Chocolatey",
            ))

        return apps

    def scan_scoop(self) -> List[Application]:
        """Scan Scoop installed apps from ~\\scoop\\apps\\."""
        apps: List[Application] = []
        scoop_apps = os.path.join(os.path.expanduser("~"), "scoop", "apps")

        # Also check SCOOP env var
        scoop_env = os.environ.get("SCOOP", "")
        if scoop_env:
            scoop_apps = os.path.join(scoop_env, "apps")

        if not os.path.isdir(scoop_apps):
            return apps

        self._update_status("Scanning Scoop packages...")
        self._update_progress(58)

        try:
            app_dirs = [d for d in os.listdir(scoop_apps)
                        if os.path.isdir(os.path.join(scoop_apps, d)) and d != "scoop"]
        except OSError as e:
            self._log_warning(f"Scoop app directory could not be listed: {e}")
            return apps

        for app_dir in app_dirs:
            if self._cancelled:
                break
            norm = self._normalize_name(app_dir)
            if norm in self.seen_apps:
                continue

            app_path = os.path.join(scoop_apps, app_dir)
            current_path = os.path.join(app_path, "current")
            name = app_dir
            version = ""
            publisher = ""

            # Parse current\manifest.json
            manifest_path = os.path.join(current_path, "manifest.json")
            if os.path.isfile(manifest_path):
                try:
                    with open(manifest_path, encoding="utf-8") as f:
                        manifest = json.load(f)
                    version = str(manifest.get("version", "")).strip()
                    publisher = str(manifest.get("homepage", "")).strip()
                except (OSError, json.JSONDecodeError, TypeError, ValueError) as e:
                    self._log_warning(f"Could not read Scoop manifest for {app_dir}: {e}")

            # Fallback: version folder name
            if not version:
                try:
                    versions = [d for d in os.listdir(app_path)
                                if os.path.isdir(os.path.join(app_path, d)) and d != "current"]
                    if versions:
                        version = sorted(versions)[-1]
                except OSError as e:
                    self._log_warning(f"Could not list Scoop versions for {app_dir}: {e}")

            self.seen_apps.add(norm)
            apps.append(Application(
                name=name,
                version=version,
                publisher=publisher,
                install_location=current_path if os.path.isdir(current_path) else app_path,
                source="Scoop",
                app_type="Scoop",
            ))

        return apps

    def scan_pip(self) -> List[Application]:
        """Scan pip-installed Python packages."""
        apps: List[Application] = []
        self._update_status("Scanning Python (pip) packages...")
        self._update_progress(64)

        try:
            result = subprocess.run(
                [sys.executable, "-m", "pip", "list", "--format=json"],
                capture_output=True, text=True, timeout=30,
                creationflags=subprocess.CREATE_NO_WINDOW,
            )
            if result.returncode != 0:
                return apps

            packages = json.loads(result.stdout)
            for pkg in packages:
                if self._cancelled:
                    break
                pkg_name = str(pkg.get("name", "")).strip()
                if not pkg_name:
                    continue
                norm = self._normalize_name(pkg_name)
                if norm in self.seen_apps:
                    continue
                self.seen_apps.add(norm)
                apps.append(Application(
                    name=pkg_name,
                    version=str(pkg.get("version", "")).strip(),
                    publisher="",
                    source="Python (pip)",
                    app_type="Python Package",
                ))
        except (FileNotFoundError, subprocess.TimeoutExpired, subprocess.SubprocessError,
                json.JSONDecodeError, OSError) as e:
            self._log_warning(f"pip package scan failed: {e}")

        return apps

    def _build_winget_map(self) -> Dict[str, str]:
        """Build a normalized-name -> winget-package-ID map via winget list."""
        winget_map: Dict[str, str] = {}
        self._update_progress(73)
        try:
            # Try JSON output (winget 1.6+)
            result = subprocess.run(
                ["winget", "list", "--accept-source-agreements",
                 "--disable-interactivity", "--output", "json"],
                capture_output=True, text=True, timeout=90,
                creationflags=subprocess.CREATE_NO_WINDOW,
            )
            packages: List[Dict[str, str]] = []
            if result.returncode == 0 and result.stdout.strip():
                packages = self._parse_winget_json_packages(result.stdout)

            # Fall back to tabular text parsing
            if not packages:
                result = subprocess.run(
                    ["winget", "list", "--accept-source-agreements",
                     "--disable-interactivity"],
                    capture_output=True, text=True, timeout=90,
                    creationflags=subprocess.CREATE_NO_WINDOW,
                )
                if result.returncode == 0:
                    packages = self._parse_winget_table(result.stdout)
                    if not packages and result.stdout.strip():
                        self._log_warning(
                            "winget text output could not be parsed; structured output is required for this locale."
                        )

            for pkg in packages:
                name = self._winget_package_field(pkg, "Name")
                winget_id = self._winget_package_field(pkg, "Id")
                if name and winget_id:
                    winget_map[self._normalize_name(name)] = winget_id

        except (FileNotFoundError, subprocess.TimeoutExpired, subprocess.SubprocessError, OSError) as e:
            self._log_warning(f"winget list cross-reference failed: {e}")

        return winget_map

    def _winget_package_field(self, pkg: Dict[str, object], field: str) -> str:
        aliases = {
            "Name": ("Name", "PackageName", "Package", "DisplayName"),
            "Id": ("Id", "PackageIdentifier", "PackageId", "Identifier"),
            "Version": ("Version", "InstalledVersion", "PackageVersion"),
        }
        for key in aliases.get(field, (field,)):
            value = pkg.get(key)
            if value is not None:
                return str(value).strip()
        return ""

    def _parse_winget_json_packages(self, output: str) -> List[Dict[str, object]]:
        """Normalize known winget JSON shapes into package dictionaries."""
        try:
            data = json.loads(output)
        except json.JSONDecodeError:
            return []

        packages: List[Dict[str, object]] = []

        def visit(node):
            if isinstance(node, list):
                for item in node:
                    visit(item)
                return
            if not isinstance(node, dict):
                return

            has_name = any(key in node for key in ("Name", "PackageName", "DisplayName"))
            has_id = any(key in node for key in ("Id", "PackageIdentifier", "PackageId", "Identifier"))
            if has_name and has_id:
                packages.append(node)
                return

            for key in ("Packages", "Data", "Items", "Sources", "Results", "Upgradeable"):
                if key in node:
                    visit(node[key])

        visit(data)
        return packages

    def _run_winget_client_packages(self) -> Optional[List[Dict[str, object]]]:
        """Read structured package data from Microsoft.WinGet.Client on PowerShell 7+."""
        command = (
            "$ErrorActionPreference = 'Stop'; "
            "if ($PSVersionTable.PSVersion.Major -lt 7) { throw 'PowerShell 7 required'; } "
            "Import-Module Microsoft.WinGet.Client -ErrorAction Stop; "
            "Get-WinGetPackage | Select-Object Name,Id,Source,InstalledVersion,IsUpdateAvailable,"
            "@{Name='AvailableVersion';Expression={ $versions = @($_.AvailableVersions); "
            "if ($versions.Count -gt 0) { [string]$versions[0] } else { '' } }} | "
            "ConvertTo-Json -Depth 4"
        )
        try:
            result = subprocess.run(
                ["pwsh", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", command],
                capture_output=True, text=True, timeout=120,
                creationflags=subprocess.CREATE_NO_WINDOW,
            )
            if result.returncode != 0 or not result.stdout.strip():
                return None

            packages = json.loads(result.stdout)
            if isinstance(packages, dict):
                return [packages]
            return packages if isinstance(packages, list) else None
        except (FileNotFoundError, subprocess.TimeoutExpired, subprocess.SubprocessError,
                json.JSONDecodeError, OSError) as e:
            self._log_warning(f"Microsoft.WinGet.Client structured scan unavailable: {e}")
            return None

    def _build_winget_client_maps_from_packages(
        self, packages: List[Dict[str, object]]
    ) -> Tuple[Dict[str, str], Dict[str, str]]:
        winget_map: Dict[str, str] = {}
        upgrade_map: Dict[str, str] = {}

        for pkg in packages:
            name = str(pkg.get("Name", "")).strip()
            package_id = str(pkg.get("Id", "")).strip()
            source = str(pkg.get("Source", "") or "").strip().lower()
            if not name or not package_id or source != "winget":
                continue

            winget_map[self._normalize_name(name)] = package_id

            is_update_available = bool(pkg.get("IsUpdateAvailable"))
            available_version = str(pkg.get("AvailableVersion", "") or "").strip()
            if is_update_available and available_version:
                upgrade_map[package_id] = available_version

        return winget_map, upgrade_map

    def _build_winget_client_maps(self) -> Optional[Tuple[Dict[str, str], Dict[str, str]]]:
        packages = self._run_winget_client_packages()
        if packages is None:
            return None
        return self._build_winget_client_maps_from_packages(packages)

    def _parse_winget_table(self, output: str) -> List[Dict[str, str]]:
        """Parse winget column-aligned text output into a list of dicts."""
        packages: List[Dict[str, str]] = []
        lines = output.splitlines()

        header_idx = -1
        for i, line in enumerate(lines):
            if "Name" in line and "Id" in line and "Version" in line:
                header_idx = i
                break
        if header_idx < 0:
            return self._parse_winget_table_by_package_id(output)

        header = lines[header_idx]
        name_pos = header.find("Name")
        id_pos = header.find("Id")
        ver_pos = header.find("Version")
        if name_pos < 0 or id_pos < 0:
            return self._parse_winget_table_by_package_id(output)

        for line in lines[header_idx + 2:]:
            if not line.strip():
                continue
            try:
                name = line[name_pos:id_pos].strip() if id_pos > name_pos else ""
                winget_id = (
                    line[id_pos:ver_pos].strip()
                    if ver_pos > id_pos
                    else line[id_pos:].strip()
                )
                version = (
                    line[ver_pos:].split()[0]
                    if ver_pos > 0 and len(line) > ver_pos
                    else ""
                )
                if name or winget_id:
                    packages.append({"Name": name, "Id": winget_id, "Version": version})
            except (IndexError, ValueError):
                continue

        if packages:
            return packages

        return self._parse_winget_table_by_package_id(output)

    def _parse_winget_table_by_package_id(self, output: str) -> List[Dict[str, str]]:
        """Parse localized winget table rows by locating package identifiers."""
        packages: List[Dict[str, str]] = []
        package_id_pattern = re.compile(
            r"(?<!\\)\b[A-Za-z0-9][A-Za-z0-9_.+-]*(?:\.[A-Za-z0-9][A-Za-z0-9_.+-]*)+\b"
        )

        for line in output.splitlines():
            stripped = line.strip()
            if not stripped or set(stripped) <= {"-", " "}:
                continue
            match = package_id_pattern.search(line)
            if not match:
                continue

            name = line[:match.start()].strip()
            package_id = match.group(0).strip()
            rest = line[match.end():].strip()
            version = rest.split()[0] if rest else ""

            if not name or name.lower() in {"name", "nom", "nombre", "名称", "名前"}:
                continue
            packages.append({"Name": name, "Id": package_id, "Version": version})

        return packages

    def _build_upgrade_map(self) -> Dict[str, str]:
        """Build a winget_id -> new_version map via winget upgrade."""
        upgrade_map: Dict[str, str] = {}
        self._update_progress(75)
        try:
            result = subprocess.run(
                ["winget", "upgrade", "--accept-source-agreements",
                 "--disable-interactivity", "--output", "json"],
                capture_output=True, text=True, timeout=60,
                creationflags=subprocess.CREATE_NO_WINDOW,
            )
            if result.returncode == 0 and result.stdout.strip():
                try:
                    data = json.loads(result.stdout)
                    upgradeable = data.get("Upgradeable", [])
                    for pkg in upgradeable:
                        pkg_id = str(pkg.get("Id", "")).strip()
                        new_ver = str(pkg.get("AvailableVersion", "")).strip()
                        if pkg_id and new_ver:
                            upgrade_map[pkg_id] = new_ver
                except json.JSONDecodeError:
                    pass
        except (FileNotFoundError, subprocess.TimeoutExpired, subprocess.SubprocessError, OSError) as e:
            self._log_warning(f"winget upgrade cross-reference failed: {e}")
        return upgrade_map

    def _build_pin_map(self) -> Dict[str, str]:
        """Build a winget_id -> pin description map via winget pin list."""
        pin_map: Dict[str, str] = {}
        try:
            result = subprocess.run(
                ["winget", "pin", "list", "--accept-source-agreements",
                 "--disable-interactivity"],
                capture_output=True, text=True, timeout=30,
                creationflags=subprocess.CREATE_NO_WINDOW,
            )
            if result.returncode != 0:
                return pin_map

            lines = result.stdout.splitlines()
            header_idx = -1
            for i, line in enumerate(lines):
                if "Id" in line and ("Version" in line or "Pin" in line):
                    header_idx = i
                    break
            if header_idx < 0:
                return pin_map

            header = lines[header_idx]
            id_pos = header.find("Id")
            ver_pos = header.find("Version")
            pin_type_pos = -1
            for label in ("Pin Type", "PinType", "Gating", "Pinned"):
                pin_type_pos = header.find(label)
                if pin_type_pos >= 0:
                    break

            if id_pos < 0:
                return pin_map

            for line in lines[header_idx + 2:]:
                if not line.strip():
                    continue
                try:
                    pkg_id = ""
                    pin_type = ""

                    if ver_pos > id_pos:
                        pkg_id = line[id_pos:ver_pos].strip()
                    else:
                        pkg_id = line[id_pos:].split()[0] if len(line) > id_pos else ""

                    if pin_type_pos >= 0 and len(line) > pin_type_pos:
                        pin_type = line[pin_type_pos:].strip()

                    if not pin_type:
                        # Derive from available version field
                        if ver_pos > 0 and len(line) > ver_pos:
                            ver_field = line[ver_pos:pin_type_pos].strip() if pin_type_pos > ver_pos else line[ver_pos:].strip()
                            if "*" in ver_field:
                                pin_type = f"Gating {ver_field}"
                            else:
                                pin_type = "Pinned"

                    if pkg_id:
                        pin_map[pkg_id] = pin_type or "Pinned"
                except (IndexError, ValueError):
                    continue

        except (FileNotFoundError, subprocess.TimeoutExpired, subprocess.SubprocessError, OSError) as e:
            self._log_warning(f"winget pin list failed: {e}")
        return pin_map

    def scan_all(self, include_sources: Optional[set] = None) -> List[Application]:
        """Perform comprehensive scan of all sources."""
        self._cancelled = False
        self.applications = []
        self.scan_diagnostics = []
        self.seen_apps = set()
        self._active_diagnostic = None

        def source_enabled(source: str) -> bool:
            return include_sources is None or source in include_sources

        def add_source(source_key: str, source_name: str, status: str, scanner: Callable[[], List[Application]]):
            if source_enabled(source_key):
                self._update_status(status)
                rows = self._run_diagnostic_step(source_name, scanner)
                self.applications.extend(rows)
                return
            self._record_skipped_source(source_name)

        # Scan registry (primary source)
        add_source(
            "registry",
            "Windows Registry",
            "Phase 1/9: Scanning Windows Registry...",
            self.scan_registry,
        )
        if self._cancelled:
            return self.applications

        # Scan Store apps
        add_source(
            "store",
            "Microsoft Store",
            "Phase 2/9: Scanning Microsoft Store apps...",
            self.scan_store_apps,
        )
        if self._cancelled:
            return self.applications

        # Scan Program Files
        add_source(
            "program_files",
            "Program Files",
            "Phase 3/9: Scanning Program Files...",
            self.scan_program_files,
        )
        if self._cancelled:
            return self.applications

        # Scan Chocolatey packages
        add_source(
            "chocolatey",
            "Chocolatey",
            "Phase 4/9: Scanning Chocolatey packages...",
            self.scan_chocolatey,
        )
        if self._cancelled:
            return self.applications

        # Scan Scoop packages
        add_source(
            "scoop",
            "Scoop",
            "Phase 5/9: Scanning Scoop packages...",
            self.scan_scoop,
        )
        if self._cancelled:
            return self.applications

        # Scan pip packages
        add_source(
            "pip",
            "Python (pip)",
            "Phase 6/9: Scanning Python (pip) packages...",
            self.scan_pip,
        )
        if self._cancelled:
            return self.applications

        # Cross-reference with winget for package IDs and upgrade status
        def scan_winget_cross_reference() -> List[Application]:
            winget_client_maps = self._build_winget_client_maps()
            if winget_client_maps is not None:
                winget_map, upgrade_map = winget_client_maps
            else:
                winget_map = self._build_winget_map()
                upgrade_map = self._build_upgrade_map()

            if winget_map:
                for app in self.applications:
                    norm = self._normalize_name(app.name)
                    if norm in winget_map:
                        app.winget_id = winget_map[norm]

            # Check for upgradeable versions
            if upgrade_map:
                for app in self.applications:
                    if app.winget_id and app.winget_id in upgrade_map:
                        app.upgrade_available = f"Update Available ({upgrade_map[app.winget_id]})"

            # Check for pinned packages
            pin_map = self._build_pin_map()
            if pin_map:
                for app in self.applications:
                    if app.winget_id and app.winget_id in pin_map:
                        app.pin_status = pin_map[app.winget_id]
            return [app for app in self.applications if app.winget_id]

        if source_enabled("winget"):
            self._update_status("Phase 7/9: Cross-referencing with winget...")
            self._run_diagnostic_step("winget", scan_winget_cross_reference)
        else:
            self._record_skipped_source("winget")

        def scan_last_used() -> List[Application]:
            self._apply_last_used_dates()
            return [app for app in self.applications if app.last_used_date]

        def scan_virustotal_hashes() -> List[Application]:
            self._apply_virustotal_hashes()
            return [app for app in self.applications if app.sha256_hash]

        self._run_diagnostic_step("Last-used activity", scan_last_used)
        self._run_diagnostic_step("Executable hashing", scan_virustotal_hashes)

        # Ghost entry detection: flag apps whose install location doesn't exist
        for app in self.applications:
            if app.install_location and not os.path.exists(app.install_location):
                app.ghost = True

        # Sort by name
        self.applications.sort(key=lambda x: x.name.lower())

        self._update_progress(100)
        self._update_status(f"Scan complete. Found {len(self.applications)} applications.")

        return self.applications
