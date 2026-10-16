# release-it-skill eval spec

One fenced JSON block. `python3 scripts/run_evals.py` reads it; the six criteria
are graded by `scripts/eval_check.py` rather than by `grep`, because `grep` only
exists on Windows when Git's `usr/bin` happens to be on `PATH` and an eval that
silently stops checking anything is worse than no eval.

```json
{
  "skill": "release-it-skill",
  "run": "python3 scripts/eval_harness.py --scenario {input} --output {output} || python scripts/eval_harness.py --scenario {input} --output {output}",
  "criteria": [
    {
      "id": "harnessRan",
      "text": "The scenario produced a verdict with a numeric exit code, so every later criterion is graded on a real run rather than on a missing file.",
      "type": "command",
      "cmd": "python3 scripts/eval_check.py {output} harnessRan || python scripts/eval_check.py {output} harnessRan"
    },
    {
      "id": "expectationMet",
      "text": "The run did exactly what the scenario requires: a clean repository released, a broken one refused, a dry run changed nothing.",
      "type": "command",
      "cmd": "python3 scripts/eval_check.py {output} expectationMet || python scripts/eval_check.py {output} expectationMet"
    },
    {
      "id": "refusalIsSafe",
      "text": "A refusal exits 2 and leaves HEAD, the tags, the remote refs and the manifest byte-for-byte unchanged, so a run that cannot prove its own safety publishes nothing.",
      "type": "command",
      "cmd": "python3 scripts/eval_check.py {output} refusalIsSafe || python scripts/eval_check.py {output} refusalIsSafe"
    },
    {
      "id": "closedLoopConsistent",
      "text": "After a release the tag, its dereferenced commit, HEAD, the tag on origin and the manifest version all describe the same commit.",
      "type": "command",
      "cmd": "python3 scripts/eval_check.py {output} closedLoopConsistent || python scripts/eval_check.py {output} closedLoopConsistent"
    },
    {
      "id": "notesNotEmpty",
      "text": "A release carries non-empty generated notes and the notes are grouped into conventional-commit sections.",
      "type": "command",
      "cmd": "python3 scripts/eval_check.py {output} notesNotEmpty || python scripts/eval_check.py {output} notesNotEmpty"
    },
    {
      "id": "linksComplete",
      "text": "A release records the repository, tag, release and compare links, so the four deliverables can be inspected afterwards.",
      "type": "command",
      "cmd": "python3 scripts/eval_check.py {output} linksComplete || python scripts/eval_check.py {output} linksComplete"
    }
  ],
  "golden": [
    {
      "id": "clean-minor",
      "input": "golden/clean-minor/input.json",
      "expected": null,
      "expected_status": "pending-first-green",
      "split": "val",
      "compare": "exact",
      "compare_ignore": ["reason", "blockers", "notes_chars", "checks", "failed_checks", "release_record", "error", "before", "after", "tag_commit", "remote_tag_commit", "stdout_tail"],
      "text": "The ordinary path: a clean tree four conventional commits past v1.0.0 releases v1.1.0."
    },
    {
      "id": "dirty-refusal",
      "input": "golden/dirty-refusal/input.json",
      "expected": null,
      "expected_status": "pending-first-green",
      "split": "val",
      "compare": "exact",
      "compare_ignore": ["reason", "blockers", "notes_chars", "checks", "failed_checks", "release_record", "error", "before", "after", "tag_commit", "remote_tag_commit", "stdout_tail"],
      "text": "An uncommitted edit refuses the release and changes nothing."
    },
    {
      "id": "tag-collision",
      "input": "golden/tag-collision/input.json",
      "expected": null,
      "expected_status": "pending-first-green",
      "split": "val",
      "compare": "exact",
      "compare_ignore": ["reason", "blockers", "notes_chars", "checks", "failed_checks", "release_record", "error", "before", "after", "tag_commit", "remote_tag_commit", "stdout_tail"],
      "text": "A minor bump that would re-point an existing published tag is refused."
    },
    {
      "id": "dry-run",
      "input": "golden/dry-run/input.json",
      "expected": null,
      "expected_status": "pending-first-green",
      "split": "val",
      "compare": "exact",
      "compare_ignore": ["reason", "blockers", "notes_chars", "checks", "failed_checks", "release_record", "error", "before", "after", "tag_commit", "remote_tag_commit", "stdout_tail"],
      "text": "The preview exits 0 and writes nothing."
    },
    {
      "id": "no-package",
      "input": "golden/no-package/input.json",
      "expected": null,
      "expected_status": "pending-first-green",
      "split": "val",
      "compare": "exact",
      "compare_ignore": ["reason", "blockers", "notes_chars", "checks", "failed_checks", "release_record", "error", "before", "after", "tag_commit", "remote_tag_commit", "stdout_tail"],
      "text": "Without a readable manifest the version is unknowable, so the run refuses rather than guessing."
    },
    {
      "id": "explicit-version",
      "input": "golden/explicit-version/input.json",
      "expected": null,
      "expected_status": "pending-first-green",
      "split": "test",
      "compare": "none",
      "text": "Holdout: a named version must be released exactly as asked instead of being re-derived from the commits."
    }
  ]
}
```
