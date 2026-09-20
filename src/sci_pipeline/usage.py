"""Report Harbor's native model usage without inventing prices for custom endpoints."""

from pathlib import Path

from .artifacts import read_json


def summarize_usage(run_dir: Path) -> dict:
    jobs = []
    for role in ("author", "builder", "reviewer", "skill-extractor", "skill-reviewer"):
        folder = "skill-extraction/" if role.startswith("skill-") else ""
        pattern = f"tasks/*/revision-*/{folder}{role}-runtime/execution/jobs/*/result.json"
        attempt_pattern = (
            f"tasks/*/revision-*/{folder}{role}-runtime/attempt-*/execution/jobs/*/result.json"
        )
        paths = [
            path
            for base in (run_dir, *sorted((run_dir / "history").glob("*")))
            for glob in (pattern, attempt_pattern)
            for path in base.glob(glob)
        ]
        for path in sorted(paths):
            stats = read_json(path).get("stats", {})
            jobs.append(
                {
                    "role": role,
                    "result_path": str(path),
                    **{
                        key: stats.get(key)
                        for key in (
                            "n_input_tokens",
                            "n_cache_tokens",
                            "n_output_tokens",
                            "cost_usd",
                        )
                    },
                }
            )

    def total(key: str):
        values = [job[key] for job in jobs]
        return sum(values) if values and all(value is not None for value in values) else None

    return {
        "jobs": jobs,
        "n_input_tokens": total("n_input_tokens"),
        "n_cache_tokens": total("n_cache_tokens"),
        "n_output_tokens": total("n_output_tokens"),
        "cost_usd": total("cost_usd"),
        "note": "Harbor-reported usage; null means unknown. Custom API invoice pricing is not inferred.",
    }
