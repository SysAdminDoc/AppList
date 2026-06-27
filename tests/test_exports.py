import csv
import json
import tempfile
import unittest
from pathlib import Path

from applist.exports import (
    diff_json_snapshots,
    get_markdown_groups,
    write_choco_export,
    write_csv_export,
    write_html_export,
    write_json_export,
    write_markdown_export,
    write_pip_requirements_export,
)
from applist.models import Application


class ExportTests(unittest.TestCase):
    def test_export_writers_emit_expected_content(self):
        apps = [
            Application(
                name="Alpha",
                publisher="Acme",
                version="1.0",
                last_used_date="2026-06-27 14:30:05",
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
            self.assertEqual(rows[1][0], "Alpha")
            self.assertIn("2026-06-27 14:30:05", rows[1])

            data = json.loads(json_path.read_text(encoding="utf-8"))
            self.assertEqual(data["total"], 3)
            self.assertEqual(data["applications"][0]["name"], "Alpha")
            self.assertEqual(data["applications"][0]["last_used_date"], "2026-06-27 14:30:05")

            markdown = md_path.read_text(encoding="utf-8")
            html = html_path.read_text(encoding="utf-8")
            self.assertIn("Last Used", markdown)
            self.assertIn("2026-06-27 14:30:05", markdown)
            self.assertIn("<table", html)
            self.assertIn("Last Used", html)
            self.assertIn("2026-06-27 14:30:05", html)
            self.assertEqual(pip_count, 1)
            self.assertIn("requests==2.32.3", pip_path.read_text(encoding="utf-8"))
            self.assertEqual(choco_count, 1)
            self.assertIn('id="git"', choco_path.read_text(encoding="utf-8"))

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


if __name__ == "__main__":
    unittest.main()
