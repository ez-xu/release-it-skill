# release-it-skill

Cut one release with `release-it` and prove that the tag, the release notes, the
published package and the recorded links all describe the same commit. Refuses
with exit 2 and publishes nothing when that cannot be proven.

## Activation

Use it when a repository must be released and the result must be inspected
afterwards: 帮我发布一个版本, 打标签并发布, 生成发布说明, bump and publish,
cut a release, tag and create a release with notes, publish this package to npm.
It also releases a **declared** non-semver version verbatim, such as
`V5.1.7.12_weiyuan_G200464803_20261016_8aef61de`.

Do not use it to build and attach a compiled firmware or binary artifact (that is
`push-release-pipeline-skill`), to push a group of repositories at once, to author a
CHANGELOG by hand, or to repair a tag that has already been published.

## Run

```bash
cat > spec.json <<'JSON'
{ "mode": "plan", "repo": ".", "increment": "minor" }
JSON

python3 scripts/run_pipeline.py --input spec.json --output release-plan.json
```

Change `mode` to `release` to publish, `verify` to read an existing release back,
or `fixture` to exercise the whole pipeline against a throwaway repository that
never leaves the machine.

For a declared version, put the exact string in `version` and set `"publish": false`:
`{ "mode": "release", "repo": ".", "version": "5.1.7.12_weiyuan_G200464803_20261016_8aef61de", "publish": false }`.
A leading `v`/`V` is split into the tag name, so the tag is still the declared string.

| Exit | Meaning |
| --- | --- |
| 0 | the release was made, or the plan was written, or the verification passed |
| 2 | refused — a blocker was found and nothing was published |
| 1 | failed — the run started and did not finish cleanly |

## Gotchas

- `release-it` ships `github.release: false` / `gitlab.release: false`, so a stock
  run tags and publishes but creates **no** release. This skill always writes the
  setting explicitly.
- `github.releaseNotes` is executed as a shell command; its stdout is the notes. A
  multi-line string in the config is run as a command and fails.
- `--dry-run` does not execute the notes command, so the preview says
  `Empty release notes` even when the notes file is complete.
- Without `GITHUB_TOKEN` / `GITLAB_TOKEN`, release-it never calls the platform API
  and falls back to a web release form — and `isAuthenticated()` still returns true
  during a dry run, so a dry run cannot detect the missing token.
- The generated configuration and notes live in `<git dir>/release-it-skill/`, not
  in the working tree, because release-it's own `git.requireCleanWorkingDir` would
  otherwise refuse the release.
- A declared version cannot go through npm: `npm version 5.1.7.12_weiyuan_…` dies with
  `Invalid version` and takes the whole run down before the tag exists. This skill
  passes `--no-npm`, so nothing changes in the repository and release-it tags the
  commit already at `HEAD` (no release commit is created).
- `${version}` is truncated in `git.commitMessage` and `git.tagAnnotation`
  (`parseVersion()` keeps only `5.1.7`); the skill substitutes the literal itself.
- Only `ez-xu/release-it` keeps a declared version verbatim — upstream 21.1.1 coerces
  it. The skill reads the installed `lib/plugin/version/Version.js` to prove the fix is
  there and otherwise falls back to `npx --yes github:ez-xu/release-it`.

## Full detail

`SKILL.md` carries the required behaviour and the complete gotcha list;
`references/` documents every `release-it` interface (CLI, configuration, plugins,
hooks, programmatic API, and an option-to-plugin index) for version 21.1.1, plus
`declared-versions.md` for non-semver release identifiers.
