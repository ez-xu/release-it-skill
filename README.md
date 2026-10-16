# release-it-skill

A release skill built on [`release-it`](https://github.com/release-it/release-it) 21.1.1.
One command produces four deliverables that all describe the same commit — and a
run that cannot prove that publishes nothing.

| Deliverable | Produced by | Confirmed by |
| --- | --- | --- |
| Tag | release-it's git plugin (annotated, pushed) | `git rev-list -n 1 <tag>` equals HEAD; `git ls-remote --tags origin` agrees |
| Release with notes | release-it's GitHub/GitLab release plugin | `gh release view` / `glab release view` reads it back |
| Package | release-it's npm plugin | `npm view <name> version gitHead` names the same commit |
| Links | recorded in the plan and report | every recorded URL points at the released version |

## Requirements

- `release-it` 21.1.1 — resolved from `node_modules/.bin`, then `PATH`, then `npx --yes release-it@21.1.1`
- Node — `release-it` 21.1.1 declares `^22.22.2 || ^24.15.0 || >=26.0.0`
- `git` 2.40 or newer
- `gh` for GitHub remotes, `glab` for GitLab remotes
- `npm` only when the package is published
- Python 3.9 or newer — the pipeline is standard library only

Tokens are read from `GITHUB_TOKEN` / `GITLAB_TOKEN` only and are never written
into the generated configuration or into any artifact.

## Install

**As part of the skills tree** (this is how it is registered here):

```bash
git -C ~/.agents/skills submodule add https://github.com/ez-xu/release-it-skill.git _sources/release-it-skill
python ~/.agents/skills/_sync.py
```

**Standalone, into any agent's skills directory:**

```bash
git clone https://github.com/ez-xu/release-it-skill.git ~/.agents/skills/release-it-skill
```

On Windows the same repository ships `install.ps1`:

```powershell
git clone https://github.com/ez-xu/release-it-skill.git "$HOME\.agents\skills\release-it-skill"
& "$HOME\.agents\skills\release-it-skill\install.ps1"
```

## Use

Write a spec and run the orchestrator:

```bash
cat > spec.json <<'JSON'
{
  "mode": "plan",
  "repo": ".",
  "increment": "minor"
}
JSON

python3 scripts/run_pipeline.py --input spec.json --output release-plan.json
```

`mode` is one of `plan`, `release`, `verify`, `fixture`. Exit codes are **0**
success, **2** refused with nothing published, **1** failed.

A first safe run on a machine you do not want to touch:

```bash
cat > spec.json <<'JSON'
{
  "mode": "release",
  "scenario": "clean",
  "increment": "minor",
  "publish": false
}
JSON

python3 scripts/run_pipeline.py --input spec.json --output release-report.json
```

That builds a throwaway repository in the temp directory, points `origin` at a
local bare repository, and runs the whole release for real without contacting a
registry or a platform API.

## What it refuses

Dirty working tree, no upstream, detached HEAD, unreadable manifest, a version
that is not strictly newer than the latest tag and the manifest, or a tag that
already exists on `origin`. Refusal exits 2 and leaves HEAD, the tags, the remote
refs and the manifest byte-for-byte unchanged.

## Documentation

- [`SKILL.md`](SKILL.md) — activation, required behaviour, gotchas
- [`references/interfaces-cli.md`](references/interfaces-cli.md) — every CLI flag, alias and dynamic option
- [`references/interfaces-config.md`](references/interfaces-config.md) — every config location, precedence rule and key
- [`references/interfaces-plugins.md`](references/interfaces-plugins.md) — internal and external plugins, the `Plugin` contract
- [`references/interfaces-hooks.md`](references/interfaces-hooks.md) — the six lifecycle hooks and their order
- [`references/interfaces-api.md`](references/interfaces-api.md) — the programmatic Node API
- [`references/interfaces-matrix.md`](references/interfaces-matrix.md) — option-to-plugin-to-hook index
- [`references/_recon-facts.md`](references/_recon-facts.md) — what was verified and what could not be

## Evals

```bash
python3 scripts/run_evals.py --rollout --include-holdout
```

Six golden cases (one held out) across six criteria, all graded by
`scripts/eval_check.py`. Every case runs the real pipeline against a throwaway
repository.

## License

MIT

## Verification

[VERIFICATION.md](VERIFICATION.md) records the latest generation-time gate and eval evidence.
