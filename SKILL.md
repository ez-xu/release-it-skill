---
name: release-it-skill
description: >-
  Cut one release of a repository with release-it 21.1.1 and prove it: bump the
  manifest, commit, push, create the annotated tag, create the GitHub or GitLab
  release with generated release notes, publish the package to npm, and then read
  every deliverable back from git, the platform and the registry so the tag, the
  notes, the package and the recorded links all describe the same commit. When
  that cannot be proven the run refuses with exit 2 and publishes nothing.
  Activate for requests such as 帮我发布一个版本, 打标签并发布, bump and publish,
  cut a release, tag and create a release with notes, publish this package to npm,
  generate release notes from commits, 为什么 release 没有发布说明,
  release-it 怎么配置, or when a tag, a release and a published package must be
  shown to agree. Do not use for firmware or embedded releases, for pushing a
  group of repositories (that is push-release-pipeline-skill), for authoring a
  CHANGELOG by hand, or to repair a tag that has already been published.
license: MIT
activation: /release-it-skill
metadata:
  author: agent-skills-platform
  version: 1.0.0
  created: 2026-10-16
  last_reviewed: 2026-10-16
  review_interval_days: 90
  dependencies:
    - name: release-it
      type: command
      note: 21.1.1; resolved from node_modules/.bin, then PATH, then npx --yes release-it@21.1.1
    - name: node
      type: runtime
      note: "release-it 21.1.1 engines are ^22.22.2 || ^24.15.0 || >=26.0.0; anything else warns"
    - name: git
      type: command
      note: 2.40 or newer; the tag, the commit and the remote refs are read back with it
    - name: gh
      type: command
      note: required only for GitHub remotes; the release is created by release-it and read back with gh
    - name: glab
      type: command
      note: required only for GitLab remotes; the release is created by release-it and read back with glab
    - name: npm
      type: command
      note: required only when the package is published; the published version is read back with npm view
    - name: python
      type: runtime
      note: 3.9 or newer; the pipeline is standard library only
    - name: api.github.com
      type: service
      url: https://api.github.com/
      note: reached by gh when the GitHub release is created and read back
    - name: github.com
      type: service
      url: https://github.com/
      note: the release page, the tag page and the compare link are built from this host
    - name: registry.npmjs.org
      type: service
      url: https://registry.npmjs.org/
      note: reached by npm when the package is published and read back
    - name: www.npmjs.com
      type: service
      url: https://www.npmjs.com/package
      note: the package page recorded in the plan and the report
    - name: raw.githubusercontent.com
      type: service
      url: https://raw.githubusercontent.com/
      note: the release-it JSON schema URL written into the generated configuration
provenance:
  maintainer: Jinghan Xu
  version: 1.0.0
  created: 2026-10-16
  source_references:
    - https://github.com/ez-xu/release-it
    - https://github.com/release-it/release-it
    - https://www.npmjs.com/package/release-it
    - https://github.com/release-it/release-it/blob/main/docs/configuration.md
    - https://github.com/release-it/release-it/blob/main/docs/plugins.md
    - https://github.com/release-it/release-it/blob/main/docs/environment-variables.md
---

# /release-it-skill

Wrap `release-it` so that one command produces four deliverables that all describe
the same commit, and so that a run which cannot prove that publishes nothing.

The four deliverables are exactly what the request asked for:

| Deliverable | Where it comes from | How it is confirmed |
| --- | --- | --- |
| The tag | release-it creates an annotated `${version}` tag and pushes it | `git rev-list -n 1 <tag>` equals HEAD, and `git ls-remote --tags origin` shows the same commit |
| The release (with release notes) | release-it's GitHub/GitLab release plugin, notes generated from conventional commits | the release is read back with `gh release view` / `glab release view` |
| The package | `npm publish` through release-it's npm plugin | `npm view <name> version gitHead` names the same commit |
| The links | recorded in the plan and the report | every recorded URL points at the released version |

`release-it` ships with `github.release: false` and `gitlab.release: false`, so a
stock run creates **no** release. This skill always writes the release setting
explicitly, because a release without notes is not the deliverable.

## Run

The skill is driven by one spec file, so the same invocation works for a plan, a
release, a verification or a sandbox test.

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

Modes:

