import json
import hashlib
import struct
import tempfile
import unittest
from datetime import datetime
from pathlib import Path
from unittest import mock

import applist.scanner as scanner_module
from applist.models import Application
from applist.scanner import ApplicationScanner


class FakeKey:
    def __init__(self, kind, payload):
        self.kind = kind
        self.payload = payload

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


class FakeWinreg:
    HKEY_LOCAL_MACHINE = object()
    HKEY_CURRENT_USER = object()
    KEY_READ = 1
    KEY_WOW64_64KEY = 2

    def __init__(self, registry):
        self.registry = registry

    def OpenKey(self, hive_or_key, path_or_subkey, *_args):
        if isinstance(hive_or_key, FakeKey):
            subkeys = hive_or_key.payload
            if path_or_subkey not in subkeys:
                raise FileNotFoundError(path_or_subkey)
            return FakeKey("subkey", subkeys[path_or_subkey])
        if path_or_subkey not in self.registry:
            raise FileNotFoundError(path_or_subkey)
        return FakeKey("root", self.registry[path_or_subkey])

    def QueryInfoKey(self, key):
        return (len(key.payload), 0, 0)

    def EnumKey(self, key, index):
        return list(key.payload.keys())[index]

    def QueryValueEx(self, key, value_name):
        if value_name not in key.payload:
            raise FileNotFoundError(value_name)
        return key.payload[value_name], None


