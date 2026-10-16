#!/usr/bin/env python3
"""Version arithmetic and release notes.

Two jobs that both have to be deterministic, because a release is public and cannot
be withdrawn:

* work out the version a release carries, from an explicit version or an increment
* turn the commits since the last tag into release notes

The notes are Conventional-Commits aware.  A commit that does not follow the
convention still appears, under "Other changes", rather than being dropped -- a
release that silently omits a change is worse than an untidy one.
"""

from __future__ import annotations

import re

_SEMVER = re.compile(
    r"^(?P<major>0|[1-9]\d*)\.(?P<minor>0|[1-9]\d*)\.(?P<patch>0|[1-9]\d*)"
    r"(?:-(?P<pre>[0-9A-Za-z\-.]+))?(?:\+(?P<build>[0-9A-Za-z\-.]+))?$"
)

INCREMENTS = (
    "major",
    "minor",
    "patch",
    "premajor",
    "preminor",
    "prepatch",
    "prerelease",
)

# Conventional Commits type -> (section title, order).  Anything unlisted lands in
# "Other changes" so that a non-conforming history is never silently truncated.
SECTIONS = {
    "feat": ("Features", 10),
    "fix": ("Bug Fixes", 20),
    "perf": ("Performance", 30),
    "refactor": ("Refactoring", 40),
    "docs": ("Documentation", 50),
    "test": ("Tests", 60),
    "build": ("Build", 70),
    "ci": ("Continuous Integration", 80),
    "style": ("Styles", 90),
    "chore": ("Chores", 100),
    "revert": ("Reverts", 110),
}
OTHER = ("Other changes", 900)
BREAKING = ("⚠ Breaking Changes", 0)

_CONVENTIONAL = re.compile(
    r"^(?P<type>[a-zA-Z]+)(?:\((?P<scope>[^)]*)\))?(?P<breaking>!)?:\s*(?P<subject>.+)$"
)
_ISSUE_REF = re.compile(r"#(\d+)")


class VersionError(ValueError):
    """The version could not be parsed or the increment is not a known one."""


def parse(version):
    match = _SEMVER.match(str(version or "").strip())
    if not match:
        raise VersionError("not a semantic version: %r" % (version,))
    return {
        "major": int(match.group("major")),
        "minor": int(match.group("minor")),
        "patch": int(match.group("patch")),
        "pre": match.group("pre") or "",
        "build": match.group("build") or "",
    }


def render(parts):
    text = "%d.%d.%d" % (parts["major"], parts["minor"], parts["patch"])
    if parts.get("pre"):
        text += "-" + parts["pre"]
    if parts.get("build"):
        text += "+" + parts["build"]
    return text


def compare(left, right):
    """Return -1, 0 or 1 for two semantic versions, honouring prerelease ordering."""
    a, b = parse(left), parse(right)
    for key in ("major", "minor", "patch"):
        if a[key] != b[key]:
            return -1 if a[key] < b[key] else 1
    if a["pre"] == b["pre"]:
        return 0
    if not a["pre"]:
        return 1
    if not b["pre"]:
        return -1
    return -1 if _pre_key(a["pre"]) < _pre_key(b["pre"]) else 1


def _pre_key(pre):
    key = []
    for part in pre.split("."):
        key.append((0, int(part), "") if part.isdigit() else (1, 0, part))
    return key


def _initial_pre(pre_release_id, pre_release_base):
    identifier = pre_release_id or "alpha"
    base = pre_release_base
    if base is None:
        base = 0
    return "%s.%d" % (identifier, int(base))


def _bump_pre(parts, pre_release_id, pre_release_base):
    current = parts.get("pre") or ""
    identifier = pre_release_id or (current.split(".")[0] if current else "alpha")
    tail = current.split(".")[1:]
    if current and tail and tail[-1].isdigit():
        numbers = list(tail)
        numbers[-1] = str(int(numbers[-1]) + 1)
        return "%s.%s" % (identifier, ".".join(numbers))
    if current and current.split(".")[0] == identifier:
        return "%s.0" % identifier
    return _initial_pre(identifier, pre_release_base)


