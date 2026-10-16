# release-it — Interface Matrix (index of the whole surface)

**Documented version: release-it 21.1.1** — upstream `release-it/release-it` @ `main`.
The `ez-xu/release-it` fork is a plain fork with **zero custom commits** (compare API `ahead_by=0`), so
everything here documents **stock upstream release-it**.

**How to read this file.** Every row is one interface: its exact name, a one-line description, and the
reference file that details it. Flags are written as they appear in `--help` / argv; config keys are
written as they appear in JSON/TOML (`kebab-case` where the option name contains a hyphen, nested
otherwise).

Sources: `lib/args.js`, `lib/config.js`, `lib/index.js`, `lib/plugin/Plugin.js`,
`lib/plugin/factory.js`, `config/release-it.json`, `schema/release-it.json`, `types/**`, `docs/**`,
`README.md`.

## Reference files

| File | Covers |
|---|---|
| [`interfaces-plugins.md`](./interfaces-plugins.md) | Plugin protocol, plugin method contract, plugin author interface, notable plugins |
| [`interfaces-hooks.md`](./interfaces-hooks.md) | Hook name grammar, emission order, template context, env vars, failure handling |
| [`interfaces-api.md`](./interfaces-api.md) | Programmatic Node API, `runTasks`, `Config`, `Plugin`, CI and dry-run contracts |
| `interfaces-cli.md` | *(not owned here — sibling agent)* every CLI flag in detail |
| `interfaces-config.md` | *(not owned here — sibling agent)* every config key in detail |

---

## 1. CLI flags

Aliases: `-c` config, `-d` dry-run, `-h` help, `-i` increment, `-v` version, `-V` verbose.
Nested flags are addressed with dots (`--git.tagName=x`). Every **string** option also accepts a
`--no-<name>` form, and **every** boolean accepts `--no-<name>`. A positional argument is the
increment (`release-it minor`).

### Top-level

| Flag | Alias | Type | Description | Details |
|---|---|---|---|---|
| `--config` | `-c` | string | Path to the config file, `false` to disable file loading. | interfaces-cli.md |
| `--configDir` | | string | Directory to resolve config from. | interfaces-cli.md |
| `--extends` | | string | Base config to inherit from (c12). | interfaces-cli.md |
| `--dry-run` | `-d` | boolean | Print commands instead of executing writes; no side effects. | interfaces-cli.md · interfaces-api.md §5 |
| `--increment` | `-i` | string | Version increment: `major`/`minor`/`patch`/`pre*` or an explicit semver. | interfaces-cli.md |
| `--preRelease` | | boolean \| string | Enable pre-releases; a value sets the pre-release id. **Mixed** type. | interfaces-cli.md |
| `--preReleaseId` | | string | Pre-release identifier (`alpha`, `beta`, `rc`…). | interfaces-cli.md |
| `--preReleaseBase` | | string | Base version to pre-release from. | interfaces-cli.md |
| `--snapshot` | | boolean \| string | Release a snapshot version. **Mixed** type. | interfaces-cli.md |
| `--ci` | | boolean | Fully automated, no prompts. Auto-enabled when `ci-info` detects CI. | interfaces-api.md §4 |
| `--only-version` | | boolean | Print the version and exit — prompt-only mode. | interfaces-api.md §2.5 |
| `--release-version` | | boolean | Print the next version and `process.exit`. Implies `ci`. | interfaces-api.md §2.5 |
| `--changelog` | | boolean | Print the changelog and `process.exit`. Implies `ci`. | interfaces-api.md §2.5 |
| `--verbose` | `-V` | boolean (repeatable) | Increase verbosity; repeat for debug output. | interfaces-cli.md |
| `--quiet` | | boolean | Suppress non-essential output. | interfaces-cli.md |
| `--version` | `-v` | boolean | Print the release-it version and exit. | interfaces-api.md §7 |
| `--help` | `-h` | boolean | Print help and exit. | interfaces-api.md §7 |
| `--hooks` | | boolean | Enable/disable all hooks (`--no-hooks`). | interfaces-hooks.md §3 |
| `--hooks.<hook>` | | boolean | Enable/disable one hook, e.g. `--no-hooks.before:init`. | interfaces-hooks.md §3 |
| `--hooks.<hook>=<cmd>` | | string | Set a hook from the command line (dynamic option). | interfaces-hooks.md §3, §8 |
| `--plugins.<name>=<opt>` | | string \| boolean | Set a plugin option from the command line (dynamic option). | interfaces-plugins.md §2 |
| `--git` / `--github` / `--gitlab` / `--npm` | | boolean | Enable/disable a whole core plugin. | interfaces-config.md |

