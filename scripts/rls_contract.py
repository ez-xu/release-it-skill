#!/usr/bin/env python3
"""Load the release-interface contract and refuse to proceed when it is not live.

The release surface -- the platform release API and the package registry -- is not
owned by this skill.  Everything a release reports afterwards is read back from that
surface, so the surface is health-checked before any release work starts and again
before a verified report is produced.

A report that is not FRESH and usable is a safe stop: nothing is published, nothing
is reported as verified, and the caller gets the exact failed checks.
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

CONTRACT_ID = "release_api"
CONTRACT_REL = Path("contracts") / "data_contract_release_api"


class SafeStop(Exception):
    """The release interface cannot be trusted, so nothing may be published."""

    def __init__(self, reason, checks=None):
        super().__init__(reason)
        self.reason = reason
        self.checks = checks or []

    def as_report(self):
        return {
            "ok": False,
            "stopped": True,
            "reason": self.reason,
            "failed_checks": [c for c in self.checks if not c.get("ok")],
        }


def contract_dir(skill_dir=None):
    base = Path(skill_dir).expanduser().resolve() if skill_dir else Path(__file__).resolve().parent.parent
    return base / CONTRACT_REL


def load_health(skill_dir=None):
    """Import the contract health module.  Raises SafeStop when it is not there."""
    directory = contract_dir(skill_dir)
    marker = directory / ".contract_id"
    module_path = directory / "code" / "contract_health.py"
    if not marker.is_file():
        raise SafeStop("release interface contract is missing: %s" % marker)
    declared = marker.read_text().strip()
    if declared != CONTRACT_ID:
        raise SafeStop("contract %s declares %r, expected %r" % (marker, declared, CONTRACT_ID))
    if not module_path.is_file():
        raise SafeStop("release interface contract has no health module: %s" % module_path)
    spec = importlib.util.spec_from_file_location("release_api_contract_health", module_path)
    if spec is None or spec.loader is None:
        raise SafeStop("cannot load the contract health module: %s" % module_path)
    module = importlib.util.module_from_spec(spec)
    sys.modules["release_api_contract_health"] = module
    spec.loader.exec_module(module)
    return module


def health(skill_dir=None, provider="", repo=".", timeout=45):
    """Return the raw health report, or a safe-stop report when loading failed."""
    try:
        module = load_health(skill_dir)
    except SafeStop as stop:
        return stop.as_report() | {"contract": CONTRACT_ID, "freshness": "MISSING", "smoke": "FAIL"}
    report = module.report(provider=provider, repo=repo, timeout=timeout)
    report["ok"] = report.get("freshness") == "FRESH" and (
        report.get("usable") is True or report.get("smoke") == "PASS"
    )
    return report


def require_healthy(skill_dir=None, provider="", repo=".", timeout=45):
    """Return the health report, raising SafeStop unless it is live and usable."""
    report = health(skill_dir=skill_dir, provider=provider, repo=repo, timeout=timeout)
    if not report.get("ok"):
        failed = [c["name"] for c in report.get("checks", []) if not c.get("ok")]
        reason = report.get("reason") or (
            "release interface is not live (freshness=%s, smoke=%s)%s"
            % (
                report.get("freshness"),
                report.get("smoke"),
                ": " + ", ".join(failed) if failed else "",
            )
        )
        raise SafeStop(reason, report.get("checks", []))
    return report


def required_operations(skill_dir=None):
    """Return the operations the contract declares, for plan documents."""
    try:
        return list(load_health(skill_dir).REQUIRED_OPERATIONS)
    except SafeStop:
        return []


if __name__ == "__main__":
    root = sys.argv[1] if len(sys.argv) > 1 else None
    provider = sys.argv[2] if len(sys.argv) > 2 else ""
    print(json.dumps(health(skill_dir=root, provider=provider), indent=2, ensure_ascii=False))
