#!/usr/bin/env python3
"""Build the release plan: the release-it configuration, the exact command line
and every link the release will produce.

Four upstream facts shape this module, and each one is a trap if ignored:

* ``github.release`` and ``gitlab.release`` default to **false**, so a stock
  release-it never creates a platform release.  The plan writes them explicitly.
* ``github.releaseNotes`` / ``gitlab.releaseNotes`` are **shell commands whose
  stdout becomes the notes**, not the notes themselves.  The plan therefore
  writes the notes to a file plus a tiny ESM printer and points the option at
  the printer, which keeps multi-line notes out of argv quoting entirely.
* Arrays in a higher-priority config **replace** the default rather than merge
  (release-it merges with ``defu``), so every array the plan sets is complete.
* release-it accepts exactly **one** positional argument, which is the increment
  or an explicit version.  The plan always resolves a concrete version and passes
  that, so the release never depends on the interactive prompt or on the silent
  ``patch`` fallback that CI mode would otherwise choose.

Generated files never touch the working tree: they live in the release-it-skill
directory inside the repository's git dir, which keeps ``requireCleanWorkingDir``
armed while still leaving the plan, the notes and the config next to the repo.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import rls_shell  # noqa: E402
from rls_repo import inspect  # noqa: E402
from rls_version import compare, render_notes, resolve_version  # noqa: E402

SKILL_NAME = "release-it-skill"
PLAN_VERSION = 1
DEFAULT_RELEASE_IT = "21.1.1"
STATE_DIR_NAME = "release-it-skill"
NPM_PACKAGE_URL = "https://www.npmjs.com/package"
SCHEMA_URL = "https://raw.githubusercontent.com/release-it/release-it/main/schema/release-it.json"

#: ``npm.publishPackageManager`` only supports npm, pnpm and bun upstream; yarn is
#: deliberately absent because release-it does not implement it.
LOCKFILE_PACKAGE_MANAGER = (
    ("pnpm-lock.yaml", "pnpm"),
    ("bun.lockb", "bun"),
    ("bun.lock", "bun"),
)

PRINT_NOTES_JS = """\
// Written by release-it-skill. Prints release-notes.md so that release-it can
// use it as `git.changelog` and as `github.releaseNotes` / `gitlab.releaseNotes`.
import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const here = dirname(fileURLToPath(import.meta.url));
process.stdout.write(readFileSync(join(here, "release-notes.md"), "utf8"));
"""


# --------------------------------------------------------------------------- #
# locations
# --------------------------------------------------------------------------- #
def git_dir(repo):
    """Absolute path of the repository's git directory, or None."""
    out, ok = rls_shell.git_ok(repo, "rev-parse", "--absolute-git-dir")
    if ok and out.strip():
        return Path(out.strip())
    out, ok = rls_shell.git_ok(repo, "rev-parse", "--git-dir")
    if ok and out.strip():
        candidate = Path(out.strip())
        if not candidate.is_absolute():
            candidate = Path(repo).resolve() / candidate
        return candidate
    return None


def default_state_dir(repo):
    """Where generated files go.  Never inside the tracked working tree."""
    directory = git_dir(repo)
    if directory is not None:
        return directory / STATE_DIR_NAME
    return Path(repo).resolve() / (".%s" % STATE_DIR_NAME)


def notes_command(state_dir):
    """The shell command release-it runs to obtain the release notes."""
    script = Path(state_dir).resolve() / "print-notes.mjs"
    return 'node "%s"' % str(script).replace("\\", "/")


# --------------------------------------------------------------------------- #
# small detections
# --------------------------------------------------------------------------- #
def detect_package_manager(repo):
    root = Path(repo)
    for filename, manager in LOCKFILE_PACKAGE_MANAGER:
        if (root / filename).exists():
            return manager
    return "npm"


def node_version():
    code, out, _ = rls_shell.run(["node", "--version"], timeout=30)
    if code != 0:
        return ""
    return out.strip().lstrip("v")


