"""Source contracts, failure isolation, publication recovery and actual DD scheduling."""

import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from sci_pipeline.artifacts import read_json, write_json
from sci_pipeline.harbor_runner import HarborRunner
from sci_pipeline.source.artifacts import validate_package
from sci_pipeline.source.backend import HarborSourceBackend, MockSourceBackend
from sci_pipeline.source.cli import main
from sci_pipeline.source.config import SourceApiSettings, SourceRunConfig
from sci_pipeline.source.contracts import Candidate, Discovery, Source, SourceRequest, expand
from sci_pipeline.source.pipeline import (
    build_plan,
    prepare,
    read_rows,
    retry_failed,
    row_directory,
    run_row,
)
from sci_pipeline.source.tavily_tool import call

SKILLS = Path(__file__).resolve().parents[1] / "skills"


class SourceTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.config = SourceRunConfig()
        self.request = SourceRequest(request_id="one", mode="domain", request="Find papers")
        self.payload = self.request.model_dump()
        write_json(self.root / "run-config.json", self.config.model_dump())

    def run_row(self, stage, row, worker=None):
        return run_row(self.root, stage, row, self.config, self.root / "absent.env", SKILLS, worker)

    def plan(self):
        self.run_row("discover", self.payload)
        return build_plan(self.root, [self.payload])

    def test_exact_dedup_only_within_request(self):
        a = Candidate(
            candidate_id="a",
            title="A",
            relevance="r",
            scope="same",
            sources=[Source(url="https://example.org/p"), Source(url="https://example.org/c")],
        )
        b = a.model_copy(update={"candidate_id": "b", "sources": list(reversed(a.sources))})
        c = a.model_copy(update={"candidate_id": "c", "scope": "different"})
        d = a.model_copy(
            update={
                "candidate_id": "d",
                "sources": [Source(url="https://example.org/p", version="2")],
            }
        )
        result = Discovery(status="completed", candidates=[a, b, c, d], report="ok")
        items = expand(self.request, result)
        self.assertEqual(len(items), 3)
        self.assertEqual([c.candidate_id for c in items[0].originals], ["a", "b"])
        other = expand(self.request.model_copy(update={"request_id": "two"}), result)
        self.assertNotEqual(items[0].item_id, other[0].item_id)

    def test_bad_request_and_duplicate_do_not_block_valid(self):
        text = "broken\n" + json.dumps(self.payload) + "\n" + json.dumps(self.payload)
        rows = prepare(self.root, text)
        self.assertEqual(len(rows), 1)
        self.assertEqual(len(json.loads((self.root / "input-errors.json").read_text())), 2)
        with self.assertRaises(ValueError):
            SourceRequest(request_id="../../escape", mode="domain", request="x")

    def test_completed_search_and_package_are_reused(self):
        plan = self.plan()
        self.assertEqual(len(plan), 2)
        result = self.run_row("package", plan[0])
        self.assertEqual(result["status"], "completed")
        with patch("sci_pipeline.source.pipeline.backend", side_effect=AssertionError("reran")):
            self.run_row("discover", self.payload)
            self.assertEqual(self.run_row("package", plan[0]), result)

    def test_publish_result_crash_window_needs_no_agent(self):
        item = self.plan()[0]
        result = self.run_row("package", item)
        path = row_directory(self.root, "package", item) / "result.json"
        path.unlink()
        with patch("sci_pipeline.source.pipeline.backend", side_effect=AssertionError("reran")):
            self.assertEqual(self.run_row("package", item), result)

    def test_corruption_requires_explicit_retry(self):
        item = self.plan()[0]
        result = self.run_row("package", item)
        (Path(result["package_uri"]) / "PACKAGE.md").write_text("corrupted")
        self.assertEqual(self.run_row("package", item)["status"], "failed")
        retry_failed(self.root, [self.payload], [item])
        self.assertEqual(self.run_row("package", item)["status"], "completed")

    def test_failed_search_retry_appends_without_renumbering_good_items(self):
        good = self.plan()
        second = self.request.model_copy(update={"request_id": "two"}).model_dump()

        class Failed(MockSourceBackend):
            def discover(self, request, output):
                raise ValueError("fixture search failed")

        self.assertEqual(self.run_row("discover", second, Failed())["status"], "failed")
        for item in good:
            self.run_row("package", item)
        retry_failed(self.root, [self.payload, second], good)
        self.run_row("discover", second)
        combined = build_plan(self.root, [self.payload, second])
        self.assertEqual(combined[: len(good)], good)
        self.assertEqual(len(combined), 4)

    def test_symlinks_and_broken_local_links_rejected(self):
        item = self.plan()[0]
        result = self.run_row("package", item)
        from sci_pipeline.source.contracts import PackageItem

        package = Path(result["package_uri"])
        (package / "link").symlink_to("PACKAGE.md")
        with self.assertRaises(ValueError):
            validate_package(package, PackageItem.model_validate(item))
        (package / "link").unlink()
        with (package / "PACKAGE.md").open("a") as stream:
            stream.write("\n[missing](materials/missing.csv)\n")
        with self.assertRaises(ValueError):
            validate_package(package, PackageItem.model_validate(item))

    def test_interrupted_package_resumes_without_repeating_search(self):
        item = self.plan()[0]

        class Interrupted(MockSourceBackend):
            def package(self, item, output):
                output.mkdir(parents=True)
                (output / "partial.txt").write_text("unfinished")
                raise KeyboardInterrupt()

        with self.assertRaises(KeyboardInterrupt):
            self.run_row("package", item, Interrupted())
        with patch.object(
            MockSourceBackend, "discover", side_effect=AssertionError("search reran")
        ):
            self.assertEqual(self.run_row("discover", self.payload)["status"], "completed")
            self.assertEqual(self.run_row("package", item)["status"], "completed")
        self.assertTrue(list(self.root.glob("items/*/attempts/*/output/partial.txt")))

    def test_no_results_is_successful_search_without_packages(self):
        class Empty(MockSourceBackend):
            def discover(self, request, output):
                output.mkdir(parents=True)
                write_json(
                    output / "candidates.json",
                    {
                        "status": "no_results",
                        "candidates": [],
                        "report": "No matching material",
                    },
                )
                (output / "report.md").write_text("No matching material")

        self.assertEqual(self.run_row("discover", self.payload, Empty())["status"], "no_results")
        self.assertEqual(build_plan(self.root, [self.payload]), [])

    def test_cancel_prevents_new_backend_calls(self):
        (self.root / "cancel.request").touch()
        with patch("sci_pipeline.source.pipeline.backend", side_effect=AssertionError("started")):
            self.assertEqual(self.run_row("discover", self.payload)["status"], "cancelled")
        self.assertFalse(
            (row_directory(self.root, "discover", self.payload) / "result.json").exists()
        )

    def test_both_credentials_scrubbed_and_only_placeholders_in_config(self):
        api = SourceApiSettings(
            api_key="model-fixture", tavily_api_key="search-fixture", model="test"
        )
        runner = HarborRunner(self.config.execution, api)
        (self.root / "log").write_text("model-fixture search-fixture")
        self.assertTrue(runner.scrub(self.root))
        self.assertNotIn("fixture", (self.root / "log").read_text())
        self.assertEqual(api.environment()["TAVILY_API_KEY"], "search-fixture")

    def test_harbor_role_injects_tool_and_search_env(self):
        api = SourceApiSettings(
            api_key="model-fixture", tavily_api_key="search-fixture", model="test"
        )
        backend = HarborSourceBackend(self.config, api, SKILLS)
        source = self.root / "input.json"
        write_json(source, self.payload)
        with (
            patch.object(backend.runner, "run", return_value={}) as run,
            patch.object(backend.runner, "collect"),
        ):
            backend._role(
                "discover",
                self.root / "output",
                {"request.json": source},
                "contract",
                self.root / "runtime",
            )
        agent = run.call_args.args[2]
        self.assertEqual(agent["env"]["TAVILY_API_KEY"], "${TAVILY_API_KEY}")
        self.assertFalse(run.call_args.kwargs["verify"])
        self.assertTrue((self.root / "runtime/role-task/environment/inputs/tavily.py").is_file())
        self.assertNotIn(
            "search-fixture", (self.root / "runtime/role-task/instruction.md").read_text()
        )

    def test_tavily_auth_header_and_usage_without_network(self):
        from io import BytesIO

        with patch(
            "sci_pipeline.source.tavily_tool.urlopen", return_value=BytesIO(b'{"results": []}')
        ) as open_url:
            self.assertEqual(call("search", {"query": "q"}, "fixture", 5), {"results": []})
        request = open_url.call_args.args[0]
        self.assertEqual(request.get_header("Authorization"), "Bearer fixture")
        self.assertTrue(json.loads(request.data)["include_usage"])
        self.assertNotIn("fixture", request.data.decode())

    def test_real_dd_failed_only_retry_and_downstream_seed_compatibility(self):
        from sci_pipeline.cli import prepare_requests
        from sci_pipeline.config import RunConfig

        inputs = self.root / "input.jsonl"
        inputs.write_text(self.request.model_dump_json() + "\n")
        config = self.root / "config.json"
        write_json(config, self.config.model_dump())
        arguments = [
            "--config",
            str(config),
            "--requests",
            str(inputs),
            "--output-root",
            str(self.root / "runs"),
            "--skills-root",
            str(SKILLS),
        ]
        original = MockSourceBackend.package

        def fail_one(worker, item, output):
            if item.item_id.endswith("c001"):
                raise ValueError("one package failed")
            return original(worker, item, output)

        with patch.dict(os.environ, {"DATA_DESIGNER_HOME": str(self.root / "dd-home")}):
            with patch.object(MockSourceBackend, "package", fail_one):
                self.assertEqual(main(arguments), 1)
            root = next((self.root / "runs").iterdir())
            self.assertEqual(len(read_rows(root / "seeds.jsonl")), 1)

            def retry_one(worker, item, output):
                self.assertTrue(item.item_id.endswith("c001"), "successful package reran")
                return original(worker, item, output)

            with (
                patch.object(
                    MockSourceBackend, "discover", side_effect=AssertionError("search reran")
                ),
                patch.object(MockSourceBackend, "package", retry_one),
            ):
                self.assertEqual(main(["--retry-failed", str(root)]), 0)
            self.assertEqual(len(read_rows(root / "seeds.jsonl")), 2)
            prepared = prepare_requests(
                root / "seeds.jsonl", self.root, self.root / "downstream", RunConfig()
            )
            self.assertEqual(len(prepared), 2)

    def test_real_dd_mock_resume_and_new_run(self):
        inputs = self.root / "input.jsonl"
        second = self.request.model_copy(update={"request_id": "two", "mode": "bench"})
        inputs.write_text(self.request.model_dump_json() + "\n" + second.model_dump_json() + "\n")
        config = self.root / "config.json"
        write_json(config, self.config.model_dump())
        arguments = [
            "--config",
            str(config),
            "--requests",
            str(inputs),
            "--output-root",
            str(self.root / "runs"),
            "--skills-root",
            str(SKILLS),
        ]
        with patch.dict(os.environ, {"DATA_DESIGNER_HOME": str(self.root / "dd-home")}):
            self.assertEqual(main(arguments), 0)
            root = next((self.root / "runs").iterdir())
            self.assertEqual(read_json(root / "summary.json")["package_count"], 4)
            with patch("sci_pipeline.source.pipeline.backend", side_effect=AssertionError("reran")):
                self.assertEqual(main(["--resume", str(root)]), 0)
            self.assertEqual(len(read_rows(root / "seeds.jsonl")), 4)
            self.assertEqual(main(arguments), 0)
            self.assertEqual(len(list((self.root / "runs").iterdir())), 2)


if __name__ == "__main__":
    unittest.main()
