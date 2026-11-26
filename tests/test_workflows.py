"""A generated addon must retain the template's complete release call graph."""
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from check import validate_workflows


class WorkflowLayoutTests(unittest.TestCase):
    def copy_workflows(self, root):
        shutil.copytree(ROOT / ".github" / "workflows", root / ".github" / "workflows")

    def test_generated_addon_keeps_working_entry_points(self):
        with tempfile.TemporaryDirectory() as temporary:
            addon = Path(temporary) / "addon"
            shutil.copytree(ROOT, addon, ignore=shutil.ignore_patterns(
                ".git", ".release", ".addon-tooling", ".addon-packager", "__pycache__"))
            subprocess.run([sys.executable, "scripts/initialize.py", "ReleaseFixture"],
                           cwd=addon, check=True, capture_output=True)
            validate_workflows(addon)
            self.assertTrue((addon / "ReleaseFixture.toc").is_file())
            self.assertEqual((addon / ".github/workflows/release.yml").read_text(),
                             (ROOT / ".github/workflows/release.yml").read_text())

    def test_removing_any_nested_workflow_is_reported(self):
        for filename in ("reusable-build.yml", "reusable-release.yml", "reusable-curseforge.yml"):
            with self.subTest(filename=filename), tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary)
                self.copy_workflows(root)
                (root / ".github/workflows" / filename).unlink()
                with self.assertRaisesRegex(ValueError, "Missing local reusable workflow"):
                    validate_workflows(root)

    def test_release_and_retry_cannot_drift_back_to_remote_entry_points(self):
        for filename in ("release.yml", "curseforge.yml"):
            with self.subTest(filename=filename), tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary)
                self.copy_workflows(root)
                path = root / ".github/workflows" / filename
                path.write_text(path.read_text().replace("uses: ./.github/workflows/",
                    "uses: CraightonH/wow-addon-template/.github/workflows/"))
                with self.assertRaisesRegex(ValueError, "must call the template's local"):
                    validate_workflows(root)


if __name__ == "__main__":
    unittest.main()