#: release-it 21.1.1 declares ``^22.22.2 || ^24.15.0 || >=26.0.0``.
ENGINE_RANGES = ((22, 22, 2), (24, 15, 0))


def engine_ok(node):
    """Whether this node satisfies release-it's engines field.  Unknown -> True."""
    try:
        major, minor, patch = (int(part) for part in str(node).split(".")[:3])
    except (TypeError, ValueError):
        return True
    if major >= 26:
        return True
    for r_major, r_minor, r_patch in ENGINE_RANGES:
        if major == r_major:
            return (minor, patch) >= (r_minor, r_patch)
    return False


def tag_prefix_for(facts, explicit=None):
    """release-it derives ``v${version}`` only when the latest tag starts with v."""
    if explicit is not None:
        return explicit
    return "v" if str(facts.get("latest_tag") or "").startswith("v") else ""


def resolve_runner(repo, pin=DEFAULT_RELEASE_IT):
    """Prefer an installed release-it, then PATH, then a pinned npx download."""
    root = Path(repo)
    names = ["release-it.cmd", "release-it"] if os.name == "nt" else ["release-it"]
    for name in names:
        candidate = root / "node_modules" / ".bin" / name
        if candidate.exists():
            return {"kind": "local", "program": str(candidate), "prefix": [], "pin": None}
    if rls_shell.available("release-it"):
        return {"kind": "path", "program": "release-it", "prefix": [], "pin": None}
    return {
        "kind": "npx",
        "program": "npx",
        "prefix": ["--yes", "release-it@%s" % pin],
        "pin": pin,
    }


# --------------------------------------------------------------------------- #
# links
# --------------------------------------------------------------------------- #
def build_links(facts, provider, tag, version, package, publishing):
    host = (facts.get("remote") or {}).get("host") or ""
    project = facts.get("project") or ""
    base = "https://%s/%s" % (host, project) if host and project else ""
    if not base:
        return {"repository": "", "tag": "", "release": "", "package": "",
                "registry": "", "compare": "", "api": ""}

    previous = facts.get("latest_tag") or ""
    if provider == "github":
        tag_url = "%s/releases/tag/%s" % (base, tag)
        release_url = tag_url
        compare_url = "%s/compare/%s...%s" % (base, previous, tag) if previous else ""
        api_url = "https://api.github.com/repos/%s/releases/tags/%s" % (project, tag)
    elif provider == "gitlab":
        tag_url = "%s/-/tags/%s" % (base, tag)
        release_url = "%s/-/releases/%s" % (base, tag)
        compare_url = "%s/-/compare/%s...%s" % (base, previous, tag) if previous else ""
        api_url = "%s/-/releases/%s" % (base, tag)
    else:
        tag_url = release_url = compare_url = api_url = ""

    # The package page is recorded whether or not this run publishes: it is the
    # canonical address of the package the tag names, and "publishing" only says
    # whether this run is the one that put it there.
    package_url = "%s/%s/v/%s" % (NPM_PACKAGE_URL, package, version) if package else ""

    return {
        "repository": base,
        "tag": tag_url,
        "release": release_url,
        "package": package_url,
        "registry": "https://registry.npmjs.org/%s" % package if package else "",
        "compare": compare_url,
        "api": api_url,
        "package_published": bool(publishing and package),
    }


