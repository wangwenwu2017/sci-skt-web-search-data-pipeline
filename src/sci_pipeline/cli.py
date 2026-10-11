"""Explicit entry point; paths in seeds are relative to --source-root."""

import argparse
import fcntl
import json
import os
import platform
from collections import Counter
from datetime import datetime, timezone
from importlib.metadata import version
from pathlib import Path
from uuid import uuid4

from .artifacts import copy_tree, fingerprint, write_json
from .config import ApiSettings, NetworkSettings, RunConfig
from .contracts import TaskRequest


def prepare_requests(
    seeds: Path, source_root: Path, run_dir: Path, config: RunConfig
) -> list[TaskRequest]:
    requests = []
    manifest = []
    errors = []
    rows = [line for line in seeds.read_text().splitlines() if line.strip()]
    if not rows:
        raise ValueError("Seed file is empty")
    for index, line in enumerate(rows):
        try:
            row = json.loads(line)
            if (
                not isinstance(row, dict)
                or set(row) != {"package_uri"}
                or not isinstance(row["package_uri"], str)
            ):
                raise ValueError("Each seed must contain exactly one string field: package_uri")
            # This milestone supports local packages. URLs belong inside PACKAGE.md.
            if "://" in row["package_uri"]:
                raise ValueError(
                    "package_uri must be a local directory; place reference URLs in PACKAGE.md"
                )
            source = (source_root / row["package_uri"]).resolve()
            if not (source / "PACKAGE.md").is_file():
                raise ValueError(f"Input package missing PACKAGE.md: {source}")
            if run_dir.is_relative_to(source):
                raise ValueError("Input package cannot contain the run directory")
            snapshot = run_dir / "inputs" / f"package-{index:03d}"
            if snapshot.exists():
                if fingerprint(snapshot) != fingerprint(source):
                    raise ValueError("Existing input snapshot differs from source; start a new run")
            else:
                staging = run_dir / "inputs" / (".copy-" + uuid4().hex)
                copy_tree(source, staging)
                staging.rename(snapshot)
            manifest.append(
                {
                    "original_package_uri": str(source),
                    "snapshot_uri": str(snapshot),
                    "sha256": fingerprint(snapshot),
                }
            )
            for variant in range(config.tasks_per_package):
                requests.append(
                    TaskRequest(
                        task_id=f"p{index:03d}-task-{variant:03d}",
                        package_uri=str(snapshot),
                        variant=variant,
                    )
                )
        except (ValueError, OSError) as exc:
            errors.append({"seed_index": index, "seed": line, "error": str(exc)})
    write_json(run_dir / "input-errors.json", errors)
    write_json(run_dir / "input-manifest.json", manifest)
    return requests


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Source-grounded scientific task production pipeline"
    )
    parser.add_argument("--config", type=Path, default=Path("examples/pipeline/mock.json"))
    parser.add_argument("--seeds", type=Path, default=Path("examples/pipeline/seeds.jsonl"))
    parser.add_argument("--source-root", type=Path, default=Path.cwd())
    parser.add_argument("--output-root", type=Path, default=Path("runs/pipeline"))
    parser.add_argument("--env-file", type=Path, default=Path(".env"))
    parser.add_argument("--skills-root", type=Path, default=Path("skills"))
    parser.add_argument(
        "--doctor",
        action="store_true",
        help="Check local runtime prerequisites without calling a model",
    )
    parser.add_argument(
        "--build-role-image",
        action="store_true",
        help="Build the reusable role image; no model calls",
    )
    parser.add_argument(
        "--role-image-context", type=Path, default=Path("runtimes/harbor/role-image")
    )
    parser.add_argument(
        "--check-api-config",
        action="store_true",
        help="Check variable presence/URL syntax only; never call an API",
    )
    recovery = parser.add_mutually_exclusive_group()
    recovery.add_argument("--resume", type=Path, help="Continue an existing run directory")
    recovery.add_argument(
        "--retry-failed", type=Path, help="Rerun unsuccessful tasks in an existing run"
    )
    recovery.add_argument(
        "--retry-skills",
        type=Path,
        help="Retry failed/rejected optional skills without rerunning tasks",
    )
    recovery.add_argument("--cancel", type=Path, help="Request cooperative cancellation of a run")
    recovery.add_argument(
        "--cleanup", type=Path, help="Recover and clean orphaned executions without rerunning tasks"
    )
    args = parser.parse_args()
    if args.cancel:
        from .lifecycle import request_cancel

        request_cancel(args.cancel.resolve())
        print("Cancellation requested; running workers will stop and clean up.")
        return 0
    if args.cleanup:
        from .lifecycle import recover_executions

        root = args.cleanup.resolve()
        with (root / ".run.lock").open("a") as lock:
            try:
                fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError:
                parser.exit(2, "Run is active; use --cancel first.\n")
            print(json.dumps(recover_executions(root), ensure_ascii=False))
        return 0
    if args.check_api_config:
        try:
            ApiSettings.load(args.env_file)
        except ValueError as exc:
            parser.exit(2, f"{exc}\n")
        print("API configuration present (credentials/connectivity not verified).")
        return 0
    existing = args.resume or args.retry_failed or args.retry_skills
    config_path = existing / "run-config.json" if existing else args.config
    config = RunConfig.model_validate_json(config_path.read_text())
    if not existing:
        values = config.model_dump()
        for field, name in (
            ("api_retries", "SCI_PIPELINE_API_RETRIES"),
            ("api_retry_delay_sec", "SCI_PIPELINE_API_RETRY_DELAY_SEC"),
        ):
            if name in os.environ:
                values[field] = os.environ[name]
        config = RunConfig.model_validate(values)
    runtime_report = None
    if config.mode == "harbor" or args.doctor or args.build_role_image:
        from .preflight import build_role_image, check

        if args.build_role_image:
            build_role_image(config, NetworkSettings.load(args.env_file), args.role_image_context)
            return 0
        api = ApiSettings.load(args.env_file)
        runtime_report = check(config, api, args.skills_root)
        if args.doctor:
            print(json.dumps(runtime_report, ensure_ascii=False, indent=2))
            return 0
    # A process-scoped lock is released even after an exception or process termination.
    if existing:
        run_dir = existing.resolve()
    else:
        run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ-") + uuid4().hex[:8]
        run_dir = args.output_root.resolve() / run_id
        run_dir.mkdir(parents=True, exist_ok=False)
    with (run_dir / ".run.lock").open("a") as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            parser.exit(2, "This run is already being processed.\n")
        from .lifecycle import cancellation_signals, cancelled, recover_executions

        recover_executions(run_dir)
        (run_dir / "cancel.request").unlink(missing_ok=True)
        with cancellation_signals(run_dir):
            code = execute_run(args, config, run_dir, runtime_report)
            return 130 if cancelled(run_dir) else code


