"""Test the publication boundaries without contacting either service."""
import importlib.util
import io
import json
import os
import shutil
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import zipfile

spec = importlib.util.spec_from_file_location("release_tools", Path(__file__).resolve().parents[1] / "release_tools.py")
tools = importlib.util.module_from_spec(spec)
spec.loader.exec_module(tools)


class ReleaseToolsTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.directory = self.root / "dist"
        self.directory.mkdir()
        self.cfg = {"name": "Fixture", "interface": 16001, "source_directory": "Fixture", "artifact_directory": "dist", "curseforge_project_id": 123, "curseforge_version_type_id": 88568}
        (self.root / "addon.json").write_text(json.dumps(self.cfg))
        (self.root / "Fixture").mkdir()
        (self.root / "Fixture/Fixture.toc").write_text("## Interface: 16001\n## X-Curse-Project-ID: 123\n## Version: 0.1.0\nCore.lua\n")
        (self.root / "LICENSE").write_text("Fixture license")
        patcher = patch.object(tools, "ROOT", self.root)
        patcher.start()
        self.addCleanup(patcher.stop)
        self.sha = "a" * 40
        self.tag = "v1.0.0-beta.2"

    def package(self, extra=None, license=True):
        path = self.directory / "Fixture.zip"
        with zipfile.ZipFile(path, "w") as archive:
            archive.writestr(zipfile.ZipInfo("Fixture/Fixture.toc"), "## Interface: 16001\n## Version: 1.0.0-beta.2\nCore.lua\n")
            archive.writestr(zipfile.ZipInfo("Fixture/Core.lua"), "-- code")
            if license:
                archive.writestr(zipfile.ZipInfo("Fixture/LICENSE"), "Fixture license")
            if extra:
                archive.writestr(zipfile.ZipInfo(extra), "unexpected")
        with patch.object(tools, "git", return_value=self.sha), patch.dict(os.environ, {"RELEASE_TAG": self.tag}):
            tools.manifest()
        return json.loads((self.directory / "release.json").read_text()), path

    def test_release_channels_and_unsafe_tags(self):
        for tag, expected in [("v1.2.3", "release"), ("v1.2.3-alpha", "alpha"), ("v1.2.3-beta.4", "beta")]:
            self.assertEqual(tools.channel(tag), expected)
        for tag in ["v1.2", "v01.2.3", "v1.2.3;command", "v1.2.3-rc.1"]:
            with self.assertRaises(ValueError):
                tools.tag_version(tag)

    def test_prepare_exports_tag_version_without_editing_toc(self):
        output = self.root / "output"
        environment = self.root / "environment"
        def git(*args):
            return "tag" if args[0] == "cat-file" else self.sha
        with patch.object(tools, "git", side_effect=git), patch.dict(os.environ, {"RELEASE_TAG": self.tag, "GITHUB_ENV": str(environment), "GITHUB_OUTPUT": str(output)}):
            tools.prepare()
        self.assertIn("ADDON_RELEASE_VERSION=1.0.0-beta.2", environment.read_text())
        self.assertIn("artifact-directory=dist", output.read_text())
        self.assertIn("## Version: 0.1.0", (self.root / "Fixture/Fixture.toc").read_text())

    def test_lightweight_release_tag_is_rejected(self):
        with patch.object(tools, "git", return_value="commit"), patch.dict(os.environ, {"RELEASE_TAG": self.tag}):
            with self.assertRaisesRegex(ValueError, "annotated"):
                tools.prepare()

    def test_tampered_zip_is_rejected(self):
        _, path = self.package()
        path.write_bytes(path.read_bytes() + b"modified")
        with self.assertRaisesRegex(ValueError, "checksum"):
            tools.verify(self.directory, self.tag, self.cfg)

    def test_changed_project_or_source_commit_is_rejected(self):
        self.package()
        for cfg, sha in [({**self.cfg, "curseforge_project_id": 456}, self.sha), (self.cfg, "b" * 40)]:
            with self.assertRaises(ValueError):
                tools.verify(self.directory, self.tag, cfg, sha)

    def test_manifest_cannot_reference_another_tag(self):
        self.package()
        with self.assertRaisesRegex(ValueError, "tag"):
            tools.verify(self.directory, "v1.0.0", self.cfg)

    def test_archive_cannot_escape_addon_folder(self):
        with self.assertRaisesRegex(ValueError, "archive path"):
            self.package("Fixture/../secret.txt")

    def test_tagged_archive_requires_license(self):
        with self.assertRaisesRegex(ValueError, "LICENSE"):
            self.package(license=False)

    def test_game_version_never_falls_back(self):
        versions = [{"name": "1.60.1", "gameVersionTypeID": 1, "id": 2}, {"name": "1.60.0", "gameVersionTypeID": 88568, "id": 3}]
        with self.assertRaises(ValueError):
            tools.select_game_version(versions, 16001, 88568)
        versions.append({"name": "1.60.1", "gameVersionTypeID": 88568, "id": 4})
        self.assertEqual(tools.select_game_version(versions, 16001, 88568), 4)

    def test_upload_preserves_bytes_flavor_and_channel(self):
        data, path = self.package()
        requests = []
        def urlopen(request, **kwargs):
            requests.append(request)
            if request.get_method() == "GET":
                return io.BytesIO(b'[{"name":"1.60.1","gameVersionTypeID":88568,"id":456}]')
            self.assertIn(path.read_bytes(), request.data)
            self.assertIn(b'"gameVersions": [456]', request.data)
            self.assertIn(b'"releaseType": "beta"', request.data)
            self.assertEqual(request.full_url, tools.API + "/projects/123/upload-file")
            return io.BytesIO(b'{"id":789}')
        with patch.object(tools.urllib.request, "urlopen", side_effect=urlopen):
            self.assertEqual(tools.upload_cf(data, path, "Notes", "test-only"), 789)
        self.assertEqual(len(requests), 2)

    def deploy(self, receipt=None, token="test-only"):
        data, path = self.package()
        release = {"draft": False, "body": "Release notes", "assets": []}
        if receipt is not None:
            release["assets"].append({"name": "curseforge-upload.json"})
        def download(tag, filename, directory):
            if filename == "curseforge-upload.json":
                contents = json.dumps(receipt).encode()
            else:
                contents = (self.directory / filename).read_bytes()
            (directory / filename).write_bytes(contents)
        with patch.object(tools, "existing_release", return_value=release), \
             patch.object(tools, "download", side_effect=download), \
             patch.object(tools, "git", return_value=self.sha), \
             patch.object(tools, "gh") as github, \
             patch.object(tools, "upload_cf", return_value=789) as upload, \
             patch.dict(os.environ, {"RELEASE_TAG": self.tag, "CF_API_TOKEN": token}):
            tools.publish_curseforge()
        return github, upload, data

    def test_success_records_receipt_on_github_release(self):
        github, upload, _ = self.deploy()
        upload.assert_called_once()
        self.assertEqual(github.call_args.args[:3], ("release", "upload", self.tag))

    def test_successful_rerun_skips_duplicate_upload(self):
        data, _ = self.package()
        receipt = {**data, "file_id": 789}
        github, upload, _ = self.deploy(receipt)
        upload.assert_not_called()
        github.assert_not_called()

    def test_conflicting_receipt_blocks_upload(self):
        data, _ = self.package()
        receipt = {**data, "file_id": 789, "curseforge_project_id": 456}
        with self.assertRaisesRegex(ValueError, "receipt differs"):
            self.deploy(receipt)

    def test_missing_secret_blocks_upload(self):
        with self.assertRaisesRegex(ValueError, "CF_API_TOKEN"):
            self.deploy(token="")

    def test_config_paths_cannot_escape_repository(self):
        (self.root / "addon.json").write_text(json.dumps({**self.cfg, "source_directory": "../outside"}))
        with self.assertRaisesRegex(ValueError, "escapes"):
            tools.config(self.root)

    def github_publish(self, exists=False, corrupt_existing=False):
        data, path = self.package()
        shutil.copytree(self.directory, self.root / ".release-artifact")
        def download(tag, filename, directory):
            content = (self.directory / filename).read_bytes()
            if corrupt_existing and filename == "release.json":
                other = json.loads(content)
                other["source_commit"] = "b" * 40
                content = json.dumps(other).encode()
            (directory / filename).write_bytes(content)
        with patch.object(tools, "existing_release", return_value={"id": 1} if exists else None), \
             patch.object(tools, "download", side_effect=download), \
             patch.object(tools, "git", return_value=self.sha), \
             patch.object(tools, "gh") as github, \
             patch.dict(os.environ, {"RELEASE_TAG": self.tag}):
            tools.publish_github()
        return github

    def test_github_publication_uses_validated_assets_and_channel(self):
        github = self.github_publish()
        args = github.call_args.args
        self.assertEqual(args[:3], ("release", "create", self.tag))
        self.assertIn("--prerelease", args)
        self.assertIn("--verify-tag", args)
        self.assertEqual(Path(args[-2]).name, "Fixture.zip")
        self.assertEqual(Path(args[-1]).name, "release.json")

    def test_github_rerun_preserves_existing_assets(self):
        github = self.github_publish(exists=True)
        github.assert_not_called()

    def test_github_rerun_rejects_different_existing_source(self):
        with self.assertRaisesRegex(ValueError, "source commit"):
            self.github_publish(exists=True, corrupt_existing=True)
