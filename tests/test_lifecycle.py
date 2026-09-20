"""Real local subprocess ownership tests; Docker operations are mocked."""

import os
import signal
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from sci_pipeline.artifacts import read_json, write_json
from sci_pipeline.lifecycle import (
    ExecutionSession,
    LifecycleError,
    identity_alive,
    process_identity,
    recover_executions,
    request_cancel,
    stop_identity,
)


class LifecycleTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        write_json(self.root / "run-config.json", {})
        self.directory = self.root / "execution"
        self.directory.mkdir()
        self.cleanup = patch("sci_pipeline.lifecycle.cleanup_job", return_value=True)
        self.cleaner = self.cleanup.start()
        self.addCleanup(self.cleanup.stop)

    def spawn(self):
        process = subprocess.Popen(
            [sys.executable, "-c", "import time; time.sleep(60)"], start_new_session=True
        )

        def finish():
            if process.poll() is None:
                os.killpg(process.pid, signal.SIGKILL)
            process.wait(timeout=5)

        self.addCleanup(finish)
        return process

    def session(self):
        return ExecutionSession(self.directory, self.directory / "jobs/sci-test", grace=1)

    def test_cancel_stops_worker_before_cleanup_and_is_idempotent(self):
        process = self.spawn()

        def clean(*args, **kwargs):
            self.assertIsNotNone(process.poll())
            return True

        self.cleaner.side_effect = clean
        with self.assertRaisesRegex(LifecycleError, "cancellation"):
            with self.session() as session:
                session.attach(process)
                request_cancel(self.root)
                session.wait(10)
        self.assertTrue(session.stop())
        self.assertEqual(self.cleaner.call_count, 1)
        record = read_json(self.directory / "execution.json")
        self.assertEqual(record["state"], "finished")
        self.assertEqual(record["outcome"], "cancelled")

    def test_timeout_stops_worker(self):
        process = self.spawn()
        with self.assertRaisesRegex(LifecycleError, "deadline"):
            with self.session() as session:
                session.attach(process)
                session.wait(0)
        self.assertIsNotNone(process.poll())
        self.assertEqual(read_json(session.path)["outcome"], "timeout")

    def test_exception_uses_same_cleanup_path(self):
        process = self.spawn()
        with self.assertRaisesRegex(ValueError, "fixture"):
            with self.session() as session:
                session.attach(process)
                raise ValueError("fixture")
        self.assertIsNotNone(process.poll())
        self.assertEqual(read_json(session.path)["state"], "finished")

    def test_cleanup_failure_blocks_new_execution(self):
        self.cleaner.return_value = False
        with self.assertRaisesRegex(LifecycleError, "Cleanup incomplete"):
            with self.session():
                pass
        self.assertEqual(read_json(self.directory / "execution.json")["state"], "cleanup_pending")
        with self.assertRaisesRegex(LifecycleError, "no new worker"):
            with self.session():
                pass

    def test_recovery_refuses_live_owner(self):
        session = self.session()
        session.save("running")
        with self.assertRaisesRegex(LifecycleError, "still alive"):
            recover_executions(self.root)
        self.cleaner.assert_not_called()

    def test_recovery_stops_orphan_and_cleans_once(self):
        process = self.spawn()
        session = self.session()
        session.attach(process)
        session.record["owner"] = None
        session.save("running")
        recovered = recover_executions(self.root)
        self.assertEqual(len(recovered), 1)
        self.assertFalse(identity_alive(process_identity(process.pid)))
        self.assertEqual(recover_executions(self.root), [])

    def test_reused_pid_is_not_signalled(self):
        process = self.spawn()
        identity = process_identity(process.pid)
        identity["start_ticks"] = "0"
        with patch("sci_pipeline.lifecycle.os.killpg") as kill:
            self.assertFalse(stop_identity(identity, 0))
            kill.assert_not_called()

    def test_recovery_refuses_foreign_host(self):
        session = self.session()
        session.record.update(host="another-host", owner=None)
        session.save("running")
        with self.assertRaisesRegex(LifecycleError, "another host"):
            recover_executions(self.root)

    def test_leftover_descendant_after_leader_exit_is_stopped(self):
        script = "import subprocess,sys; p=subprocess.Popen([sys.executable,'-c','import time; time.sleep(60)']); print(p.pid,flush=True)"
        process = subprocess.Popen(
            [sys.executable, "-c", script],
            stdout=subprocess.PIPE,
            text=True,
            start_new_session=True,
        )
        identity = process_identity(process.pid)
        child_pid = int(process.stdout.readline())
        process.wait(timeout=5)
        process.stdout.close()
        self.addCleanup(lambda: stop_identity(identity, 0))
        self.assertIsNotNone(process_identity(child_pid))
        self.assertTrue(stop_identity(identity, 1))
        self.assertIsNone(process_identity(child_pid))

    def test_recovery_after_actual_owner_process_crash(self):
        script = """
import os, subprocess, sys
from pathlib import Path
from sci_pipeline.lifecycle import ExecutionSession
path = Path(sys.argv[1])
with ExecutionSession(path, path / 'jobs/sci-crash', grace=1) as session:
    process = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(60)'],
                               start_new_session=True, stdout=subprocess.DEVNULL,
                               stderr=subprocess.DEVNULL)
    session.attach(process)
    os._exit(77)
"""
        owner = subprocess.run([sys.executable, "-c", script, str(self.directory)], timeout=10)
        self.assertEqual(owner.returncode, 77)
        record = read_json(self.directory / "execution.json")
        self.addCleanup(lambda: stop_identity(record["worker"], 0))
        self.assertTrue(identity_alive(record["worker"]))
        self.assertEqual(len(recover_executions(self.root)), 1)
        self.assertFalse(identity_alive(record["worker"]))

    def test_worker_refuses_start_after_owner_exit(self):
        session = self.session()
        session.record["owner"] = None
        session.save("starting")
        worker = subprocess.run(
            [
                sys.executable,
                "-m",
                "sci_pipeline.harbor_worker",
                str(self.directory / "job.json"),
                "1",
            ],
            capture_output=True,
            text=True,
            timeout=15,
        )
        self.assertEqual(worker.returncode, 125, worker.stderr)
        self.assertFalse((self.directory / "jobs").exists())
