#!/usr/bin/env python3
"""Turn a plan, a run record and a verification report into the release report.

Two artifacts are produced from the same dictionary: ``release-report.json`` for
machines and ``release-report.md`` for the person reading the release.  The
report always names what was released, where each deliverable lives and which
commit all of them describe -- and when they do not agree, it says so instead of
reporting a success.
"""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

REPORT_VERSION = 1
SKILL_NAME = "release-it-skill"

VERDICT_TITLE = {
    "verified": "Verified",
    "web-pending": "Tag and commit verified; the platform release is still pending",
    "dry-run": "Dry run: nothing was written",
    "refused": "Refused: a required check failed, nothing was published",
    "failed": "Failed",
}


def deliverable(name, value, url="", commit="", ok=False, detail=""):
    return {"name": name, "value": value, "url": url, "commit": commit, "ok": bool(ok), "detail": detail}


def build_report(plan, record=None, verification=None):
    """Return the release report as a dictionary."""
    record = record or {}
    verification = verification or {}
    links = plan.get("links") or {}
    commits = verification.get("commits") or {}
    consistent = bool(verification.get("consistent"))
    commit = commits.get("tag") or commits.get("head") or ""
    published = bool(plan.get("operations", {}).get("publish")) and not plan["operations"].get("dry_run")
    released = bool(plan.get("operations", {}).get("release")) and not plan["operations"].get("dry_run")

    release_api = verification.get("release") or {}
    if release_api.get("exists"):
        release_detail = "release created with %d characters of notes" % release_api.get("notes_chars", 0)
    elif record.get("web_fallback"):
        release_detail = "no API release: release-it generated the web release form instead"
    elif not released:
        release_detail = "no platform release was requested"
    else:
        release_detail = "the platform release could not be read back"

    deliverables = [
        deliverable("tag", plan["tag"], links.get("tag", ""), commit,
                    ok=bool(commit) and consistent,
                    detail="annotated tag pushed to origin"),
        deliverable("release", plan["tag"], release_api.get("url") or links.get("release", ""),
                    commits.get("release", commit),
                    ok=(not released) or bool(release_api.get("exists")),
                    detail=release_detail),
        deliverable("package", "%s@%s" % (plan.get("package"), plan["version"]) if plan.get("package") else "(none)",
                    links.get("package", ""), commits.get("package", commit),
                    ok=(not published) or bool(verification.get("package", {}).get("published")),
                    detail="gitHead %s" % commits.get("package", "") if commits.get("package") else
                    ("publishing is switched off" if not published else "")),
        deliverable("commit", commit, links.get("compare", ""), commit,
                    ok=bool(commit), detail="the commit every deliverable resolves to"),
    ]

    verdict = verification.get("verdict") or ("failed" if record.get("exit_code") not in (0, None) else "planned")

    report = {
        "report_version": REPORT_VERSION,
        "skill": SKILL_NAME,
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "verdict": verdict,
        "repo": plan.get("repo"),
        "provider": plan.get("provider"),
        "project": plan.get("project"),
        "branch": plan.get("branch"),
        "remote": plan.get("remote"),
        "package": plan.get("package"),
        "version": plan["version"],
        "version_source": plan.get("version_source"),
        "previous_tag": plan.get("previous_tag"),
        "tag": plan["tag"],
        "tag_prefix": plan.get("tag_prefix"),
        "commit": commit,
        "consistent": consistent,
        "notes": {
            "path": plan.get("notes", {}).get("path"),
            "chars": plan.get("notes", {}).get("chars", 0),
            "sections": plan.get("notes", {}).get("sections", []),
        },
        "deliverables": deliverables,
        "links": links,
        "operations": plan.get("operations", {}),
        "release_it": {
            "command": record.get("display") or plan.get("release_it", {}).get("display"),
            "exit_code": record.get("exit_code"),
            "duration_s": record.get("duration_s"),
            "classification": record.get("classification"),
            "warnings": record.get("warnings", []),
            "web_fallback": record.get("web_fallback", False),
        },
        "checks": verification.get("checks", []),
        "failed": verification.get("failed", []),
        "release_form": record.get("release_link", ""),
        "blockers": plan.get("blockers", []),
        "warnings": plan.get("warnings", []),
        "state": plan.get("state", {}),
        "next": next_steps(verdict, plan, record, verification),
    }
    if verdict == "refused" and not verification.get("consistent"):
        report["verdict_line"] = "Refused: the deliverables do not all describe the same commit, nothing was published"
    else:
        report["verdict_line"] = VERDICT_TITLE.get(verdict, verdict)
    return report


