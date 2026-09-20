"""Wall-clock timings from native Harbor trial records, including failed attempts."""

from datetime import datetime
from pathlib import Path

from .artifacts import read_json


def duration(timing: dict | None) -> float | None:
    if not timing or not timing.get("started_at") or not timing.get("finished_at"):
        return None
    start = datetime.fromisoformat(timing["started_at"])
    end = datetime.fromisoformat(timing["finished_at"])
    return round((end - start).total_seconds(), 3)


def summarize_timing(run_dir: Path, started_at: datetime, finished_at: datetime) -> dict:
    stages = []
    for role in ("author", "builder", "reviewer", "skill-extractor", "skill-reviewer"):
        folder = "skill-extraction/" if role.startswith("skill-") else ""
        for pattern in (
            f"tasks/*/revision-*/{folder}{role}-runtime/execution/jobs/*/*/result.json",
            f"tasks/*/revision-*/{folder}{role}-runtime/attempt-*/execution/jobs/*/*/result.json",
        ):
            for path in sorted(
                [
                    path
                    for base in (run_dir, *sorted((run_dir / "history").glob("*")))
                    for path in base.glob(pattern)
                ]
            ):
                result = read_json(path)
                stages.append(
                    {
                        "stage": role,
                        "trial_path": str(path),
                        "elapsed_sec": duration(result),
                        "environment_setup_sec": duration(result.get("environment_setup")),
                        "agent_execution_sec": duration(result.get("agent_execution")),
                        "exception_type": (result.get("exception_info") or {}).get(
                            "exception_type"
                        ),
                    }
                )
    for path in sorted(
        [
            path
            for base in (run_dir, *sorted((run_dir / "history").glob("*")))
            for path in base.glob("tasks/*/revision-*/builder/checks/*/jobs/*/*/result.json")
        ]
    ):
        result = read_json(path)
        stages.append(
            {
                "stage": path.parents[3].name,
                "trial_path": str(path),
                "elapsed_sec": duration(result),
                "environment_setup_sec": duration(result.get("environment_setup")),
                "agent_execution_sec": duration(result.get("agent_execution")),
                "verifier_sec": duration(result.get("verifier")),
                "exception_type": (result.get("exception_info") or {}).get("exception_type"),
            }
        )
    totals = {}
    for stage in stages:
        if stage["elapsed_sec"] is not None:
            name = stage["stage"]
            totals[name] = round(totals.get(name, 0) + stage["elapsed_sec"], 3)
    return {
        "started_at": started_at.isoformat(),
        "finished_at": finished_at.isoformat(),
        "elapsed_sec": round((finished_at - started_at).total_seconds(), 3),
        "stage_total_sec": totals,
        "trials": stages,
        "note": "Elapsed is wall-clock time. Stage totals include retries; concurrent stages may overlap. No synthetic zero for missing native timing.",
    }
