"""Optional skills cannot change acceptance or expose unreviewed artifacts."""

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from sci_pipeline.artifacts import fingerprint, read_json, write_json
from sci_pipeline.config import RunConfig
from sci_pipeline.contracts import TaskRequest
from sci_pipeline.mock import MockBackend
from sci_pipeline.pipeline import produce_task


class SkillExtractionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.source = self.root / "source"
        self.source.mkdir()
        (self.source / "PACKAGE.md").write_text("fixture")
        self.request = TaskRequest(task_id="task-0", package_uri=str(self.source), variant=0)
        self.run = self.root / "run"
        self.config = RunConfig(generate_skills=True)

    def produce(self, backend=None, config=None):
        return produce_task(self.request, self.run, config or self.config, backend or MockBackend())

    def test_disabled_does_not_call_optional_roles(self):
        with patch.object(MockBackend, "extract_skill", side_effect=AssertionError("unexpected")):
            result = self.produce(config=RunConfig())
        self.assertEqual(result.skill_status, "disabled")
        self.assertFalse(list(self.run.rglob("skill-extraction")))

    def test_reviewed_skill_is_separate_and_not_claimed_as_validated_in_mock(self):
        result = self.produce()
        self.assertEqual(result.status, "mock_completed")
        self.assertEqual(result.skill_status, "mock_completed")
        self.assertFalse(Path(result.skill_package_uri).is_relative_to(result.task_package_uri))
        self.assertTrue(Path(result.skill_package_uri, "SKILL.md").is_file())
        link = read_json(Path(result.skill_report_uri).parent / "skill-link.json")
        self.assertFalse(link["transfer_evaluated"])
        self.assertFalse(link["solver_access"])
        self.assertEqual(link["candidate_revision"], result.candidate_revision)
        self.assertFalse(result.validated)

    def test_failure_does_not_change_task_status(self):
        with patch.object(
            MockBackend, "extract_skill", side_effect=RuntimeError("fixture failure")
        ):
            result = self.produce()
        self.assertEqual(result.status, "mock_completed")
        self.assertEqual(result.skill_status, "failed")
        self.assertIsNone(result.skill_package_uri)
        self.assertIn("fixture failure", result.skill_error)

    def test_rejected_skill_not_published(self):
        original = MockBackend.review_skill

        def reject(backend, *args):
            original(backend, *args)
            path = args[3] / "skill-review.json"
            review = read_json(path)
            review.update(decision="reject", findings=["Task-specific answer included"])
            write_json(path, review)

        with patch.object(MockBackend, "review_skill", reject):
            result = self.produce()
        self.assertEqual(result.status, "mock_completed")
        self.assertEqual(result.skill_status, "rejected")
        self.assertIsNone(result.skill_package_uri)

    def test_review_interruption_reuses_draft_and_task(self):
        with patch.object(MockBackend, "review_skill", side_effect=KeyboardInterrupt):
            with self.assertRaises(KeyboardInterrupt):
                self.produce()
        with (
            patch.object(MockBackend, "author", side_effect=AssertionError("author reran")),
            patch.object(MockBackend, "extract_skill", side_effect=AssertionError("draft reran")),
        ):
            result = self.produce()
        self.assertEqual(result.skill_status, "mock_completed")

    def test_mutating_extractor_cannot_damage_task(self):
        def mutate(backend, request, inputs, output, revision):
            (inputs / "candidate/task/instruction.md").write_text("damaged")
            raise RuntimeError("bad extractor")

        with patch.object(MockBackend, "extract_skill", mutate):
            result = self.produce()
        self.assertEqual(result.status, "mock_completed")
        self.assertEqual(result.skill_status, "failed")
        self.assertEqual(
            fingerprint(Path(result.task_package_uri).parent), result.candidate_revision
        )

    def test_no_skill_for_unaccepted_task(self):
        with (
            patch.object(MockBackend, "author", side_effect=RuntimeError("failed task")),
            patch.object(MockBackend, "extract_skill", side_effect=AssertionError("unexpected")),
        ):
            result = self.produce()
        self.assertEqual(result.status, "failed")
        self.assertEqual(result.skill_status, "not_applicable")
        self.assertEqual(
            json.loads(Path(result.report_uri).read_text())["skill_status"], "not_applicable"
        )

    def test_no_reusable_method_is_explicit(self):
        def decline(backend, request, inputs, output, revision):
            write_json(
                output / "skill-draft.json",
                {
                    "task_id": request.task_id,
                    "candidate_revision": revision,
                    "status": "not_applicable",
                    "reason": "No reusable method",
                },
            )

        with patch.object(MockBackend, "extract_skill", decline):
            result = self.produce()
        self.assertEqual(result.skill_status, "not_applicable")
        self.assertEqual(result.status, "mock_completed")