def next_steps(verdict, plan, record, verification):
    steps = []
    if verdict == "refused" or plan.get("blockers"):
        steps.append("Fix the named checks, then run the pipeline again. Nothing was published.")
    elif verdict == "dry-run":
        steps.append("Re-run without --dry-run to publish.")
    elif verdict == "web-pending":
        steps.append(
            "Set %s in the environment and re-run, or open the release form and paste %s."
            % ("GITHUB_TOKEN" if plan.get("provider") == "github" else "GITLAB_TOKEN",
               plan.get("notes", {}).get("path"))
        )
    elif verdict == "verified":
        steps.append("Nothing further: the tag, the release notes, the package and the links describe %s."
                     % (verification.get("commits", {}).get("tag", "one commit")))
    elif verdict == "failed":
        steps.append("Read the release-it output in the run record; the repository may be half-released, "
                     "so check `git log` and `git ls-remote --tags origin` before retrying.")
    return steps


def render_markdown(report):
    """Render the report as markdown."""
    lines = [
        "# Release report: %s" % report["tag"],
        "",
        "**%s**" % report.get("verdict_line", report["verdict"]),
        "",
        "| | |",
        "| --- | --- |",
        "| Repository | %s |" % (report.get("remote") or report.get("repo") or "-"),
        "| Provider | %s |" % (report.get("project") or "-"),
        "| Version | %s (%s) |" % (report["version"], report.get("version_source") or "-"),
        "| Previous tag | %s |" % (report.get("previous_tag") or "(none)"),
        "| Commit | `%s` |" % (report.get("commit") or "-"),
        "| All deliverables agree | %s |" % ("yes" if report.get("consistent") else "no"),
        "",
        "## Deliverables",
        "",
        "| Deliverable | Value | Link | Commit |",
        "| --- | --- | --- | --- |",
    ]
    for item in report["deliverables"]:
        lines.append(
            "| %s | `%s` | %s | `%s` |"
            % (item["name"], item["value"],
               "[%s](%s)" % (item["name"], item["url"]) if item["url"] else "-",
               (item["commit"] or "-")[:12])
        )

    lines += ["", "## Checks", "", "| Check | Result | Detail |", "| --- | --- | --- |"]
    for check in report["checks"]:
        mark = "skipped" if check["skipped"] else ("pass" if check["ok"] else "**FAIL**")
        lines.append("| %s | %s | %s |" % (check["id"], mark, check["detail"].replace("|", "\\|")))

    lines += ["", "## Release notes", "", "`%s` (%d characters, sections: %s)" % (
        report["notes"]["path"], report["notes"]["chars"],
        ", ".join(report["notes"]["sections"]) or "none")]

    if report.get("operations"):
        lines += ["", "## Operations", ""]
        for key in ("commit", "tag", "push", "release", "publish", "dry_run"):
            lines.append("- %s: %s" % (key, report["operations"].get(key)))

    lines += ["", "## Command", "", "```", report["release_it"].get("command") or "-", "```"]

    if report.get("release_form"):
        lines += ["", "## Web release form", "",
                  "release-it could not reach the platform API, so it generated a form to finish by hand:",
                  "", "<%s>" % report["release_form"]]

    if report.get("warnings"):
        lines += ["", "## Warnings", ""] + ["- %s" % item for item in report["warnings"]]
    if report.get("failed"):
        lines += ["", "## Failed checks", ""] + ["- %s" % item for item in report["failed"]]
    if report.get("next"):
        lines += ["", "## Next", ""] + ["- %s" % item for item in report["next"]]

    lines.append("")
    return "\n".join(lines)


def write_report(report, directory=None, stem="release-report"):
    """Write both report artifacts and return their paths."""
    directory = Path(directory).expanduser() if directory else Path(report["state"].get("dir") or ".")
    directory.mkdir(parents=True, exist_ok=True)
    json_path = directory / ("%s.json" % stem)
    md_path = directory / ("%s.md" % stem)
    json_path.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    md_path.write_text(render_markdown(report), encoding="utf-8")
    return {"json": str(json_path), "markdown": str(md_path)}


def main(argv=None):
    import argparse

    parser = argparse.ArgumentParser(prog="rls_report.py",
                                     description="Render the release report from a plan and a verification.")
    parser.add_argument("--plan", required=True)
    parser.add_argument("--record", help="a release run record written by rls_release.py")
    parser.add_argument("--verification", help="a verification report written by rls_verify.py")
    parser.add_argument("--output-dir")
    parser.add_argument("--stdout", action="store_true", help="print the markdown")
    args = parser.parse_args(argv)

    plan = json.loads(Path(args.plan).expanduser().read_text(encoding="utf-8"))
    record = json.loads(Path(args.record).expanduser().read_text(encoding="utf-8")) if args.record else {}
    verification = (
        json.loads(Path(args.verification).expanduser().read_text(encoding="utf-8"))
        if args.verification else {}
    )

    report = build_report(plan, record, verification)
    written = write_report(report, args.output_dir)
    print("verdict  %s" % report["verdict_line"])
    print("json     %s" % written["json"])
    print("markdown %s" % written["markdown"])
    if args.stdout:
        print()
        print(render_markdown(report))
    return 0


if __name__ == "__main__":
    sys.exit(main())
