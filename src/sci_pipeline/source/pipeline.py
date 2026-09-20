"""Row checkpoints, immutable packaging plans and atomic publication."""

import fcntl
import json
import time
from pathlib import Path
from uuid import uuid4

from sci_pipeline.artifacts import copy_tree, read_json, write_json
from sci_pipeline.harbor_runner import HarborExecutionError
from sci_pipeline.lifecycle import cancelled

from .artifacts import atomic_text, digest, jsonl, validate_package
from .config import SourceApiSettings
from .contracts import Discovery, PackageItem, SourceRequest, expand


def row_directory(root, stage, row):
    if stage == "discover":
        return root / "requests" / row["request_id"] / "discovery"
    return root / "items" / row["item_id"]


def backend(config, env_file, skills_root):
    from .backend import HarborSourceBackend, MockSourceBackend

    if config.execution.mode == "mock":
        return MockSourceBackend()
    return HarborSourceBackend(config, SourceApiSettings.load(env_file), skills_root)


def recovered_result(directory, stage, payload):
    """Validate durable success before reuse, including the publish/result crash window."""
    result_path = directory / "result.json"
    delivery = directory / "delivery"
    signature = digest(payload)
    if result_path.exists():
        result = read_json(result_path)
        if result["input_sha256"] != signature:
            raise ValueError("Row input changed; start a new run")
        if result["status"] == "failed":
            return result
    elif not delivery.exists():
        return None
    manifest = read_json(delivery / "manifest.json")
    if manifest["input_sha256"] != signature:
        raise ValueError("Delivery does not match frozen input")
    if stage == "discover":
        discovery = Discovery.model_validate(read_json(delivery / "candidates.json"))
        if digest(discovery.model_dump()) != manifest["content_sha256"]:
            raise ValueError("Saved discovery content changed")
        if not (delivery / "report.md").read_text().strip():
            raise ValueError("Missing saved discovery report")
        result = {
            "status": discovery.status,
            "request_id": payload["request_id"],
            "error": discovery.report if discovery.status == "failed" else None,
        }
    else:
        item = PackageItem.model_validate(payload)
        hashed = validate_package(delivery / "package", item)
        if hashed != manifest["content_sha256"]:
            raise ValueError("Published package content changed; use --retry-failed to rebuild")
        result = {
            "status": "completed",
            "item_id": item.item_id,
            "request_id": item.request.request_id,
            "candidate_ids": [candidate.candidate_id for candidate in item.originals],
            "package_uri": str((delivery / "package").resolve()),
        }
    result.update(input_sha256=signature, execution_mode=manifest["execution_mode"])
    write_json(result_path, result)
    return result


