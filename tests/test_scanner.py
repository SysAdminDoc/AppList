import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import applist.scanner as scanner_module
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


if __name__ == "__main__":
    unittest.main()
