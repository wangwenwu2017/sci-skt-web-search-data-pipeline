"""Standalone stdlib-only Tavily tool, copied into the role container."""

import argparse
import json
import os
import sys
import time
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen
from uuid import uuid4


def call(operation, payload, key, timeout):
    request = Request(
        "https://api.tavily.com/" + operation,
        data=json.dumps({**payload, "include_usage": True}).encode(),
        headers={"Authorization": "Bearer " + key, "Content-Type": "application/json"},
        method="POST",
    )
    # A single bounded request. No hidden retry loop multiplying role attempts.
    with urlopen(request, timeout=timeout) as response:
        return json.load(response)


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Tavily Search/Extract; credentials from environment"
    )
    parser.add_argument("operation", choices=["search", "extract"])
    parser.add_argument("--query")
    parser.add_argument("--urls", nargs="+")
    parser.add_argument("--max-results", type=int, default=5, choices=range(1, 21))
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    key = os.environ.get("TAVILY_API_KEY")
    if not key:
        parser.error("TAVILY_API_KEY is not configured")
    if args.operation == "search" and not args.query:
        parser.error("search requires --query")
    if args.operation == "extract" and not args.urls:
        parser.error("extract requires --urls")
    payload = (
        {"query": args.query, "max_results": args.max_results, "search_depth": "basic"}
        if args.operation == "search"
        else {"urls": args.urls}
    )
    started = time.monotonic()
    record = {"operation": args.operation, "status": "failed"}
    try:
        result = call(args.operation, payload, key, int(os.environ.get("SCI_SEARCH_TIMEOUT", "60")))
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(result, ensure_ascii=False).replace(key, "[REDACTED]"))
        record.update(status="completed", usage=result.get("usage"))
        print(str(args.output))
        return 0
    except HTTPError as exc:
        record["error"] = f"HTTP {exc.code}"
    except (URLError, TimeoutError, OSError, ValueError):
        record["error"] = "Search transport, response, or output error"
    finally:
        record["elapsed_sec"] = time.monotonic() - started
        log = Path("/workspace/output/tool-events")
        log.mkdir(parents=True, exist_ok=True)
        (log / (uuid4().hex + ".json")).write_text(json.dumps(record))
    print(record["error"], file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