class ScannerTests(unittest.TestCase):
    def _filetime(self, value: datetime) -> int:
        return int((value - scanner_module.FILETIME_EPOCH).total_seconds() * 10_000_000)

    def test_registry_scan_deduplicates_and_parses_fields(self):
        fake_registry = {
            r"SOFTWARE\TestApps": {
                "Alpha": {
                    "DisplayName": "Alpha App",
                    "Publisher": "Acme",
                    "DisplayVersion": "1.0",
                    "InstallDate": "20260627",
                    "EstimatedSize": "2048",
                    "UninstallString": r"C:\Alpha\uninstall.exe",
                    "InstallLocation": r"C:\Alpha",
                },
                "AlphaDuplicate": {
                    "DisplayName": "Alpha-App",
                    "Publisher": "Acme",
                },
            }
        }
        fake_winreg = FakeWinreg(fake_registry)
        scanner = ApplicationScanner()

        with mock.patch.object(scanner_module, "winreg", fake_winreg), mock.patch.object(
            scanner_module,
            "REGISTRY_PATHS",
            [(fake_winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\TestApps", "HKLM64")],
        ):
            apps = scanner.scan_registry()

        self.assertEqual(len(apps), 1)
        self.assertEqual(apps[0].name, "Alpha App")
        self.assertEqual(apps[0].install_date, "2026-06-27")
        self.assertEqual(apps[0].estimated_size, "2.0 MB")

    def test_store_scan_uses_subprocess_json_without_shell(self):
        payload = [
            {
                "Name": "Contoso.PhotoViewer",
                "Publisher": "CN=Contoso, O=Contoso",
                "Version": "3.2.1",
                "InstallLocation": r"C:\Program Files\WindowsApps\Contoso",
                "PackageFullName": "Contoso.PhotoViewer_3.2.1_x64",
            }
        ]
        completed = mock.Mock(returncode=0, stdout=json.dumps(payload))
        with mock.patch.object(scanner_module.subprocess, "run", return_value=completed) as run_mock:
            apps = ApplicationScanner().scan_store_apps()

        self.assertEqual(len(apps), 1)
        self.assertEqual(apps[0].publisher, "Contoso")
        self.assertFalse(run_mock.call_args.kwargs.get("shell", False))

    def test_program_files_scan_finds_executables_and_skips_seen_names(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "Alpha").mkdir()
            (root / "Alpha" / "alpha.exe").write_text("", encoding="utf-8")
            (root / "Beta").mkdir()

            scanner = ApplicationScanner()
            scanner.seen_apps.add(scanner._normalize_name("Alpha"))
            with mock.patch.dict("os.environ", {"ProgramFiles": str(root), "ProgramFiles(x86)": str(root), "LOCALAPPDATA": str(root)}):
                apps = scanner.scan_program_files()

        self.assertEqual(apps, [])

    def test_parse_winget_table(self):
        output = "\n".join(
            [
                "Name                  Id                         Version",
                "----------------------------------------------------------",
                "Alpha App             Acme.Alpha                 1.0.0",
                "Beta Tool             Contoso.Beta               2.0.0",
            ]
        )

        packages = ApplicationScanner()._parse_winget_table(output)

        self.assertEqual(packages[0]["Name"], "Alpha App")
        self.assertEqual(packages[0]["Id"], "Acme.Alpha")
        self.assertEqual(packages[1]["Version"], "2.0.0")

    def test_parse_winget_table_handles_localized_headers_by_package_id(self):
        output = "\n".join(
            [
                "Nom                   Identifiant                Version",
                "----------------------------------------------------------",
                "Alpha App             Acme.Alpha                 1.0.0",
                "Beta Tool             Contoso.Beta               2.0.0",
            ]
        )

        packages = ApplicationScanner()._parse_winget_table(output)

        self.assertEqual(packages[0], {"Name": "Alpha App", "Id": "Acme.Alpha", "Version": "1.0.0"})
        self.assertEqual(packages[1], {"Name": "Beta Tool", "Id": "Contoso.Beta", "Version": "2.0.0"})

    def test_parse_winget_json_packages_handles_nested_shapes(self):
        output = json.dumps(
            {
                "Sources": [
                    {
                        "Packages": [
                            {
                                "PackageName": "Alpha App",
                                "PackageIdentifier": "Acme.Alpha",
                                "PackageVersion": "1.0.0",
                            }
                        ]
                    }
                ]
            }
        )

        packages = ApplicationScanner()._parse_winget_json_packages(output)

        self.assertEqual(packages[0]["PackageName"], "Alpha App")
        self.assertEqual(ApplicationScanner()._winget_package_field(packages[0], "Id"), "Acme.Alpha")

    def test_winget_map_warns_when_text_output_is_unparseable(self):
        scanner = ApplicationScanner()
        json_failure = mock.Mock(returncode=1, stdout="")
        text_result = mock.Mock(returncode=0, stdout="sortie inconnue sans colonnes ni identifiants")

        with mock.patch.object(scanner_module.subprocess, "run", side_effect=[json_failure, text_result]), mock.patch.object(
            scanner, "_log_warning"
        ) as warning_mock:
            winget_map = scanner._build_winget_map()

        self.assertEqual(winget_map, {})
        warning_mock.assert_called_with(
            "winget text output could not be parsed; structured output is required for this locale."
        )

    def test_winget_map_handles_missing_stdout_from_decode_failure(self):
        scanner = ApplicationScanner()
        json_failure = mock.Mock(returncode=1, stdout=None)
        text_result = mock.Mock(returncode=0, stdout=None)

        with mock.patch.object(scanner_module.subprocess, "run", side_effect=[json_failure, text_result]):
            self.assertEqual(scanner._build_winget_map(), {})

    def test_scan_all_records_source_diagnostics(self):
        scanner = ApplicationScanner()

        with mock.patch.object(scanner, "scan_registry", return_value=[Application(name="Alpha")]), \
                mock.patch.object(scanner, "_apply_last_used_dates"), \
                mock.patch.object(scanner, "_apply_virustotal_hashes"):
            apps = scanner.scan_all(include_sources={"registry"})

        self.assertEqual([app.name for app in apps], ["Alpha"])
        diagnostics = {diagnostic.source: diagnostic for diagnostic in scanner.scan_diagnostics}
        self.assertEqual(diagnostics["Windows Registry"].status, "ok")
        self.assertEqual(diagnostics["Windows Registry"].row_count, 1)
        self.assertEqual(diagnostics["Microsoft Store"].status, "skipped")
        self.assertEqual(diagnostics["winget"].status, "skipped")

    def test_scan_all_records_failed_source_diagnostics(self):
        scanner = ApplicationScanner()

        with mock.patch.object(scanner, "scan_registry", side_effect=OSError("registry denied")), \
                mock.patch.object(scanner, "_apply_last_used_dates"), \
                mock.patch.object(scanner, "_apply_virustotal_hashes"):
            apps = scanner.scan_all(include_sources={"registry"})

        self.assertEqual(apps, [])
        diagnostic = next(d for d in scanner.scan_diagnostics if d.source == "Windows Registry")
        self.assertEqual(diagnostic.status, "failed")
        self.assertEqual(diagnostic.row_count, 0)
        self.assertEqual(diagnostic.warnings, ["registry denied"])

    def test_package_manager_consistency_flags_rows_without_local_evidence(self):
        scanner = ApplicationScanner()
        scanner.applications = [
            Application(name="Alpha App", app_type="Desktop", source="HKLM64"),
            Application(name="Alpha App", app_type="Chocolatey", source="Chocolatey"),
            Application(name="Ghost Tool", app_type="Scoop", source="Scoop"),
        ]

        scanner._apply_package_manager_consistency()

        self.assertEqual(scanner.applications[1].consistency_status, "")
        self.assertEqual(
            scanner.applications[2].consistency_status,
            "No registry, Store, Program Files, or executable evidence",
        )

    def test_winget_client_maps_use_structured_winget_packages(self):
        scanner = ApplicationScanner()
        packages = [
            {
                "Name": "Alpha App",
                "Id": "Acme.Alpha",
                "Source": "winget",
                "IsUpdateAvailable": True,
                "AvailableVersion": "2.0.0",
            },
            {
                "Name": "ARP Only",
                "Id": r"ARP\Machine\X64\ARP Only",
                "Source": None,
                "IsUpdateAvailable": False,
                "AvailableVersion": "",
            },
        ]

        winget_map, upgrade_map = scanner._build_winget_client_maps_from_packages(packages)

        self.assertEqual(winget_map[scanner._normalize_name("Alpha App")], "Acme.Alpha")
        self.assertNotIn(scanner._normalize_name("ARP Only"), winget_map)
        self.assertEqual(upgrade_map, {"Acme.Alpha": "2.0.0"})

    def test_pip_scan_parses_json_packages(self):
        completed = mock.Mock(
            returncode=0,
            stdout=json.dumps([{"name": "requests", "version": "2.32.3"}]),
        )
        with mock.patch.object(scanner_module.subprocess, "run", return_value=completed):
            apps = ApplicationScanner().scan_pip()

        self.assertEqual(len(apps), 1)
        self.assertEqual(apps[0].name, "requests")
        self.assertEqual(apps[0].app_type, "Python Package")

    def test_pip_scan_skips_in_frozen_mode_without_interpreter(self):
        scanner = ApplicationScanner()
        with mock.patch.object(scanner_module.sys, "frozen", True, create=True), \
                mock.patch.object(scanner_module.shutil, "which", return_value=None), \
                mock.patch.object(scanner, "_log_warning") as warn_mock:
            apps = scanner.scan_pip()

        self.assertEqual(apps, [])
        warn_mock.assert_called_once()
        self.assertIn("frozen", warn_mock.call_args[0][0])

    def test_pip_scan_uses_external_interpreter_when_frozen(self):
        scanner = ApplicationScanner()
        completed = mock.Mock(
            returncode=0,
            stdout=json.dumps([{"name": "numpy", "version": "1.26.0"}]),
        )
        with mock.patch.object(scanner_module.sys, "frozen", True, create=True), \
                mock.patch.object(scanner_module.shutil, "which", return_value=r"C:\Python312\python.exe"), \
                mock.patch.object(scanner_module.subprocess, "run", return_value=completed) as run_mock:
            apps = scanner.scan_pip()

        self.assertEqual(len(apps), 1)
        self.assertEqual(apps[0].name, "numpy")
        self.assertEqual(run_mock.call_args[0][0][0], r"C:\Python312\python.exe")

    def test_portable_app_scan_finds_exe_bearing_folders(self):
        with tempfile.TemporaryDirectory() as tmp:
            portable_dir = Path(tmp) / "Portable"
            portable_dir.mkdir()
            (portable_dir / "MyTool").mkdir()
            (portable_dir / "MyTool" / "mytool.exe").write_text("", encoding="utf-8")
            (portable_dir / "EmptyDir").mkdir()

            scanner = ApplicationScanner()
            with mock.patch.dict("os.environ", {"LOCALAPPDATA": "", "USERPROFILE": str(tmp), "HOMEDRIVE": "Z:"}):
                apps = scanner.scan_portable_apps()

            names = {a.name for a in apps}
            self.assertIn("MyTool", names)
            self.assertNotIn("EmptyDir", names)
            tool = next(a for a in apps if a.name == "MyTool")
            self.assertEqual(tool.app_type, "Portable")
            self.assertEqual(tool.source, "Portable")

    def test_wsl_scan_parses_distro_list(self):
        wsl_output = (
            "  NAME            STATE           VERSION\n"
            "* Ubuntu-22.04    Running         2\n"
            "  Debian          Stopped         1\n"
        ).encode("utf-16-le")
        completed = mock.Mock(returncode=0, stdout=wsl_output)
        with mock.patch.object(scanner_module.subprocess, "run", return_value=completed):
            apps = ApplicationScanner().scan_wsl_distros()

        self.assertEqual(len(apps), 2)
        self.assertEqual(apps[0].name, "Ubuntu-22.04")
        self.assertEqual(apps[0].version, "WSL 2")
        self.assertEqual(apps[0].app_type, "WSL Distro")
        self.assertEqual(apps[1].name, "Debian")
        self.assertEqual(apps[1].consistency_status, "Stopped")

    def test_scan_all_skip_flags_record_skipped_diagnostics(self):
        scanner = ApplicationScanner()
        with mock.patch.object(scanner, "scan_registry", return_value=[Application(name="Alpha")]):
            scanner.scan_all(
                include_sources={"registry"},
                skip_network=True,
                skip_hashing=True,
                skip_last_used=True,
            )

        diag_map = {d.source: d.status for d in scanner.scan_diagnostics}
        self.assertEqual(diag_map["winget"], "skipped")
        self.assertEqual(diag_map["Last-used activity"], "skipped")
        self.assertEqual(diag_map["Executable hashing"], "skipped")
        self.assertEqual(diag_map["Windows Registry"], "ok")

    def test_userassist_timestamp_parser_reads_filetime_offset(self):
        scanner = ApplicationScanner()
        payload = bytearray(72)
        struct.pack_into("<Q", payload, 60, self._filetime(datetime(2026, 6, 27, 14, 30, 5)))

        self.assertEqual(scanner._extract_userassist_timestamp(bytes(payload)), "2026-06-27 14:30:05")

    def test_last_used_enrichment_prefers_newest_matching_signal(self):
        scanner = ApplicationScanner()
        scanner.applications = [
            Application(name="Alpha App", install_location=""),
            Application(name="[Folder] BetaTool", install_location=""),
        ]

        alpha_key = scanner._normalize_name("Alpha App")
        beta_key = scanner._normalize_name("BetaTool")
        with mock.patch.object(
            scanner,
            "_build_userassist_last_used_map",
            return_value={alpha_key: "2026-06-27 09:00:00", beta_key: "2026-06-26 09:00:00"},
        ), mock.patch.object(
            scanner,
            "_build_prefetch_last_used_map",
            return_value={alpha_key: "2026-06-27 11:00:00", beta_key: "2026-06-27 10:00:00"},
        ):
            scanner._apply_last_used_dates()

        self.assertEqual(scanner.applications[0].last_used_date, "2026-06-27 11:00:00")
        self.assertEqual(scanner.applications[1].last_used_date, "2026-06-27 10:00:00")

    def test_virustotal_hash_enrichment_hashes_and_reuses_cache(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            exe_path = root / "Alpha.exe"
            exe_path.write_bytes(b"alpha executable")
            cache_path = root / "wingetlist-sha-cache.json"
            expected_hash = hashlib.sha256(b"alpha executable").hexdigest()

            scanner = ApplicationScanner()
            scanner.applications = [Application(name="Alpha", executable_path=str(exe_path))]

            with mock.patch.object(scanner, "_hash_cache_path", return_value=cache_path):
                scanner._apply_virustotal_hashes()

            app = scanner.applications[0]
            self.assertEqual(app.sha256_hash, expected_hash)
            self.assertEqual(app.virustotal_url, f"https://www.virustotal.com/gui/file/{expected_hash}")
            self.assertTrue(cache_path.is_file())

            app.sha256_hash = ""
            app.virustotal_url = ""
            with mock.patch.object(scanner, "_hash_cache_path", return_value=cache_path), mock.patch.object(
                scanner, "_hash_file_sha256", side_effect=AssertionError("cache was not reused")
            ):
                scanner._apply_virustotal_hashes()

            self.assertEqual(app.sha256_hash, expected_hash)


if __name__ == "__main__":
    unittest.main()
