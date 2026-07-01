import json
import tempfile
import unittest
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path

from applist.cli import run_cli


class CliTests(unittest.TestCase):
    def test_diff_mode_writes_text_report(self):
        with tempfile.TemporaryDirectory() as tmp:
            old_path = Path(tmp) / "old.json"
            new_path = Path(tmp) / "new.json"
            report_path = Path(tmp) / "report.txt"
            old_path.write_text(
                json.dumps(
                    {
                        "machine": "oldpc",
                        "generated": "2026-01-01T00:00:00",
                        "applications": [{"name": "Alpha", "version": "1.0"}],
                    }
                ),
                encoding="utf-8",
            )
            new_path.write_text(
                json.dumps(
                    {
                        "machine": "newpc",
                        "generated": "2026-01-02T00:00:00",
                        "applications": [
                            {"name": "Alpha", "version": "2.0"},
                            {"name": "Beta", "version": "1.0"},
                        ],
                    }
                ),
                encoding="utf-8",
            )

            with redirect_stdout(StringIO()):
                exit_code = run_cli(["--diff", str(old_path), str(new_path), "-o", str(report_path)])

            self.assertEqual(exit_code, 0)
            report = report_path.read_text(encoding="utf-8")
            self.assertIn("ADDED (1)", report)
            self.assertIn("VERSION CHANGED (1)", report)


    def test_compliance_reports_missing_apps(self):
        from unittest import mock
        from applist.models import Application

        with tempfile.TemporaryDirectory() as tmp:
            ref_path = Path(tmp) / "required.txt"
            ref_path.write_text("Alpha\nGamma\n# comment\n", encoding="utf-8")
            report_path = Path(tmp) / "compliance.json"

            scanner_mock = mock.MagicMock()
            scanner_mock.scan_all.return_value = [Application(name="Alpha", version="1.0")]
            scanner_mock.scan_diagnostics = []

            with mock.patch("applist.cli.ApplicationScanner", return_value=scanner_mock):
                with redirect_stdout(StringIO()):
                    exit_code = run_cli([
                        "--compliance", str(ref_path),
                        "-o", str(report_path),
                    ])

            self.assertEqual(exit_code, 1)
            report = json.loads(report_path.read_text(encoding="utf-8"))
            self.assertFalse(report["compliant"])
            self.assertIn("Alpha", report["present"])
            self.assertIn("Gamma", report["missing"])


if __name__ == "__main__":
    unittest.main()
