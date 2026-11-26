"""Release boundary checks; all publishing and issue writes are mocked."""
import hashlib
import io
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
import zipfile

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import artifact
import publish
import watch


class ReleaseTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.release = self.root / ".release"
        self.release.mkdir()
        self.cfg = {
            "name": "TestAddon", "interface": 16001, "curseforge_project_id": 123,
            "curseforge_version_type_id": 88568, "reviewed_upstream_commit": "a" * 40,
        }
        (self.root / "addon.json").write_text(json.dumps(self.cfg))
        (self.release / "notes.md").write_text("Release notes")

    def package(self, extra=None):
        path = self.release / "TestAddon.zip"
        with zipfile.ZipFile(path, "w") as archive:
            archive.writestr("TestAddon/TestAddon.toc", "## Interface: 16001\n## Version: v1.0.0-alpha.1\nCore.lua\n")
            archive.writestr("TestAddon/Core.lua", "-- test\n")
            if extra:
                archive.writestr(extra, "unwanted")
        manifest = {
            "addon": "TestAddon", "interface": 16001, "filename": path.name,
            "tag": "v1.0.0-alpha.1", "version": "v1.0.0-alpha.1",
            "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        }
        (self.release / "release.json").write_text(json.dumps(manifest))
        return path

    def test_modified_zip_is_rejected(self):
        path = self.package()
        path.write_bytes(path.read_bytes() + b"tampered")
        with self.assertRaisesRegex(AssertionError, "checksum"):
            artifact.verify(self.release, "v1.0.0-alpha.1")

    def test_wrong_release_is_rejected(self):
        self.package()
        with self.assertRaisesRegex(AssertionError, "tag"):
            artifact.verify(self.release, "v1.0.1")

    def test_payload_path_is_rejected(self):
        self.package("TestAddon/../private.txt")
        with self.assertRaisesRegex(AssertionError, "ZIP path"):
            artifact.verify(self.release)

    def test_game_version_requires_exact_flavor_and_version(self):
        versions = [
            {"name": "1.60.1", "gameVersionTypeID": 1, "id": 2},
            {"name": "1.60.0", "gameVersionTypeID": 88568, "id": 3},
        ]
        with self.assertRaises(ValueError):
            publish.select_game_version(versions, 16001, 88568)
        versions.append({"name": "1.60.1", "gameVersionTypeID": 88568, "id": 4})
        self.assertEqual(publish.select_game_version(versions, 16001, 88568), 4)

    def test_upload_sends_original_bytes_and_correct_channel(self):
        path = self.package()
        requests = []
        def urlopen(request, **kwargs):
            requests.append(request)
            if request.get_method() == "GET":
                return io.BytesIO(json.dumps([{"name": "1.60.1", "gameVersionTypeID": 88568, "id": 999}]).encode())
            self.assertIn(path.read_bytes(), request.data)
            self.assertIn(b'"gameVersions": [999]', request.data)
            self.assertIn(b'"releaseType": "alpha"', request.data)
            return io.BytesIO(b'{"id": 42}')
        with patch.object(publish, "ROOT", self.root), patch.dict(os.environ, {
            "RELEASE_TAG": "v1.0.0-alpha.1", "CF_API_TOKEN": "test-only", "CF_PUBLISH": "1",
        }), patch.object(publish.urllib.request, "urlopen", side_effect=urlopen):
            publish.main()
        self.assertEqual(len(requests), 2)
        self.assertEqual(requests[1].get_method(), "POST")

    def watch_run(self, existing):
        calls = []
        observation = {"commit": "b" * 40, "repository": "Gethe/wow-ui-source", "branch": "forever", "build": "1.60.1.12345"}
        with patch.object(watch, "ROOT", self.root), patch.object(watch, "observe", return_value=observation), \
             patch.object(watch.subprocess, "check_output", return_value=json.dumps(existing)), \
             patch.object(watch, "gh", side_effect=lambda *a, **kw: calls.append((a, kw))), \
             patch.dict(os.environ, {"GH_REPO": "example/addon", "GITHUB_OUTPUT": str(self.root / "output")}):
            watch.main()
        return calls, (self.root / "output").read_text()

    def test_new_upstream_creates_review_and_candidate(self):
        calls, output = self.watch_run([])
        self.assertEqual(calls[0][0][1], "POST")
        self.assertIn("changed=true", output)

    def test_same_observation_does_not_reopen_closed_issue(self):
        issue = {
            "number": 1, "title": "Review WoW Forever compatibility", "state": "CLOSED",
            "body": "<!-- wow-addon-template:forever-compatibility -->\n<!-- upstream-sha:" + "b" * 40 + " -->",
        }
        calls, output = self.watch_run([issue])
        self.assertEqual(calls, [])
        self.assertIn("changed=false", output)


if __name__ == "__main__":
    unittest.main()
