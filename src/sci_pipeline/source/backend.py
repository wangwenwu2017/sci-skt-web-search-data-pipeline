"""One curator role, with deterministic mock and isolated Harbor implementations."""

import json
import shutil
from pathlib import Path

from sci_pipeline.artifacts import copy_tree, read_json, write_json
from sci_pipeline.harbor_backend import HarborBackend
from sci_pipeline.harbor_runner import HarborRunner

from .artifacts import validate_package
from .config import SourceApiSettings, SourceRunConfig
from .contracts import Candidate, Discovery, Source


class MockSourceBackend:
    def discover(self, request, output):
        output.mkdir(parents=True)
        candidates = []
        for index, name in enumerate(("A", "B", "A")[: request.max_candidates]):
            candidates.append(
                Candidate(
                    candidate_id=f"c{index}",
                    title=f"Mock source {name}",
                    relevance="Deterministic fixture, not a real scientific search",
                    scope=f"Mock material {name}",
                    sources=[Source(url=f"https://example.org/{name}")],
                )
            )
        result = Discovery(
            status="completed", candidates=candidates, report="Mock; no network used."
        )
        write_json(output / "candidates.json", result.model_dump())
        (output / "report.md").write_text(result.report)

    def package(self, item, output):
        package = output / "package"
        package.mkdir(parents=True)
        (package / "PACKAGE.md").write_text(
            "# Mock source package\n\nThis is a fixture, not verified scientific material.\n\n"
            + item.candidate.scope
            + "\n\n"
            + "\n".join(source.url for source in item.candidate.sources)
            + "\n"
        )


class HarborSourceBackend(HarborBackend):
    def __init__(self, config: SourceRunConfig, api: SourceApiSettings, skills_root: Path):
        super().__init__(config.execution, api, skills_root)
        self.source_config = config
        self.runner = HarborRunner(config.execution, api)

    def _role(self, role, output, inputs, instructions, runtime):
        envelope = runtime / "role-task"
        environment = envelope / "environment"
        environment.mkdir(parents=True)
        for name, source in inputs.items():
            destination = environment / "inputs" / name
            destination.parent.mkdir(parents=True, exist_ok=True)
            if source.is_dir():
                copy_tree(source, destination)
            else:
                shutil.copy2(source, destination)
        shutil.copy2(Path(__file__).with_name("tavily_tool.py"), environment / "inputs/tavily.py")
        (environment / "Dockerfile").write_text(
            f"FROM {self.config.role_image}\nCOPY inputs /inputs\n"
            "RUN chmod -R a-w /inputs && mkdir -p /workspace/output && chown -R node:node /workspace\n"
            "WORKDIR /workspace\n"
        )
        (envelope / "task.toml").write_text(
            'schema_version = "1.4"\n[agent]\nuser = "node"\n'
            f"timeout_sec = {self.config.role_timeout_sec}\n"
            f"[environment]\ncpus = {self.config.environment_cpus}\n"
            f"memory_mb = {self.config.environment_memory_mb}\n"
        )
        skill = (self.skills_root / "source-curator/SKILL.md").read_text()
        (envelope / "instruction.md").write_text(skill + "\n\n# 本次交付合同\n" + instructions)
        agent = self.runner.codex()
        agent["env"].update(
            TAVILY_API_KEY="${TAVILY_API_KEY}",
            SCI_SEARCH_TIMEOUT=str(self.source_config.search_timeout_sec),
        )
        result = self.runner.run(
            envelope,
            runtime / "execution",
            agent,
            verify=False,
            timeout=self.config.role_timeout_sec,
            artifacts=True,
            credentials=True,
        )
        self.runner.collect(result, output)

    def discover(self, request, output):
        request_path = output.parent / "request.json"
        write_json(request_path, request.model_dump())

        def validate(path):
            result = Discovery.model_validate(read_json(path / "candidates.json"))
            if len(result.candidates) > request.max_candidates:
                raise ValueError("Too many candidates")
            if not (path / "report.md").read_text().strip():
                raise ValueError("Missing discovery report")
            # A tool outage is not evidence that no sources exist.
            events = [read_json(p) for p in (path / "tool-events").glob("*.json")]
            if result.status != "failed" and not any(
                e.get("status") == "completed" for e in events
            ):
                raise ValueError("Successful discovery requires a successful Tavily call")

        self._deliver(
            "discover",
            output,
            {"request.json": request_path},
            "模式 discover。读取 /inputs/request.json。输出 /workspace/output/candidates.json，"
            "必须符合以下 JSON schema；另写 report.md。资料不足可以少于 max_candidates。\n"
            + json.dumps(Discovery.model_json_schema(), ensure_ascii=False),
            validate,
        )

    def package(self, item, output):
        item_path = output.parent / "item.json"
        write_json(item_path, item.model_dump())
        self._deliver(
            "package",
            output,
            {"item.json": item_path},
            "模式 package。读取 /inputs/item.json（包括 originals 中的全部证据）。"
            "交付 /workspace/output/package/PACKAGE.md 和可选 materials/。"
            "PACKAGE.md 必须列出所有输入来源 URL，说明版本、材料关系、用途、缺失和读取情况。",
            lambda path: validate_package(path / "package", item),
        )
