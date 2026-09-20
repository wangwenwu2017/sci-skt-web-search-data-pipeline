"""Durable source outputs and conservative package validation."""

import hashlib
import json
import re
from pathlib import Path
from urllib.parse import unquote, urlsplit

from sci_pipeline.artifacts import fingerprint, safe_path


def digest(value) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, ensure_ascii=False).encode()
    ).hexdigest()


def atomic_text(path: Path, value: str):
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(value)
    tmp.replace(path)


def jsonl(path: Path, rows):
    atomic_text(path, "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows))


def validate_package(package: Path, item) -> str:
    if package.is_symlink():
        raise ValueError("Package must not be a symlink")
    for path in package.rglob("*"):
        if path.is_symlink() or not (path.is_file() or path.is_dir()):
            raise ValueError("Package contains a symlink or special file")
    description = (package / "PACKAGE.md").read_text()
    if not description.strip():
        raise ValueError("PACKAGE.md is empty")
    for original in item.originals:
        for source in original.sources:
            if source.url not in description:
                raise ValueError("PACKAGE.md must list each input source URL")
    # Check ordinary Markdown links and reference definitions, including images.
    targets = re.findall(r"\]\(([^\n)]+)\)", description)
    targets += re.findall(r"^\s*\[[^\]]+\]:\s*(\S+)", description, flags=re.M)
    for raw in targets:
        target = raw.strip().split(' "', 1)[0].strip("<>")
        parts = urlsplit(target)
        if parts.scheme in {"http", "https", "mailto"} or not parts.path:
            continue
        if parts.scheme or parts.netloc:
            raise ValueError("Unsupported link scheme in PACKAGE.md")
        local = safe_path(package, unquote(parts.path))
        if not local.is_file():
            raise ValueError("PACKAGE.md local link does not point to a package file")
    return fingerprint(package)
