# Evolution log

Appended automatically by scripts/run_evals.py (and scripts/evolve.py) when a check fails. Each entry is the raw evidence for a fix/regenerate step.

## 2026-10-16T09:52:42Z — run_evals --rollout FAILED

- counts: passed=5, failed=1, errors=0, regressions=0, judge_failed=0
- failing checks (raw):

```json
[
  {
    "case": "declared-version",
    "criterion": "closedLoopConsistent",
    "status": "fail"
  }
]
```

