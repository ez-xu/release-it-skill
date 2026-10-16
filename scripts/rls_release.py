#!/usr/bin/env python3
"""Run release-it from a release plan.

The plan is the single source of truth.  This module never composes its own
release-it invocation and never edits the repository: it writes the plan's state
files, runs the plan's argv, and classifies what happened.

It refuses to run when the plan carries a blocker.  The failure impact recorded
for this workflow is that a wrong or incomplete public tag reaches downstream
users, so a plan that cannot prove its own safety publishes nothing.
"""

from __future__ import annotations

import json
import re
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from rls_plan import write_state  # noqa: E402
from rls_shell import redact, run  # noqa: E402

RELEASE_LINK_RE = re.compile(r"\N{ELECTRIC TORCH}\s+(\S+)")
LINK_FALLBACK_RE = re.compile(r"^\s*\W*\s*(https?://\S+)\s*$", re.MULTILINE)
WARNING_RE = re.compile(r"^\s*WARNING\s+(.+)$", re.MULTILINE)
ERROR_RE = re.compile(r"^\s*(?:ERROR|Error:)\s*(.+)$", re.MULTILINE)

WEB_FALLBACK = "Falling back to web-based"

CLASSIFICATIONS = ("dry-run", "released", "web-pending", "published", "failed", "refused")


class Refused(Exception):
    """The run did not start because the plan could not prove its own safety."""


def _tail(text, limit=6000):
    text = redact(text or "")
    return text if len(text) <= limit else "..." + text[-limit:]


def classify(exit_code, combined, argv, plan):
    """Name what the run actually did, from release-it's own output."""
    if exit_code != 0:
        return "failed"
    if "--dry-run" in argv:
        return "dry-run"
    if WEB_FALLBACK in combined:
        return "web-pending"
    if plan["operations"].get("publish"):
        return "published"
    return "released"


def release_link(combined):
    match = RELEASE_LINK_RE.search(combined)
    if match:
        return match.group(1)
    for candidate in LINK_FALLBACK_RE.findall(combined):
        if "/releases/" in candidate:
            return candidate
    return ""


def execute(plan, timeout=900, dry_run=None, allow_blockers=False):
    """Write the plan state, run release-it, and return the run record."""
    blockers = list(plan.get("blockers") or [])
    if blockers and not allow_blockers:
        raise Refused("; ".join(blockers))

    argv = list(plan["release_it"]["argv"])
    if dry_run is True and "--dry-run" not in argv:
        argv.insert(1, "--dry-run")

    written = write_state(plan)
    started = time.time()
    exit_code, stdout, stderr = run(argv, cwd=plan["repo"], timeout=timeout)
    duration = round(time.time() - started, 2)

    combined = (stdout or "") + (stderr or "")
    warnings = [line.strip() for line in WARNING_RE.findall(combined)]
    errors = [line.strip() for line in ERROR_RE.findall(combined)]

    return {
        "argv": argv,
        "display": plan["release_it"]["display"] if argv == plan["release_it"]["argv"] else " ".join(argv),
        "cwd": plan["repo"],
        "exit_code": exit_code,
        "duration_s": duration,
        "classification": classify(exit_code, combined, argv, plan),
        "release_link": release_link(combined),
        "warnings": warnings,
        "errors": errors,
        "token_warning": any("is required for automated" in line for line in warnings),
        "web_fallback": WEB_FALLBACK in combined,
        "stdout_tail": _tail(stdout),
        "stderr_tail": _tail(stderr),
        "written": written,
    }


def main(argv=None):
    import argparse

    parser = argparse.ArgumentParser(
        prog="rls_release.py",
        description="Run release-it for a repository, following the release plan.",
    )
    parser.add_argument("--repo", default=".")
    parser.add_argument("--plan", help="reuse an existing release-plan.json instead of rebuilding it")
    parser.add_argument("--increment", choices=("major", "minor", "patch", "premajor", "preminor",
                                                 "prepatch", "prerelease", "pre"))
    parser.add_argument("--version", help="release exactly this version")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--no-publish", dest="publish", action="store_false", default=None)
    parser.add_argument("--no-release", dest="release", action="store_false", default=None)
    parser.add_argument("--allow-dirty", action="store_true")
    parser.add_argument("--timeout", type=int, default=900)
    parser.add_argument("--output", help="where to write the run record JSON")
    args = parser.parse_args(argv)

    from rls_plan import build_plan

    if args.plan:
        plan = json.loads(Path(args.plan).expanduser().read_text(encoding="utf-8"))
    else:
        plan = build_plan(
            args.repo,
            increment=args.increment,
            version=args.version,
            dry_run=args.dry_run,
            publish=args.publish,
            release=args.release,
            allow_dirty=args.allow_dirty,
        )

    try:
        record = execute(plan, timeout=args.timeout)
    except Refused as exc:
        print("REFUSED: %s" % exc)
        return 2

    record["plan"] = {
        "version": plan["version"],
        "tag": plan["tag"],
        "project": plan["project"],
        "provider": plan["provider"],
        "links": plan["links"],
    }

    if args.output:
        output = Path(args.output).expanduser()
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(record, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    print("run      %s" % record["display"])
    print("result   %s (exit %s, %ss)" % (record["classification"], record["exit_code"], record["duration_s"]))
    if record["release_link"]:
        print("release  %s" % record["release_link"])
    for warning in record["warnings"]:
        print("warning: %s" % warning)
    for error in record["errors"]:
        print("error:   %s" % error)
    if args.output:
        print("record   %s" % args.output)

    return 0 if record["classification"] not in ("failed",) else 1


if __name__ == "__main__":
    sys.exit(main())
