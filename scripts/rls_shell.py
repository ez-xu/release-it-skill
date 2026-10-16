#!/usr/bin/env python3
"""Process helpers shared by the release pipeline.

Two Windows facts drive this module:

* ``npm`` ships as ``npm.CMD``.  ``shutil.which`` finds it because it honours
  PATHEXT, but CreateProcess cannot start a batch file, so the launcher has to be
  wrapped in the command interpreter.
* Command output is echoed into plan and report documents that a human or an agent
  reads, so anything credential-shaped is redacted before it is kept.
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess

_SECRET_PATTERNS = (
    re.compile(r"\b(gh[pousr])_[A-Za-z0-9]{16,}\b"),
    re.compile(r"\bglpat-[A-Za-z0-9_\-]{16,}\b"),
    re.compile(r"\bnpm_[A-Za-z0-9]{30,}\b"),
)


def redact(text):
    redacted = str(text or "")
    for pattern in _SECRET_PATTERNS:
        redacted = pattern.sub("<redacted>", redacted)
    return redacted


def launcher(program):
    """Return the argv prefix that actually starts ``program``."""
    path = shutil.which(program) or program
    if os.name == "nt" and str(path).lower().endswith((".cmd", ".bat")):
        return [os.environ.get("COMSPEC", "cmd.exe"), "/c", path]
    return [path]


def run(argv, cwd=None, timeout=120, env=None):
    """Run argv.  Returns (returncode, stdout, stderr).  Never raises."""
    command = launcher(argv[0]) + [str(arg) for arg in argv[1:]]
    try:
        completed = subprocess.run(
            command,
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
            env=env,
        )
    except subprocess.TimeoutExpired:
        return 124, "", "timed out after %ss: %s" % (timeout, " ".join(str(a) for a in argv))
    except (OSError, subprocess.SubprocessError) as exc:
        return 127, "", str(exc)
    return completed.returncode, completed.stdout or "", completed.stderr or ""


def run_text(argv, cwd=None, timeout=120):
    """Run argv and return (returncode, combined redacted output)."""
    code, out, err = run(argv, cwd=cwd, timeout=timeout)
    lines = [line for line in (out + "\n" + err).splitlines() if line.strip()]
    return code, redact("\n".join(lines)).strip()


def available(program):
    return bool(shutil.which(program))


def git(repo, *args, **kwargs):
    return run_text(["git", "-C", str(repo), *args], **kwargs)


def git_ok(repo, *args, **kwargs):
    code, out = git(repo, *args, **kwargs)
    return (out if code == 0 else ""), code == 0