# --------------------------------------------------------------------------- #
# configuration
# --------------------------------------------------------------------------- #
def build_config(facts, opts, state_dir):
    """The effective release-it configuration, with every array written in full."""
    provider = opts["provider"]
    prefix = opts["tag_prefix"]
    notes = notes_command(state_dir)

    git = {
        "requireCleanWorkingDir": not opts["allow_dirty"],
        "requireUpstream": not opts["allow_no_upstream"],
        "commit": True,
        "commitMessage": opts["commit_message"],
        "tag": True,
        "tagName": "%s${version}" % prefix,
        "tagAnnotation": opts["tag_annotation"] or None,
        "push": True,
        "pushArgs": ["--follow-tags"],
        "changelog": notes,
    }
    if opts["require_branch"]:
        git["requireBranch"] = opts["require_branch"]

    npm = {
        "publish": bool(opts["publish"]),
        "publishPath": ".",
        "publishPackageManager": opts["publish_package_manager"],
    }

    github = {
        "release": bool(opts["release"] and provider == "github"),
        "releaseName": opts["release_name"],
        "releaseNotes": notes,
        "autoGenerate": bool(opts["auto_generate"]),
        "draft": bool(opts["draft"]),
        "preRelease": bool(opts["prerelease"]),
    }
    if opts["assets"]:
        github["assets"] = list(opts["assets"])

    gitlab = {
        "release": bool(opts["release"] and provider == "gitlab"),
        "releaseName": opts["release_name"],
        "releaseNotes": notes,
    }
    if opts["assets"]:
        gitlab["assets"] = list(opts["assets"])
    if provider == "gitlab":
        if opts["draft"]:
            gitlab["draft"] = True
        if opts["prerelease"]:
            gitlab["preRelease"] = True

    return {"$schema": SCHEMA_URL, "git": git, "npm": npm, "github": github, "gitlab": gitlab}


def build_argv(opts, runner, config_path, version):
    """The complete argv, program first, so it can be executed as-is.

    release-it accepts exactly one positional argument; this skill always passes
    the already-resolved version so nothing depends on a prompt or on the silent
    ``patch`` fallback that CI mode would otherwise pick.
    """
    argv = [runner["program"]]
    argv += list(runner["prefix"])
    argv.append("--ci")
    argv += ["--config", str(config_path)]
    if opts["dry_run"]:
        argv.append("--dry-run")
    if not opts["publish"]:
        argv.append("--no-npm.publish")
    if not opts["release"]:
        argv.append("--no-github.release")
        argv.append("--no-gitlab.release")
    argv.append(version)
    return argv


# --------------------------------------------------------------------------- #
# the plan
# --------------------------------------------------------------------------- #
def assess(facts, opts, version, tag, state_dir):
    """Return (blockers, warnings) as lists of human-readable strings."""
    blockers = []
    warnings = []

    for problem in facts.get("problems", []):
        if problem == "working tree is not clean" and opts["allow_dirty"]:
            warnings.append(
                "the working tree is dirty and --allow-dirty was given, so "
                "git.requireCleanWorkingDir is false in the generated config"
            )
            continue
        if problem == "the current branch has no upstream" and opts["allow_no_upstream"]:
            warnings.append(
                "the branch has no upstream and --allow-no-upstream was given, "
                "so git.requireUpstream is false and the push remote must exist"
            )
            continue
        blockers.append(problem)

    if not facts.get("provider"):
        blockers.append("no release interface could be chosen for this remote")

    if facts.get("manifest_error"):
        blockers.append("package manifest cannot be read: %s" % facts["manifest_error"])

    latest = str(facts.get("latest_tag") or "")
    if latest:
        latest_version = latest.lstrip("v")
        if _same_or_behind(version, latest_version):
            blockers.append(
                "%s is not newer than the released tag %s; release-it only accepts an explicit "
                "version it considers greater than or equal to the latest tag" % (version, latest)
            )
    elif facts.get("version") and _same_or_behind(version, facts["version"]):
        blockers.append(
            "%s is not newer than package.json version %s; release-it would try to publish an "
            "already published version" % (version, facts["version"])
        )
    if rls_shell.available("git") and facts.get("remote", {}).get("url"):
        if _remote_tag_exists(facts, tag):
            blockers.append("tag %s already exists on origin; a published version is never reused" % tag)

    if not facts.get("manifest"):
        warnings.append(
            "no package.json was found, so npm.publish is false and no package link is recorded"
        )

    node = node_version()
    if node and not engine_ok(node):
        warnings.append(
            "node %s does not satisfy release-it %s engines %s; expect an engines warning and "
            "possibly a hard failure" % (node, runner_pin(opts), "^22.22.2 || ^24.15.0 || >=26.0.0")
        )

    if opts["provider"] == "gitlab" and (opts["draft"] or opts["prerelease"]):
        warnings.append(
            "GitLab has no documented draft or pre-release support; the options were passed "
            "through anyway, so verify the created release for the draft/pre-release flags"
        )
    if opts["auto_generate"] and opts["provider"] == "github":
        warnings.append(
            "github.autoGenerate is on, so GitHub writes the release body and release-notes.md "
            "is only used for the plan preview and the report"
        )
    if opts["dry_run"]:
        warnings.append("dry run: release-it performs every check but writes nothing")

    return blockers, warnings