def bump(version, increment, pre_release_id=None, pre_release_base=None):
    """Return the next version for ``increment`` applied to ``version``."""
    name = str(increment or "").strip().lower()
    if name not in INCREMENTS:
        raise VersionError(
            "unknown increment %r; expected one of %s" % (increment, ", ".join(INCREMENTS))
        )
    parts = parse(version)
    major, minor, patch = parts["major"], parts["minor"], parts["patch"]
    pre = parts["pre"]

    if name == "major":
        return render({"major": major + 1, "minor": 0, "patch": 0, "pre": "", "build": ""})
    if name == "minor":
        return render({"major": major, "minor": minor + 1, "patch": 0, "pre": "", "build": ""})
    if name == "patch":
        return render({"major": major, "minor": minor, "patch": patch + 1, "pre": "", "build": ""})
    if name == "premajor":
        base = {"major": major + 1, "minor": 0, "patch": 0, "pre": "", "build": ""}
    elif name == "preminor":
        base = {"major": major, "minor": minor + 1, "patch": 0, "pre": "", "build": ""}
    elif name == "prepatch":
        base = {"major": major, "minor": minor, "patch": patch + 1, "pre": "", "build": ""}
    else:
        base = {"major": major, "minor": minor, "patch": patch, "pre": "", "build": ""}
        if not pre:
            base["patch"] = patch + 1
    base["pre"] = _bump_pre(parts, pre_release_id, pre_release_base) if pre or name == "prerelease" else _initial_pre(pre_release_id, pre_release_base)
    return render(base)


def normalise_tag(tag_name, prefix):
    """Strip the configured tag prefix so a tag name can be compared to a version."""
    text = str(tag_name or "")
    if prefix and text.startswith(prefix):
        return text[len(prefix) :]
    return text


def parse_commits(rows):
    """Group 'sha<TAB>subject' rows into Conventional-Commits sections."""
    buckets = {}
    for sha, subject in rows:
        short = sha[:7]
        match = _CONVENTIONAL.match(subject)
        if match:
            kind = match.group("type").lower()
            scope = (match.group("scope") or "").strip()
            text = match.group("subject").strip()
            breaking = bool(match.group("breaking"))
        else:
            kind, scope, text, breaking = "", "", subject.strip(), False
        entry = {"sha": short, "scope": scope, "text": text, "subject": subject.strip()}
        if breaking:
            buckets.setdefault(BREAKING[0], []).append(entry)
        title = SECTIONS.get(kind, OTHER)[0]
        buckets.setdefault(title, []).append(entry)
    return buckets


def _order(title):
    for key, (name, rank) in SECTIONS.items():
        if name == title:
            return rank
    if title == OTHER[0]:
        return OTHER[1]
    if title == BREAKING[0]:
        return BREAKING[1]
    return 500


def render_notes(version, rows, previous_tag="", package=None, repository_url=""):
    """Render release notes as Markdown from commit rows."""
    buckets = parse_commits(rows)
    title = "Release %s" % version
    lines = ["## %s" % title, ""]
    if package:
        lines.append("Package: `%s`" % package)
        lines.append("")
    if previous_tag:
        lines.append("Changes since `%s`." % previous_tag)
        lines.append("")
    if not rows:
        lines.append("No commits since the previous tag.")
        lines.append("")
    for name in sorted(buckets, key=_order):
        lines.append("### %s" % name)
        lines.append("")
        for entry in buckets[name]:
            label = "**%s:** " % entry["scope"] if entry["scope"] else ""
            suffix = " (%s)" % entry["sha"]
            refs = _ISSUE_REF.findall(entry["subject"])
            if repository_url and refs:
                suffix += " " + " ".join(
                    "[#%s](%s/issues/%s)" % (ref, repository_url.rstrip("/"), ref) for ref in refs
                )
            lines.append("* %s%s%s" % (label, entry["text"], suffix))
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def resolve_version(current, increment=None, version=None, pre_release_id=None, pre_release_base=None):
    """Return the version the release carries, with how it was derived."""
    if version:
        explicit = str(version).strip()
        parse(explicit)
        return explicit, "explicit"
    if increment:
        return bump(current, increment, pre_release_id, pre_release_base), "increment:%s" % increment
    return current, "current"
