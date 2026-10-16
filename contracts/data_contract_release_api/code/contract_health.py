#!/usr/bin/env python3
"""Health probe for the release interface behind release-it-skill.

The release surface -- the platform release API and the package registry -- is an
external structured interface, not something this skill owns.  A release is only
reported once the record has been read back from that surface, so the surface is
probed live before anything is believed about it.

``report()`` never raises.  When the release command line interface is missing,
unauthenticated, or does not expose an operation this skill depends on, the report
comes back not usable.  Callers must treat that as a safe stop: publish nothing and
name the operation that could not be reached.

Every parameter carries a default, because the factory's health gate calls
``report()`` with no arguments at all.
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import sys

CONTRACT_ID = "release_api"

INTERFACE = (
    "GitHub Releases (gh) and GitLab Releases (glab) command line interfaces, "
    "plus the npm registry"
)

REQUIRED_OPERATIONS = (
    "resolve a tag to the commit it names",
    "read a release and its notes by tag name",
    "create a release for a tag that already exists",
    "read a published package version back from the registry",
)

CLI_FOR_PROVIDER = {"github": "gh", "gitlab": "glab"}

# Subcommands that the release interface must expose per provider.  Only --help is
# ever run, so probing cannot create, download or delete anything.
RELEASE_OPERATIONS = {
    "github": ("create", "view", "list"),
    "gitlab": ("create", "view", "list"),
}

_MAX_DETAIL = 240

# Probe output is echoed into reports that a user or an agent may read, so anything
# shaped like a credential is stripped before it can be quoted back.
_SECRET_PATTERNS = (
    re.compile(r"\b(gh[pousr])_[A-Za-z0-9]{16,}\b"),
    re.compile(r"\bglpat-[A-Za-z0-9_\-]{16,}\b"),
    re.compile(r"\bnpm_[A-Za-z0-9]{30,}\b"),
)


def _redact(text):
    redacted = str(text or "")
    for pattern in _SECRET_PATTERNS:
        redacted = pattern.sub("<redacted>", redacted)
    return redacted


def _launcher(program):
    """Return the argv prefix that actually starts ``program``.

    Windows ships npm as ``npm.CMD``.  ``shutil.which`` honours PATHEXT and finds
    it, but CreateProcess cannot start a batch file directly, so the launcher has
    to be wrapped in the command interpreter.  Without this, every npm probe fails
    with WinError 2 even though npm is installed and on PATH.
    """
    path = shutil.which(program) or program
    if os.name == "nt" and str(path).lower().endswith((".cmd", ".bat")):
        return [os.environ.get("COMSPEC", "cmd.exe"), "/c", path]
    return [path]


def _run(argv, cwd=None, timeout=45):
    """Run argv and return (returncode, combined output).  Never raises."""
    command = _launcher(argv[0]) + [str(arg) for arg in argv[1:]]
    try:
        completed = subprocess.run(
            command,
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
    except subprocess.TimeoutExpired:
        return 124, "timed out: %s" % " ".join(str(a) for a in argv)
    except (OSError, subprocess.SubprocessError) as exc:
        return 127, str(exc)
    output = (completed.stdout or "") + (completed.stderr or "")
    return completed.returncode, output.strip()


def _clip(text):
    text = _redact(re.sub(r"\s+", " ", str(text or "")).strip())
    return text[:_MAX_DETAIL]


def _check(name, ok, detail=""):
    return {"name": name, "ok": bool(ok), "detail": _clip(detail)}


def detect_provider(repo="."):
    """Return (provider, remote_url).  Provider is 'github', 'gitlab' or ''."""
    if not shutil.which("git"):
        return "", ""
    code, out = _run(["git", "-C", str(repo), "remote", "get-url", "origin"])
    if code != 0:
        return "", ""
    url = out.strip().splitlines()[0].strip() if out.strip() else ""
    lowered = url.lower()
    if "github" in lowered:
        return "github", url
    if "gitlab" in lowered:
        return "gitlab", url
    return "", url


def _probe_cli(checks, provider, timeout):
    """Probe one provider's CLI: present, authenticated, operations exposed."""
    cli = CLI_FOR_PROVIDER[provider]
    path = shutil.which(cli)
    checks.append(_check("cli:%s" % cli, bool(path), path or "%s not on PATH" % cli))
    if not path:
        return False
    code, out = _run([cli, "auth", "status"], timeout=timeout)
    checks.append(_check("auth:%s" % cli, code == 0, out or "exit %s" % code))
    authenticated = code == 0
    operations_ok = True
    for operation in RELEASE_OPERATIONS[provider]:
        code, out = _run([cli, "release", operation, "--help"], timeout=timeout)
        ok = code == 0
        operations_ok = operations_ok and ok
        checks.append(
            _check(
                "op:%s release %s" % (cli, operation),
                ok,
                "exposed" if ok else (out or "exit %s" % code),
            )
        )
    return authenticated and operations_ok


def _probe_registry(checks, timeout):
    npm = shutil.which("npm")
    checks.append(_check("cli:npm", bool(npm), npm or "npm not on PATH"))
    if not npm:
        return False
    code, out = _run(["npm", "ping"], timeout=timeout)
    ok = code == 0
    checks.append(_check("registry:npm ping", ok, out or "exit %s" % code))
    return ok


def _probe_git(checks, repo, timeout):
    git = shutil.which("git")
    checks.append(_check("cli:git", bool(git), git or "git not on PATH"))
    if not git:
        return False
    code, out = _run(["git", "-C", str(repo), "rev-parse", "--is-inside-work-tree"], timeout=timeout)
    ok = code == 0 and out.strip().startswith("true")
    checks.append(
        _check("worktree:git", ok, "inside a work tree" if ok else (out or "not a git work tree"))
    )
    return ok


def report(provider="", repo=".", timeout=45):
    """Probe the release interface and return its health.  Never raises."""
    checks = []
    remote = ""
    resolved = str(provider or "").strip().lower()

    git_ok = _probe_git(checks, repo, timeout)

    if resolved not in CLI_FOR_PROVIDER:
        detected, remote = detect_provider(repo)
        resolved = detected or ""
    elif shutil.which("git"):
        _, remote = detect_provider(repo)

    checks.append(
        _check(
            "provider",
            bool(resolved),
            resolved or ("could not derive a provider from the origin remote: %s" % (remote or "no origin")),
        )
    )

    if resolved:
        interface_ok = _probe_cli(checks, resolved, timeout)
    else:
        interface_ok = False

    registry_ok = _probe_registry(checks, timeout)

    fresh = bool(git_ok and resolved and interface_ok and registry_ok)
    smoke = "PASS" if all(item["ok"] for item in checks) else "FAIL"

    return {
        "contract": CONTRACT_ID,
        "interface": INTERFACE,
        "provider": resolved or "unknown",
        "remote": remote,
        "repo": str(repo),
        "freshness": "FRESH" if fresh else "UNKNOWN",
        "smoke": smoke,
        "usable": bool(fresh and smoke == "PASS"),
        "required_operations": list(REQUIRED_OPERATIONS),
        "checks": checks,
    }


if __name__ == "__main__":
    here = sys.argv[1] if len(sys.argv) > 1 else "."
    provider = sys.argv[2] if len(sys.argv) > 2 else ""
    import json

    print(json.dumps(report(provider=provider, repo=here), indent=2))