### `git.*`

| Flag | Type | Description | Details |
|---|---|---|---|
| `--git.addUntrackedFiles` | boolean | `git add` untracked files before committing. | interfaces-config.md |
| `--git.changelog` | string | Command that generates the changelog for the commit body. | interfaces-config.md |
| `--git.commit` | boolean | Commit the release. | interfaces-config.md |
| `--git.commitArgs` | array | Extra args for `git commit`. | interfaces-config.md |
| `--git.commitMessage` | string | Commit message template, e.g. `chore: release v${version}`. | interfaces-config.md · interfaces-hooks.md §4 |
| `--git.commitsPath` | string | Restrict changelog generation to this path. | interfaces-config.md |
| `--git.getLatestTagFromAllRefs` | boolean | Consider tags from all refs when finding the latest. | interfaces-config.md |
| `--git.push` | boolean | Push the commit and tag. | interfaces-config.md |
| `--git.pushArgs` | array | Extra args for `git push`. | interfaces-config.md |
| `--git.pushRepo` | string | Remote to push to. | interfaces-config.md |
| `--git.requireBranch` | array \| string | Branch(es) the release is allowed from. | interfaces-config.md |
| `--git.requireCleanWorkingDir` | boolean | Abort when the working directory is dirty. | interfaces-config.md |
| `--git.requireCommits` | boolean | Require commits since the last tag. | interfaces-config.md |
| `--git.requireCommitsFail` | boolean | Fail (rather than warn) on a missing-commits skip. | interfaces-config.md |
| `--git.requireUpstream` | boolean | Require the current branch to have an upstream. | interfaces-config.md |
| `--git.tag` | boolean | Create a Git tag. | interfaces-config.md |
| `--git.tagAnnotation` | string | Annotated-tag message. | interfaces-config.md |
| `--git.tagArgs` | array | Extra args for `git tag`. | interfaces-config.md |
| `--git.tagExclude` | string | Tag glob to exclude. | interfaces-config.md |
| `--git.tagMatch` | string | Tag glob to match (default `v*.*.*` style patterns). | interfaces-config.md |
| `--git.tagName` | string | Tag name template, e.g. `v${version}`. | interfaces-config.md · interfaces-hooks.md §4 |

### `npm.*`

| Flag | Type | Description | Details |
|---|---|---|---|
| `--npm` | boolean | Enable/disable the npm plugin. | interfaces-config.md |
| `--npm.allowSameVersion` | boolean | Allow publishing a version identical to the published one. | interfaces-config.md |
| `--npm.ignoreVersion` | boolean | Don't verify the published version. | interfaces-config.md |
| `--npm.otp` | string | One-time password for the registry. | interfaces-config.md |
| `--npm.publish` | boolean | Publish to npm. | interfaces-config.md |
| `--npm.publishArgs` | array | Extra args for `npm publish`. | interfaces-config.md |
| `--npm.publishPackageManager` | string | Package manager to publish with. | interfaces-config.md |
| `--npm.publishPath` | string | Directory to publish from. | interfaces-config.md |
| `--npm.skipChecks` | boolean | Skip `npm ping` / auth checks. | interfaces-config.md |
| `--npm.stage` | boolean | Stage the publish instead of publishing. | interfaces-config.md |
| `--npm.tag` | string | Dist-tag to publish under (default `latest`). | interfaces-config.md |
| `--npm.timeout` | string | Registry request timeout. | interfaces-config.md |
| `--npm.versionArgs` | array | Extra args for the version command. | interfaces-config.md |

### `github.*`

