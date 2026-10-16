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

## 2026-10-16T10:31:58Z — run_evals --rollout FAILED

- counts: passed=42, failed=0, errors=0, regressions=5, judge_failed=0
- failing checks (raw):

```json
[
  {
    "case": "clean-minor",
    "criterion": "<baseline>",
    "status": "regression"
  },
  {
    "case": "dirty-refusal",
    "criterion": "<baseline>",
    "status": "regression"
  },
  {
    "case": "dry-run",
    "criterion": "<baseline>",
    "status": "regression"
  },
  {
    "case": "no-package",
    "criterion": "<baseline>",
    "status": "regression"
  },
  {
    "case": "declared-version",
    "criterion": "<baseline>",
    "status": "regression"
  }
]
```

## 2026-10-16T10:34:00Z — run_evals --rollout FAILED

- counts: passed=42, failed=0, errors=0, regressions=5, judge_failed=0
- failing checks (raw):

```json
[
  {
    "case": "clean-minor",
    "criterion": "<baseline>",
    "status": "regression"
  },
  {
    "case": "dirty-refusal",
    "criterion": "<baseline>",
    "status": "regression"
  },
  {
    "case": "dry-run",
    "criterion": "<baseline>",
    "status": "regression"
  },
  {
    "case": "no-package",
    "criterion": "<baseline>",
    "status": "regression"
  },
  {
    "case": "declared-version",
    "criterion": "<baseline>",
    "status": "regression"
  }
]
```

## 2026-10-16T10:35:25Z — run_evals --rollout FAILED

- counts: passed=42, failed=0, errors=0, regressions=5, judge_failed=0
- failing checks (raw):

```json
[
  {
    "case": "clean-minor",
    "criterion": "<baseline>",
    "status": "regression"
  },
  {
    "case": "dirty-refusal",
    "criterion": "<baseline>",
    "status": "regression"
  },
  {
    "case": "dry-run",
    "criterion": "<baseline>",
    "status": "regression"
  },
  {
    "case": "no-package",
    "criterion": "<baseline>",
    "status": "regression"
  },
  {
    "case": "declared-version",
    "criterion": "<baseline>",
    "status": "regression"
  }
]
```