def execute_run(args, config: RunConfig, run_dir: Path, runtime_report: dict | None) -> int:
    started_at = datetime.now(timezone.utc)
    write_json(run_dir / "run-config.json", config.model_dump())
    if runtime_report:
        write_json(run_dir / "preflight.json", runtime_report)
    write_json(
        run_dir / "versions.json",
        {
            "python": platform.python_version(),
            **{name: version(name) for name in ("data-designer", "harbor", "pydantic")},
        },
    )
    try:
        registry = run_dir / "requests.json"
        if registry.exists():
            requests = [TaskRequest.model_validate(row) for row in json.loads(registry.read_text())]
            for item in json.loads((run_dir / "input-manifest.json").read_text()):
                if fingerprint(Path(item["snapshot_uri"])) != item["sha256"]:
                    raise ValueError(
                        "Input snapshot changed; start a new run for changed materials"
                    )
        else:
            preparation = run_dir / "preparation.json"
            if not preparation.exists():
                if args.resume or args.retry_failed or args.retry_skills:
                    raise ValueError("Legacy run has no recovery metadata; start a new run")
                write_json(
                    preparation,
                    {
                        "seeds": args.seeds.read_text(),
                        "source_root": str(args.source_root.resolve()),
                    },
                )
            inputs = json.loads(preparation.read_text())
            saved_seeds = run_dir / "original-seeds.jsonl"
            saved_seeds.write_text(inputs["seeds"])
            requests = prepare_requests(saved_seeds, Path(inputs["source_root"]), run_dir, config)
            write_json(registry, [request.model_dump() for request in requests])
        input_errors = json.loads((run_dir / "input-errors.json").read_text())
        active = run_dir / "active-submission.json"
        if args.retry_failed or args.retry_skills:
            if args.retry_skills and not config.generate_skills:
                raise ValueError("This run did not enable generate_skills")
            selected = []
            for request in requests:
                result_path = run_dir / "tasks" / request.task_id / "result.json"
                if not result_path.exists():
                    raise ValueError("Run is incomplete; use --resume before --retry-failed")
                saved_result = json.loads(result_path.read_text())
                if args.retry_skills:
                    if saved_result.get("skill_status") in {"failed", "rejected"}:
                        selected.append(request)
                elif saved_result["status"] not in {"accepted", "mock_completed"}:
                    selected.append(request)
            submission = "retry-" + uuid4().hex[:8]
            plan = {
                "name": submission,
                "retry": True,
                "skill_only": bool(args.retry_skills),
                "requests": [request.model_dump() for request in selected],
            }
            write_json(active, plan)
        elif active.exists():
            plan = json.loads(active.read_text())
            selected = [TaskRequest.model_validate(row) for row in plan["requests"]]
        else:
            selected = requests
            plan = {
                "name": "initial",
                "retry": False,
                "requests": [request.model_dump() for request in selected],
            }
            write_json(active, plan)
        submission_dir = run_dir / "submissions" / plan["name"]
        submission_dir.mkdir(parents=True, exist_ok=True)
        if plan["retry"]:
            # The persisted plan makes archival restartable if interrupted between renames.
            for request in selected:
                task_dir = run_dir / "tasks" / request.task_id
                original = task_dir
                if plan.get("skill_only"):
                    saved_result = json.loads((task_dir / "result.json").read_text())
                    original = (
                        task_dir / f"revision-{saved_result['revision']:03d}" / "skill-extraction"
                    )
                archive = run_dir / "history" / plan["name"] / original.relative_to(run_dir)
                prepared = submission_dir / (request.task_id + ".prepared.json")
                if prepared.exists():
                    continue
                if not archive.exists() and original.exists():
                    if config.mode == "harbor":
                        from .cleanup import cleanup_job

                        for job in original.glob("**/jobs/*"):
                            if job.is_dir() and not cleanup_job(job):
                                raise RuntimeError("Cannot confirm cleanup before retry")
                    archive.parent.mkdir(parents=True, exist_ok=True)
                    original.rename(archive)
                if plan.get("skill_only"):
                    saved_result.update(
                        skill_status="pending",
                        skill_package_uri=None,
                        skill_report_uri=None,
                        skill_error=None,
                    )
                    write_json(task_dir / "result.json", saved_result)
                write_json(prepared, {"task_id": request.task_id})
        os.environ.setdefault("DATA_DESIGNER_HOME", str(run_dir / "designer-home"))
        from .designer import create_dataset

        if selected:
            create_dataset(
                run_dir,
                selected,
                config,
                args.env_file.resolve(),
                args.skills_root.resolve(),
                submission_dir=submission_dir,
            )
        results = [
            json.loads((run_dir / "tasks" / request.task_id / "result.json").read_text())
            for request in requests
        ]
        if config.mode == "harbor":
            from .usage import summarize_usage

            write_json(run_dir / "usage.json", summarize_usage(run_dir))
        (run_dir / "results.jsonl").write_text(
            "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in results)
        )
        counts = dict(Counter(row["status"] for row in results))
        write_json(
            run_dir / "summary.json",
            {
                "execution_mode": config.mode,
                "validated": bool(results)
                and not input_errors
                and all(row["validated"] for row in results),
                "input_error_count": len(input_errors),
                "counts": counts,
                "skill_counts": dict(
                    Counter(row.get("skill_status", "disabled") for row in results)
                ),
                "task_count": len(results),
            },
        )
    except Exception as exc:
        write_json(
            run_dir / "run-error.json", {"error_type": type(exc).__name__, "error": str(exc)}
        )
        raise
    finally:
        from .timing import summarize_timing

        timing = summarize_timing(run_dir, started_at, datetime.now(timezone.utc))
        write_json(run_dir / "timing.json", timing)
        write_json(
            run_dir / "invocations" / (started_at.strftime("%Y%m%dT%H%M%S%fZ") + ".json"), timing
        )
    print(
        f"Run: {run_dir}\nMode: {config.mode}\nResults: {counts}\nInvalid inputs: {len(input_errors)}"
    )
    if config.generate_skills:
        print(f"Skills: {dict(Counter(row.get('skill_status', 'disabled') for row in results))}")
    for row in results:
        if row.get("skill_error"):
            print(f"{row['task_id']} skill: {row['skill_error']}")
        if row.get("error"):
            print(f"{row['task_id']}: {row['error']}")
    return (
        0
        if results
        and not input_errors
        and all(row["status"] in {"mock_completed", "accepted"} for row in results)
        else 1
    )
