#!/usr/bin/env python3
"""Grade one eval criterion against one scenario verdict.

    python3 scripts/eval_check.py out/clean-release.json closedLoopConsistent

Exit 0 means the criterion holds for that scenario, 1 means it does not.  A
criterion that a scenario does not exercise passes with a note, so the same six
criteria can be graded over every case in the suite.

This exists instead of ``grep`` because grep is only present on Windows when
Git's ``usr/bin`` happens to be on PATH, and an eval that silently stops
checking anything is worse than no eval.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

from rls_version import is_semver

CRITERIA = (
    "harnessRan",
    "expectationMet",
    "refusalIsSafe",
    "closedLoopConsistent",
    "notesNotEmpty",
    "linksComplete",
)

REQUIRED_LINKS = ("repository", "tag", "release", "compare")


def load(path):
    try:
        return json.loads(Path(path).expanduser().read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        return {"_load_error": "%s: %s" % (type(exc).__name__, exc)}


def not_applicable(why):
    return True, why


def harness_ran(v):
    if v.get("_load_error"):
        return False, "the verdict could not be read (%s)" % v["_load_error"]
    if not v.get("scenario"):
        return False, "the verdict names no scenario"
    if not isinstance(v.get("exit_code"), int):
        return False, "the verdict has no numeric exit code"
    return True, "scenario %s ran with exit code %s" % (v["scenario"], v["exit_code"])


def expectation_met(v):
    if not harness_ran(v)[0]:
        return False, "no usable verdict"
    if v.get("satisfied"):
        return True, v.get("reason", "the run did what the scenario requires")
    return False, "expected %r: %s" % (v.get("expect"), v.get("reason", "the run did something else"))


def refusal_is_safe(v):
    if v.get("expect") != "refused":
        return not_applicable("not a refusal scenario")
    if not v.get("untouched"):
        return False, ("a refusal changed the repository: HEAD %s -> %s, tags %s -> %s"
                       % (v.get("before", {}).get("head", "?")[:12], v.get("after", {}).get("head", "?")[:12],
                          v.get("before", {}).get("tags"), v.get("after", {}).get("tags")))
    if v.get("added_tags"):
        return False, "a refusal still created %s" % v["added_tags"]
    if v.get("exit_code") != 2:
        return False, "a refusal must exit 2, got %s" % v.get("exit_code")
    return True, "refused with exit 2 and nothing changed"


def closed_loop_consistent(v):
    if v.get("expect") != "released":
        return not_applicable("not a release scenario")
    problems = []
    if v.get("exit_code") != 0:
        problems.append("exit code %s" % v.get("exit_code"))
    if not v.get("consistent"):
        problems.append("the verification did not find one commit (verdict %s)" % (v.get("verdict") or "none"))
    if v.get("tag") not in (v.get("after", {}).get("tags") or []):
        problems.append("tag %s is missing locally" % v.get("tag"))
    if not v.get("tag_commit"):
        problems.append("the tag does not resolve to a commit")
    if v.get("tag_commit") and v["tag_commit"] != v.get("after", {}).get("head"):
        problems.append("the tag resolves to %s but HEAD is %s"
                        % (v["tag_commit"][:12], (v.get("after", {}).get("head") or "?")[:12]))
    if v.get("remote_tag_commit") and v["remote_tag_commit"] != v.get("tag_commit"):
        problems.append("origin has the tag at %s, locally it is %s"
                        % (v["remote_tag_commit"][:12], (v.get("tag_commit") or "?")[:12]))
    # A declared non-semver version has no manifest carrier: npm cannot hold such a
    # version, so the npm plugin is switched off and package.json deliberately keeps its
    # previous value.  The manifest clause therefore only applies to semantic versions.
    if v.get("version") and is_semver(str(v["version"])) and v.get("after", {}).get("version") != v["version"]:
        problems.append("the manifest says %s but the release is %s"
                        % (v.get("after", {}).get("version"), v["version"]))
    if problems:
        return False, "; ".join(problems)
    return True, "%s, HEAD and origin all point at %s" % (v.get("tag"), (v.get("tag_commit") or "")[:12])


def notes_not_empty(v):
    if v.get("expect") != "released":
        return not_applicable("not a release scenario")
    sections = v.get("notes_sections") or []
    if not sections:
        return False, "the release notes have no sections"
    if not v.get("notes_chars"):
        return False, "the release notes are empty"
    return True, "release notes carry %s" % ", ".join(sections)


def links_complete(v):
    if v.get("expect") != "released":
        return not_applicable("not a release scenario")
    links = v.get("links") or {}
    missing = [key for key in REQUIRED_LINKS if not links.get(key)]
    if missing:
        return False, "missing link(s): %s" % ", ".join(missing)
    return True, "recorded %s" % ", ".join(REQUIRED_LINKS)


CHECKS = {
    "harnessRan": harness_ran,
    "expectationMet": expectation_met,
    "refusalIsSafe": refusal_is_safe,
    "closedLoopConsistent": closed_loop_consistent,
    "notesNotEmpty": notes_not_empty,
    "linksComplete": links_complete,
}


def main(argv=None):
    if not argv:
        argv = sys.argv[1:]
    if len(argv) != 2 or argv[1] not in CHECKS:
        sys.stderr.write("usage: eval_check.py <verdict.json> <%s>\n" % "|".join(CRITERIA))
        return 2

    verdict_path, criterion = argv
    verdict = load(verdict_path)
    ok, detail = CHECKS[criterion](verdict)
    print("%-22s %-4s %s" % (criterion, "pass" if ok else "FAIL", detail))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
