#!/usr/bin/env python3
"""Run one release scenario through the real pipeline and write a verdict.

The harness builds a throwaway repository, snapshots it, runs ``run_pipeline``
against it, and records what changed.  Nothing touches the network or a real
provider: ``origin`` is a bare repository next to the sandbox and publishing is
switched off, so the suite is safe to re-run.

    python3 scripts/eval_harness.py --scenario evals/golden/clean-release/input.json \
                                    --output out/clean-release.json
"""

from __future__ import annotations

import argparse
import contextlib
import io
import json
import shutil
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import rls_shell  # noqa: E402
from rls_fixture import build as build_fixture  # noqa: E402
from rls_repo import read_manifest  # noqa: E402

MODES = ("plan", "release", "verify")


def snapshot(repo):
    """Everything a refused or dry run promises not to change."""
    head, _ = rls_shell.git_ok(repo, "rev-parse", "HEAD")
    tags, _ = rls_shell.git_ok(repo, "tag", "--list")
    remote, _ = rls_shell.git_ok(repo, "ls-remote", "--tags", "origin")
    manifest, _ = rls_shell.git_ok(repo, "rev-parse", "HEAD:package.json")
    return {
        "head": head.strip(),
        "tags": sorted(line.strip() for line in tags.splitlines() if line.strip()),
        "remote_refs": sorted(line.split()[-1] for line in remote.splitlines() if line.strip()),
        "manifest_blob": manifest.strip(),
        "version": None,
    }


def load_scenario(path):
    spec = {
        "id": Path(path).stem,
        "scenario": "clean",
        "mode": "release",
        "increment": "minor",
        "publish": False,
        "dry_run": False,
        "expect": "released",
    }
    spec.update(json.loads(Path(path).expanduser().read_text(encoding="utf-8")))
    if spec.get("mode") not in MODES:
        raise SystemExit("scenario %r has an unknown mode %r" % (spec["id"], spec["mode"]))
    return spec


def tag_commit(repo, tag):
    output, ok = rls_shell.git_ok(repo, "rev-list", "-n", "1", tag)
    return output.strip() if ok else ""


def remote_tag_commit(repo, tag):
    code, output = rls_shell.run_text(["git", "ls-remote", "--tags", "origin", "refs/tags/%s*" % tag], cwd=repo)
    if code != 0:
        return ""
    peeled, plain = [], []
    for line in output.splitlines():
        parts = line.split()
        if len(parts) != 2:
            continue
        (peeled if parts[1].endswith("^{}") else plain).append(parts[0])
    return (peeled or plain or [""])[0]


def classify_expectation(spec, before, after, plan, verification, exit_code):
    """Did the run do what the scenario says it must do?"""
    expect = spec["expect"]
    tag = plan.get("tag") or ""
    added_tags = sorted(set(after["tags"]) - set(before["tags"]))
    untouched = (
        before["head"] == after["head"]
        and before["tags"] == after["tags"]
        and before["manifest_blob"] == after["manifest_blob"]
    )

    if expect == "refused":
        ok = exit_code == 2 and not added_tags and untouched
        reason = ("refused with exit 2 and changed nothing" if ok
                  else "expected a refusal that changed nothing (exit %s, added tags %s)" % (exit_code, added_tags))
    elif expect == "dry-run":
        ok = exit_code == 0 and untouched
        reason = ("dry run wrote nothing" if ok
                  else "expected a dry run to change nothing (exit %s, added tags %s)" % (exit_code, added_tags))
    elif expect == "released":
        consistent = bool(verification.get("consistent"))
        ok = exit_code == 0 and consistent and tag in after["tags"] and bool(after["head"])
        reason = ("released %s at %s; every deliverable agrees" % (tag, after["head"][:12]) if ok
                  else "expected a consistent release of %s (exit %s, consistent %s, tags %s)"
                       % (tag, exit_code, consistent, added_tags))
    else:
        ok, reason = False, "unknown expectation %r" % (expect,)

    return ok, reason, untouched, added_tags