```bash
# 1. Resolve and show what would be released. Writes nothing.
python3 scripts/run_pipeline.py --input spec.json --output release-plan.json

# 2. Release for real: bump, commit, push, tag, create the release, publish.
#    Add "publish": false to skip npm, "release": false to skip the platform release,
#    or "dry_run": true for release-it's own preview.
python3 scripts/run_pipeline.py --input spec.json --output release-report.json

# 3. Read an existing release back and judge it.
python3 scripts/run_pipeline.py --input verify-spec.json --output release-report.json

# 4. Exercise the whole thing against a throwaway repository (nothing leaves the machine).
python3 scripts/run_pipeline.py --input fixture-spec.json --output release-report.json
```

Useful spec keys: `mode`, `repo`, `increment` (`patch|minor|major|prepatch|preminor|premajor|prerelease`),
`version` (an explicit version wins over `increment`), `publish`, `release`, `dry_run`,
`pre_release_id`, `pre_release_base`, `tag_prefix`, `manifest`, `sandbox`, `scenario`,
`offline`, `allow_dirty`, `allow_no_upstream`, `publish_package_manager`, `state_dir`.

`version` also accepts a **declared version** — a release identifier that is not semantic but
that `ez-xu/release-it` keeps verbatim, such as `5.1.7.12_weiyuan_G200464803_20261016_8aef61de`
or `V5.1.7.12_weiyuan_G200464803_20261016_8aef61de`. It is carried unchanged, never compared
and never incremented, and a string release-it would silently coerce is refused instead. See
`references/declared-versions.md`.

Exit codes: **0** success, **2** refused (nothing was published), **1** failed.

## Required behavior

1. Resolve the repository first: provider, project, branch, manifest version, latest tag
   and the configured remote URL. Every later decision reads those facts and never
   re-derives them from the environment.
2. Refuse, with exit 2 and no side effects, when the working tree is dirty, the branch
   has no upstream, HEAD is detached, the manifest is unreadable, the resolved version is
   not strictly newer than the latest tag and the manifest, or the tag already exists on
   `origin`. A wrong public tag cannot be withdrawn by this skill, so an unprovable run
   must publish nothing.
3. Derive the version from the latest tag plus the requested increment, honouring the
   repository's existing tag prefix (`v` only when the latest tag has one), or take an
   explicit version as given.
4. Write the generated release-it configuration and the generated notes **outside the
   working tree** — the default is `<git dir>/release-it-skill/` — because release-it's
   own `git.requireCleanWorkingDir` would otherwise refuse the release the skill just
   configured.
5. Generate the release notes from conventional commits since the previous tag as a list of
   **feature items, one per line** — a single bullet carrying the commit subject, its short
   id and any issue it names — under a `###` heading, with no prose and no boilerplate
   repeated from the report. A breaking change is listed even when it is not a feature, and a
   release with no feature item lists its highest-ranked section instead, so the notes are
   never empty. Hand them to release-it as a command whose stdout is the notes;
   `releaseNotes` is executed as a shell command, so a multi-line string cannot be passed as
   a config value.
6. Run release-it once, non-interactively, with the version as the positional argument
   so nothing depends on a prompt or on the silent `patch` fallback that CI mode would
   otherwise choose.
7. After the run, read every deliverable back: the tag locally and its dereferenced
   commit, the tag on `origin`, HEAD, the manifest version at HEAD, the commit subject,
   the release through the platform API, and the package through the registry. A read
   that cannot be performed is reported as `skipped` with its reason — never as a pass.
8. Report the four links (repository, tag, release, compare) plus the package page, and
   state plainly which deliverable could not be confirmed and what would confirm it.
9. Never write a token into the configuration or into an artifact. Tokens are read from
   `GITHUB_TOKEN` / `GITLAB_TOKEN` only, and every generated message passes through a
   redactor that strips `gh[pousr]_…`, `glpat-…` and `npm_…` before it is printed.
10. Treat a **declared** version as a first-class version: carry it unchanged, never compare
    it, never increment it. Refuse anything release-it would silently rewrite, naming the
    corrected command. For a declared version the npm plugin is switched off, `${version}` is
    substituted by the skill so no truncating template reaches release-it, the runner must be
    shown to carry the fork's fix, and the checks that cannot apply are reported `skipped`
    with their reason. See `references/declared-versions.md`.

## Gotchas

- **A stock release-it run creates no release.** `config/release-it.json` ships
  `github.release: false` and `gitlab.release: false`; `npm.publish` is the only thing
  that is on by default.
- **`github.releaseNotes` is a shell command, not text.** `GitRelease.beforeRelease()`
  runs it and takes the stdout; when it is unset the notes are the changelog. A
  multi-line string in the config is executed as a command and fails.
