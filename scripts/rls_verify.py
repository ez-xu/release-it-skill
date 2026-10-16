#!/usr/bin/env python3
"""Read the four release deliverables back and prove they describe one commit.

The success measure for this workflow is that the tag, the release notes, the
published package and the recorded links all describe the same commit.  This
module reads each one back from where it actually lives -- the local repository,
the remote, the platform release API and the package registry -- and reports
``verified`` only when they agree.

Nothing here writes.  A read that cannot be performed (no token, publishing
switched off) is reported as ``skipped`` with its reason, never as a pass.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from rls_repo import find_manifest, read_manifest  # noqa: E402
from rls_shell import git_ok, run_text  # noqa: E402

VERDICTS = ("verified", "web-pending", "dry-run", "refused", "failed")

REQUIRED_ALWAYS = (
    "tag-local",
    "tag-dereference",
    "tag-remote",
    "head-commit",
    "manifest-version",
    "commit-subject",
    "notes-non-empty",
    "links-complete",
)


def _check(checks, cid, ok, detail, value=None, required=True, skipped=False):
    checks.append(
        {
            "id": cid,
            "ok": bool(ok),
            "detail": detail,
            "value": value,
            "required": bool(required),
            "skipped": bool(skipped),
        }
    )
    return bool(ok)


def _render(template, version):
    return str(template or "").replace("${version}", version)


def token_available(provider):
    """True when the provider CLI can authenticate without prompting."""
    if provider == "github":
        if os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN"):
            return True
        code, output = run_text(["gh", "auth", "token"], timeout=45)
        return code == 0 and bool(output.strip())
    if provider == "gitlab":
        return bool(os.environ.get("GITLAB_TOKEN") or os.environ.get("GITLAB_PERSONAL_ACCESS_TOKEN"))
    return False


def read_release(provider, project, tag, timeout=60):
    """Read the platform release back.  Returns (ok, payload, detail)."""
    if provider == "github":
        code, output = run_text(
            ["gh", "release", "view", tag, "--repo", project,
             "--json", "tagName,name,url,isDraft,isPrerelease,body"],
            timeout=timeout,
        )
        if code != 0:
            return False, {}, output.strip() or "gh release view failed"
        try:
            return True, json.loads(output), ""
        except ValueError:
            return False, {}, "gh returned output that is not JSON"
    if provider == "gitlab":
        code, output = run_text(["glab", "release", "view", tag, "-R", project], timeout=timeout)
        if code != 0:
            return False, {}, output.strip() or "glab release view failed"
        return True, {"tagName": tag, "body": output}, ""
    return False, {}, "no release interface for provider %r" % (provider,)


def read_package(spec, timeout=90):
    """Read the published package back from the registry."""
    code, output = run_text(
        ["npm", "view", spec, "version", "gitHead", "dist.tarball", "--json"], timeout=timeout
    )
    if code != 0:
        return False, {}, output.strip() or "npm view failed"
    try:
        payload = json.loads(output)
    except ValueError:
        return False, {}, "npm returned output that is not JSON"
    if isinstance(payload, list):
        payload = payload[-1] if payload else {}
    if not isinstance(payload, dict):
        return False, {}, "npm returned an unexpected payload"
    return True, payload, ""


def verify(plan, record=None, timeout=90, offline=False):
    """Return the verification report for ``plan``."""
    checks = []
    tag = plan["tag"]
    version = plan["version"]
    repo = plan["repo"]
    provider = plan.get("provider") or ""
    project = plan.get("project") or ""
    manifest = plan.get("manifest") or find_manifest(repo)

    record = record or {}
    classification = record.get("classification") or ""
    dry_run = bool(plan.get("operations", {}).get("dry_run")) or classification == "dry-run"

    # --- the tag -------------------------------------------------------- #
    tag_sha, tag_ok = git_ok(repo, "rev-parse", "--verify", "refs/tags/%s" % tag)
    _check(checks, "tag-local", tag_ok, "git rev-parse --verify refs/tags/%s" % tag,
           tag_sha.strip() if tag_ok else None)

    commit_sha, deref_ok = git_ok(repo, "rev-list", "-n", "1", tag)
    commit_sha = commit_sha.strip() if deref_ok else ""
    _check(checks, "tag-dereference", deref_ok and bool(commit_sha),
           "git rev-list -n 1 %s (annotated tags are two objects)" % tag, commit_sha or None)

    # The remote read is a git operation, not a platform API call, so it runs
    # even when the platform reads are switched off: a tag that never reached
    # origin is not a release.
    remote_sha = ""
    remote_ok = False
    remote_detail = "no origin configured"
    remote_skipped = True
    code, output = run_text(["git", "remote", "get-url", "origin"], cwd=repo, timeout=timeout)
    if code == 0 and output.strip():
        code, output = run_text(["git", "ls-remote", "--tags", "origin", "refs/tags/%s*" % tag],
                                cwd=repo, timeout=timeout)
        peeled = []
        for line in output.splitlines():
            parts = line.split()
            if len(parts) == 2 and parts[1].startswith("refs/tags/%s" % tag):
                peeled.append((parts[1], parts[0]))
        remote_skipped = False
        if code != 0:
            remote_detail = output.strip() or "git ls-remote failed"
        elif not peeled:
            remote_detail = "%s is not on origin" % tag
        else:
            dereferenced = [sha for ref, sha in peeled if ref.endswith("^{}")]
            remote_sha = (dereferenced or [sha for _, sha in peeled])[0]
            remote_ok = not commit_sha or remote_sha == commit_sha
            remote_detail = "origin has %s at %s" % (tag, remote_sha)
            if commit_sha and remote_sha != commit_sha:
                remote_detail += " but locally it dereferences to %s" % commit_sha
    _check(checks, "tag-remote", remote_ok, remote_detail, remote_sha or None, skipped=remote_skipped)

    head_sha, head_ok = git_ok(repo, "rev-parse", "HEAD")
    head_sha = head_sha.strip() if head_ok else ""
    same_commit = bool(head_sha) and head_sha == commit_sha
    _check(checks, "head-commit", same_commit,
           "HEAD %s must be the commit the tag dereferences to (%s)" % (head_sha or "?", commit_sha or "?"),
           head_sha or None)

    # --- the manifest inside that commit --------------------------------- #
    manifest_ok = False
    manifest_detail = "no manifest"
    manifest_version = None
    if manifest:
        rel = Path(manifest)
        try:
            rel = rel.relative_to(Path(repo))
        except ValueError:
            rel = Path(Path(manifest).name)
        shown, shown_ok = git_ok(repo, "show", "HEAD:%s" % rel.as_posix())
        if shown_ok:
            try:
                manifest_version = json.loads(shown).get("version")
            except ValueError:
                manifest_version = None
            manifest_ok = manifest_version == version
            manifest_detail = "HEAD:%s has version %r, expected %r" % (rel.as_posix(), manifest_version, version)
        else:
            manifest_detail = "git show HEAD:%s failed" % rel.as_posix()
    _check(checks, "manifest-version", manifest_ok, manifest_detail, manifest_version)

    expected_subject = _render(plan["config"]["git"].get("commitMessage"), version)
    subject, subject_ok = git_ok(repo, "log", "-1", "--pretty=%s")
    subject = subject.strip() if subject_ok else ""
    _check(checks, "commit-subject", subject == expected_subject,
           "HEAD subject %r, expected %r" % (subject, expected_subject), subject or None)

    # --- the notes ------------------------------------------------------- #
    notes_path = Path(plan["state"]["notes"])
    notes_text = notes_path.read_text(encoding="utf-8") if notes_path.exists() else ""
    _check(checks, "notes-non-empty", bool(notes_text.strip()),
           "%s is %d characters" % (notes_path.name, len(notes_text)), len(notes_text))

    links = plan.get("links") or {}
    required_links = ["repository", "tag", "release", "compare"]
    if plan.get("package"):
        required_links.append("package")
    missing = [key for key in required_links if not links.get(key)]
    _check(checks, "links-complete", not missing,
           "missing link(s): %s" % ", ".join(missing) if missing else
           "recorded %s" % ", ".join(key for key in required_links if links.get(key)),
           sorted(links))

    # --- the platform release -------------------------------------------- #
    release_payload = {}
    release_commit = ""
    needs_release = bool(plan.get("operations", {}).get("release")) and not dry_run
    have_token = False if offline else token_available(provider)
    if not needs_release:
        _check(checks, "release-api", True, "no platform release was requested", required=False, skipped=True)
    elif not have_token:
        _check(checks, "release-api", False,
               "%s is not authenticated; release-it fell back to the web release form" % (provider or "provider"),
               required=False, skipped=True)
    else:
        ok, payload, detail = read_release(provider, project, tag, timeout=timeout)
        release_payload = payload
        if ok:
            body = payload.get("body") or ""
            name_ok = (payload.get("tagName") or tag) == tag
            _check(checks, "release-api", name_ok and bool(body.strip()),
                   "release %s exists with %d characters of notes" % (tag, len(body)),
                   {"url": payload.get("url", ""), "notes_chars": len(body)})
            if provider == "github" and project:
                code, output = run_text(
                    ["gh", "api", "repos/%s/commits/%s" % (project, tag), "--jq", ".sha"], timeout=timeout
                )
                release_commit = output.strip() if code == 0 else ""
        else:
            _check(checks, "release-api", False, detail)

    # --- the published package ------------------------------------------- #
    package = plan.get("package")
    package_payload = {}
    package_git_head = ""
    needs_package = bool(plan.get("operations", {}).get("publish")) and not dry_run
    if not needs_package or not package:
        reason = "publishing is switched off" if not needs_package else "the repository has no package manifest"
        _check(checks, "package-registry", True, reason, required=False, skipped=True)
    elif offline:
        _check(checks, "package-registry", True, "offline check", required=False, skipped=True)
    else:
        ok, payload, detail = read_package("%s@%s" % (package, version), timeout=timeout)
        package_payload = payload
        if ok:
            published = str(payload.get("version") or "")
            package_git_head = str(payload.get("gitHead") or "")
            _check(checks, "package-registry", published == version,
                   "%s@%s is published (gitHead %s)" % (package, published or "?", package_git_head or "unknown"),
                   {"version": published, "gitHead": package_git_head, "tarball": payload.get("dist.tarball", "")})
        else:
            _check(checks, "package-registry", False, detail)

    # --- one commit? ------------------------------------------------------ #
    commits = {"tag": commit_sha, "head": head_sha}
    if release_commit:
        commits["release"] = release_commit
    if package_git_head:
        commits["package"] = package_git_head
    compared = {key: value for key, value in commits.items() if value}
    consistent = len(set(compared.values())) == 1 and bool(compared.get("tag"))

    failed = [check for check in checks if check["required"] and not check["ok"] and not check["skipped"]]
    if dry_run:
        verdict = "dry-run"
    elif failed:
        verdict = "refused"
    elif not consistent:
        verdict = "refused"
    elif not have_token and needs_release:
        verdict = "web-pending"
    else:
        verdict = "verified"

    return {
        "verdict": verdict,
        "consistent": consistent,
        "commits": commits,
        "checks": checks,
        "failed": [check["id"] for check in failed],
        "release": {
            "exists": bool(release_payload),
            "url": release_payload.get("url", ""),
            "notes_chars": len(release_payload.get("body") or ""),
        },
        "package": {
            "published": bool(package_payload),
            "version": package_payload.get("version", ""),
            "gitHead": package_git_head,
            "tarball": (package_payload.get("dist") or {}).get("tarball", "")
            if isinstance(package_payload.get("dist"), dict) else package_payload.get("dist.tarball", ""),
        },
        "links": links,
    }


def main(argv=None):
    import argparse

    parser = argparse.ArgumentParser(
        prog="rls_verify.py",
        description="Read the tag, the release, the package and the links back and compare them.",
    )
    parser.add_argument("--repo", default=".")
    parser.add_argument("--plan", help="reuse an existing release-plan.json")
    parser.add_argument("--tag", help="verify this tag instead of building a plan")
    parser.add_argument("--version", help="the version the tag carries")
    parser.add_argument("--offline", action="store_true", help="check only the local repository and origin")
    parser.add_argument("--timeout", type=int, default=90)
    parser.add_argument("--output", help="where to write the verification JSON")
    args = parser.parse_args(argv)

    from rls_plan import build_plan

    if args.plan:
        plan = json.loads(Path(args.plan).expanduser().read_text(encoding="utf-8"))
    else:
        plan = build_plan(args.repo, version=args.version, increment="patch")

    if args.tag:
        plan["tag"] = args.tag

    report = verify(plan, offline=args.offline, timeout=args.timeout)

    if args.output:
        output = Path(args.output).expanduser()
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    for check in report["checks"]:
        mark = "skip" if check["skipped"] else ("ok" if check["ok"] else "FAIL")
        print("%-18s %-4s %s" % (check["id"], mark, check["detail"]))
    print("commits  %s" % json.dumps(report["commits"], sort_keys=True))
    print("verdict  %s" % report["verdict"])
    if args.output:
        print("report   %s" % args.output)

    return 0 if report["verdict"] in ("verified", "web-pending", "dry-run") else 1


if __name__ == "__main__":
    sys.exit(main())
