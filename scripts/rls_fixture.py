#!/usr/bin/env python3
"""Build a disposable release sandbox: a real git repository whose ``origin``
looks like GitHub but is transparently rewritten to a local bare repository.

Why the URL rewrite instead of a plain local remote:

* release-it aborts when ``git fetch`` fails, so the remote has to be reachable;
* ``parseGitUrl`` (and this skill's own provider detection) has to see a real
  GitHub URL or no release interface is chosen and no link can be predicted;
* nothing may leave the machine, and a real release is public and hard to
  withdraw, so the sandbox must be the only remote involved.

``git config url.<bare>.insteadOf <github-url>`` satisfies all three at once:
fetch, push and ``ls-remote`` all resolve to the local bare repository, while
every URL-shaped read still reports the GitHub form.

Scenarios exist so the eval cases can drive refusals as well as releases:
``clean``, ``dirty``, ``untracked``, ``tagged``, ``no-package``, ``not-a-repo``.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import stat
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import rls_shell  # noqa: E402

DEFAULT_OWNER = "ez-xu"
DEFAULT_NAME = "release-it-skill-fixture"
SCENARIOS = ("clean", "dirty", "untracked", "tagged", "no-package", "not-a-repo")

PACKAGE_JSON = {
    "name": "release-it-skill-fixture",
    "version": "1.0.0",
    "private": True,
    "description": "Disposable repository used to exercise the release-it-skill pipeline.",
    "license": "MIT",
}

COMMITS = (
    ("feat", "add release plan builder", "src/plan.js"),
    ("fix", "keep the tag prefix when the latest tag has one", "src/tag.js"),
    ("docs", "describe the release interfaces", "docs/interfaces.md"),
    ("feat", "record the published package link", "src/links.js"),
)


def _must(repo, *args):
    code, out = rls_shell.git(repo, *args)
    if code != 0:
        raise RuntimeError("git %s failed in %s: %s" % (" ".join(args), repo, out))
    return out


def _write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def build(dest, scenario="clean", owner=DEFAULT_OWNER, name=DEFAULT_NAME, force=False):
    """Create the sandbox at ``dest`` and return a summary dictionary."""
    if scenario not in SCENARIOS:
        raise ValueError("unknown scenario %r" % (scenario,))

    dest = Path(dest).expanduser().resolve()
    bare = dest.parent / (dest.name + "-remote.git")

    if dest.exists():
        if not force:
            raise FileExistsError("%s exists; pass force to replace it" % dest)
        _remove(dest)
        _remove(bare)

    if scenario == "not-a-repo":
        dest.mkdir(parents=True, exist_ok=True)
        _write(dest / "README.md", "# not a repository\n")
        return {"repo": str(dest), "scenario": scenario, "remote": "", "bare": "", "tags": []}

    dest.mkdir(parents=True)
    _remove(bare)
    bare.parent.mkdir(parents=True, exist_ok=True)
    _must(dest.parent, "init", "--bare", "--initial-branch=main", str(bare))
    _must(dest, "init", "--initial-branch=main")
    _must(dest, "config", "user.name", "release-it-skill fixture")
    _must(dest, "config", "user.email", "fixture@example.invalid")
    _must(dest, "config", "commit.gpgsign", "false")
    _must(dest, "config", "tag.gpgsign", "false")

    github_url = "https://github.com/%s/%s.git" % (owner, name)
    _must(dest, "remote", "add", "origin", github_url)
    _must(dest, "config", "url.%s.insteadOf" % bare.as_posix(), github_url)

    if scenario != "no-package":
        package = dict(PACKAGE_JSON, name=name)
        _write(dest / "package.json", json.dumps(package, indent=2) + "\n")
    _write(dest / "README.md", "# %s\n\nFixture repository for release-it-skill.\n" % name)
    _write(dest / ".gitignore", "node_modules/\n")

    _must(dest, "add", "-A")
    _must(dest, "commit", "-m", "chore: initial commit")
    _must(dest, "push", "-u", "origin", "main")

    _must(dest, "tag", "-a", "v1.0.0", "-m", "Release 1.0.0")
    _must(dest, "push", "origin", "v1.0.0")

    for kind, subject, path in COMMITS:
        _write(dest / path, "// %s\n" % subject)
        _must(dest, "add", "-A")
        _must(dest, "commit", "-m", "%s: %s" % (kind, subject))

    if scenario == "tagged":
        _must(dest, "tag", "-a", "v1.1.0", "-m", "Release 1.1.0")
        _must(dest, "push", "origin", "v1.1.0")
    if scenario == "dirty":
        _write(dest / "src" / "plan.js", "// uncommitted edit\n")
    if scenario == "untracked":
        _write(dest / "scratch.txt", "uncommitted\n")

    tags = [line.strip() for line in _must(dest, "tag", "--list").splitlines() if line.strip()]
    return {
        "repo": str(dest),
        "scenario": scenario,
        "remote": github_url,
        "bare": str(bare),
        "tags": tags,
        "package": None if scenario == "no-package" else name,
    }


def _force_writable(func, path, _exc):
    """git writes its object files read-only, which blocks rmtree on Windows."""
    try:
        os.chmod(path, stat.S_IWRITE)
        func(path)
    except OSError:
        pass


def _remove(path):
    path = Path(path)
    if path.is_dir():
        shutil.rmtree(path, onerror=_force_writable)
    elif path.exists():
        os.chmod(path, stat.S_IWRITE)
        path.unlink()


def main(argv=None):
    parser = argparse.ArgumentParser(prog="rls_fixture.py",
                                     description="Build a disposable release sandbox.")
    parser.add_argument("dest", help="directory to create the sandbox in")
    parser.add_argument("--scenario", choices=SCENARIOS, default="clean")
    parser.add_argument("--owner", default=DEFAULT_OWNER)
    parser.add_argument("--name", default=DEFAULT_NAME)
    parser.add_argument("--force", action="store_true", help="replace an existing sandbox")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)

    summary = build(args.dest, args.scenario, args.owner, args.name, args.force)
    if args.json:
        print(json.dumps(summary, indent=2, ensure_ascii=False))
    else:
        print("fixture  %s" % summary["repo"])
        print("scenario %s" % summary["scenario"])
        if summary["remote"]:
            print("remote   %s -> %s" % (summary["remote"], summary["bare"]))
        print("tags     %s" % (", ".join(summary["tags"]) or "(none)"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