def runner_pin(opts):
    return opts.get("release_it_version") or DEFAULT_RELEASE_IT


def _remote_tag_exists(facts, tag):
    from rls_repo import tag_exists

    try:
        return bool(tag_exists(facts.get("repo", "."), tag))
    except Exception:  # pragma: no cover - a network hiccup must not abort planning
        return False


def _same_or_behind(version, base):
    """True when ``version`` is not strictly newer than ``base``.  Unknown -> False."""
    try:
        return compare(version, base) <= 0
    except Exception:
        return False


def build_plan(repo=".", **kwargs):
    """Return the release plan as a dictionary."""
    facts = inspect(repo, kwargs.get("manifest"), kwargs.get("tag_match"))
    opts = normalise_options(facts, kwargs)

    state_dir = Path(opts["state_dir"]).expanduser()
    config_path = state_dir / "release-it.json"
    notes_path = state_dir / "release-notes.md"

    if opts["notes_text"] is not None:
        notes_text = opts["notes_text"]
    else:
        rows = commits_missing_from_tags(facts, opts)
        notes_text = render_notes(
            opts["version"] or facts.get("version") or "0.0.0",
            rows,
            previous_tag=facts.get("latest_tag") or "",
            package=facts.get("package"),
            repository_url=build_links(
                facts, opts["provider"], opts["tag"], opts["version"], facts.get("package"), opts["publish"]
            )["repository"],
        )

    config = build_config(facts, opts, state_dir)
    runner = resolve_runner(facts.get("repo", repo), runner_pin(opts))
    argv = build_argv(opts, runner, config_path, opts["version"])
    blockers, warnings = assess(facts, opts, opts["version"], opts["tag"], state_dir)
    links = build_links(
        facts, opts["provider"], opts["tag"], opts["version"], facts.get("package"), opts["publish"]
    )

    manifest = Path(facts["manifest"]) if facts.get("manifest") else None
    return {
        "plan_version": PLAN_VERSION,
        "skill": SKILL_NAME,
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "repo": facts.get("repo"),
        "provider": facts.get("provider"),
        "remote": (facts.get("remote") or {}).get("url", ""),
        "project": facts.get("project"),
        "branch": facts.get("branch"),
        "detached": facts.get("detached"),
        "clean": facts.get("clean"),
        "dirty_paths": facts.get("dirty_paths", []),
        "manifest": str(manifest) if manifest else None,
        "package": facts.get("package"),
        "current_version": facts.get("version"),
        "version": opts["version"],
        "version_source": opts["version_source"],
        "previous_tag": facts.get("latest_tag") or "",
        "tag": opts["tag"],
        "tag_prefix": opts["tag_prefix"],
        "config": config,
        "release_it": {
            "runner": runner["kind"],
            "program": runner["program"],
            "pin": runner["pin"],
            "argv": argv,
            "display": " ".join(quote(arg) for arg in argv),
            "engines": "^22.22.2 || ^24.15.0 || >=26.0.0",
        },
        "operations": {
            "commit": True,
            "tag": True,
            "push": True,
            "release": bool(opts["release"]),
            "publish": bool(opts["publish"]),
            "dry_run": bool(opts["dry_run"]),
        },
        "notes": {
            "path": str(notes_path),
            "command": notes_command(state_dir),
            "chars": len(notes_text),
            "sections": section_titles(notes_text),
        },
        "state": {
            "dir": str(state_dir),
            "config": str(config_path),
            "notes": str(notes_path),
            "printer": str(state_dir / "print-notes.mjs"),
        },
        "links": links,
        "blockers": blockers,
        "warnings": warnings,
        "notes_text": notes_text,
    }


