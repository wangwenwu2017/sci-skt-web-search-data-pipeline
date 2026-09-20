"""Two ordinary Data Designer builds; durable business results make dispatch idempotent."""

import json
from pathlib import Path
from uuid import uuid4

import data_designer.config as dd
from data_designer.config.run_config import RunConfig as DesignerRunConfig
from data_designer.interface import DataDesigner, ResumeMode
from pydantic import BaseModel

from sci_pipeline.artifacts import read_json, write_json
from sci_pipeline.lifecycle import cancelled

from .artifacts import jsonl
from .config import SourceRunConfig
from .pipeline import recovered_result, row_directory, run_row


class GeneratorParams(BaseModel):
    run_dir: str
    stage: str
    config: SourceRunConfig
    env_file: str
    skills_root: str


@dd.custom_column_generator(required_columns=["row_id", "payload"])
def generate_source(row: dict, generator_params: GeneratorParams) -> dict:
    p = generator_params
    result = run_row(
        Path(p.run_dir),
        p.stage,
        json.loads(row["payload"]),
        p.config,
        Path(p.env_file),
        Path(p.skills_root),
    )
    return {**row, "source_result": json.dumps(result, ensure_ascii=False)}


def run_batch(root, stage, rows, config, env_file, skills_root):
    if not rows or cancelled(root):
        return
    pending = []
    for payload in rows:
        directory = row_directory(root, stage, payload)
        try:
            saved = recovered_result(directory, stage, payload)
        except (ValueError, FileNotFoundError):
            # Record corruption as a failed row. Explicit retry archives/rebuilds it.
            run_row(root, stage, payload, config, env_file, skills_root)
            continue
        if saved is None:
            pending.append(payload)
    if not pending:
        return
    parent = root / "stages" / stage
    active = parent / "active.json"
    if active.exists():
        submission = read_json(active)
    else:
        submission = {"id": uuid4().hex, "rows": pending}
        write_json(active, submission)
    directory = parent / submission["id"]
    seeds = directory / "seeds.jsonl"
    expected = []
    seed_rows = []
    for payload in submission["rows"]:
        identity = payload.get("item_id", payload.get("request_id"))
        expected.append(identity)
        seed_rows.append({"row_id": identity, "payload": json.dumps(payload, ensure_ascii=False)})
    jsonl(seeds, seed_rows)
    builder = dd.DataDesignerConfigBuilder()
    builder.with_seed_dataset(dd.LocalFileSeedSource(path=str(seeds)))
    builder.add_column(
        dd.CustomColumnConfig(
            name="source_result",
            generator_function=generate_source,
            generator_params=GeneratorParams(
                run_dir=str(root),
                stage=stage,
                config=config,
                env_file=str(env_file),
                skills_root=str(skills_root),
            ),
        )
    )
    concurrency = config.execution.max_concurrency
    designer = DataDesigner()
    designer.set_run_config(
        DesignerRunConfig(
            buffer_size=1,
            max_concurrent_row_groups=concurrency,
            display_tui=False,
            otel_metrics_port=None,
            non_inference_max_parallel_workers=concurrency,
            max_in_flight_tasks=concurrency,
        )
    )
    generated = designer.create(
        builder,
        num_records=len(seed_rows),
        dataset_name="dataset",
        artifact_path=directory / "designer",
        resume=ResumeMode.ALWAYS if (directory / "designer/dataset").exists() else ResumeMode.NEVER,
    )
    actual = generated.load_dataset().to_dict(orient="records")
    if len(actual) != len(expected) or {r["row_id"] for r in actual} != set(expected):
        raise RuntimeError("Data Designer did not return exactly one result per source row")
    # A cancelled DD row may be committed without a business result. New submission on resume.
    active.unlink()
    if not cancelled(root):
        missing = [p for p in rows if not (row_directory(root, stage, p) / "result.json").exists()]
        if missing:
            # This also handles an interrupted older submission followed by appended rows.
            run_batch(root, stage, missing, config, env_file, skills_root)
