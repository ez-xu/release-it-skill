# release-it — Command-Line Interface Reference

**Documented version: `release-it` 21.1.1** (npm `latest` dist-tag; `npm view release-it version` → `21.1.1`).
Applies to stock upstream `release-it/release-it`. See [`_recon-facts.md`](./_recon-facts.md) for provenance.

Primary source: the shipped parser, `lib/args.js` (334 lines), and the shipped help text in `lib/cli.js`.
Every row below cites its source. `npm pkg` = local copy at
`_probe/node_modules/release-it/` (installed from `release-it@21.1.1`).

---

## 1. Invocation and subcommands

release-it has **no subcommands**. It has exactly **one command**: the default action, plus two
short-circuit flags that print and exit without releasing.

| # | Invocation | Purpose | Source |
|---|-----------|---------|--------|
| 1 | `release-it [increment] [options]` | The release flow. Optional **single positional** is the increment (`major`/`minor`/`patch`/`pre*` or an explicit version). | `lib/cli.js:8` help text; `lib/args.js:332` |
| 2 | `release-it --help` / `-h` | Prints help text, exits `0`. Does not run the release. | `lib/cli.js:34-41` |
| 3 | `release-it --version` / `-v` | Prints `v<version>` (e.g. `v21.1.1`), exits `0`. **This is release-it's own version, not your project's.** | `lib/cli.js:28,34` |

There are **no other subcommands** — no `release-it init`, `release-it config`, etc.
(Project scaffolding is a separate package entry point: `npm init release-it`.)

```bash
# minimal invocation
npx release-it patch
npx release-it minor --ci
npx release-it --release-version        # print next version, release nothing
```

### Positional argument rules
| Rule | Detail | Source |
|------|--------|--------|
| Max 1 positional | A 2nd positional throws `Unexpected positional argument "<x>".` | `lib/args.js:310-312` |
| Positional = increment | `options.increment = positionals[0] ?? options.increment` — positional **overrides** `--increment` | `lib/args.js:332` |
| Positionals must come last | Node's `parseArgs` convention; the error text says to put a leading-dash positional after `--` | `lib/args.js:300-306` (empirical, `--nope` error) |

---

## 2. Complete flag table

`Type` is the declared parse type: `boolean` (`--flag`), `string` (`--flag=value` or `--flag value`),
`array` (`multiple: true`), or `mixed` (boolean **or** string).

### 2.1 Core flags

| Flag | Short | Type | Default | What it does | Source |
|------|-------|------|---------|--------------|--------|
| `--increment` | `-i` | string | `"patch"` (per help); **absent** from the config object unless supplied | Increment `major`/`minor`/`patch`/`pre*`, or an explicit version string. Positional form is equivalent. | `lib/cli.js:15`; `lib/args.js:131` |
| `--config` | `-c` | string | `".release-it"` | Path to the configuration file. c12 resolves extensions. `--config=false` disables config-file loading entirely. | `lib/args.js:128`; `lib/config.js:169-174` |
| `--configDir` | — | string | `process.cwd()` | Base directory used to resolve the config file. | `lib/args.js:65`; `lib/config.js:177-179` |
| `--dry-run` | `-d` | boolean | — | Do not touch or write anything; show the commands that *would* run. Read-only commands still execute (`$`), mutating ones print as `!`. | `lib/cli.js:13`; `docs/dry-runs.md`; `lib/config.js:53-55` |
| `--help` | `-h` | boolean | — | Print help, exit `0`. | `lib/cli.js:14,34-37` |
| `--version` | `-v` | boolean | — | Print release-it's version, exit `0`. | `lib/cli.js:18,34-36` |
| `--verbose` | `-V` | boolean, repeatable | — | `-V` prints output of every **user hook**; `-VV` also prints **internal** command output. Collapses to the count of consecutive trues after the last false. Config equivalent: `verbose: 2`. | `lib/cli.js:22-23`; `lib/args.js:132,266-271` |
| `--quiet` | — | boolean | `false` | Suppress preview output (changelog/changeset/release notes) during the release flow. Does **not** affect `--changelog` mode. | `lib/cli.js:21`; `schema/release-it.json` |
| `--ci` | — | boolean | auto-detected | No prompts, no interaction. Activated automatically in CI environments. | `lib/cli.js:16`; `lib/config.js:110` |
| `--only-version` | — | boolean | — | Prompt **only** for the version; automate everything after. Implies CI for the remaining steps. | `lib/cli.js:17`; `lib/index.js:115-117` |
| `--release-version` | — | boolean | — | Print the next version and exit `0`; release nothing. Prints nothing if no next version. | `lib/cli.js:19`; `lib/index.js:105-110` |
| `--changelog` | — | boolean | — | Print the changelog for the version to be released, then exit. | `lib/cli.js:20`; `lib/index.js:65-73` |

