"""Application scanner engine — discovers installed software from multiple sources."""

import json
import os
import re
import subprocess
import sys
import winreg
from typing import Dict, List, Optional

from .models import Application
from .constants import REGISTRY_PATHS


class ApplicationScanner:
    """Core engine for scanning installed applications from multiple sources."""

    def __init__(self, progress_callback=None, status_callback=None):
        self.progress_callback = progress_callback
        self.status_callback = status_callback
        self.applications: List[Application] = []
        self.seen_apps: set = set()
        self._cancelled = False

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
        print(f"Warning: {message}", file=sys.stderr)

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
                try:
                    data = json.loads(result.stdout)
                    if isinstance(data, list) and data:
                        packages = data
                except json.JSONDecodeError:
                    pass

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

            for pkg in packages:
                name = str(pkg.get("Name", "")).strip()
                winget_id = str(pkg.get("Id", "")).strip()
                if name and winget_id:
                    winget_map[self._normalize_name(name)] = winget_id

        except (FileNotFoundError, subprocess.TimeoutExpired, subprocess.SubprocessError, OSError) as e:
            self._log_warning(f"winget list cross-reference failed: {e}")

        return winget_map

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
            return packages

        header = lines[header_idx]
        name_pos = header.find("Name")
        id_pos = header.find("Id")
        ver_pos = header.find("Version")
        if name_pos < 0 or id_pos < 0:
            return packages

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
        self.seen_apps = set()

        def source_enabled(source: str) -> bool:
            return include_sources is None or source in include_sources

        # Scan registry (primary source)
        if source_enabled("registry"):
            self._update_status("Phase 1/7: Scanning Windows Registry...")
            registry_apps = self.scan_registry()
            self.applications.extend(registry_apps)

            if self._cancelled:
                return self.applications

        # Scan Store apps
        if source_enabled("store"):
            self._update_status("Phase 2/7: Scanning Microsoft Store apps...")
            store_apps = self.scan_store_apps()
            self.applications.extend(store_apps)

            if self._cancelled:
                return self.applications

        # Scan Program Files
        if source_enabled("program_files"):
            self._update_status("Phase 3/7: Scanning Program Files...")
            folder_apps = self.scan_program_files()
            self.applications.extend(folder_apps)

            if self._cancelled:
                return self.applications

        # Scan Chocolatey packages
        if source_enabled("chocolatey"):
            self._update_status("Phase 4/7: Scanning Chocolatey packages...")
            choco_apps = self.scan_chocolatey()
            self.applications.extend(choco_apps)

            if self._cancelled:
                return self.applications

        # Scan Scoop packages
        if source_enabled("scoop"):
            self._update_status("Phase 5/7: Scanning Scoop packages...")
            scoop_apps = self.scan_scoop()
            self.applications.extend(scoop_apps)

            if self._cancelled:
                return self.applications

        # Scan pip packages
        if source_enabled("pip"):
            self._update_status("Phase 6/7: Scanning Python (pip) packages...")
            pip_apps = self.scan_pip()
            self.applications.extend(pip_apps)

            if self._cancelled:
                return self.applications

        # Cross-reference with winget for package IDs and upgrade status
        if source_enabled("winget"):
            self._update_status("Phase 7/7: Cross-referencing with winget...")
            winget_map = self._build_winget_map()
            if winget_map:
                for app in self.applications:
                    norm = self._normalize_name(app.name)
                    if norm in winget_map:
                        app.winget_id = winget_map[norm]

            # Check for upgradeable versions
            upgrade_map = self._build_upgrade_map()
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

        # Ghost entry detection: flag apps whose install location doesn't exist
        for app in self.applications:
            if app.install_location and not os.path.exists(app.install_location):
                app.ghost = True

        # Sort by name
        self.applications.sort(key=lambda x: x.name.lower())

        self._update_progress(100)
        self._update_status(f"Scan complete. Found {len(self.applications)} applications.")

        return self.applications