| Flag | Type | Description | Details |
|---|---|---|---|
| `--github` | boolean | Enable/disable the GitHub plugin. | interfaces-config.md |
| `--github.assets` | array | Globs of files to upload as release assets. | interfaces-config.md |
| `--github.autoGenerate` | boolean | Let GitHub generate release notes. | interfaces-config.md |
| `--github.comments.issue` | string | Comment on issues referenced in the release. | interfaces-config.md |
| `--github.comments.pr` | string | Comment on pull requests referenced in the release. | interfaces-config.md |
| `--github.comments.submit` | boolean | Actually submit those comments. | interfaces-config.md |
| `--github.discussionCategoryName` | boolean \| string | Create a discussion in this category. **Mixed** type. | interfaces-config.md |
| `--github.draft` | boolean | Create the release as a draft. | interfaces-config.md |
| `--github.host` | string | GitHub host (GitHub Enterprise). | interfaces-config.md |
| `--github.makeLatest` | boolean \| string | Mark the release as latest. **Mixed** type. | interfaces-config.md |
| `--github.preRelease` | boolean | Mark the release as a pre-release. | interfaces-config.md |
| `--github.proxy` | string | HTTP proxy for API calls. | interfaces-config.md |
| `--github.release` | boolean | Create a GitHub Release. | interfaces-config.md |
| `--github.releaseName` | string | Release title template. | interfaces-config.md |
| `--github.releaseNotes` | string | Release body template. | interfaces-config.md |
| `--github.releaseNotes.commit` | string | Release notes per commit. | interfaces-config.md |
| `--github.releaseNotes.excludeMatches` | array | Patterns excluded from release notes. | interfaces-config.md |
| `--github.skipChecks` | boolean | Skip remote/connectivity checks. | interfaces-config.md |
| `--github.timeout` | string | API timeout. | interfaces-config.md |
| `--github.tokenRef` | string | Env var name holding the token (default `GITHUB_TOKEN`). | interfaces-hooks.md §5 · interfaces-config.md |
| `--github.update` | boolean | Update an existing release. | interfaces-config.md |
| `--github.web` | boolean | Open the release in a browser. | interfaces-config.md |

### `gitlab.*`

| Flag | Type | Description | Details |
|---|---|---|---|
| `--gitlab` | boolean | Enable/disable the GitLab plugin. | interfaces-config.md |
| `--gitlab.assets` | array | Globs of files to upload as release assets. | interfaces-config.md |
| `--gitlab.autoGenerate` | boolean | Let GitLab generate release notes. | interfaces-config.md |
| `--gitlab.certificateAuthorityFile` | string | CA bundle path. | interfaces-config.md |
| `--gitlab.certificateAuthorityFileRef` | string | Env var holding the CA bundle path. | interfaces-config.md |
| `--gitlab.draft` | boolean | Create the release as a draft. | interfaces-config.md |
| `--gitlab.genericPackageRepositoryName` | string | Generic package repository for assets. | interfaces-config.md |
| `--gitlab.milestones` | array | Milestones to attach to the release. | interfaces-config.md |
| `--gitlab.origin` | string | GitLab origin/remote to use. | interfaces-config.md |
| `--gitlab.preRelease` | boolean | Mark the release as a pre-release. | interfaces-config.md |
| `--gitlab.proxy` | boolean | Use the origin's proxy for API calls. | interfaces-config.md |
| `--gitlab.release` | boolean | Create a GitLab Release. | interfaces-config.md |
| `--gitlab.releaseName` | string | Release title template. | interfaces-config.md |
| `--gitlab.releaseNotes` | string | Release body template. | interfaces-config.md |
| `--gitlab.repoId` | string | Project id override. | interfaces-config.md |
| `--gitlab.secure` | boolean | Force `https://`. | interfaces-config.md |
| `--gitlab.skipChecks` | boolean | Skip remote/connectivity checks. | interfaces-config.md |
| `--gitlab.tokenHeader` | string | Header carrying the token (default `PRIVATE-TOKEN`). | interfaces-config.md |
| `--gitlab.tokenRef` | string | Env var name holding the token (default `GITLAB_TOKEN`). | interfaces-hooks.md §5 · interfaces-config.md |
| `--gitlab.useGenericPackageRepositoryForAssets` | boolean | Upload assets to the generic package repo. | interfaces-config.md |
| `--gitlab.useIdsForUrls` | boolean | Use numeric ids in release URLs. | interfaces-config.md |

---

## 2. Config keys

Each key is a `hook`-free slice of the same option tree the CLI writes into.

