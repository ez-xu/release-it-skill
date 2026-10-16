#!/usr/bin/env python3
"""Read the facts about the repository that is about to be released.

Nothing here mutates anything.  This is the read-only half of a release: which
platform the origin points at, which branch and working tree state the release
would start from, which version the manifest currently declares, and which tag is
the newest one that already exists.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import rls_shell

MANIFEST_CANDIDATES = ("package.json",)

_REMOTE_PATTERNS = (
    re.compile(r"^(?P<scheme>https?|git|ssh)://(?:[^@/]+@)?(?P<host>[^/:]+)(?::\d+)?/(?P<path>.+?)(?:\.git)?/?$"),
    # scp-like `[user@]host:path`.  The host needs two or more characters and the
    # path must not start with a separator, otherwise a Windows drive letter
    # (`C:/Users/...` -> host "c") is misread as a hostname.
    re.compile(r"^(?:[^@]+@)?(?P<host>[^:/@]{2,}):(?P<path>[^/\\].*?)(?:\.git)?/?$"),
)


def configured_remote_url(repo, name="origin"):
    """The remote URL as configured, before ``url.<base>.insteadOf`` rewriting.

    ``git remote get-url`` applies that rewriting, so a repository behind a
    mirror, a proxy, or an offline fixture reports a local path even though the
    provider and every link have to be decided from the configured URL.  The
    configured value is preferred and the resolved one is the fallback.
    """
    out, ok = rls_shell.git_ok(repo, "config", "--get", "remote.%s.url" % name)
    configured = out.strip() if ok else ""
    if configured:
        return configured, True
    out, ok = rls_shell.git_ok(repo, "remote", "get-url", name)
    resolved = out.strip() if ok else ""
    return resolved, bool(resolved)


def parse_remote(url):
    """Split a git remote URL into provider, host and project path."""
    text = str(url or "").strip()
    if not text:
        return {"provider": "", "host": "", "project": "", "url": ""}
    host = ""
    project = ""
    for pattern in _REMOTE_PATTERNS:
        match = pattern.match(text)
        if match:
            host = match.group("host").lower()
            project = match.group("path").strip("/")
            break
    if "github" in host:
        provider = "github"
    elif "gitlab" in host:
        provider = "gitlab"
    else:
        provider = ""
    return {"provider": provider, "host": host, "project": project, "url": text}


def find_manifest(repo, manifest=None):
    """Return the version manifest path, or None when the repository has none."""
    root = Path(repo)
    if manifest:
        candidate = Path(manifest)
        candidate = candidate if candidate.is_absolute() else root / candidate
        return candidate if candidate.is_file() else None
    for name in MANIFEST_CANDIDATES:
        candidate = root / name
        if candidate.is_file():
            return candidate
    return None


def read_manifest(path):
    """Return (name, version) from a version manifest.  Raises ValueError when absent."""
    if path is None:
        raise ValueError("no version manifest found in the repository")
    try:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise ValueError("cannot read %s: %s" % (path, exc)) from exc
    version = data.get("version")
    if not isinstance(version, str) or not version.strip():
        raise ValueError("%s does not declare a version field" % path)
    name = data.get("name")
    return (name if isinstance(name, str) and name.strip() else None), version.strip()


def remote_tags(repo, timeout=60):
    """Return the tag names that already exist on origin."""
    out, ok = rls_shell.git_ok(repo, "ls-remote", "--tags", "origin", timeout=timeout)
    if not ok:
        return []
    names = []
    for line in out.splitlines():
        parts = line.split()
        if len(parts) < 2:
            continue
        ref = parts[1]
        if not ref.startswith("refs/tags/"):
            continue
        name = ref[len("refs/tags/") :]
        if name.endswith("^{}"):
            name = name[:-3]
        if name and name not in names:
            names.append(name)
    return names


def tag_exists(repo, tag, timeout=60):
    return tag in remote_tags(repo, timeout=timeout)


def commit_for_tag(repo, tag):
    """Resolve a tag to the commit it names, dereferencing an annotated tag.

    An annotated tag is a tag object that points at a commit, so ``rev-list -n 1``
    on the tag name is what resolves it to that commit rather than to the tag object.
    """
    out, ok = rls_shell.git_ok(repo, "rev-list", "-n", "1", tag)
    return out.strip() if ok else ""


def latest_tag(repo, tag_match=None):
    """Return the newest reachable tag, optionally filtered by a prefix pattern.

    ``tag_match`` is the release-it style pattern: ``v*`` becomes a ``v`` prefix and
    ``*`` becomes "any".  A plain string is treated as a literal prefix.
    """
    args = ["tag", "--sort=-v:refname", "--merged", "HEAD"]
    if tag_match:
        pattern = str(tag_match).replace("*", "*")
        args += ["-l", pattern]
    out, ok = rls_shell.git_ok(repo, *args)
    if not ok or not out.strip():
        return ""
    return out.strip().splitlines()[0].strip()


def reachable_tags(repo, tag_match=None):
    args = ["tag", "--sort=-v:refname", "--merged", "HEAD"]
    if tag_match:
        args += ["-l", str(tag_match)]
    out, ok = rls_shell.git_ok(repo, *args)
    if not ok:
        return []
    return [line.strip() for line in out.splitlines() if line.strip()]


def commits_between(repo, start, end="HEAD", path=""):
    """Return 'sha<TAB>subject' lines for the commits in start..end."""
    args = ["log", "--no-merges", "--pretty=format:%H%x09%s"]
    if start:
        args.append("%s..%s" % (start, end))
    else:
        args.append(end)
    if path:
        args += ["--", path]
    out, ok = rls_shell.git_ok(repo, *args)
    if not ok or not out.strip():
        return []
    rows = []
    for line in out.splitlines():
        if "\t" not in line:
            continue
        sha, subject = line.split("\t", 1)
        rows.append((sha.strip(), subject.strip()))
    return rows


def inspect(repo=".", manifest=None, tag_match=None):
    """Collect every read-only fact the pipeline needs about the repository."""
    root = Path(repo).expanduser().resolve()
    facts = {
        "repo": str(root),
        "is_worktree": False,
        "remote": {"provider": "", "host": "", "project": "", "url": ""},
        "provider": "",
        "project": "",
        "branch": "",
        "detached": False,
        "clean": False,
        "dirty_paths": [],
        "has_upstream": False,
        "manifest": None,
        "package": None,
        "version": None,
        "manifest_error": None,
        "latest_tag": "",
        "reachable_tags": [],
        "problems": [],
    }

    out, ok = rls_shell.git_ok(root, "rev-parse", "--is-inside-work-tree")
    facts["is_worktree"] = bool(ok and out.strip() == "true")
    if not facts["is_worktree"]:
        facts["problems"].append("%s is not a git work tree" % root)
        return facts

    url, ok = configured_remote_url(root)
    facts["remote"] = parse_remote(url if ok else "")
    facts["provider"] = facts["remote"]["provider"]
    facts["project"] = facts["remote"]["project"]
    if not facts["remote"]["url"]:
        facts["problems"].append("origin has no remote URL")
    elif not facts["provider"]:
        facts["problems"].append(
            "origin host %r is neither GitHub nor GitLab, so no release interface is known"
            % facts["remote"]["host"]
        )

    branch, ok = rls_shell.git_ok(root, "symbolic-ref", "--short", "HEAD")
    facts["branch"] = branch.strip() if ok else ""
    facts["detached"] = not facts["branch"]

    status, ok = rls_shell.git_ok(root, "status", "--porcelain")
    dirty = [line for line in status.splitlines() if line.strip()] if ok else []
    facts["dirty_paths"] = dirty
    facts["clean"] = ok and not dirty

    _, ok = rls_shell.git_ok(root, "rev-parse", "--verify", "--quiet", "@{upstream}")
    facts["has_upstream"] = bool(ok)

    path = find_manifest(root, manifest)
    facts["manifest"] = str(path) if path else None
    try:
        name, version = read_manifest(path)
        facts["package"], facts["version"] = name, version
    except ValueError as exc:
        facts["manifest_error"] = str(exc)

    facts["latest_tag"] = latest_tag(root, tag_match)
    facts["reachable_tags"] = reachable_tags(root, tag_match)

    if facts["detached"]:
        facts["problems"].append("HEAD is detached; a release needs a branch")
    if not facts["clean"]:
        facts["problems"].append("working tree is not clean")
    if not facts["has_upstream"]:
        facts["problems"].append("the current branch has no upstream")
    if facts["manifest_error"]:
        facts["problems"].append(facts["manifest_error"])

    return facts


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", default=".")
    parser.add_argument("--manifest")
    parser.add_argument("--tag-match")
    parsed = parser.parse_args()
    print(json.dumps(inspect(parsed.repo, parsed.manifest, parsed.tag_match), indent=2, ensure_ascii=False))
