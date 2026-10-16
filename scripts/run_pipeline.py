#!/usr/bin/env python3
"""Run the release-it-skill pipeline: plan, release, verify, report.

Every step is wired to the next in code, so the artifact that a later step reads
is the artifact the earlier step just wrote:

    spec.json -> plan ------> state/{release-it.json, release-notes.md, print-notes.mjs}
                        |
                        +--> release-it ----> run record
                        |                        |
                        +--> verification <------+
                                 |
                                 +--> release-report.json / release-report.md

The pipeline is deterministic and offline unless it is asked to publish.  With
no ``repo`` in the spec it builds a disposable sandbox (a real git repository
whose ``origin`` is a bare repository next to it) so the whole workflow can be
exercised without touching a public release.

Exit codes: 0 success, 2 refused (the plan could not prove its own safety), 1 the
run itself failed.
"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from rls_fixture import DEFAULT_NAME, DEFAULT_OWNER, SCENARIOS, build as build_fixture  # noqa: E402
from rls_plan import build_plan, summarise, write_state  # noqa: E402
from rls_release import Refused, execute  # noqa: E402
from rls_report import build_report, write_report  # noqa: E402
from rls_verify import verify  # noqa: E402

MODES = ("plan", "release", "verify", "fixture")

DEFAULT_SPEC = {
    "mode": "plan",
    "scenario": "clean",
    "owner": DEFAULT_OWNER,
    "name": DEFAULT_NAME,
    "increment": "minor",
    "publish": False,
    "dry_run": False,
    "offline": False,
}

PLAN_OPTION_KEYS = (
    "manifest", "increment", "version", "pre_release_id", "pre_release_base",
    "tag_prefix", "tag_match", "release_name", "commit_message", "tag_annotation",
    "assets", "require_branch", "publish", "release", "draft", "prerelease",
    "auto_generate", "dry_run", "allow_dirty", "allow_no_upstream",
    "publish_package_manager", "state_dir",
)


def load_spec(path=None):
    spec = dict(DEFAULT_SPEC)
    if path:
        spec.update(json.loads(Path(path).expanduser().read_text(encoding="utf-8")))
    return spec


def plan_options(spec):
    return {key: spec[key] for key in PLAN_OPTION_KEYS if spec.get(key) is not None}


def resolve_repo(spec, keep=False):
    """Return (repo, sandbox_summary).  Builds a sandbox when the spec has no repo."""
    if spec.get("repo"):
        return str(Path(spec["repo"]).expanduser().resolve()), {}

    sandbox = spec.get("sandbox")
    if not sandbox:
        sandbox = str(Path(tempfile.gettempdir()) / "release-it-skill-pipeline")
    summary = build_fixture(
        sandbox,
        scenario=spec.get("scenario", "clean"),
        owner=spec.get("owner", DEFAULT_OWNER),
        name=spec.get("name", DEFAULT_NAME),
        force=True,
    )
    return summary["repo"], summary


def run(spec, output=None, keep=False):
    """Run the pipeline and return (exit_code, artifacts)."""
    mode = spec.get("mode", "plan")
    if mode not in MODES:
        raise SystemExit("unknown mode %r; choose one of %s" % (mode, ", ".join(MODES)))

    repo, sandbox = resolve_repo(spec, keep=keep)
    artifacts = {"mode": mode, "repo": repo, "sandbox": sandbox}

    if mode == "fixture":
        return 0, artifacts

    plan = build_plan(repo, **plan_options(spec))
    written = write_state(plan)
    artifacts["plan_state"] = written

    plan_payload = {key: value for key, value in plan.items() if key != "notes_text"}
    plan_payload["written"] = written
    artifacts["plan"] = plan_payload

    print(summarise(plan))

    if mode == "plan":
        if output:
            write_json(output, plan_payload)
            print("plan     %s" % output)
        return (2 if plan["blockers"] else 0), artifacts

    if mode == "verify":
        report = verify(plan, offline=spec.get("offline", False))
        artifacts["verification"] = report
        if output:
            write_json(output, report)
            print("verdict  %s" % report["verdict"])
            print("report   %s" % output)
        return (0 if report["verdict"] in ("verified", "web-pending", "dry-run") else 1), artifacts

    if plan["blockers"]:
        artifacts["refused"] = list(plan["blockers"])
        if output:
            write_json(output, {"refused": plan["blockers"], "plan": plan_payload})
        print("REFUSED: %s" % "; ".join(plan["blockers"]))
        return 2, artifacts

    record = execute(plan, dry_run=spec.get("dry_run"))
    artifacts["record"] = record
    print("result   %s (exit %s, %ss)" % (record["classification"], record["exit_code"], record["duration_s"]))

    # A sandbox has no platform release and no registry entry, so those two reads
    # are skipped there on purpose; a real repository is checked wherever it lives.
    offline = bool(spec.get("offline")) or (bool(sandbox) and not spec.get("repo"))
    verification = verify(plan, record, offline=offline)
    artifacts["verification"] = verification

    report = build_report(plan, record, verification)
    targets = write_report(report, directory=Path(output).expanduser().parent if output else None)
    artifacts["report"] = report
    artifacts["report_files"] = targets

    if output:
        write_json(output, report)

    print("verdict  %s" % report["verdict_line"])
    for check in verification["checks"]:
        mark = "skip" if check["skipped"] else ("ok" if check["ok"] else "FAIL")
        print("  %-18s %-4s %s" % (check["id"], mark, check["detail"]))
    print("report   %s" % targets["markdown"])
    print("report   %s" % targets["json"])

    code = 1 if record["classification"] == "failed" else 0
    if verification["verdict"] == "refused":
        code = 2
    return code, artifacts


def write_json(path, payload):
    target = Path(path).expanduser()
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return target


def main(argv=None):
    parser = argparse.ArgumentParser(
        prog="run_pipeline.py",
        description="Plan, publish, verify and report a release-it release.",
    )
    parser.add_argument("--input", help="the spec JSON: what to release and where")
    parser.add_argument("--output", help="where to write the plan, the verification or the report")
    parser.add_argument("--repo", help="plan a release for this repository instead of a sandbox")
    parser.add_argument("--mode", choices=MODES, help="override the spec's mode")
    parser.add_argument("--scenario", choices=SCENARIOS, help="the sandbox scenario to build")
    parser.add_argument("--increment", help="major, minor, patch or a prerelease increment")
    parser.add_argument("--version", help="release exactly this version")
    parser.add_argument("--dry-run", action="store_true", default=None)
    parser.add_argument("--publish", dest="publish", action="store_true", default=None)
    parser.add_argument("--no-publish", dest="publish", action="store_false")
    parser.add_argument("--offline", action="store_true", help="check only the local repository and origin")
    parser.add_argument("--sandbox", help="where to build the disposable sandbox")
    parser.add_argument("--keep", action="store_true", help="do not delete the sandbox afterwards")
    args = parser.parse_args(argv)

    spec = load_spec(args.input)
    for key in ("repo", "mode", "scenario", "increment", "version", "publish", "offline", "sandbox"):
        if getattr(args, key, None) is not None:
            spec[key] = getattr(args, key)
    if args.dry_run:
        spec["dry_run"] = True

    code, artifacts = run(spec, output=args.output, keep=args.keep)

    if spec.get("sandbox") is None and not spec.get("repo") and not args.keep:
        shutil.rmtree(Path(tempfile.gettempdir()) / "release-it-skill-pipeline", ignore_errors=True)
        remote = Path(tempfile.gettempdir()) / "release-it-skill-pipeline-remote.git"
        shutil.rmtree(remote, ignore_errors=True)

    return code


if __name__ == "__main__":
    sys.exit(main())
