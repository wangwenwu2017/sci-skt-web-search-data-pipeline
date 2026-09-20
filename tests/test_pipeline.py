"""Boundary tests for role ownership, bounded repairs and truthful status."""

import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from harbor.models.task.config import TaskConfig

from sci_pipeline.artifacts import copy_tree, fingerprint, safe_path
from sci_pipeline.cli import prepare_requests
from sci_pipeline.config import ApiSettings, RunConfig
from sci_pipeline.contracts import TaskRequest
from sci_pipeline.mock import MockBackend
from sci_pipeline.pipeline import produce_task


class PipelineTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.source = self.root / "source"
        self.source.mkdir()
        (self.source / "PACKAGE.md").write_text("Scientific references go here.\n")
        self.request = TaskRequest(task_id="task-001", package_uri=str(self.source), variant=0)

    def run_task(self, backend=None, **kwargs):
        return produce_task(
            self.request, self.root / "run", RunConfig(**kwargs), backend or MockBackend()
        )

    def test_mock_completes_without_claiming_validation(self):
        result = self.run_task()
        self.assertEqual(result.status, "mock_completed")
        self.assertFalse(result.validated)
        task = Path(result.task_package_uri)
        TaskConfig.model_validate_toml((task / "task.toml").read_text())
        checks = json.loads(
            (self.root / "run/tasks/task-001/revision-000/builder/validation.json").read_text()
        )
        self.assertTrue(all(check["status"] == "not_run" for check in checks["checks"]))

    def test_revision_returns_to_author_and_preserves_previous(self):
        result = self.run_task(MockBackend(revise_once=True))
        self.assertEqual(result.status, "mock_completed")
        self.assertEqual(result.revision, 1)
        task_dir = self.root / "run/tasks/task-001"
        revisions = [
            json.loads((task_dir / f"revision-{n:03d}/reviewer/review.json").read_text())
            for n in range(2)
        ]
        self.assertNotEqual(revisions[0]["candidate_revision"], revisions[1]["candidate_revision"])
        self.assertTrue((task_dir / "revision-000/feedback.json").is_file())

    def test_revision_budget_exhaustion_is_not_success(self):
        result = self.run_task(MockBackend(revise_once=True), max_revisions=0)
        self.assertEqual(result.status, "revision_limit")
        self.assertFalse(result.validated)

    def test_builder_cannot_change_task(self):
        class MutatingBuilder(MockBackend):
            def build(self, request, candidate, output, candidate_revision):
                (candidate / "task/instruction.md").write_text("silently changed")
                return super().build(request, candidate, output, candidate_revision)

        result = self.run_task(MutatingBuilder())
        self.assertEqual(result.status, "failed")
        self.assertIn("Builder changed", result.error)
        self.assertIn(
            "Mock arithmetic", Path(result.task_package_uri, "instruction.md").read_text()
        )

    def test_reviewer_cannot_change_builder_evidence(self):
        class MutatingReviewer(MockBackend):
            def review(
                self, request, source, candidate, build_output, output, candidate_revision, revision
            ):
                (build_output / "validation.json").write_text("{}")
                return super().review(
                    request, source, candidate, build_output, output, candidate_revision, revision
                )

        result = self.run_task(MutatingReviewer())
        self.assertEqual(result.status, "failed")
        self.assertIn("Reviewer changed", result.error)

    def test_stale_evidence_rejected(self):
        class StaleBuilder(MockBackend):
            def build(self, request, candidate, output, candidate_revision):
                return super().build(request, candidate, output, "previous-version")

        result = self.run_task(StaleBuilder())
        self.assertEqual(result.status, "failed")
        self.assertIn("another candidate", result.error)

    def test_backend_exception_preserves_failure_artifact(self):
        class BrokenAuthor(MockBackend):
            def author(self, *args):
                raise RuntimeError("fixture failure")

        result = self.run_task(BrokenAuthor())
        self.assertEqual(result.status, "failed")
        self.assertTrue(Path(result.report_uri).is_file())

    def test_missing_materials_is_not_retried_as_invalid_format(self):
        class MissingMaterialsAuthor(MockBackend):
            def author(self, request, source, output, *args):
                (output / "author-result.json").write_text(
                    '{"status":"needs_materials","tasks":[],"issues":[]}'
                )

        result = self.run_task(MissingMaterialsAuthor())
        self.assertEqual(result.status, "needs_materials")
        self.assertFalse(result.validated)

    def test_pass_with_blocker_rejected(self):
        class ContradictoryReviewer(MockBackend):
            def review(self, *args):
                result = super().review(*args)
                result.issues = [{"severity": "blocking"}]
                return result

        self.assertEqual(self.run_task(ContradictoryReviewer()).status, "failed")

    def test_output_path_escape_rejected(self):
        with self.assertRaises(ValueError):
            safe_path(self.root, "../outside")
        link = self.root / "link"
        link.symlink_to(self.root.parent)
        with self.assertRaises(ValueError):
            safe_path(self.root, "link/outside")

    def test_internal_links_are_materialized_without_changing_contents(self):
        (self.source / "alias.md").symlink_to("PACKAGE.md")
        expected = fingerprint(self.source)
        copied = self.root / "copied"
        copy_tree(self.source, copied)
        self.assertFalse((copied / "alias.md").is_symlink())
        self.assertEqual(fingerprint(copied), expected)

    def test_external_and_cyclic_links_are_rejected(self):
        link = self.source / "escape"
        link.symlink_to(self.root)
        with self.assertRaises(ValueError):
            fingerprint(self.source)
        link.unlink()
        link.symlink_to(self.source)
        with self.assertRaisesRegex(ValueError, "cyclic"):
            fingerprint(self.source)

    def test_seed_expansion_has_unique_ids_and_snapshot(self):
        seeds = self.root / "seeds.jsonl"
        seeds.write_text(json.dumps({"package_uri": "source"}) + "\n")
        requests = prepare_requests(
            seeds, self.root, self.root / "batch", RunConfig(tasks_per_package=3)
        )
        self.assertEqual(len({r.task_id for r in requests}), 3)
        self.assertNotEqual(requests[0].package_uri, str(self.source))
        self.assertTrue(Path(requests[0].package_uri, "PACKAGE.md").is_file())

    def test_config_rejects_unknown_fields_and_bad_limits(self):
        for args in ({"max_concurreny": 2}, {"tasks_per_package": 0}, {"max_revisions": -1}):
            with self.assertRaises(ValueError):
                RunConfig(**args)

    def test_credentials_environment_precedence_and_secret_repr(self):
        env_file = self.root / ".env"
        env_file.write_text("OPENAI_API_KEY=file-secret\nSCI_PIPELINE_MODEL=fixture-model\n")
        with patch.dict(os.environ, {"OPENAI_API_KEY": "environment-secret"}, clear=True):
            settings = ApiSettings.load(env_file)
            self.assertEqual(settings.api_key.get_secret_value(), "environment-secret")
            self.assertNotIn("environment-secret", repr(settings))
            self.assertNotIn("environment-secret", settings.model_dump_json())

    def test_missing_api_config_reports_names_only(self):
        with patch.dict(os.environ, {}, clear=True):
            with self.assertRaisesRegex(ValueError, "OPENAI_API_KEY, SCI_PIPELINE_MODEL"):
                ApiSettings.load(self.root / "missing.env")


if __name__ == "__main__":
    unittest.main()
