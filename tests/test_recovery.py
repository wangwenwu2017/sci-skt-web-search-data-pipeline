"""Recovery tests use real Data Designer scheduling with local mock roles only."""

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from sci_pipeline.cli import main, prepare_requests
from sci_pipeline.config import RunConfig
from sci_pipeline.contracts import TaskRequest
from sci_pipeline.mock import MockBackend
from sci_pipeline.pipeline import produce_task


class RecoveryTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.source = self.root / "source"
        self.source.mkdir()
        (self.source / "PACKAGE.md").write_text("References")
        self.run = self.root / "run"
        self.request = TaskRequest(task_id="test", package_uri=str(self.source), variant=0)

    def test_bad_inputs_do_not_block_good_inputs_or_shift_ids(self):
        seeds = self.root / "seeds.jsonl"
        seeds.write_text('not json\n{"package_uri":"absent"}\n{"package_uri":"source"}\n')
        requests = prepare_requests(seeds, self.root, self.run, RunConfig())
        self.assertEqual([r.task_id for r in requests], ["p002-task-000"])
        self.assertEqual(len(json.loads((self.run / "input-errors.json").read_text())), 2)

    def test_resume_after_builder_interruption_reuses_author(self):
        class Interrupted(MockBackend):
            def build(self, *args):
                raise KeyboardInterrupt()

        with self.assertRaises(KeyboardInterrupt):
            produce_task(self.request, self.run, RunConfig(), Interrupted())
        with patch.object(MockBackend, "author", side_effect=AssertionError("author reran")):
            result = produce_task(self.request, self.run, RunConfig(), MockBackend())
        self.assertEqual(result.status, "mock_completed")

    def test_resume_after_review_interruption_reuses_both_stages(self):
        class Interrupted(MockBackend):
            def review(self, *args):
                output = args[4]
                output.mkdir()
                (output / "partial.txt").write_text("interrupted")
                raise KeyboardInterrupt()

        with self.assertRaises(KeyboardInterrupt):
            produce_task(self.request, self.run, RunConfig(), Interrupted())
        with (
            patch.object(MockBackend, "author", side_effect=AssertionError("author reran")),
            patch.object(MockBackend, "build", side_effect=AssertionError("builder reran")),
        ):
            result = produce_task(self.request, self.run, RunConfig(), MockBackend())
        self.assertEqual(result.status, "mock_completed")
        self.assertTrue(list((self.run / "history").rglob("partial.txt")))

    def test_modified_checkpoint_is_rejected(self):
        class Interrupted(MockBackend):
            def build(self, *args):
                raise KeyboardInterrupt()

        with self.assertRaises(KeyboardInterrupt):
            produce_task(self.request, self.run, RunConfig(), Interrupted())
        path = next((self.run / "tasks").rglob("instruction.md"))
        path.write_text("tampered")
        result = produce_task(self.request, self.run, RunConfig(), MockBackend())
        self.assertEqual(result.status, "failed")
        self.assertIn("artifacts changed", result.error)

    def cli(self, *args):
        with (
            patch.object(sys, "argv", ["sci-pipeline", *map(str, args)]),
            patch.dict(os.environ, {"DATA_DESIGNER_HOME": str(self.root / "dd-home")}),
        ):
            return main()

    def test_real_designer_resume_and_failed_only_retry(self):
        config = self.root / "config.json"
        config.write_text(RunConfig(tasks_per_package=2, max_concurrency=2).model_dump_json())
        seeds = self.root / "seeds.jsonl"
        seeds.write_text('{"package_uri":"source"}\n')
        original = MockBackend.author

        def fail_second(backend, request, *args):
            if request.variant == 1:
                raise RuntimeError("transient fixture failure")
            return original(backend, request, *args)

        with patch.object(MockBackend, "author", fail_second):
            self.assertEqual(
                self.cli(
                    "--config",
                    config,
                    "--seeds",
                    seeds,
                    "--source-root",
                    self.root,
                    "--output-root",
                    self.root / "runs",
                ),
                1,
            )
        run = next((self.root / "runs").iterdir())
        accepted = run / "tasks/p000-task-000/result.json"
        before = accepted.stat().st_mtime_ns
        with patch.object(MockBackend, "author", side_effect=AssertionError("unexpected call")):
            self.assertEqual(self.cli("--resume", run), 1)
        self.assertEqual(self.cli("--retry-failed", run), 0)
        self.assertEqual(before, accepted.stat().st_mtime_ns)
        self.assertTrue(list((run / "history").glob("retry-*/tasks/p000-task-001/result.json")))
        with patch.object(MockBackend, "author", side_effect=AssertionError("unexpected call")):
            self.assertEqual(self.cli("--resume", run), 0)

    def test_all_invalid_inputs_finish_with_report(self):
        config = self.root / "config.json"
        config.write_text(RunConfig().model_dump_json())
        seeds = self.root / "seeds.jsonl"
        seeds.write_text('{"package_uri":"absent"}\n')
        self.assertEqual(
            self.cli(
                "--config",
                config,
                "--seeds",
                seeds,
                "--source-root",
                self.root,
                "--output-root",
                self.root / "runs",
            ),
            1,
        )
        run = next((self.root / "runs").iterdir())
        summary = json.loads((run / "summary.json").read_text())
        self.assertEqual(summary["task_count"], 0)
        self.assertFalse(summary["validated"])
        self.assertEqual(summary["input_error_count"], 1)

    def test_native_designer_partial_checkpoint_resume(self):
        import subprocess

        from sci_pipeline.designer import create_dataset

        self.run.mkdir()
        requests = [self.request.model_copy(update={"task_id": f"task-{i}"}) for i in range(4)]
        config = RunConfig(max_concurrency=1)
        script = """
import os, sys
from pathlib import Path
from unittest.mock import patch
from data_designer.interface import DataDesigner
from sci_pipeline.config import RunConfig
from sci_pipeline.contracts import TaskRequest
from sci_pipeline.designer import create_dataset
root = Path(sys.argv[1])
os.environ['DATA_DESIGNER_HOME'] = str(root / 'dd-home')
requests = [TaskRequest(task_id=f'task-{i}', package_uri=str(root / 'source'), variant=0)
            for i in range(4)]
original = DataDesigner.create
def interrupted(designer, *args, **kwargs):
    return original(designer, *args, **kwargs, on_batch_complete=lambda _: os._exit(77))
with patch.object(DataDesigner, 'create', interrupted):
    create_dataset(root / 'run', requests, RunConfig(max_concurrency=1), root / '.env', root)
"""
        child = subprocess.run(
            [sys.executable, "-c", script, str(self.root)],
            capture_output=True,
            text=True,
            timeout=30,
        )
        self.assertEqual(child.returncode, 77, child.stderr)
        first = self.run / "tasks/task-0/result.json"
        before = first.stat().st_mtime_ns
        self.assertFalse((self.run / "tasks/task-3/result.json").exists())
        with patch.dict(os.environ, {"DATA_DESIGNER_HOME": str(self.root / "dd-home")}):
            results = create_dataset(self.run, requests, config, self.root / ".env", self.root)
        self.assertEqual(len(results), 4)
        self.assertEqual(before, first.stat().st_mtime_ns)

    def test_run_lock_rejects_second_writer(self):
        import fcntl

        self.run.mkdir()
        (self.run / "run-config.json").write_text(RunConfig().model_dump_json())
        with (self.run / ".run.lock").open("a") as lock:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            with self.assertRaises(SystemExit) as raised:
                self.cli("--resume", self.run)
        self.assertEqual(raised.exception.code, 2)

    def test_retry_skills_keeps_accepted_task_and_uses_designer(self):
        config = self.root / "config.json"
        config.write_text(RunConfig(generate_skills=True).model_dump_json())
        seeds = self.root / "seeds.jsonl"
        seeds.write_text('{"package_uri":"source"}\n')
        with patch.object(MockBackend, "extract_skill", side_effect=RuntimeError("skill failed")):
            self.assertEqual(
                self.cli(
                    "--config",
                    config,
                    "--seeds",
                    seeds,
                    "--source-root",
                    self.root,
                    "--output-root",
                    self.root / "runs",
                ),
                0,
            )
        run = next((self.root / "runs").iterdir())
        result_path = run / "tasks/p000-task-000/result.json"
        result = json.loads(result_path.read_text())
        self.assertEqual(result["skill_status"], "failed")
        instruction = Path(result["task_package_uri"]) / "instruction.md"
        before = instruction.stat().st_mtime_ns
        with patch.object(MockBackend, "author", side_effect=AssertionError("task reran")):
            self.assertEqual(self.cli("--retry-skills", run), 0)
            self.assertEqual(self.cli("--resume", run), 0)
        self.assertEqual(instruction.stat().st_mtime_ns, before)
        self.assertEqual(json.loads(result_path.read_text())["skill_status"], "mock_completed")