def section_titles(notes_text):
    return [line[4:].strip() for line in notes_text.splitlines() if line.startswith("### ")]


def commits_missing_from_tags(facts, opts):
    from rls_repo import commits_between

    repo = facts.get("repo", ".")
    start = facts.get("latest_tag") or ""
    if start:
        return commits_between(repo, start, "HEAD")
    return commits_between(repo, "", "HEAD")


def normalise_options(facts, kwargs):
    opts = dict(kwargs)
    opts.setdefault("manifest", None)
    opts.setdefault("tag_match", None)
    opts.setdefault("increment", None)
    opts.setdefault("version", None)
    opts.setdefault("pre_release_id", None)
    opts.setdefault("pre_release_base", None)
    opts.setdefault("notes_text", None)
    opts.setdefault("assets", None)
    opts.setdefault("require_branch", None)
    opts.setdefault("commit_message", "chore(release): ${version}")
    opts.setdefault("tag_annotation", "Release ${version}")
    opts.setdefault("release_name", "Release ${version}")
    opts.setdefault("draft", False)
    opts.setdefault("prerelease", False)
    opts.setdefault("auto_generate", False)
    opts.setdefault("dry_run", False)
    opts.setdefault("allow_dirty", False)
    opts.setdefault("allow_no_upstream", False)
    opts.setdefault("release_it_version", DEFAULT_RELEASE_IT)
    if "publish" not in opts or opts["publish"] is None:
        opts["publish"] = bool(facts.get("manifest"))
    if "release" not in opts or opts["release"] is None:
        opts["release"] = True
    if "provider" not in opts or not opts["provider"]:
        opts["provider"] = facts.get("provider") or ""

    opts["publish_package_manager"] = opts.get("publish_package_manager") or detect_package_manager(
        facts.get("repo", ".")
    )
    opts["tag_prefix"] = tag_prefix_for(facts, opts.get("tag_prefix"))
    opts["state_dir"] = opts.get("state_dir") or str(default_state_dir(facts.get("repo", ".")))

    current = facts.get("version") or "0.0.0"
    if not facts.get("version"):
        current = str(facts.get("latest_tag") or "0.0.0").lstrip("v") or "0.0.0"
    version, source = resolve_version(
        current,
        increment=opts.get("increment"),
        version=opts.get("version"),
        pre_release_id=opts.get("pre_release_id"),
        pre_release_base=opts.get("pre_release_base"),
    )
    opts["version"] = version
    opts["version_source"] = source
    opts["tag"] = "%s%s" % (opts["tag_prefix"], version)
    return opts


def quote(arg):
    text = str(arg)
    if text and not any(ch in text for ch in ' \t"'):
        return text
    return '"%s"' % text.replace('"', '\\"')