| Config key | Type | Description | Details |
|---|---|---|---|
| `$schema` | string | JSON Schema reference (`schema/release-it.json`). Editor-only. | interfaces-config.md |
| `extends` | string \| object | Base config to inherit from (c12). | interfaces-config.md |
| `plugins` | object | Map of package name or path → plugin options. Keys become namespaces. | interfaces-plugins.md §2 |
| `hooks` | object | Map of hook name → command or array of commands. | interfaces-hooks.md §3 |
| `git` | object \| `false` | Git plugin section; `false` disables it. | interfaces-config.md |
| `npm` | object \| `false` | npm plugin section; `false` disables it. | interfaces-config.md |
| `github` | object \| `false` | GitHub plugin section; `false` disables it (default `release: false`). | interfaces-config.md |
| `gitlab` | object \| `false` | GitLab plugin section; `false` disables it (default `release: false`). | interfaces-config.md |
| `increment` | string \| `false` | Increment to use; `false` means "use the version already in the manifest". | interfaces-config.md |
| `preRelease` | string | Pre-release id shorthand; expands into `version` at config-init time. | interfaces-config.md · docs/pre-releases.md |
| `preReleaseBase` | number \| string | Base for pre-release increments. | interfaces-config.md |
| `dry-run` | boolean | Dry-run mode. **Kebab-case — `release({ 'dry-run': true })`, not `dryRun`.** | interfaces-api.md §5 |
| `ci` | boolean | Non-interactive mode. Default is `ci-info`'s detection. | interfaces-api.md §4 |
| `verbose` | boolean \| number | Verbosity level (repeatable on the CLI). | interfaces-config.md |
| `quiet` | boolean | Quiet mode. | interfaces-config.md |
| `only-version` | boolean | Prompt for the version only. | interfaces-api.md §2.5 |
| `release-version` | boolean | Print the version and exit; implies `ci`. | interfaces-api.md §2.5 |
| `changelog` | boolean | Print the changelog and exit; implies `ci`. | interfaces-api.md §2.5 |
| `config` | string \| `false` | Config file path; `false` skips file loading. | interfaces-config.md |
| `configDir` | string | Directory to resolve config from. | interfaces-config.md |
| `env` | object | *(plugin/hook exec path)* extra key/value pairs merged into an exec environment. | interfaces-config.md |
| `snapshot` | boolean \| string | Snapshot release. | interfaces-config.md |

Formats: `.release-it.json`, `.release-it.js`/`.cjs`/`.mjs`, `.release-it.toml`,
`.release-it.yaml`/`.yml`, a `release-it` key in `package.json`, or `--config <path>`. Config files are
loaded with [c12], so `extends` and `$schema` are honoured.

---

## 3. Plugins

The protocol, the full method contract and the notable-plugin table live in
[`interfaces-plugins.md`](./interfaces-plugins.md). Index:

| Plugin topic | One-line description | Details |
|---|---|---|
| `plugins: { "<name>": { …options } }` | Declares a plugin and its options; the key is the package name or a path. | interfaces-plugins.md §2 |
| Key → namespace mapping | A path key's namespace is the file basename (extension stripped). | interfaces-plugins.md §2.1 |
| `RELEASE_IT_PLUGINS` | `unverified` — no such env var appears in `lib/` or `docs/`; plugin resolution is `resolvePlugin` in `lib/plugin/factory.js`. | interfaces-plugins.md §2.2 |
| Plugin methods (12) | `init`, `getName`, `getLatestVersion`, `getChangelog`, `getIncrement`, `getIncrementedVersionCI`, `getIncrementedVersion`, `beforeBump`, `bump`, `beforeRelease`, `release`, `afterRelease`. | interfaces-plugins.md §3.1 |
| Statics | `static isEnabled(options)` (default `true`), `static disablePlugin(options)`. | interfaces-plugins.md §3.2 |
| Helpers on `this` | `getInitialOptions`, `getContext`, `setContext`, `exec`, `registerPrompts`, `showPrompt`, `step`. | interfaces-plugins.md §3.3 |
| `reduceUntil` | The six getter methods short-circuit: the **first** plugin returning a non-`undefined` value wins. | interfaces-plugins.md §3.1 |
| Plugin-list reversal | `[external, …internal]` for the early phases, `[internal, …external]` for `release`/`afterRelease`. | interfaces-plugins.md §3.1 · interfaces-hooks.md §2 |
| `@release-it/conventional-changelog` | Recommended bump from conventional commits + `CHANGELOG.md`. | interfaces-plugins.md §5 |
| `@release-it/bumper` | Read & write the version from/to any file (json, yaml, toml, ini, xml, html, text). | interfaces-plugins.md §5 |
| `@release-it/keep-a-changelog` | Maintain `CHANGELOG.md` per Keep a Changelog. | interfaces-plugins.md §5 |
| `@release-it-plugins/lerna-changelog` | lerna-changelog integration. | interfaces-plugins.md §5 |
| `@release-it-plugins/workspaces` | Bump and publish each configured workspace. | interfaces-plugins.md §5 |
| `release-it-lerna-changelog` | Deprecated predecessor of the above. | interfaces-plugins.md §5 |
| Starter kit | Minimal scaffold for a new plugin. | interfaces-plugins.md §7 |

Core plugins, in list order: `npm` → `git` → `github` → `gitlab` → `version` (filtered by
`static isEnabled`).

---

## 4. Hooks

Grammar, emission order and evidence live in [`interfaces-hooks.md`](./interfaces-hooks.md). Index:

