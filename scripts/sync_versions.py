#!/usr/bin/env python3
"""Propagate config/version.json into every other file that hardcodes a version.

Edits (idempotent):
  mobile/pyproject.toml                          version = "..."
  mobile_build/pyproject.toml                    version = "..."
  mobile_build/build/flutter/pubspec.yaml        version: X.Y.Z+B
  kingdom-landing/package.json                   "version": "..."
  kingdom-landing/public/version.json            mirror of config/version.json

Run: python3 scripts/sync_versions.py
"""
from __future__ import annotations

import json
import re
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
VERSION_JSON = ROOT / "config" / "version.json"


def load_version() -> dict:
    return json.loads(VERSION_JSON.read_text(encoding="utf-8"))


def replace_in_file(path: Path, pattern: str, replacement: str) -> bool:
    if not path.exists():
        print(f"skip (missing): {path.relative_to(ROOT)}")
        return False
    text = path.read_text(encoding="utf-8")
    new = re.sub(pattern, replacement, text, count=1, flags=re.MULTILINE)
    if new != text:
        path.write_text(new, encoding="utf-8")
        print(f"updated: {path.relative_to(ROOT)}")
        return True
    print(f"already up-to-date: {path.relative_to(ROOT)}")
    return False


def main() -> None:
    v = load_version()
    app = v["app_version"]
    flutter = v["flutter_build"]

    replace_in_file(
        ROOT / "mobile" / "pyproject.toml",
        r'^version\s*=\s*"[^"]*"',
        f'version = "{app}"',
    )
    replace_in_file(
        ROOT / "mobile_build" / "pyproject.toml",
        r'^version\s*=\s*"[^"]*"',
        f'version = "{app}"',
    )
    replace_in_file(
        ROOT / "mobile_build" / "build" / "flutter" / "pubspec.yaml",
        r"^version:\s*[0-9]+\.[0-9]+\.[0-9]+\+[0-9]+",
        f"version: {flutter}",
    )
    pkg = ROOT / "kingdom-landing" / "package.json"
    if pkg.exists():
        data = json.loads(pkg.read_text(encoding="utf-8"))
        if data.get("version") != app:
            data["version"] = app
            pkg.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
            print(f"updated: {pkg.relative_to(ROOT)}")
        else:
            print(f"already up-to-date: {pkg.relative_to(ROOT)}")

    # Publish version.json alongside the landing page so the PWA can fetch it.
    public_version = ROOT / "kingdom-landing" / "public" / "version.json"
    public_version.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(VERSION_JSON, public_version)
    print(f"updated: {public_version.relative_to(ROOT)}")

    print("done.")


if __name__ == "__main__":
    main()
