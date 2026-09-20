"""Independent source CLI; successful seeds feed sci-pipeline unchanged."""

import argparse
import fcntl
import json
import os
import time
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from sci_pipeline.artifacts import read_json, write_json
from sci_pipeline.lifecycle import (
    cancellation_signals,
    cancelled,
    recover_executions,
    request_cancel,
)

from .artifacts import digest
from .config import SourceApiSettings, SourceRunConfig
from .pipeline import execute, prepare, read_rows, retry_failed


def usage(root):
    jobs = []
    patterns = (
        "requests/*/discovery/attempts/*/discover-runtime/attempt-*/execution/jobs/*/result.json",
        "items/*/attempts/*/package-runtime/attempt-*/execution/jobs/*/result.json",
    )
    for pattern in patterns:
        for path in sorted(root.glob(pattern)):
            jobs.append({"path": str(path), **read_json(path).get("stats", {})})
    tool_events = []
    # Only role artifacts, not collected copies or retry feedback input copies.
    for path in root.glob("**/execution/jobs/*/*/artifacts/output/tool-events/*.json"):
        tool_events.append({"path": str(path), **read_json(path)})

    def total(key):
        values = [job.get(key) for job in jobs]
        return sum(values) if values and all(v is not None for v in values) else None

    credits = [
        event.get("usage", {}).get("credits")
        for event in tool_events
        if isinstance(event.get("usage"), dict)
    ]
    return {
        "jobs": jobs,
        "tool_events": tool_events,
        **{
            key: total(key)
            for key in ("n_input_tokens", "n_cache_tokens", "n_output_tokens", "cost_usd")
        },
        "tool_call_count": len(tool_events),
        "reported_tavily_credits": sum(credits)
        if credits and all(v is not None for v in credits)
        else None,
        "note": "Reported values only. Missing usage is unknown; no API invoice prices inferred.",
    }


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Discover scientific sources and produce source packages"
    )
    parser.add_argument("--config", type=Path, default=Path("examples/source/mock.json"))
    parser.add_argument("--requests", type=Path, default=Path("examples/source/requests.jsonl"))
    parser.add_argument("--output-root", type=Path, default=Path("runs/source"))
    parser.add_argument("--env-file", type=Path, default=Path(".env"))
    parser.add_argument("--skills-root", type=Path, default=Path("skills"))
    parser.add_argument("--check-api-config", action="store_true")
    parser.add_argument("--doctor", action="store_true")
    action = parser.add_mutually_exclusive_group()
    for name in ("resume", "retry-failed", "cancel", "cleanup"):
        action.add_argument("--" + name, type=Path)
    args = parser.parse_args(argv)
    if args.check_api_config:
        SourceApiSettings.load(args.env_file)
        print("Model and Tavily settings present; no network requests made.")
        return 0
    if args.cancel:
        request_cancel(args.cancel.resolve())
        print("Cancellation requested; running workers will stop and clean up.")
        return 0
    existing = args.resume or args.retry_failed or args.cleanup
    if existing:
        root = existing.resolve()
        if not (root / "source-run.json").is_file():
            raise ValueError("Not a recoverable source run")
    else:
        root = args.output_root.resolve() / (
            datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ-") + uuid4().hex[:8]
        )
        root.mkdir(parents=True)
    with (root / ".run.lock").open("a") as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise ValueError("Run is active; use --cancel first") from None
        recover_executions(root)
        if args.cleanup:
            print("Registered orphan executions cleaned.")
            return 0
        if existing:
            meta = read_json(root / "source-run.json")
            if meta.get("schema_version") != 1:
                raise ValueError("Unsupported source run schema")
            config = SourceRunConfig.model_validate(read_json(root / "run-config.json"))
            skills = Path(meta["skills_root"])
            if digest(config.model_dump()) != meta["config_sha256"]:
                raise ValueError("Run config changed; start a new run")
            if digest((skills / "source-curator/SKILL.md").read_text()) != meta["skill_sha256"]:
                raise ValueError("Curator skill changed; start a new run")
        else:
            config = SourceRunConfig.model_validate_json(args.config.read_text())
            skills = args.skills_root.resolve()
            meta = {
                "original_requests": args.requests.read_text(),
                "config_sha256": digest(config.model_dump()),
                "skills_root": str(skills),
                "skill_sha256": digest((skills / "source-curator/SKILL.md").read_text()),
                "schema_version": 1,
            }
            write_json(root / "run-config.json", config.model_dump())
            write_json(root / "source-run.json", meta)
        if config.execution.mode == "harbor" or args.doctor:
            from sci_pipeline.preflight import check

            api = SourceApiSettings.load(args.env_file)
            report = check(config.execution, api, skills, skill_names=["source-curator"])
            write_json(root / "preflight.json", report)
            if args.doctor:
                print(json.dumps(report, ensure_ascii=False, indent=2))
                return 0
        requests = prepare(root, meta["original_requests"])
        if args.retry_failed or (root / "retry-plan.json").exists():
            plan = (
                read_rows(root / "package-plan.jsonl")
                if (root / "package-plan.jsonl").exists()
                else []
            )
            retry_failed(root, requests, plan)
        (root / "cancel.request").unlink(missing_ok=True)
        os.environ.setdefault("DATA_DESIGNER_HOME", str(root / "designer-home"))
        from .designer import run_batch

        started = time.monotonic()
        invocation = uuid4().hex
        try:
            with cancellation_signals(root):
                summary = execute(root, config, args.env_file.resolve(), skills, run_batch)
        except Exception as exc:
            write_json(
                root / "run-error.json", {"error_type": type(exc).__name__, "error": str(exc)}
            )
            raise
        finally:
            write_json(
                root / "invocations" / (invocation + ".json"),
                {
                    "elapsed_sec": time.monotonic() - started,
                },
            )
            timings = [read_json(p)["elapsed_sec"] for p in (root / "invocations").glob("*.json")]
            stage_times = {}
            for stage, pattern in (
                ("discover", "requests/*/discovery/attempts/*/timing.json"),
                ("package", "items/*/attempts/*/timing.json"),
            ):
                stage_times[stage] = sum(read_json(p)["elapsed_sec"] for p in root.glob(pattern))
            write_json(
                root / "timing.json",
                {
                    "invocation_elapsed_sec": time.monotonic() - started,
                    "total_active_wall_sec": sum(timings),
                    "role_elapsed_sec": stage_times,
                    "note": "Role durations sum across concurrent rows; wall time excludes pauses between invocations.",
                },
            )
            write_json(root / "usage.json", usage(root))
        print(f"Run: {root}\nStatus: {summary['status']}\nPackages: {summary['package_count']}")
        print(f"Seeds: {root / 'seeds.jsonl'}")
        return 130 if cancelled(root) else (0 if summary["status"] == "completed" else 1)


if __name__ == "__main__":
    raise SystemExit(main())
