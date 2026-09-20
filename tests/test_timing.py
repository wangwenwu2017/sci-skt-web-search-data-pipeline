import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

from sci_pipeline.artifacts import write_json
from sci_pipeline.timing import duration, summarize_timing


class TimingTests(unittest.TestCase):
    def test_retries_and_validation_are_counted_without_copied_evidence(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            record = {
                "started_at": "2026-09-17T07:00:00Z",
                "finished_at": "2026-09-17T07:00:10Z",
            }
            for attempt in (0, 1):
                write_json(
                    root
                    / f"tasks/t/revision-000/author-runtime/attempt-{attempt}/execution/jobs/j/t/result.json",
                    record,
                )
            write_json(
                root / "tasks/t/revision-000/builder/checks/oracle/jobs/j/t/result.json", record
            )
            write_json(root / "tasks/t/revision-000/reviewer-input/copied/result.json", record)
            result = summarize_timing(
                root,
                datetime(2026, 9, 17, 7, tzinfo=timezone.utc),
                datetime(2026, 9, 17, 7, 1, tzinfo=timezone.utc),
            )
            self.assertEqual(result["elapsed_sec"], 60)
            self.assertEqual(result["stage_total_sec"], {"author": 20, "oracle": 10})
            self.assertEqual(len(result["trials"]), 3)
            self.assertIsNone(duration({"started_at": record["started_at"]}))
