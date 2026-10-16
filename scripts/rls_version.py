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

# A declared version is a release identifier that is not a semantic version, e.g.
# 5.1.7.12_weiyuan_G200464803_20261016_8aef61de.  ez-xu/release-it keeps such a version
# verbatim (upstream truncates it to the leading semver), so the skill treats it as a
# first-class version: carried unchanged, never compared, never incremented.
#
# release-it decides "verbatim" with semver.coerce(): it keeps the string only when the
# coerced semver is a true *prefix* and what follows continues numerically.  Everything
# else is silently rewritten, which for a release means a tag nobody asked for -- so the
# cases release-it would rewrite are refused here with the exact corrected command.
_COERCE = re.compile(r"(?:^|[^\d])(\d{1,16})(?:\.(\d{1,16}))?(?:\.(\d{1,16}))?")
_CONTINUATION = re.compile(r"^[.-]?\d")

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

# The notes lead with the feature items: a release note is a list of what is new.
FEATURES = SECTIONS["feat"]

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


def is_semver(version):
    """True for a strict semantic version."""
    return bool(_SEMVER.match(str(version or "").strip()))


def coerce(version):
    """The semantic version release-it would coerce ``version`` into, or None.

    Mirrors semver.coerce(): the first run of up to three numbers, padded to three parts.
    """
    match = _COERCE.search(str(version or "").strip())
    if not match:
        return None
    parts = [group for group in match.groups() if group is not None]
    while len(parts) < 3:
        parts.append("0")
    return "%d.%d.%d" % tuple(int(part) for part in parts[:3])


def is_declared(version):
    """True when release-it keeps ``version`` verbatim instead of coercing it."""
    text = str(version or "").strip()
    if not text or is_semver(text):
        return False
    coerced = coerce(text)
    if not coerced or not text.startswith(coerced):
        return False
    return bool(_CONTINUATION.match(text[len(coerced) :]))


def coercion_of(version):
    """The version release-it would silently substitute, or None when it keeps it."""
    text = str(version or "").strip()
    if is_semver(text) or is_declared(text):
        return None
    return coerce(text)


def split_prefix(version):
    """Split a leading v/V that release-it would drop into a coercion.

    ``V5.1.7.12_weiyuan_...`` is a *tag name*: release-it would coerce the whole string to
    ``5.1.7``.  Returned as ``(prefix, version)`` so the prefix can be expressed where it
    belongs (``git.tagName``) and the version stays verbatim.
    """
    text = str(version or "").strip()
    if text[:1] in ("v", "V") and is_declared(text[1:]):
        return text[0], text[1:]
    return "", text


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


def visible_sections(buckets):
    """Return the section titles the notes show, in order.

    Only the feature items are listed — a release note is a list of what is new.  A
    breaking change is shown whether or not it is a feature, because leaving one out of
    a release note is worse than a longer note.  When the release has no feature item at
    all, the highest-ranked section that does have content is shown instead, so that a
    release made only of fixes still says something.
    """
    features = buckets.get(FEATURES[0], [])
    breaking = [entry for entry in buckets.get(BREAKING[0], []) if entry not in features]
    if features or breaking:
        names = []
        if breaking:
            names.append(BREAKING[0])
        if features:
            names.append(FEATURES[0])
        return names
    for name in sorted(buckets, key=_order):
        if buckets[name]:
            return [name]
    return []


def render_notes(version, rows, previous_tag="", package=None, repository_url=""):
    """Render the release notes as a one-line-per-feature Markdown outline.

    One feature item per line: a single bullet carrying the subject it was committed
    with, its short commit id and any issue it names.  The section headings are the
    outline; nothing is explained in prose, and no boilerplate line (the package, the
    comparison base) is repeated here — the report and the links already carry those.
    ``previous_tag``, ``package`` and ``repository_url`` are kept in the signature for
    callers; only ``repository_url`` is used, to make an issue reference a link that
    still renders as a short ``#12``.
    """
    buckets = parse_commits(rows)
    lines = ["## Release %s" % version, ""]
    if not rows:
        lines.append("- no changes since the previous tag")
        return "\n".join(lines).rstrip() + "\n"
    for name in visible_sections(buckets):
        lines.append("### %s" % name)
        for entry in buckets[name]:
            # Collapse any whitespace so one requirement can never become two lines.
            text = " ".join(str(entry["text"]).split())
            prefix = "%s: " % entry["scope"] if entry["scope"] else ""
            if repository_url:
                # The subject already names its issue; make that mention a link rather
                # than naming the issue a second time on the same line.
                for ref in _ISSUE_REF.findall(entry["subject"]):
                    text = text.replace(
                        "#%s" % ref,
                        "[#%s](%s/issues/%s)" % (ref, repository_url.rstrip("/"), ref),
                    )
            lines.append("- %s%s (%s)" % (prefix, text, entry["sha"]))
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def resolve_version(current, increment=None, version=None, pre_release_id=None, pre_release_base=None):
    """Return the version the release carries, with how it was derived.

    A declared non-semver version is carried verbatim and is never compared or
    incremented: it has no ordering, so an increment cannot apply to it.  Anything
    release-it would silently coerce is refused rather than truncated, because the tag
    that resulted would not be the tag that was asked for.
    """
    if version:
        explicit = str(version).strip()
        if is_semver(explicit):
            return explicit, "explicit"
        if is_declared(explicit):
            return explicit, "declared"
        coerced = coercion_of(explicit)
        if coerced:
            raise VersionError(
                "%r is not a version release-it keeps: it would silently release %r. "
                "release-it uses a version verbatim only when the semantic part is a true "
                "prefix and the rest continues with a digit or a separator, e.g. "
                "5.1.7.12_weiyuan_G200464803_20261016_8aef61de." % (explicit, coerced)
            )
        raise VersionError("not a semantic version: %r" % (explicit,))
    if increment:
        if not is_semver(current):
            raise VersionError(
                "the latest version %r is not a semantic version, so the increment %r cannot "
                "be applied to it. Declare the exact version instead, e.g. "
                "--version 5.1.7.12_weiyuan_G200464803_20261016_8aef61de." % (current, increment)
            )
        return bump(current, increment, pre_release_id, pre_release_base), "increment:%s" % increment
    return current, "current"