def run_scenario(spec, root=None, timeout=900):
    root = Path(root or Path(tempfile.gettempdir()) / "release-it-skill-evals").expanduser()
    dest = root / spec["id"]
    summary = build_fixture(dest, scenario=spec["scenario"], owner=spec.get("owner", "ez-xu"),
                            name=spec.get("name", "release-it-skill-fixture"), force=True)
    repo = summary["repo"]

    if spec.get("pre_tag"):
        rls_shell.git_ok(repo, "tag", "-a", spec["pre_tag"], "-m", "pre-existing")
        rls_shell.git_ok(repo, "push", "origin", spec["pre_tag"])

    before = snapshot(repo)
    name, version = read_manifest(str(dest / "package.json")) if (dest / "package.json").exists() else (None, None)
    before["version"] = version

    pipeline_spec = {
        "repo": repo,
        "mode": spec["mode"],
        "increment": spec.get("increment"),
        "version": spec.get("version"),
        "publish": spec.get("publish", False),
        "release": spec.get("release", True),
        "dry_run": spec.get("dry_run", False),
        "offline": True,
        "allow_dirty": spec.get("allow_dirty", False),
        "allow_no_upstream": spec.get("allow_no_upstream", False),
    }
    pipeline_spec = {key: value for key, value in pipeline_spec.items() if value is not None}

    output = root / ("%s.report.json" % spec["id"])
    buffer = io.StringIO()
    from run_pipeline import run as run_pipeline

    with contextlib.redirect_stdout(buffer):
        try:
            exit_code, artifacts = run_pipeline(pipeline_spec, output=str(output))
        except Exception as exc:  # the harness must always produce a verdict
            exit_code, artifacts = 70, {"error": "%s: %s" % (type(exc).__name__, exc)}

    after = snapshot(repo)
    _, after_version = read_manifest(str(dest / "package.json")) if (dest / "package.json").exists() else (None, None)
    after["version"] = after_version

    verification = artifacts.get("verification") or {}
    record = artifacts.get("record") or {}
    plan = artifacts.get("plan") or {}
    notes = plan.get("notes") or {}
    tag = plan.get("tag") or ("v%s" % plan.get("version") if plan.get("version") else "")

    ok, reason, untouched, added_tags = classify_expectation(
        spec, before, after, plan, verification, exit_code
    )

    return {
        "scenario": spec["id"],
        "expect": spec["expect"],
        "mode": spec["mode"],
        "exit_code": exit_code,
        "satisfied": ok,
        "reason": reason,
        "verdict": verification.get("verdict", ""),
        "consistent": bool(verification.get("consistent")),
        "refused": artifacts.get("refused", []),
        "blockers": plan.get("blockers", []),
        "tag": tag,
        "version": plan.get("version") or after.get("version"),
        "notes_chars": (verification.get("release") or {}).get("notes_chars") or notes.get("chars") or 0,
        "notes_sections": notes.get("sections") or [],
        "release_record": record,
        "links": plan.get("links", {}),
        "checks": verification.get("checks", []),
        "failed_checks": verification.get("failed", []),
        "error": artifacts.get("error", ""),
        "before": before,
        "after": after,
        "added_tags": added_tags,
        "untouched": untouched,
        "tag_commit": tag_commit(repo, tag) if tag in after["tags"] else "",
        "remote_tag_commit": remote_tag_commit(repo, tag) if tag in after["tags"] else "",
        "stdout_tail": buffer.getvalue()[-2000:],
    }


def main(argv=None):
    parser = argparse.ArgumentParser(prog="eval_harness.py",
                                     description="Run one release scenario and write its verdict.")
    parser.add_argument("--scenario", required=True, help="the scenario spec JSON")
    parser.add_argument("--output", required=True, help="where to write the verdict JSON")
    parser.add_argument("--root", help="where to build the sandboxes")
    parser.add_argument("--keep", action="store_true")
    args = parser.parse_args(argv)

    spec = load_scenario(args.scenario)
    verdict = run_scenario(spec, root=args.root)

    output = Path(args.output).expanduser()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(verdict, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    print("%-28s %-9s exit %-3s %s" % (verdict["scenario"], verdict["expect"], verdict["exit_code"],
                                       "ok" if verdict["satisfied"] else "MISMATCH"))
    print("  %s" % verdict["reason"])
    if verdict.get("error"):
        print("  error: %s" % verdict["error"])

    if not args.keep and not args.root:
        root = Path(tempfile.gettempdir()) / "release-it-skill-evals"
        shutil.rmtree(root, ignore_errors=True)

    return 0 if verdict["satisfied"] else 1


if __name__ == "__main__":
    sys.exit(main())
