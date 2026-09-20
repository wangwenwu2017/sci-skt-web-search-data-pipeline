import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from sci_pipeline.artifacts import write_json
from sci_pipeline.cleanup import cleanup_job


class CleanupTests(unittest.TestCase):
    def test_only_resources_with_this_trials_prefix_are_removed(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_json(root / "trial/config.json", {"trial_name": "task__AbC123"})
            calls = []

            def run(args, **kwargs):
                calls.append(args)
                output = "owned123 task__abc123__env\nunrelated456 another-project\n"
                if args[-1] == "{{.ID}}":
                    output = "unrelated456\n"
                return subprocess.CompletedProcess(args, 0, stdout=output, stderr="")

            with patch("sci_pipeline.cleanup.subprocess.run", side_effect=run):
                self.assertTrue(cleanup_job(root))
            removals = [args for args in calls if "rm" in args]
            self.assertEqual(len(removals), 2)
            self.assertTrue(
                all("owned123" in args and "unrelated456" not in args for args in removals)
            )

    def test_unreadable_record_does_not_trigger_broad_cleanup(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "trial").mkdir()
            (root / "trial/config.json").write_text("{")
            with patch("sci_pipeline.cleanup.subprocess.run") as run:
                self.assertFalse(cleanup_job(root))
                run.assert_not_called()

    def test_execution_label_cleans_without_trial_metadata(self):
        with tempfile.TemporaryDirectory() as tmp:
            calls = []

            def run(args, **kwargs):
                calls.append(args)
                output = "ours project sci-123\ntheirs other sci-456\n"
                if args[-1] == "{{.ID}}":
                    output = "theirs\n"
                return subprocess.CompletedProcess(args, 0, stdout=output)

            with patch("sci_pipeline.cleanup.subprocess.run", side_effect=run):
                self.assertTrue(cleanup_job(Path(tmp), execution_id="sci-123"))
            self.assertTrue(all("theirs" not in args for args in calls if "rm" in args))

    def test_successful_remove_command_with_remaining_resource_is_failure(self):
        with tempfile.TemporaryDirectory() as tmp:

            def run(args, **kwargs):
                output = "ours" if args[-1] == "{{.ID}}" else "ours project sci-123\n"
                return subprocess.CompletedProcess(args, 0, stdout=output)

            with patch("sci_pipeline.cleanup.subprocess.run", side_effect=run):
                self.assertFalse(cleanup_job(Path(tmp), execution_id="sci-123"))