# --------------------------------------------------------------------------- #
# writing
# --------------------------------------------------------------------------- #
def write_state(plan):
    """Write the config, the notes and the printer.  Returns the paths written."""
    state = Path(plan["state"]["dir"])
    state.mkdir(parents=True, exist_ok=True)

    config_path = Path(plan["state"]["config"])
    config_path.write_text(
        json.dumps(plan["config"], indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )

    notes_path = Path(plan["state"]["notes"])
    notes_path.write_text(plan["notes_text"], encoding="utf-8")

    printer_path = Path(plan["state"]["printer"])
    printer_path.write_text(PRINT_NOTES_JS, encoding="utf-8")

    return {
        "config": str(config_path),
        "notes": str(notes_path),
        "printer": str(printer_path),
    }


def summarise(plan):
    lines = [
        "%s %s (%s)" % (plan["provider"] or "unknown provider", plan["project"] or "-", plan["branch"] or "-"),
        "version  %s  from %s" % (plan["version"], plan["version_source"]),
        "tag      %s" % plan["tag"],
        "previous %s" % (plan["previous_tag"] or "(none)"),
        "runner   %s" % plan["release_it"]["display"],
        "writes   %s" % plan["state"]["dir"],
    ]
    if plan["links"]["release"]:
        lines.append("release  %s" % plan["links"]["release"])
    if plan["links"]["package"]:
        lines.append("package  %s" % plan["links"]["package"])
    for warning in plan["warnings"]:
        lines.append("warning: %s" % warning)
    for blocker in plan["blockers"]:
        lines.append("BLOCKED: %s" % blocker)
    return "\n".join(lines)


def main(argv=None):
    parser = argparse.ArgumentParser(
        prog="rls_plan.py",
        description="Build the release plan for a repository without changing it.",
    )
    parser.add_argument("--repo", default=".")
    parser.add_argument("--provider", choices=("github", "gitlab"),
                        help="override the provider inferred from origin")
    parser.add_argument("--manifest")
    parser.add_argument("--increment", choices=("major", "minor", "patch", "premajor", "preminor",
                                                 "prepatch", "prerelease", "pre"))
    parser.add_argument("--version", help="release exactly this version")
    parser.add_argument("--pre-release-id")
    parser.add_argument("--pre-release-base")
    parser.add_argument("--tag-prefix", help="defaults to 'v' when the latest tag starts with one")
    parser.add_argument("--tag-match")
    parser.add_argument("--release-name", default="Release ${version}")
    parser.add_argument("--commit-message", default="chore(release): ${version}")
    parser.add_argument("--tag-annotation", default="Release ${version}",
                        help="empty string creates a lightweight tag")
    parser.add_argument("--assets", nargs="*", default=None)
    parser.add_argument("--require-branch", default=None)
    parser.add_argument("--publish-package-manager", choices=("npm", "pnpm", "bun"))
    parser.add_argument("--publish", dest="publish", action="store_true", default=None)
    parser.add_argument("--no-publish", dest="publish", action="store_false")
    parser.add_argument("--release", dest="release", action="store_true", default=None)
    parser.add_argument("--no-release", dest="release", action="store_false")
    parser.add_argument("--draft", action="store_true")
    parser.add_argument("--prerelease", action="store_true")
    parser.add_argument("--auto-generate", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--allow-dirty", action="store_true")
    parser.add_argument("--allow-no-upstream", action="store_true")
    parser.add_argument("--notes-file", help="use this file as the release notes")
    parser.add_argument("--state-dir")
    parser.add_argument("--release-it-version", default=DEFAULT_RELEASE_IT)
    parser.add_argument("--output", help="where to write the plan JSON")
    parser.add_argument("--print", dest="print_plan", action="store_true",
                        help="print the plan JSON to stdout as well")
    args = parser.parse_args(argv)

    notes_text = None
    if args.notes_file:
        notes_text = Path(args.notes_file).expanduser().read_text(encoding="utf-8")

    kwargs = vars(args).copy()
    for key in ("repo", "notes_file", "output", "print_plan"):
        kwargs.pop(key, None)
    kwargs["notes_text"] = notes_text

    plan = build_plan(args.repo, **kwargs)
    written = write_state(plan)

    output = Path(args.output).expanduser() if args.output else Path(plan["state"]["dir"]) / "release-plan.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    payload = {key: value for key, value in plan.items() if key != "notes_text"}
    payload["written"] = written
    output.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    print(summarise(plan))
    print("plan     %s" % output)
    if args.print_plan:
        print(json.dumps(payload, indent=2, ensure_ascii=False))

    return 2 if plan["blockers"] else 0


if __name__ == "__main__":
    sys.exit(main())