def run_row(root, stage, payload, config, env_file, skills_root, implementation=None):
    directory = row_directory(root, stage, payload)
    directory.mkdir(parents=True, exist_ok=True)
    with (directory / ".row.lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        try:
            saved = recovered_result(directory, stage, payload)
            if saved:
                return saved
            if cancelled(root):
                return {"status": "cancelled"}
            worker = implementation or backend(config, env_file, skills_root)
            attempt = directory / "attempts" / uuid4().hex
            attempt.mkdir(parents=True)
            started = time.monotonic()
            try:
                output = attempt / "output"
                if stage == "discover":
                    request = SourceRequest.model_validate(payload)
                    worker.discover(request, output)
                    discovery = Discovery.model_validate(read_json(output / "candidates.json"))
                    expand(request, discovery)  # validates candidate count, even in mock backends
                    if not (output / "report.md").read_text().strip():
                        raise ValueError("Missing discovery report")
                    content_sha = digest(discovery.model_dump())
                    staging = attempt / "delivery"
                    staging.mkdir()
                    write_json(staging / "candidates.json", discovery.model_dump())
                    atomic_text(staging / "report.md", (output / "report.md").read_text())
                else:
                    item = PackageItem.model_validate(payload)
                    worker.package(item, output)
                    content_sha = validate_package(output / "package", item)
                    staging = attempt / "delivery"
                    staging.mkdir()
                    copy_tree(output / "package", staging / "package")
                write_json(
                    staging / "manifest.json",
                    {
                        "input_sha256": digest(payload),
                        "content_sha256": content_sha,
                        "execution_mode": config.execution.mode,
                    },
                )
                staging.rename(directory / "delivery")
                return recovered_result(directory, stage, payload)
            finally:
                write_json(attempt / "timing.json", {"elapsed_sec": time.monotonic() - started})
        except (ValueError, FileNotFoundError, HarborExecutionError) as exc:
            if cancelled(root):
                return {"status": "cancelled"}
            result = {
                "status": "failed",
                "input_sha256": digest(payload),
                "error_type": type(exc).__name__,
                "error": str(exc),
                "execution_mode": config.execution.mode,
            }
            write_json(directory / "result.json", result)
            return result


def prepare(root: Path, original: str):
    requests, errors, seen = [], [], set()
    for number, line in enumerate(original.splitlines(), start=1):
        if not line.strip():
            continue
        try:
            request = SourceRequest.model_validate_json(line)
            if request.request_id in seen:
                raise ValueError("Duplicate request_id")
            seen.add(request.request_id)
            requests.append(request.model_dump())
        except ValueError as exc:
            errors.append({"line": number, "error": str(exc)})
    jsonl(root / "requests.jsonl", requests)
    write_json(root / "input-errors.json", errors)
    return requests


def read_rows(path):
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def build_plan(root, requests):
    path = root / "package-plan.jsonl"
    plan = read_rows(path) if path.exists() else []
    by_request = {row["request_id"]: row for row in requests}
    identities = set()
    for payload in plan:
        item = PackageItem.model_validate(payload)
        if item.item_id in identities:
            raise ValueError("Duplicate item in saved package plan")
        identities.add(item.item_id)
        if item.request.model_dump() != by_request.get(item.request.request_id):
            raise ValueError("Saved package plan differs from frozen requests")
    for payload in requests:
        directory = row_directory(root, "discover", payload)
        result = (
            read_json(directory / "result.json") if (directory / "result.json").exists() else {}
        )
        if result.get("status") == "completed":
            request = SourceRequest.model_validate(payload)
            discovered = Discovery.model_validate(read_json(directory / "delivery/candidates.json"))
            expected = [item.model_dump() for item in expand(request, discovered)]
            saved = [row for row in plan if row["request"]["request_id"] == request.request_id]
            if saved and saved != expected:
                raise ValueError("Saved plan differs from discovery; start a new run")
            if not saved:
                plan.extend(expected)
    jsonl(path, plan)
    return plan


def retry_failed(root, requests, plan):
    """Persist retry selection before moving any failed output; restart the same selection."""
    marker = root / "retry-plan.json"
    if marker.exists():
        retry = read_json(marker)
    else:
        selected = []
        for stage, rows in (("discover", requests), ("package", plan)):
            for payload in rows:
                directory = row_directory(root, stage, payload)
                path = directory / "result.json"
                if not path.exists():
                    raise ValueError("Run is incomplete; use --resume before --retry-failed")
                if read_json(path)["status"] == "failed":
                    selected.append(str(directory.relative_to(root)))
        retry = {"id": uuid4().hex, "directories": selected}
        write_json(marker, retry)
    for relative in retry["directories"]:
        directory = root / relative
        history = directory / "history" / retry["id"]
        history.mkdir(parents=True, exist_ok=True)
        if (history / "prepared.json").exists():
            continue
        for name in ("result.json", "delivery"):
            source = directory / name
            destination = history / name
            if source.exists() and not destination.exists():
                source.rename(destination)
        write_json(history / "prepared.json", {"prepared": True})
    marker.unlink()


def summarize(root, requests, plan, config):
    results, discovery_results = [], []
    for stage, rows, destination in (
        ("discover", requests, discovery_results),
        ("package", plan, results),
    ):
        for payload in rows:
            path = row_directory(root, stage, payload) / "result.json"
            result = read_json(path) if path.exists() else {"status": "pending"}
            result = {"row_id": payload.get("item_id", payload.get("request_id")), **result}
            destination.append(result)
    seeds = [{"package_uri": r["package_uri"]} for r in results if r["status"] == "completed"]
    jsonl(root / "results.jsonl", results)
    jsonl(root / "discovery-results.jsonl", discovery_results)
    jsonl(root / "seeds.jsonl", seeds)
    errors = json.loads((root / "input-errors.json").read_text())
    unfinished = any(r["status"] in {"failed", "pending"} for r in results + discovery_results)
    status = "partial" if errors or unfinished else "completed"
    if not requests or (unfinished and not seeds):
        status = "failed"
    if cancelled(root):
        status = "cancelled"
    summary = {
        "status": status,
        "execution_mode": config.execution.mode,
        "request_count": len(requests),
        "package_count": len(seeds),
        "input_error_count": len(errors),
        "no_results_count": sum(r["status"] == "no_results" for r in discovery_results),
        "validated": False,  # These are sources, not scientifically verified tasks.
    }
    write_json(root / "summary.json", summary)
    return summary


def execute(root, config, env_file, skills_root, batch):
    requests = read_rows(root / "requests.jsonl")
    batch(root, "discover", requests, config, env_file, skills_root)
    plan = build_plan(root, requests)
    if not cancelled(root):
        batch(root, "package", plan, config, env_file, skills_root)
    return summarize(root, requests, plan, config)