- **`--dry-run` never executes the notes command.** release-it marks it with `!` and the
  preview prints `Empty release notes` even though the notes file is complete. Do not
  read that line as "the notes are broken".
- **Without a token release-it silently degrades.** It prints
  `WARNING Environment variable "GITHUB_TOKEN" is required for automated GitHub Releases.`
  and falls back to a web form whose URL embeds the whole notes body. `GitHub.isAuthenticated()`
  returns `true` during a dry run, so a dry run cannot detect the missing token. Review an
  unauthenticated run before trusting its release.
- **release-it 21.1.1 requires Node `^22.22.2 || ^24.15.0 || >=26.0.0`.** Node 24.14.0 is
  below the floor and warns; the release still runs, but record the warning.
- **Arrays replace, they do not merge.** `c12`/`defu` means a config that sets
  `git.pushArgs` drops the shipped `["--follow-tags"]`, so this skill always writes every
  element it needs.
- **`.releaserc` is not read.** `lib/config.js` loads with `rcFile: false`; use
  `.release-it.json`, `.release-it.js`, `.release-it.yaml` or the `release-it` key in
  `package.json`.
- **An annotated tag is two objects.** `git ls-remote --tags origin` lists both
  `refs/tags/v1.1.0` and `refs/tags/v1.1.0^{}`; compare the dereferenced commit
  (`git rev-list -n 1 <tag>`), never the tag object id.
- **`git remote get-url origin` applies `url.<base>.insteadOf` rewriting** and can return a
  local path where the configured URL is what matters. Read `git config --get remote.origin.url`.
- **On Windows npm is `npm.CMD`.** `shutil.which` finds it through `PATHEXT` but
  `CreateProcess` cannot start a batch file — the failure is `[WinError 2] 系统找不到指定的文件。`.
  Every subprocess launch wraps `.cmd`/`.bat` in `cmd.exe /c`.
- **`git` writes its object files read-only**, so `shutil.rmtree(..., ignore_errors=True)`
  silently leaves a sandbox behind on Windows and the next build dies with
  `FileExistsError: [WinError 183]`.
- **A declared version belongs in the tag, not in the version string.** `V5.1.7.12_weiyuan_…`
  is coerced by release-it's own semver code (`WARNING Coerced invalid semver version
  "V5.1.7.12_weiyuan_…" into "5.1.7"`); only the bare `5.1.7.12_weiyuan_…` is kept verbatim.
  This skill moves a leading `v`/`V` into `git.tagName`, so the tag is still exactly the
  declared string, and warns that it did.
- **npm cannot carry a declared version.** A real run against stock settings dies at the
  manifest step with `npm error Invalid version: 5.1.7.12_weiyuan_…` and leaves nothing
  behind — no commit, no tag. The skill passes `--no-npm` and switches publishing off, so the
  npm plugin never runs.
- **`${version}` is truncated in the commit message and the tag annotation.**
  `git.commitMessage` and `git.tagAnnotation` are routed through `parseVersion()` in
  `lib/utils.js`, which shortens a non-semver version to its prefix (`git commit --message
  Release 5.1.7`). The skill substitutes the literal itself, so both carry the full string.
- **With the npm plugin off there is no release commit to write.** Nothing in the repository
  changes, so release-it tags the commit that is already `HEAD`; `commit-subject` is reported
  `skipped` for a declared version instead of failing.
- **Upstream release-it truncates a declared version.** The runner must carry the fork's fix
  (`npm install github:ez-xu/release-it`). The skill proves it by reading the installed
  `lib/plugin/version/Version.js` and otherwise falls back to `npx --yes github:ez-xu/release-it`.

## References

Read these for the documented interfaces of `release-it` 21.1.1; they are
reference material, not steps to execute.

- Read `references/interfaces-cli.md` for every flag, alias, negation and dynamic option.
- Read `references/interfaces-config.md` for every config location, precedence rule and key, with the shipped defaults.
- Read `references/interfaces-plugins.md` for the internal and external plugins, the `Plugin` contract and the plugin API.
- Read `references/interfaces-hooks.md` for the six lifecycle hooks and their exact order.
- Read `references/interfaces-api.md` for the programmatic Node API (`runTasks`, `Config`, `Plugin`).
- Read `references/interfaces-matrix.md` for the option-to-plugin-to-hook index.
- Read `references/declared-versions.md` for non-semver declared versions: the fork's rule, the tag-prefix split, and what npm, the commit message and the release body can carry.
- Read `references/_recon-facts.md` for what was verified, how, and the twelve things that could not be.
