#!/usr/bin/env python3
"""Shadowfox-OS Canon linter (CANON-360).

Single source of truth for org-standard GitHub Actions pins and repo-setup
canon. Scans a repository's workflow files and fails on drift from the
canonical Node 24-native action versions.

This file is the canonical copy, in
``Shadowfox-OS-Specification-Repository/canon/canon_lint.py``. Each consuming
repo vendors an *identical* copy at ``.canon/canon_lint.py`` and runs it in CI
(``python3 .canon/canon_lint.py``). The ``canon-sweep`` workflow in the spec
repo verifies every vendored copy reports the same ``CANON_REVISION`` as this
source of truth, so a single edit here is detectable everywhere.

Dependency-free (Python 3 stdlib only) so it runs on any GitHub runner without
a setup step, in Python and non-Python repos alike.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

# ---------------------------------------------------------------------------
# CANON — the single source of truth.
# Bump CANON_REVISION whenever the tables below change. The canon-sweep
# workflow compares each repo's vendored revision against this value, so a
# stale vendored copy becomes a failing check (propagation is enforced, not
# hoped for).
# ---------------------------------------------------------------------------
CANON_REVISION = "2026.07.04"

# Org-standard Node 24-native action majors (CANON-360, June 2026 migration).
# GitHub forces the Node 24 runtime on runners; the action *packages* must be
# updated to match, not just ``node-version``.
EXPECTED_ACTIONS: dict[str, int] = {
    "actions/checkout": 7,
    "actions/setup-node": 6,
    "actions/setup-python": 6,
    "actions/upload-artifact": 7,
    "actions/download-artifact": 7,
    "actions/cache": 4,
}

# Matches ``uses: owner/repo@ref`` with an optional trailing ``# comment``,
# e.g. ``uses: actions/checkout@v7`` or
# ``uses: actions/checkout@<40-hex sha> # v7.0.1``.
_USES_RE = re.compile(
    r"""uses:\s*['"]?(?P<action>[A-Za-z0-9._/-]+)@(?P<ref>[^\s'"#]+)['"]?"""
    r"""(?:\s*#\s*(?P<comment>.*))?""",
)
# A version-tag ref: ``v7``, ``v7.0``, ``7.0.1``.
_TAG_REF_RE = re.compile(r"v?(?P<major>[0-9]+)(?:\.[0-9]+)*")
# A full commit SHA. T0 interpretation of CANON-360 (DL-H, 2026-10-12): a full
# SHA pin satisfies the canon when its trailing comment names the canon major
# (``# v7`` or ``# v7.0.1``). The comment is the pin author's assertion; this
# linter does not verify that the SHA belongs to that release.
_SHA_REF_RE = re.compile(r"[0-9a-f]{40}")
_COMMENT_MAJOR_RE = re.compile(r"v(?P<major>[0-9]+)(?:\.[0-9]+)*\b")


class Finding:
    """A single drift finding: an action pinned off-canon."""

    __slots__ = ("file", "line", "action", "found", "expected", "reason")

    def __init__(
        self,
        file: str,
        line: int,
        action: str,
        found: int | None,
        expected: int,
        reason: str = "drift",
    ):
        self.file = file
        self.line = line
        self.action = action
        self.found = found  # None when no major can be read from the pin
        self.expected = expected
        # "drift": wrong major. "sha_without_major_comment": a full SHA pin
        # with no ``# vN`` comment. "unversioned_ref": a branch, short SHA or
        # other ref that names no major.
        self.reason = reason

    def as_dict(self) -> dict:
        return {
            "file": self.file,
            "line": self.line,
            "action": self.action,
            "found": None if self.found is None else f"v{self.found}",
            "expected": f"v{self.expected}",
            "reason": self.reason,
        }

    def __str__(self) -> str:
        where = f"{self.file}:{self.line}: {self.action}"
        if self.reason == "sha_without_major_comment":
            return (
                f"{where}: full SHA pin has no '# v{self.expected}' comment "
                f"naming the canon major"
            )
        if self.reason == "unversioned_ref":
            return (
                f"{where}: ref names no major; pin @v{self.expected} or a full "
                f"SHA with '# v{self.expected}'"
            )
        return f"{where}@v{self.found} drifts from canon @v{self.expected}"


def scan_workflow_text(text: str, filename: str = "<workflow>") -> list[Finding]:
    """Return drift findings for a single workflow file's text."""
    findings: list[Finding] = []
    for lineno, raw in enumerate(text.splitlines(), start=1):
        m = _USES_RE.search(raw)
        if not m:
            continue
        action = m.group("action")
        expected = EXPECTED_ACTIONS.get(action)
        if expected is None:
            continue
        ref = m.group("ref")
        tag = _TAG_REF_RE.fullmatch(ref)
        if tag:
            major = int(tag.group("major"))
        elif _SHA_REF_RE.fullmatch(ref):
            cm = _COMMENT_MAJOR_RE.match(m.group("comment") or "")
            if not cm:
                findings.append(
                    Finding(filename, lineno, action, None, expected,
                            "sha_without_major_comment")
                )
                continue
            major = int(cm.group("major"))
        else:
            findings.append(
                Finding(filename, lineno, action, None, expected, "unversioned_ref")
            )
            continue
        if major != expected:
            findings.append(Finding(filename, lineno, action, major, expected))
    return findings


def workflow_files(root: Path) -> list[Path]:
    wf_dir = root / ".github" / "workflows"
    if not wf_dir.is_dir():
        return []
    return sorted(
        [*wf_dir.glob("*.yml"), *wf_dir.glob("*.yaml")],
        key=lambda p: p.name,
    )


def lint_repo(root: Path) -> list[Finding]:
    """Scan every workflow under ``root/.github/workflows`` for pin drift."""
    findings: list[Finding] = []
    for wf in workflow_files(root):
        rel = wf.relative_to(root).as_posix()
        findings.extend(scan_workflow_text(wf.read_text(encoding="utf-8"), rel))
    return findings


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Shadowfox-OS Canon linter (CANON-360) — checks workflow "
        "action pins against org-standard Node 24-native versions.",
    )
    parser.add_argument(
        "--root", default=".", help="Repository root to lint (default: cwd)."
    )
    parser.add_argument(
        "--print-revision",
        action="store_true",
        help="Print CANON_REVISION and exit (used by the canon-sweep).",
    )
    parser.add_argument(
        "--json", action="store_true", help="Emit findings as JSON."
    )
    args = parser.parse_args(argv)

    if args.print_revision:
        print(CANON_REVISION)
        return 0

    root = Path(args.root)
    findings = lint_repo(root)

    if args.json:
        print(
            json.dumps(
                {
                    "canon_revision": CANON_REVISION,
                    "root": str(root),
                    "findings": [f.as_dict() for f in findings],
                },
                indent=2,
            )
        )
    else:
        wf_count = len(workflow_files(root))
        if not findings:
            print(
                f"canon-lint OK (rev {CANON_REVISION}): "
                f"{wf_count} workflow file(s) conform to Node 24-native pins."
            )
        else:
            print(
                f"canon-lint FAILED (rev {CANON_REVISION}): "
                f"{len(findings)} action pin(s) drift from canon.\n"
            )
            for f in findings:
                print(f"  ✗ {f}")
            print(
                "\nFix: bump the drifting actions to the canon versions "
                "(see canon/CANON.md), as @vN or a full SHA with a '# vN' "
                "comment. Node 24-native majors: "
                + ", ".join(f"{a}@v{v}" for a, v in EXPECTED_ACTIONS.items())
            )

    return 1 if findings else 0


if __name__ == "__main__":
    raise SystemExit(main())