### 2.2 Plugin enable/disable shorthands

| Flag | Type | Effect | Source |
|------|------|--------|--------|
| `--git` / `--no-git` | boolean | Enable/disable the whole `git` plugin. `--no-git` skips commit, tag and push. | `lib/args.js:16`; `docs/git.md` |
| `--npm` / `--no-npm` | boolean | Disable ⇒ `npm: false`: ignores `package.json`, no version bump, no publish. | `lib/args.js:21`; `docs/npm.md` |
| `--github` / `--no-github` | boolean | Enable/disable the `github` plugin. | `lib/args.js:17` |
| `--gitlab` / `--no-gitlab` | boolean | Enable/disable the `gitlab` plugin. | `lib/args.js:18` |
| `--hooks` / `--no-hooks` | boolean | `--no-hooks` skips **all** hooks. | `lib/args.js:20`; `README.md` |

```bash
release-it --no-git                    # bump only, touch no git
release-it --no-npm                    # skip npm entirely
release-it minor --no-hooks            # run release, skip every hook
release-it --no-npm.publish            # keep version bump, skip only the publish step
```

### 2.3 Increment / pre-release flags

| Flag | Type | Default | What it does | Source |
|------|------|---------|--------------|--------|
| `--preRelease` | **mixed** | absent | Boolean ⇒ start/increment a pre-release; string ⇒ use that pre-release id (e.g. `beta`). | `lib/args.js:23,116`; `lib/config.js:123-133` |
| `--preReleaseId` | string | — | Explicit pre-release identifier when `preRelease` is boolean. | `lib/args.js:68`; `lib/config.js:127` |
| `--preReleaseBase` | string | — | Base version number for the pre-release increment. | `lib/args.js:67`; `lib/config.js:132` |
| `--snapshot` | **mixed** | absent | Boolean/string snapshot release. When a **string**, release-it **hard-codes** several sub-options (see below). | `lib/args.js:26,116`; `lib/config.js:134-141` |
| `--no-increment` | boolean (negation of `--increment`) | — | Do **not** increment; update the last existing tag/version instead. Useful to re-run/update an existing release. | `lib/config.js:57-59`; `README.md` |

`--snapshot=<id>` forces, in `lib/config.js:134-141`:
```js
options.git.tagMatch = `0.0.0-${snapshot}.[0-9]*`;
options.git.getLatestTagFromAllRefs = true;
options.git.requireBranch = '!main';
options.git.requireUpstream = false;
options.npm.ignoreVersion = true;
```

```bash
release-it --preRelease=beta           # 2.0.0 -> 2.0.0-beta.0 / beta.1 ...
release-it --preRelease beta           # same, space-separated form
release-it --preRelease --preReleaseId rc
release-it --no-increment --no-npm     # re-push an existing tag, skip npm publish
```

### 2.4 Dynamic `hooks.*` and `plugins.*` flags

These are **not** in the static option list. They are discovered at parse time (`discoverDynamicOptions`,
`lib/args.js:179-210`).

| Form | Type | Rule | Source |
|------|------|------|--------|
| `--hooks.<name>=<command>` | string | A command is **required**; bare `--hooks.<name>` throws `Option "--hooks.<name>" requires a command.` | `lib/args.js:193-195` |
| `--no-hooks.<name>` | boolean | Disables that single hook. | `lib/args.js:197`; `README.md` |
| `--hooks.<name>` (repeated) | array | Repeated occurrences become a `multiple: true` array. | `lib/args.js:204-208` |
| `--plugins.<name>.<key>[=value]` | boolean or string | No value ⇒ boolean `true`; with value ⇒ string. | `lib/args.js:186,197` |
| `--no-plugins.<name>.<key>` | boolean | Disables a plugin option. | `README.md`; `docs/configuration.md` |
| `--no-plugins.<name>` | boolean | Disables the plugin. | `docs/configuration.md` |

A dynamic option **cannot** be used as both boolean and string
(`Option "--<name>" cannot be used as both a boolean and a string.`, `lib/args.js:200-202`).

```bash
release-it --'hooks.after:release="echo released ${version}"'
release-it --no-hooks.before:init
release-it --no-plugins.@release-it/keep-a-changelog.strictLatest
```

> Hook names contain colons, so quote the whole argument. Note `docs/configuration.md` and `README.md`
> show the `--'…'` form; `--hooks.after:release=…` is the same shape.

### 2.5 Static plugin options accepted as CLI flags

These names are declared in `lib/args.js` and therefore parse as real flags (not dynamic).

**Boolean** (`lib/args.js:28-60`) — each is also negatable as `--no-<name>`:

```
git.addUntrackedFiles          git.commit                     git.getLatestTagFromAllRefs
git.push                       git.requireCleanWorkingDir     git.requireCommits
git.requireCommitsFail         git.requireUpstream            git.tag
npm.allowSameVersion           npm.ignoreVersion              npm.publish
npm.skipChecks                 npm.stage
github.autoGenerate            github.comments.submit         github.discussionCategoryName
github.draft                   github.makeLatest              github.preRelease
github.release                 github.skipChecks              github.update
github.web
gitlab.autoGenerate            gitlab.draft                   gitlab.preRelease
gitlab.proxy                   gitlab.release                 gitlab.secure
gitlab.skipChecks              gitlab.useGenericPackageRepositoryForAssets
gitlab.useIdsForUrls
```

**String** (`lib/args.js:63-101`) — each gets an automatic `--no-<name>` boolean twin:

```
config                         configDir                      extends
increment                      preReleaseBase                 preReleaseId
git.changelog                  git.commitsPath                git.commitMessage
git.pushRepo                   git.tagAnnotation              git.tagExclude
git.tagMatch                   git.tagName
npm.otp                        npm.publishPackageManager      npm.publishPath
npm.tag                        npm.timeout
github.comments.issue          github.comments.pr             github.host
github.proxy                   github.releaseName             github.releaseNotes
github.releaseNotes.commit     github.timeout                 github.tokenRef
gitlab.certificateAuthorityFile  gitlab.certificateAuthorityFileRef
gitlab.genericPackageRepositoryName  gitlab.origin
gitlab.releaseName             gitlab.releaseNotes            gitlab.repoId
gitlab.tokenHeader             gitlab.tokenRef
```

**Array** (`lib/args.js:103-114`) — repeatable; a single `--no-<name>` collapses the array to `false`:

```
git.commitArgs                 git.requireBranch              git.pushArgs
git.tagArgs                    npm.publishArgs                npm.versionArgs
github.assets                  github.releaseNotes.excludeMatches
gitlab.assets                  gitlab.milestones
```

```bash
release-it minor --git.pushArgs=--follow-tags --git.pushArgs=--force
release-it --github.assets=dist/*.zip --gitlab.assets='dist/*.dmg'
release-it --git.requireBranch=main --git.requireBranch=next   # array
release-it --no-git.requireCleanWorkingDir
```

> **Repeating an array flag replaces the default.** `git.pushArgs` defaults to `["--follow-tags"]`;
> supplying it manually drops `--follow-tags` unless you re-add it (`docs/git.md`).

### 2.6 Flags mentioned in the task brief that do NOT exist

| Claimed flag | Finding |
|--------------|---------|
| `--disable-metrics` | **Does not exist.** |
| `--no-metrics` / `--metrics` | **Does not exist.** |

release-it 21.1.1 contains **no metrics/telemetry/analytics code at all**: a recursive grep for
`metric|telemetr|analytics|amplitude|posthog` across every shipped `.js`/`.json`/`.ts`/`.md` file
returns **zero matches**. Any such flag would be rejected with exit code `1`.

### 2.7 Configuration-keys-as-flags (the override mechanism)

The flag list above is *not* the limit of the CLI. **Any configuration key can be set from the
command line and takes highest priority.**

| Aspect | Behaviour | Source |
|--------|-----------|--------|
| Nested key → flag | A config key at path `a.b.c` becomes `--a.b.c=value`. Dots are **structural**: `--github.release` sets `github.release`, not a flat key named `github.release`. | `lib/args.js:273-293` (`setNestedOption`) |
| Value passing | `--key=value`, `--key value`, and (for short flags) `-i=minor` all work. Quotes around the value are stripped. | `lib/args.js:163-177` |
| Boolean disabling | Prefix the **whole dotted path** with `no-`: `--no-npm.publish`, `--no-git.tag`, `--no-github.draft`. | `docs/configuration.md`; `lib/args.js:139-141,212-218` |
| Boolean enabling | Bare `--github.release` sets `true`. Value coercion also accepts `--github.release=true` / `=false` / `true` / `false` as a following positional. | `lib/args.js:149,251-257` |
| Priority | CLI wins over everything, including config files. | `docs/configuration.md` |
| Unknown options | **Rejected.** `--nope` ⇒ exit `1` with `ERROR Unknown option '--nope'.` | `lib/args.js:300-306`; empirical |
| Unknown *release-it* options | Rejected. But **hook names and external-plugin options are accepted dynamically**. | `docs/configuration.md`; `lib/args.js:179-210` |
| `hooks.*` / `plugins.*` | Bypass the static list via `discoverDynamicOptions`. | `lib/args.js:186` |
| Path safety | `__proto__`, `constructor`, `prototype` segments and empty segments are rejected (`Unsafe option path`, `Invalid option path`). | `lib/args.js:119,151-161` |
| Type conflict | Two paths that disagree (scalar vs object) throw `Conflicting option "--<path>".` | `lib/args.js:282-290` |

