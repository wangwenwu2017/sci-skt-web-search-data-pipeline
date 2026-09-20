"""Offline planning calculator. No API calls, cluster access, or third-party packages."""
import argparse
import json
import math
from pathlib import Path


def nonnegative(value, name):
    if not isinstance(value, (int, float)) or isinstance(value, bool) or not math.isfinite(value) or value < 0:
        raise ValueError(f"{name} must be a finite nonnegative number")
    return value


def estimate(config, candidates=None, solver=None):
    n = nonnegative(config["candidates"] if candidates is None else candidates, "candidates")
    q = nonnegative(config["qualification_rate"], "qualification_rate")
    if q > 1:
        raise ValueError("qualification_rate must be <= 1")
    qualified = n * q
    calibration = nonnegative(config["calibration_attempts"], "calibration_attempts")
    production = nonnegative(config["production_attempts"], "production_attempts")
    attempts = qualified * (calibration + production) + nonnegative(config.get("extra_attempts", 0), "extra_attempts")
    counts = dict(author=n, review=n, repair=n * nonnegative(config["repair_calls_per_candidate"], "repair_calls_per_candidate"),
                  qualification=n, solver=attempts, verifier=attempts)
    stages = {}
    for name, count in counts.items():
        stage = config["stages"][name]
        model = solver if name == "solver" and solver else stage["model"]
        input_tokens = nonnegative(stage["input_tokens"], f"{name}.input_tokens")
        output_tokens = nonnegative(stage["output_tokens"], f"{name}.output_tokens")
        api = 0.0
        if model:
            price = config["models"][model]
            api = count * (input_tokens * nonnegative(price["input_per_million"], "input_price") +
                           output_tokens * nonnegative(price["output_per_million"], "output_price")) / 1e6
        hours = count * nonnegative(stage["minutes"], f"{name}.minutes") / 60
        stages[name] = {"expected_calls": count, "model": model, "api_usd": api,
                        "vcpu_hours": hours * nonnegative(stage["vcpu"], f"{name}.vcpu"),
                        "gib_hours": hours * nonnegative(stage["memory_gib"], f"{name}.memory_gib")}
    api_total = sum(s["api_usd"] for s in stages.values())
    cpu = sum(s["vcpu_hours"] for s in stages.values())
    memory = sum(s["gib_hours"] for s in stages.values())
    infra = {}
    for name, usage in [("vcpu_hour", cpu), ("gib_hour", memory), ("storage_gb_month", config["storage_gb_months"])]:
        price = config["infrastructure_prices"].get(name)
        infra[name] = None if price is None else nonnegative(price, name) * nonnegative(usage, name + "_usage")
    complete = all(x is not None for x in infra.values())
    total = api_total + sum(infra.values()) if complete else None
    margin = 1 + nonnegative(config["contingency"], "contingency")
    concurrency = nonnegative(config["solver_concurrency"], "solver_concurrency")
    utilization = nonnegative(config["utilization"], "utilization")
    minutes = config["stages"]["solver"]["minutes"]
    if not 0 < utilization <= 1 or concurrency <= 0 or minutes <= 0:
        raise ValueError("positive concurrency, duration and utilization <= 1 required")
    per_hour = concurrency * 60 / minutes * utilization
    fx = config.get("usd_to_cny")
    if fx is not None:
        nonnegative(fx, "usd_to_cny")
        if fx == 0:
            raise ValueError("usd_to_cny must be positive")
    return {
        "currency": "USD", "status": "planning_estimate_not_measured",
        "candidates": n, "expected_qualified_tasks": qualified, "expected_rollouts": attempts,
        "stages": stages, "api_usd": api_total, "api_with_contingency_usd": api_total * margin,
        "api_per_qualified_task_usd": api_total / qualified if qualified else None,
        "vcpu_hours": cpu, "gib_hours": memory,
        "infrastructure_costs_usd": infra,
        "modeled_total_usd": total,
        "modeled_total_cny": total * fx if total is not None and fx is not None else None,
        "solver_only_wall_hours": attempts / per_hour,
        "required_solver_input_tpm": per_hour * config["stages"]["solver"]["input_tokens"] / 60,
        "required_solver_output_tpm": per_hour * config["stages"]["solver"]["output_tokens"] / 60,
        "excluded": ["staff", "GPU", "always-on services", "idle reserved nodes", "network", "extra cold builds", "cache/long-context/tier pricing adjustments"],
        "warning": "Null costs are unpriced, not free. Qualified counts are expectations. Add rejected-task calibration and re-reviews explicitly. CPU pricing uses reserved resource-hours."
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("config", type=Path)
    parser.add_argument("--candidates", type=int)
    parser.add_argument("--solver", help="Model price profile key from configuration")
    args = parser.parse_args()
    try:
        result = estimate(json.loads(args.config.read_text()), args.candidates, args.solver)
    except (ValueError, KeyError) as exc:
        parser.error(str(exc))
    print(json.dumps(result, ensure_ascii=False, indent=2))
