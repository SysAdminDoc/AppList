import unittest
import subprocess
from pathlib import Path


class DependencyLockTests(unittest.TestCase):
    def test_requirements_are_exact_pins(self):
        requirements = Path("requirements.txt").read_text(encoding="utf-8").splitlines()
        package_lines = [
            line.strip()
            for line in requirements
            if line.strip() and not line.strip().startswith("#")
        ]

        self.assertTrue(package_lines)
        for line in package_lines:
            self.assertIn("==", line)
            self.assertNotIn(">=", line)
            self.assertNotIn("~=", line)

    def test_release_dependencies_include_audit_and_known_good_gui_pin(self):
        requirements = Path("requirements.txt").read_text(encoding="utf-8")

        self.assertIn("customtkinter==5.2.2", requirements)
        self.assertIn("pip-audit==2.10.1", requirements)
        self.assertIn("pyinstaller==6.19.0", requirements)
        self.assertIn("setuptools==83.0.0", requirements)

    def test_checked_native_helper_propagates_nonzero_exit_code(self):
        helper = Path("tools/invoke_checked_native.ps1").resolve()
        command = (
            f". '{helper}'; "
            "Invoke-CheckedNative -FilePath 'cmd.exe' "
            "-ArgumentList @('/c', 'exit', '37')"
        )
        result = subprocess.run(
            [
                "powershell",
                "-NoProfile",
                "-ExecutionPolicy",
                "Bypass",
                "-Command",
                command,
            ],
            capture_output=True,
            text=True,
            check=False,
        )

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("exit code 37", result.stdout + result.stderr)


if __name__ == "__main__":
    unittest.main()