| Hook form | One-line description | Details |
|---|---|---|
| `before:<lifecycle>` | Fires once per lifecycle, before the **first** plugin of the current list. | interfaces-hooks.md §2 |
| `after:<lifecycle>` | Fires once per lifecycle, after the **last** plugin of the current list. | interfaces-hooks.md §2 |
| `before:<namespace>:<lifecycle>` | Fires before one plugin's lifecycle method. | interfaces-hooks.md §2 |
| `after:<namespace>:<lifecycle>` | Fires after one plugin's lifecycle method; **skipped if it returned `false`**. | interfaces-hooks.md §2 |
| `<lifecycle>` ∈ | `init`, `beforeBump`, `bump`, `beforeRelease`, `release`, `afterRelease`. | interfaces-hooks.md §1, §2.2 |
| `--no-hooks` / `--no-hooks.<name>` | Disable all hooks, or one hook. | interfaces-hooks.md §3 |
| Template context | Every config option plus `version`, `latestVersion`, `changelog`, `name`, `repo.*`, `branchName`, `remoteUrl`, `latestTag`, `secondLatestTag`, `tagTemplate`, `tagName`, `releaseUrl`. | interfaces-hooks.md §4 |
| Hook value type | `string` or `string[]` — **shell commands only**, never JS functions. | interfaces-hooks.md §3 |
| No hooks for getters | `getName`, `getLatestVersion`, `getChangelog`, `getIncrement`, `getIncrementedVersionCI`, `getIncrementedVersion` have **no** hooks. | interfaces-hooks.md §2.1 |
| Failure | A non-zero exit rejects and aborts the whole release. | interfaces-hooks.md §6 |
| `RELEASE_IT_*` env vars | `unverified` — not present; hook values are template variables, not env vars. | interfaces-hooks.md §5 |

---

## 5. Programmatic API

Full signatures and examples: [`interfaces-api.md`](./interfaces-api.md). Index:

| Export / member | Signature | Description | Details |
|---|---|---|---|
| default export | `runTasks(opts, di) → Promise<{ name, changelog, latestVersion, version }>` | Runs the whole release process. Docs import it as `release`. | interfaces-api.md §2 |
| `Config` (named) | `new Config(config = {})`, `await config.init()` | Option resolution, context and flags. **`init()` is required** before use. | interfaces-api.md §3.1 |
| `Plugin` (named) | `class X extends Plugin` | Base class for plugins. | interfaces-api.md §3.2 · interfaces-plugins.md §4 |
| `config.getContext(path?)` | `→ Object` | The merged option + runtime context. | interfaces-api.md §3.1 |
| `config.setContext(options)` | `→ void` | How plugins publish `version`, `repo`, `tagName`… | interfaces-api.md §3.1 |
| `config.setCI(value = true)` | `→ void` | Force CI mode mid-run (used by `--only-version`). | interfaces-api.md §3.1 |
| `config.isCI` / `isDryRun` / `isIncrement` / `isVerbose` / `isQuiet` / `isDebug` | getter `→ boolean`/`number` | Flags derived from the merged options. | interfaces-api.md §3.1 |
| `config.isReleaseVersion` / `isChangelog` / `isPromptOnlyVersion` | getter `→ boolean` | One-shot CLI modes; the first two also force `isCI`. | interfaces-api.md §3.1 |
| `di` injection | `{ config, log, spinner, prompt, shell }` | Dependency-injection seam for tests and embedding. | interfaces-api.md §2.2 |
| `getIncrementedVersionCI` | plugin method | Non-interactive version resolution, run first so the banner shows the right version. | interfaces-api.md §4.2 |
| `--ci` contract | option `ci: true` | No prompts anywhere; `Version` returns `null` rather than prompting. | interfaces-api.md §4 |
| Dry-run contract | option `'dry-run': true` | `Shell` prints write commands (`! cmd`) and skips them; read-only commands still run. | interfaces-api.md §5 |
| Package shape | ESM only (`"type": "module"`), `exports["."] → lib/index.js` | Node `^22.22.2 \|\| ^24.15.0 \|\| >=26.0.0`. | interfaces-api.md §1 |
| `checkGitStatus()` | — | `unverified` — not a public export; git checks live in the `git` plugin's `init()`. | interfaces-api.md §8 |
| `ReleaseIt` class / `releaseIt` export / `dryRun()` | — | `unverified` — do not exist in 21.1.1. | interfaces-api.md §8 |

---

## 6. Coverage legend

| Marker | Meaning |
|---|---|
| *(plain row)* | Verified against the sources listed at the top. |
| `unverified — <reason>` | A source did not confirm it. **Never assume these exist.** |

[c12]: https://github.com/unjs/c12
[`ci-info`]: https://www.npmjs.com/package/ci-info
[semver]: https://www.npmjs.com/package/semver
