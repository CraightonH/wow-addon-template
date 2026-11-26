"""The client watcher reports changes without publishing releases."""
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import watch


class WatchTests(unittest.TestCase):
    def run_watch(self, issues):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "addon.json").write_text(json.dumps({"reviewed_upstream_commit": "a" * 40}))
            observation = {"commit": "b" * 40, "repository": "Gethe/wow-ui-source", "branch": "forever", "build": "1.60.1.12345"}
            calls = []
            with patch.object(watch, "ROOT", root), patch.object(watch, "observe", return_value=observation), \
                 patch.object(watch.subprocess, "check_output", return_value=json.dumps(issues)), \
                 patch.object(watch, "gh", side_effect=lambda *a, **kw: calls.append((a, kw))), \
                 patch.dict(os.environ, {"GH_REPO": "example/addon", "GITHUB_OUTPUT": str(root / "output")}):
                watch.main()
            return calls, (root / "output").read_text()

    def test_new_observation_requests_candidate(self):
        calls, output = self.run_watch([])
        self.assertEqual(calls[0][0][1], "POST")
        self.assertIn("changed=true", output)

    def test_closed_observation_is_not_reopened(self):
        issue = {"number": 1, "title": "Review WoW Forever compatibility", "state": "CLOSED", "body": "<!-- wow-addon-template:forever-compatibility -->\n<!-- upstream-sha:" + "b" * 40 + " -->"}
        calls, output = self.run_watch([issue])
        self.assertEqual(calls, [])
        self.assertIn("changed=false", output)
