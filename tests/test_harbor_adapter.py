"""Check adapter boundaries without launching Docker or paid models."""

import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from harbor.models.job.config import JobConfig

from sci_pipeline.artifacts import write_json
from sci_pipeline.config import ApiSettings, RunConfig
from sci_pipeline.contracts import TaskRequest
from sci_pipeline.harbor_backend import HarborBackend
from sci_pipeline.harbor_runner import HarborExecutionError, HarborRunner
from sci_pipeline.mock import MockBackend
from sci_pipeline.probe import IncorrectSubmissionAgent
from sci_pipeline.usage import summarize_usage


class HarborAdapterTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        (self.root / "task.toml").write_text('schema_version = "1.4"\n')
        self.api = ApiSettings(
            api_key="fixture-secret", model="fixture-model", base_url="https://example.com/v1"
        )
        self.runner = HarborRunner(RunConfig(mode="harbor"), self.api)
        cleanup = patch("sci_pipeline.lifecycle.cleanup_job", return_value=True)
        cleanup.start()
        self.addCleanup(cleanup.stop)

    def test_job_config_uses_variable_references_not_key(self):
        config = JobConfig.model_validate({"agents": [self.runner.codex()]})
        self.assertNotIn("fixture-secret", config.model_dump_json())
        self.assertIn("${OPENAI_API_KEY}", config.model_dump_json())

    def test_role_receives_scoped_credentials_only(self):
        def popen(command, *, env, **kwargs):
            self.assertEqual(env["OPENAI_API_KEY"], "fixture-secret")
            self.assertNotIn("CODEX_FORCE_AUTH_JSON", env)
            self.assertNotIn("UNRELATED_TOKEN", env)
            self.assertEqual(env["BUILDX_BUILDER"], "default")
            config = JobConfig.model_validate_json(Path(command[-2]).read_text())
            trial = config.jobs_dir / config.job_name / "trial" / "result.json"
            write_json(trial, {"exception_info": None})
            process = Mock()
            process.pid = 99999999
            process.wait.return_value = 0
            return process

        with (
            patch.dict(
                "os.environ", {"CODEX_FORCE_AUTH_JSON": "true", "UNRELATED_TOKEN": "private"}
            ),
            patch("sci_pipeline.harbor_runner.subprocess.Popen", side_effect=popen),
        ):
            self.runner.run(
                self.root,
                self.root / "job",
                self.runner.codex(),
                verify=False,
                timeout=30,
                credentials=True,
            )

    def test_task_validation_does_not_receive_api_key(self):
        def popen(command, *, env, **kwargs):
            self.assertNotIn("OPENAI_API_KEY", env)
            config = JobConfig.model_validate_json(Path(command[-2]).read_text())
            write_json(
                config.jobs_dir / config.job_name / "trial/result.json", {"exception_info": None}
            )
            process = Mock()
            process.pid = 99999999
            process.wait.return_value = 0
            return process

        with patch("sci_pipeline.harbor_runner.subprocess.Popen", side_effect=popen):
            self.runner.run(
                self.root, self.root / "job", {"name": "oracle"}, verify=True, timeout=30
            )

    def test_log_scrubbing(self):
        log = self.root / "worker.log"
        log.write_text("error fixture-secret")
        self.assertTrue(self.runner.scrub(self.root))
        self.assertEqual(log.read_text(), "error [REDACTED_API_KEY]")

    def test_native_usage_ignores_copies_and_unknown_prices(self):
        result = {
            "stats": {
                "n_input_tokens": 100,
                "n_cache_tokens": 0,
                "n_output_tokens": 20,
                "cost_usd": None,
            }
        }
        path = "tasks/t/revision-000/author-runtime/execution/jobs/job/result.json"
        write_json(self.root / path, result)
        write_json(self.root / "tasks/t/revision-000/reviewer-input/copied-result.json", result)
        summary = summarize_usage(self.root)
        self.assertEqual(summary["n_input_tokens"], 100)
        self.assertIsNone(summary["cost_usd"])

    def test_probe_is_concrete_harbor_agent(self):
        agent = IncorrectSubmissionAgent(logs_dir=self.root, probe_path=str(self.root / "probe.sh"))
        self.assertEqual(agent.name(), "incorrect-submission")

    def test_custom_difficulty_reaches_author_without_changing_public_task(self):
        guidance = "研究级反演：区分测量偏差与动力学参数。\n允许等价解，不设主观难度淘汰。"
        # Recreate the serialized run policy passed through the DD generator parameters.
        config = RunConfig.model_validate_json(
            RunConfig(mode="harbor", difficulty_guidance=guidance).model_dump_json()
        )
        backend = HarborBackend(config, self.api, self.root / "skills")
        request = TaskRequest(task_id="test-task", package_uri=str(self.root), variant=0)

        def role(role, output, inputs, instructions, runtime):
            self.assertEqual(role, "author")
            self.assertIn(guidance, instructions)
            self.assertIn(str(config.environment_memory_mb), instructions)
            MockBackend().author(request, self.root, output, 0, None, None)

        with patch.object(backend, "_role", side_effect=role):
            backend.author(request, self.root, self.root / "author", 0, None, None)
        task = self.root / "author/tasks/test-task/task"
        self.assertNotIn(guidance, (task / "instruction.md").read_text())
        self.assertNotIn("difficulty_guidance", (task / "task.toml").read_text())

    def test_legacy_and_empty_difficulty_configs_remain_unspecified(self):
        for config in (RunConfig(mode="harbor"), RunConfig(mode="harbor", difficulty_guidance="")):
            self.assertEqual(config.difficulty_guidance, "")
            backend = HarborBackend(config, self.api, self.root)
            request = TaskRequest(task_id="test-task", package_uri=str(self.root), variant=0)
            with patch.object(backend, "_deliver") as delivered:
                backend.author(request, self.root, self.root / "author", 0, None, None)
            self.assertIn("未指定", delivered.call_args.args[3])

    def test_incomplete_author_handoff_gets_bounded_retry_with_partial_files(self):
        backend = HarborBackend(RunConfig(mode="harbor"), self.api, self.root / "skills")
        request = TaskRequest(task_id="test-task", package_uri=str(self.root), variant=0)
        count = 0

        def role(role, output, inputs, instructions, runtime):
            nonlocal count
            count += 1
            output.mkdir(parents=True)
            if count == 1:
                (output / "partial.txt").write_text("incomplete")
            else:
                self.assertIn("partial-output", inputs)
                MockBackend().author(request, self.root, output, 0, None, None)

        with patch.object(backend, "_role", side_effect=role):
            backend.author(request, self.root, self.root / "author", 0, None, None)
        self.assertEqual(count, 2)
        self.assertTrue((self.root / "author/author-result.json").is_file())

    def test_provider_retry_is_fresh_and_does_not_consume_handoff_attempts(self):
        backend = HarborBackend(
            RunConfig(mode="harbor", max_role_attempts=1, api_retries=2, api_retry_delay_sec=0),
            self.api,
            self.root,
        )
        request = TaskRequest(task_id="test-task", package_uri=str(self.root), variant=0)
        runtimes = []

        def role(role, output, inputs, instructions, runtime):
            runtimes.append(runtime)
            if len(runtimes) < 3:
                raise HarborExecutionError("provider failed", retryable=True)
            MockBackend().author(request, self.root, output, 0, None, None)

        with patch.object(backend, "_role", side_effect=role):
            backend.author(request, self.root, self.root / "author", 0, None, None)
        self.assertEqual(len(set(runtimes)), 3)
        self.assertTrue((runtimes[0] / "api-error.json").is_file())
        self.assertTrue((self.root / "author/author-result.json").is_file())

    def test_non_provider_failure_is_not_retried(self):
        backend = HarborBackend(
            RunConfig(mode="harbor", api_retry_delay_sec=0), self.api, self.root
        )
        with patch.object(
            backend, "_role", side_effect=HarborExecutionError("Docker failed")
        ) as called:
            with self.assertRaises(HarborExecutionError):
                backend._deliver("author", self.root / "out", {}, "", lambda _: None)
        self.assertEqual(called.call_count, 1)

    def test_provider_retry_limit_is_enforced(self):
        backend = HarborBackend(
            RunConfig(mode="harbor", api_retries=2, api_retry_delay_sec=0), self.api, self.root
        )
        with patch.object(
            backend, "_role", side_effect=HarborExecutionError("provider", retryable=True)
        ) as called:
            with self.assertRaises(HarborExecutionError):
                backend._deliver("author", self.root / "out", {}, "", lambda _: None)
        self.assertEqual(called.call_count, 3)

    def test_collect_classifies_provider_evidence_and_rejects_generic_exit(self):
        log = self.root / "agent/codex.txt"
        log.parent.mkdir()
        result = {
            "exception_info": {"exception_type": "NonZeroAgentExitCodeError"},
            "local_trial_dir": str(self.root),
        }
        for diagnostic, expected in (
            ("invalid_encrypted_content", True),
            ("rate limit exceeded", True),
            ("apply_patch: command not found", False),
            ("HTTP 401 unauthorized", False),
        ):
            log.write_text(diagnostic)
            with self.assertRaises(HarborExecutionError) as caught:
                self.runner.collect(result, self.root / "output")
            self.assertEqual(caught.exception.retryable, expected)

    def test_native_rate_limit_type_is_retryable_without_generic_exit(self):
        result = {
            "exception_info": {"exception_type": "ApiRateLimitError"},
            "local_trial_dir": str(self.root),
        }
        with self.assertRaises(HarborExecutionError) as caught:
            self.runner.collect(result, self.root / "out")
        self.assertTrue(caught.exception.retryable)

    def test_handoff_retry_limit_is_enforced(self):
        backend = HarborBackend(RunConfig(mode="harbor", max_role_attempts=2), self.api, self.root)

        def role(role, output, inputs, instructions, runtime):
            output.mkdir(parents=True)

        request = TaskRequest(task_id="test-task", package_uri=str(self.root), variant=0)
        with patch.object(backend, "_role", side_effect=role) as called:
            with self.assertRaisesRegex(ValueError, "after 2 attempts"):
                backend.author(request, self.root, self.root / "author", 0, None, None)
        self.assertEqual(called.call_count, 2)


if __name__ == "__main__":
    unittest.main()
