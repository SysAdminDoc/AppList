import csv
import json
import tempfile
import unittest
import zipfile
from pathlib import Path

from applist import JSON_SCHEMA_VERSION
from applist.exports import (
    diff_json_snapshots,
    get_markdown_groups,
    redact_applications,
    validate_restore_bundle,
    write_choco_export,
    write_csv_export,
    write_html_export,
    write_json_export,
    write_markdown_export,
    write_pip_requirements_export,
    write_restore_bundle_export,
    write_txt_export,
)
from applist.models import Application, ScanDiagnostic

FIXTURES_DIR = Path(__file__).parent / "fixtures"


class ExportTests(unittest.TestCase):
    def test_export_writers_emit_expected_content(self):
        apps = [
            Application(
                name="Alpha",
                publisher="Acme",
                version="1.0",
                last_used_date="2026-06-27 14:30:05",
                executable_path=r"C:\Alpha\alpha.exe",
                sha256_hash="a" * 64,
                virustotal_url="https://www.virustotal.com/gui/file/" + ("a" * 64),
                app_type="Desktop",
                source="HKLM64",
            ),
            Application(name="requests", version="2.32.3", app_type="Python Package", source="Python (pip)"),
            Application(name="git", version="2.45.0", app_type="Chocolatey", source="Chocolatey"),
        ]

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            csv_path = root / "apps.csv"
            json_path = root / "apps.json"
            md_path = root / "apps.md"
            html_path = root / "apps.html"
            pip_path = root / "requirements.txt"
            choco_path = root / "packages.config"

            write_csv_export(apps, str(csv_path))
            write_json_export(apps, str(json_path))
            write_markdown_export(apps, str(md_path))
            write_html_export(apps, str(html_path))
            pip_count = write_pip_requirements_export(apps, str(pip_path))
            choco_count = write_choco_export(apps, str(choco_path))

            with csv_path.open(encoding="utf-8-sig", newline="") as f:
                rows = list(csv.reader(f))
            self.assertEqual(rows[0][0], "Application Name")
            self.assertIn("Last Used", rows[0])
            self.assertIn("SHA-256", rows[0])
            self.assertIn("VirusTotal URL", rows[0])
            self.assertIn("Consistency", rows[0])
            self.assertEqual(rows[1][0], "Alpha")
            self.assertIn("2026-06-27 14:30:05", rows[1])
            self.assertIn("a" * 64, rows[1])

            data = json.loads(json_path.read_text(encoding="utf-8"))
            self.assertEqual(data["total"], 3)
            self.assertEqual(data["applications"][0]["name"], "Alpha")
            self.assertEqual(data["applications"][0]["last_used_date"], "2026-06-27 14:30:05")
            self.assertEqual(data["applications"][0]["sha256_hash"], "a" * 64)

            markdown = md_path.read_text(encoding="utf-8")
            html = html_path.read_text(encoding="utf-8")
            self.assertIn("Last Used", markdown)
            self.assertIn("2026-06-27 14:30:05", markdown)
            self.assertIn("SHA-256", markdown)
            self.assertIn("Consistency", markdown)
            self.assertIn("Report", markdown)
            self.assertIn("<table", html)
            self.assertIn("Last Used", html)
            self.assertIn("2026-06-27 14:30:05", html)
            self.assertIn("SHA-256", html)
            self.assertIn("Consistency", html)
            self.assertIn("virustotal.com/gui/file", html)
            self.assertEqual(pip_count, 1)
            self.assertIn("requests==2.32.3", pip_path.read_text(encoding="utf-8"))
            self.assertEqual(choco_count, 1)
            self.assertIn('id="git"', choco_path.read_text(encoding="utf-8"))

    def test_report_exports_include_partial_scan_diagnostics(self):
        apps = [Application(name="Alpha", source="HKLM64")]
        diagnostics = [
            ScanDiagnostic(source="Windows Registry", status="ok", row_count=1, duration_seconds=0.1),
            ScanDiagnostic(
                source="Microsoft Store",
                status="failed",
                row_count=0,
                duration_seconds=0.2,
                warnings=["PowerShell unavailable"],
            ),
            ScanDiagnostic(source="Scoop", status="skipped"),
        ]

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            txt_path = root / "apps.txt"
            json_path = root / "apps.json"
            md_path = root / "apps.md"
            html_path = root / "apps.html"

            write_txt_export(apps, str(txt_path), diagnostics)
            write_json_export(apps, str(json_path), diagnostics)
            write_markdown_export(apps, str(md_path), diagnostics)
            write_html_export(apps, str(html_path), diagnostics)

            self.assertIn("Scan Diagnostics", txt_path.read_text(encoding="utf-8"))
            json_data = json.loads(json_path.read_text(encoding="utf-8"))
            self.assertEqual(json_data["diagnostics"][1]["source"], "Microsoft Store")
            self.assertEqual(json_data["diagnostics"][1]["status"], "failed")
            self.assertIn("Scoop", md_path.read_text(encoding="utf-8"))
            html = html_path.read_text(encoding="utf-8")
            self.assertIn("Scan Diagnostics", html)
            self.assertIn("PowerShell unavailable", html)

    def test_restore_bundle_export_creates_restore_artifacts_zip(self):
        apps = [
            Application(name="Alpha", publisher="Acme", version="1.0", winget_id="Acme.Alpha", source="HKLM64"),
            Application(name="requests", version="2.32.3", app_type="Python Package", source="Python (pip)"),
            Application(name="git", version="2.45.0", app_type="Chocolatey", source="Chocolatey"),
            Application(name="Manual Tool", publisher="Acme", version="3.0", source="HKLM64"),
        ]
        diagnostics = [ScanDiagnostic(source="Scoop", status="skipped")]

        with tempfile.TemporaryDirectory() as tmp:
            bundle_path = Path(tmp) / "restore.zip"
            manifest = write_restore_bundle_export(apps, str(bundle_path), diagnostics)

            self.assertEqual(manifest["application_count"], 4)
            self.assertTrue(bundle_path.exists())
            with zipfile.ZipFile(bundle_path) as zf:
                names = set(zf.namelist())
                self.assertIn("applist.json", names)
                self.assertIn("winget-packages.json", names)
                self.assertIn("requirements.txt", names)
                self.assertIn("packages.config", names)
                self.assertIn("report.md", names)
                self.assertIn("dashboard.html", names)
                self.assertIn("restore-commands.ps1", names)
                self.assertIn("unmatched-skipped.md", names)
                self.assertIn("manifest.json", names)
                commands = zf.read("restore-commands.ps1").decode("utf-8")
                self.assertIn("winget import", commands)
                self.assertIn("pip install", commands)
                self.assertIn("choco install", commands)
                unmatched = zf.read("unmatched-skipped.md").decode("utf-8")
                self.assertIn("Manual Tool", unmatched)

    def test_restore_bundle_refuses_non_empty_folder(self):
        apps = [Application(name="Alpha", source="HKLM64")]
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp) / "existing_bundle"
            folder.mkdir()
            (folder / "user_data.txt").write_text("important", encoding="utf-8")

            with self.assertRaises(ValueError) as ctx:
                write_restore_bundle_export(apps, str(folder))
            self.assertIn("already contains files", str(ctx.exception))

    def test_restore_bundle_overwrites_folder_when_flag_set(self):
        apps = [Application(name="Alpha", source="HKLM64")]
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp) / "existing_bundle"
            folder.mkdir()
            (folder / "old_file.txt").write_text("stale", encoding="utf-8")

            manifest = write_restore_bundle_export(apps, str(folder), overwrite=True)
            self.assertEqual(manifest["application_count"], 1)
            self.assertFalse((folder / "old_file.txt").exists())
            self.assertTrue((folder / "applist.json").exists())

    def test_restore_bundle_zip_uses_atomic_write(self):
        apps = [Application(name="Alpha", source="HKLM64")]
        with tempfile.TemporaryDirectory() as tmp:
            zip_path = Path(tmp) / "bundle.zip"
            write_restore_bundle_export(apps, str(zip_path))
            self.assertTrue(zip_path.exists())
            self.assertFalse(zip_path.with_suffix(".zip.tmp").exists())
            with zipfile.ZipFile(zip_path) as zf:
                self.assertIn("applist.json", zf.namelist())

    def test_markdown_groups_preserve_unknown_types(self):
        groups = get_markdown_groups(
            [
                Application(name="Known", app_type="Desktop"),
                Application(name="Mystery", app_type="Custom Type"),
            ]
        )

        self.assertEqual([name for name, _ in groups], ["Desktop Apps", "Custom Type"])

    def test_diff_json_snapshots_reports_add_remove_and_version_change(self):
        with tempfile.TemporaryDirectory() as tmp:
            old_path = Path(tmp) / "old.json"
            new_path = Path(tmp) / "new.json"
            old_path.write_text(
                json.dumps(
                    {
                        "machine": "oldpc",
                        "applications": [
                            {"name": "Alpha", "version": "1.0"},
                            {"name": "Removed", "version": "1.0"},
                        ],
                    }
                ),
                encoding="utf-8",
            )
            new_path.write_text(
                json.dumps(
                    {
                        "machine": "newpc",
                        "applications": [
                            {"name": "Alpha", "version": "2.0"},
                            {"name": "Added", "version": "1.0"},
                        ],
                    }
                ),
                encoding="utf-8",
            )

            diff = diff_json_snapshots(str(old_path), str(new_path))

            self.assertEqual(diff["summary"], {"added": 1, "removed": 1, "version_changed": 1})
            self.assertEqual(diff["added"][0]["name"], "Added")
            self.assertEqual(diff["removed"][0]["name"], "Removed")
            self.assertEqual(diff["version_changed"][0]["name"], "Alpha")

    def test_json_export_emits_stable_schema_version(self):
        apps = [Application(name="Alpha")]
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "out.json"
            write_json_export(apps, str(path))
            data = json.loads(path.read_text(encoding="utf-8"))
            self.assertEqual(data["schema"], f"AppList/{JSON_SCHEMA_VERSION}")

    def test_diff_cross_version_v1_0_to_v1_1_fixtures(self):
        diff = diff_json_snapshots(
            str(FIXTURES_DIR / "snapshot_v1_0.json"),
            str(FIXTURES_DIR / "snapshot_v1_1.json"),
        )
        self.assertEqual(diff["summary"]["added"], 1)
        self.assertEqual(diff["summary"]["removed"], 1)
        self.assertEqual(diff["summary"]["version_changed"], 2)
        added_names = {a["name"] for a in diff["added"]}
        removed_names = {a["name"] for a in diff["removed"]}
        changed_names = {c["name"] for c in diff["version_changed"]}
        self.assertIn("Gamma Suite", added_names)
        self.assertIn("Beta Tool", removed_names)
        self.assertIn("Alpha App", changed_names)
        self.assertIn("requests", changed_names)

    def test_diff_handles_missing_optional_fields_gracefully(self):
        with tempfile.TemporaryDirectory() as tmp:
            old_path = Path(tmp) / "old.json"
            new_path = Path(tmp) / "new.json"
            old_path.write_text(json.dumps({
                "applications": [{"name": "A", "version": "1.0"}],
            }), encoding="utf-8")
            new_path.write_text(json.dumps({
                "schema": "AppList/1.1",
                "applications": [
                    {"name": "A", "version": "1.0", "last_used_date": "2026-07-01", "sha256_hash": "abc"},
                ],
            }), encoding="utf-8")

            diff = diff_json_snapshots(str(old_path), str(new_path))
            self.assertEqual(diff["summary"]["version_changed"], 0)
            self.assertEqual(diff["summary"]["added"], 0)
            self.assertEqual(diff["summary"]["removed"], 0)

    def test_validate_bundle_passes_on_valid_zip(self):
        apps = [
            Application(name="Alpha", winget_id="Acme.Alpha", source="HKLM64"),
            Application(name="requests", version="2.32.3", app_type="Python Package", source="Python (pip)"),
            Application(name="git", version="2.45.0", app_type="Chocolatey", source="Chocolatey"),
        ]
        with tempfile.TemporaryDirectory() as tmp:
            zip_path = Path(tmp) / "bundle.zip"
            write_restore_bundle_export(apps, str(zip_path))
            result = validate_restore_bundle(str(zip_path))
            self.assertTrue(result["valid"])
            self.assertEqual(result["errors"], [])

    def test_validate_bundle_catches_missing_manifest(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp) / "bad_bundle"
            folder.mkdir()
            (folder / "applist.json").write_text("{}", encoding="utf-8")
            result = validate_restore_bundle(str(folder))
            self.assertFalse(result["valid"])
            self.assertTrue(any("manifest.json" in e for e in result["errors"]))

    def test_validate_bundle_catches_missing_declared_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp) / "partial_bundle"
            folder.mkdir()
            manifest = {"files": {"winget": "winget-packages.json"}, "skipped": {}}
            (folder / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
            (folder / "applist.json").write_text(
                json.dumps({"applications": []}), encoding="utf-8"
            )
            result = validate_restore_bundle(str(folder))
            self.assertFalse(result["valid"])
            self.assertTrue(any("winget-packages.json" in e for e in result["errors"]))

    def test_validate_bundle_reports_nonexistent_path(self):
        result = validate_restore_bundle("/nonexistent/bundle.zip")
        self.assertFalse(result["valid"])
        self.assertTrue(any("not found" in e for e in result["errors"]))

    def test_redact_applications_strips_sensitive_fields(self):
        from unittest import mock
        apps = [
            Application(
                name="Alpha",
                install_location=r"C:\Users\TestUser\AppData\Alpha",
                executable_path=r"C:\Users\TestUser\AppData\Alpha\alpha.exe",
                uninstall_registry_key=r"HKLM\SOFTWARE\Alpha",
                uninstall_command=r"C:\Alpha\uninstall.exe",
                sha256_hash="abc123",
                virustotal_url="https://www.virustotal.com/gui/file/abc123",
            ),
        ]
        with mock.patch.dict("os.environ", {"USERNAME": "TestUser", "USERPROFILE": r"C:\Users\TestUser", "COMPUTERNAME": "TESTPC"}):
            redacted = redact_applications(apps)

        self.assertEqual(len(redacted), 1)
        r = redacted[0]
        self.assertEqual(r.name, "Alpha")
        self.assertNotIn("TestUser", r.install_location)
        self.assertNotIn("TestUser", r.executable_path)
        self.assertEqual(r.uninstall_registry_key, "")
        self.assertEqual(r.uninstall_command, "")
        self.assertEqual(r.sha256_hash, "")
        self.assertEqual(r.virustotal_url, "")
        self.assertEqual(apps[0].sha256_hash, "abc123")


if __name__ == "__main__":
    unittest.main()