```bash
# nested key -> dotted flag, exact shapes that work
release-it minor --git.requireBranch=main --github.release
release-it --no-npm.publish
release-it --github.releaseName="Arcade Silver"
release-it --npm.otp=123456
release-it --git.commitMessage='chore: release v${version}'
```

**How a short alias is derived:** `-c`, `-d`, `-h`, `-i`, `-v`, `-V` only. In addition, after
parsing, each of `c d h i v` is *mirrored* onto the parsed options object when the long name exists
(`lib/args.js:328-330`), so `options.c === options.config`. `V` is deliberately excluded.

---

## 3. Exit codes

| Code | Meaning | Where | Source |
|------|---------|-------|--------|
| `0` | Success — release completed; or `--help`/`--version`/`--release-version` printed; or `--changelog` found a changelog. | `bin/release-it.js:15-18`; `lib/index.js:65-73,105-110` | `bin/release-it.js` |
| `1` | Any error. Specifically: (a) argument-parse failure — printed as `ERROR <message>`, bypassing the normal error path; (b) `--changelog` when **no** changelog was found (`log.warn('No changelog found')`); (c) any thrown error whose `.code` is not a number. | `bin/release-it.js:8-13,17`; `lib/index.js:69-72,145-154` | `bin/release-it.js` |
| `N` | A thrown error carrying a **numeric** `code` property exits with that code: `process.exit(Number.isInteger(code) ? code : 1)`. release-it itself throws no numeric codes; this exists for plugins/shell failures. | `bin/release-it.js:17` | `bin/release-it.js` |

`--release-version` exits `0` **even when no next version is available** — it prints nothing and
succeeds (`README.md`: "If no next version is available, it prints nothing and exits successfully").

```bash
# empirical
$ node bin/release-it.js --help           ; echo $?   # 0
$ node bin/release-it.js --version        ; echo $?   # 0  -> "v21.1.1"
$ node bin/release-it.js --nope           ; echo $?   # 1  -> "ERROR Unknown option '--nope'."
```

---

## 4. `--ci` mode

| Aspect | Normal (interactive) run | `--ci` run |
|--------|--------------------------|------------|
| Prompts | release-it asks to confirm each task before execution (version, then commit/tag/push/etc.) | Fully automated, no prompts |
| Activation | default | `--ci`, **or** automatically when a CI environment is detected |
| Auto-detection | — | `ci: isCI` is merged from the `ci-info` package (`lib/config.js:3,110`) |
| Also implies CI | — | `--release-version` and `--changelog` both count as CI (`isCI` ORs them in) |
| `--only-version` | — | Prompts for the version **only**, then calls `config.setCI(true)` for the rest of the flow |
| GitHub release | Opens the browser with a pre-populated GitHub release page when no token is set | Does **not** open a browser; prints the URL with pre-populated fields instead |

Sources: `lib/cli.js:16`; `lib/config.js:77-79`; `lib/index.js:115-117`; `docs/ci.md`;
`docs/github-releases.md`.

### `--ci` combined with `--dry-run`

The two are independent flags and **both take effect** — nothing in the code short-circuits one
because of the other.

| Combination | Behaviour |
|-------------|-----------|
| `--ci --dry-run` | No prompts *and* no writes. release-it prints the full command list; read-only commands (`$ git rev-parse …`) really run, mutating ones print as `! git commit …`. |
| `--dry-run` alone | Prompts normally (interactive preview), still writes nothing. |
| `--ci` alone | Writes for real, with no prompts. |

Because `isDryRun` is read independently everywhere (`lib/config.js:53-55`), `--ci` never overrides
`--dry-run`. Authentication checks short-circuit in dry runs (`GitHub.isAuthenticated()` returns
`true` when `config.isDryRun`), so `--ci --dry-run` does not fail on a missing `GITHUB_TOKEN`.

```bash
release-it minor --ci --dry-run         # safe rehearsal, fully non-interactive
release-it --only-version --dry-run     # prompt once for version, then preview only
```

---

## 5. Quick-reference: copy-paste examples

```bash
release-it                                  # interactive, patch
release-it minor                            # positional increment
release-it --increment=minor                # equivalent flag form
release-it 2.0.0                            # explicit version
release-it --preRelease=beta                # pre-release
release-it --ci                             # unattended
release-it --dry-run                        # show commands only
release-it -VV                              # extra verbose
release-it --release-version                # print next version
release-it --changelog                      # print changelog
release-it --config ./ci/release-it.json    # alternate config file
release-it --no-git --no-npm                # version bump only
release-it --github.release --gitlab.release
release-it --git.tagName='${npm.name}@${version}'
release-it --'hooks.before:init="npm test"'
```
