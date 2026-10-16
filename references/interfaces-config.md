# release-it — Configuration Interface Reference

**Documented version: `release-it` 21.1.1** (npm `latest`). Stock upstream `release-it/release-it`.
See [`_recon-facts.md`](./_recon-facts.md) for provenance.

Primary sources:
- `config/release-it.json` — the **shipped defaults** (reproduced verbatim in §3)
- `lib/config.js` — config loading and merging
- `schema/*.json` — the shipped JSON Schemas (`release-it.json`, `git.json`, `npm.json`, `github.json`, `gitlab.json`)
- `types/config.d.ts` and `types/hooks.d.ts` — shipped TypeScript types
- `docs/*.md` — narrative docs

---

## 1. Config file locations and loading

### 1.1 How loading works

`lib/config.js:145-190` calls c12 with:

```js
loadC12({
  name: 'release-it',
  configFile: file,        // default '.release-it'
  packageJson: true,       // read the `release-it` key of package.json
  rcFile: false,           // .releaserc is NOT read
  envName: false,          // no RELEASE_IT_* env override
  cwd: dir,                // default process.cwd(), or --configDir
  extend,                  // undefined unless `extends` is set
  defaultConfig
})
```

`envName: false` is significant: **c12's environment-variable config override is switched off**, so
there is no `RELEASE_IT_*` config env var. See §6.

A failure to load the file is re-thrown as `Invalid configuration file at <file>` (`lib/config.js:162-164`).

### 1.2 Search order / precedence

Highest priority first (`lib/config.js:106-114`, `defu(...)`):

| Rank | Source | Notes |
|------|--------|-------|
| 1 | **CLI arguments** | `--git.tag=false`, `--no-npm.publish`, … Highest priority. |
| 2 | Constructor config | Used with the programmatic API (2nd arg to `release-it`). |
| 3 | `ci: isCI` | Auto-injected boolean from the `ci-info` package. |
| 4 | **Local config file** | The first file c12 resolves from §1.3. |
| 5 | Shipped `config/release-it.json` | Lowest priority — the defaults. |

**Arrays are replaced, not concatenated**: `createDefu` overrides `defu`'s array-merge so an array
in a higher-priority source **replaces** the lower one entirely (`lib/config.js:13-18`). This is why
setting `git.pushArgs` drops the default `["--follow-tags"]` unless you re-add it.

### 1.3 Supported file names and formats

At project root (cwd, or `--configDir`). Base name is `.release-it`; `-c/--config` overrides it.

| File | Format | How it is loaded | Source |
|------|--------|------------------|--------|
| `.release-it.json` | JSON | Parsed as JSON | `docs/configuration.md` |
| `.release-it.ts` | TypeScript | Loaded via c12's TS support; `satisfies Config` gives typing hints | `docs/configuration.md` |
| `.release-it.js` | ESM/CJS JS | Export an object: `module.exports = {}` | `docs/configuration.md` |
| `.release-it.cjs` | CommonJS | Same as `.js` | `docs/configuration.md` |
| `.release-it.mjs` | ESM | Export an object | `docs/configuration.md` |
| `.release-it.yaml` | YAML | Parsed as YAML | `docs/configuration.md` |
| `.release-it.yml` | YAML | Parsed as YAML | `docs/configuration.md` |
| `.release-it.toml` | TOML | Parsed as TOML | `docs/configuration.md` |
| `package.json` → `release-it` key | JSON | `packageJson: true` reads the `release-it` property | `docs/configuration.md` |

```jsonc
// .release-it.json
{
  "$schema": "https://unpkg.com/release-it@20/schema/release-it.json",
  "git": { "commitMessage": "chore: release v${version}" },
  "github": { "release": true }
}
```

```jsonc
// package.json
{
  "name": "my-package",
  "devDependencies": { "release-it": "*" },
  "release-it": { "github": { "release": true } }
}
```

```ts
// .release-it.ts
import type { Config } from 'release-it';
export default {
  git: { commit: true, tag: true, push: true },
  github: { release: true },
  npm: { publish: true }
} satisfies Config;
```

```toml
# .release-it.toml
[hooks]
"before:init" = "npm test"
```

`--config=false` disables config-file loading entirely (`lib/config.js:170`).

> **Not read:** `.releaserc`, `.releaserc.json`, `.release-it.rc`, and any rc-style file — `rcFile: false`.
> This is a common source of confusion with cosmiconfig-based tools.

### 1.4 `extends` — remote configuration

| Value | Meaning |
|-------|---------|
| `github:owner/repo` | Config from the repo's default branch (`main`) |
| `github:owner/repo#tag` | Config from the specified tag |
| `github:owner/repo:subdir#tag` | Config from the subdirectory at the specified tag |
| `gitlab:` / `bitbucket:` / `https:` | Other supported schemas |

Implemented by c12 (`lib/config.js:181-189`); `extends: false` disables it.

```json
{ "extends": "github:release-it/release-it-configuration" }
```

---

## 2. Top-level and nested key reference

Legend: **Type** / **Default**. Defaults are from the shipped `config/release-it.json` unless noted.
`mixed` means boolean-or-string.

### 2.1 Top level

| Key | Type | Default | Meaning | Source |
|-----|------|---------|---------|--------|
| `$schema` | string | — | Schema URL for editor validation; ignored at runtime | `schema/release-it.json` |
| `extends` | string | — | Remote config to extend (§1.4) | `schema/release-it.json` |
| `hooks` | object | `{}` | Shell commands run at lifecycle points (§2.7) | `config/release-it.json` |
| `plugins` | object | — | External plugin registry, keyed by module name (§2.8) | `schema/release-it.json` |
| `git` | object \| `false` | object (§2.2) | Git plugin. `false` disables it | `schema/release-it.json` |
| `npm` | object \| `false` | object (§2.3) | npm plugin. `false` disables it | `schema/release-it.json` |
| `github` | object \| `false` | object (§2.4) | GitHub Releases | `schema/release-it.json` |
| `gitlab` | object \| `false` | object (§2.5) | GitLab Releases | `schema/release-it.json` |
| `quiet` | boolean | `false` | Suppress preview output (changelog/changeset/release notes) during the release flow. Does **not** affect `--changelog` mode | `schema/release-it.json` |
| `verbose` | number \| boolean | — | `2` is the config equivalent of `-VV`. Not in the shipped defaults; set only via config/CLI | `README.md` |
| `ci` | boolean | auto | Injected from `ci-info`; normally not set by hand | `lib/config.js:110` |
| `increment` | string | (help says `"patch"`) | Increment or explicit version | `lib/cli.js:15` |

The shipped schema sets `additionalProperties: false` at the top level — unknown **top-level** keys
are invalid, though the CLI parser is what actually rejects unknown flags at runtime.

### 2.2 `git.*`

| Key | Type | Default | Meaning |
|-----|------|---------|---------|
| `git.changelog` | string | `git log --pretty=format:"* %s (%h)" ${from}...${to}` | Changelog command (stdout is captured) |
| `git.requireCleanWorkingDir` | boolean | `true` | Require a clean working tree (`git status`) |
| `git.requireBranch` | `false` \| string \| string[] | `false` | Require the release to run on this branch name. Wildcards allowed (`release/*`); array = allowlist. CLI: **array-typed**, collapses a single value |
| `git.requireUpstream` | boolean | `true` | Require a tracking upstream; `false` adds `--set-upstream <remote> <branch>` to push |
| `git.requireCommits` | boolean | `false` | Exit if there are no commits since the previous release |
| `git.requireCommitsFail` | boolean | `true` | With no commits, continue but use exit code `0` |
| `git.commitsPath` | string | `""` | Path to the directory included in the release changes |
| `git.addUntrackedFiles` | boolean | `false` | Include untracked files in the release commit |
| `git.commit` | boolean | `true` | If `false`, skip the commit step |
| `git.commitMessage` | string | `Release ${version}` | Commit message (templated) |
| `git.commitArgs` | string[] | `[]` | Extra args to `git commit` (e.g. `["-S"]`) |
| `git.tag` | boolean | `true` | If `false`, skip the tag step |
| `git.tagExclude` | string \| null | `null` | Glob to exclude tags from latest-tag detection (e.g. `*[-]*`). No effect when `getLatestTagFromAllRefs: true` |
| `git.tagName` | string \| null | `null` | Custom tag name. `v` prefix is reused automatically when the latest tag had one |
| `git.tagMatch` | string \| null | `null` | Glob (not regex) overriding latest-tag matching, e.g. `[0-9]*.[0-9]*.[0-9]*` |
| `git.getLatestTagFromAllRefs` | boolean | `false` | Consider all tags (reachable or not), sorted by version, instead of `git describe` |
| `git.tagAnnotation` | string | `Release ${version}` | Annotation message for the tag |
| `git.tagArgs` | string[] | `[]` | Extra args to `git tag` |
| `git.push` | boolean | `true` | If `false`, skip the push step |
| `git.pushArgs` | string[] | `["--follow-tags"]` | Extra args to `git push`. Supplying this **replaces** the default |
| `git.pushRepo` | string | `""` | Remote name or Git URL to push to (defaults to `origin`) |

Sources: `config/release-it.json`, `schema/git.json`, `types/config.d.ts`, `docs/git.md`.

```json
{
  "git": {
    "requireCleanWorkingDir": false,
    "requireBranch": "main",
    "commitMessage": "chore(release): cut v${version}",
    "tagName": "${npm.name}@${version}",
    "tagAnnotation": "Release ${version}",
    "getLatestTagFromAllRefs": true,
    "pushArgs": ["--follow-tags", "--force"],
    "commitArgs": ["-S"]
  }
}
```

### 2.3 `npm.*`

| Key | Type | Default | Meaning |
|-----|------|---------|---------|
| `npm.publish` | boolean | `true` | Set `false` to bump the version but skip `npm publish` |
| `npm.publishPath` | string | `"."` | Publish only this folder (e.g. `dist`) |
| `npm.publishArgs` | string[] | `[]` | Extra args to `npm publish` |
| `npm.publishPackageManager` | `'npm'`\|`'pnpm'`\|`'bun'` | `"npm"` | Package manager used to publish |
| `npm.tag` | string \| null | `null` | dist-tag (e.g. `beta`). Derived from the pre-release id, else `latest`/`next` |
| `npm.stage` | boolean | `false` | Use `npm stage publish` (or `pnpm`) instead of a direct publish |
| `npm.otp` | string \| null | `null` | One-time password |
| `npm.ignoreVersion` | boolean | `false` | Ignore `version` in `package.json`; use the latest Git tag |
| `npm.allowSameVersion` | boolean | `false` | Allow the new version to equal the current one |
| `npm.versionArgs` | string[] | `[]` | Extra args to `npm version` |
| `npm.skipChecks` | boolean | `false` | Skip registry-up/permission checks. **Required** for Trusted Publishing (OIDC) |
| `npm.timeout` | integer | `10` | Seconds to wait for an npm registry response |

Sources: `config/release-it.json`, `schema/npm.json`, `docs/npm.md`.

```json
{
  "npm": {
    "publish": true,
    "publishPath": "dist",
    "tag": "beta",
    "versionArgs": ["--allow-same-version"],
    "publishArgs": ["--include-workspace-root"],
    "skipChecks": true
  }
}
```

### 2.4 `github.*`

| Key | Type | Default | Meaning |
|-----|------|---------|---------|
| `github.release` | boolean | **`false`** | Create a GitHub Release. **Must be enabled explicitly** |
| `github.releaseName` | string | `Release ${version}` | Release title |
| `github.releaseNotes` | string \| null \| function \| object | `null` | Custom notes. String = shell command on stdout; function = `(context) => string` (JS/TS config only); object = `{ commit, excludeMatches }` |
| `github.releaseNotes.commit` | string | — | Template rendered against Octokit commit objects (`${commit.subject}`, `${sha}`, `${author.login}`) |
| `github.releaseNotes.excludeMatches` | string[] | `[]` | Values that suppress the placeholder block they appear in |
| `github.autoGenerate` | boolean | `false` | Let GitHub generate release notes (**overrides** other notes; incompatible with `web: true`) |
| `github.makeLatest` | `true`\|`false`\|`'legacy'` | `true` (schema/types) | Whether this becomes the "latest" release. `false` for support releases. **Mixed** type on CLI |
| `github.discussionCategoryName` | string \| boolean | `false` | Create a Discussion in this category and link it to the release. **Mixed** type |
| `github.preRelease` | boolean | `false` | Mark as pre-release. Set automatically `true` for semver pre-releases |
| `github.draft` | boolean | `false` | Create as a draft |
| `github.tokenRef` | string | `"GITHUB_TOKEN"` | Name of the env var holding the token |
| `github.assets` | string[] \| null | `null` | Glob patterns of assets to upload |
| `github.host` | string \| null | `null` | Alternate API host (GitHub Enterprise). `"private.example.org"` ⇒ `https://private.example.org/api/v3` |
| `github.timeout` | integer | `0` | API response timeout (seconds) |
| `github.proxy` | string \| null | `null` | Proxy URL, e.g. `"http://proxy:8080"` |
| `github.skipChecks` | boolean | `false` | Skip `GITHUB_TOKEN` and collaborator checks |
| `github.web` | boolean | `false` | Force web-based (manual) release instead of the API |
| `github.update` | boolean | — (**not in shipped defaults**) | Update an existing release instead of creating one. Accepted by the CLI parser |
| `github.comments.submit` | boolean | `false` | Comment on every merged PR and closed issue in the release |
| `github.comments.issue` | string | `:rocket: _This issue has been resolved in v${version}. See [${releaseName}](${releaseUrl}) for release notes._` | Issue comment text |
| `github.comments.pr` | string | `:rocket: _This pull request is included in v${version}. See [${releaseName}](${releaseUrl}) for release notes._` | PR comment text |

Sources: `config/release-it.json`, `schema/github.json`, `types/config.d.ts`, `docs/github-releases.md`,
`lib/plugin/github/GitHub.js:52`.

Behavioral notes (`docs/github-releases.md`):
- If no token and not `web`, release-it warns and **falls back to the web-based release**, skipping auth checks.
- Releases **with** assets publish in two steps (create draft → upload assets → publish) because of immutable releases.
- `--github.update` requires `--no-increment --no-git`; the tag must already exist.

```json
{
  "github": {
    "release": true,
    "releaseName": "Release ${version}",
    "releaseNotes": "generate-release-notes.sh ${latestTag} ${tagName}",
    "draft": false,
    "preRelease": false,
    "makeLatest": true,
    "assets": ["dist/*.zip"],
    "comments": { "submit": true }
  }
}
```

### 2.5 `gitlab.*`

| Key | Type | Default | Meaning |
|-----|------|---------|---------|
| `gitlab.release` | boolean | **`false`** | Create a GitLab Release. **Must be enabled explicitly** |
| `gitlab.releaseName` | string | `Release ${version}` | Release title |
| `gitlab.releaseNotes` | any \| null | `null` | Custom notes: string = shell command; function = `(context) => string` (JS/TS config only) |
| `gitlab.milestones` | string[] | `[]` | Milestone titles to associate. A missing milestone **fails** the release unless `skipChecks` |
| `gitlab.tokenRef` | string | `"GITLAB_TOKEN"` | Env var holding the token |
| `gitlab.tokenHeader` | string | `"Private-Token"` | HTTP header carrying the token |
| `gitlab.certificateAuthorityFile` | any \| null | `null` | Path to a private CA cert |
| `gitlab.certificateAuthorityFileRef` | string | `"CI_SERVER_TLS_CA_FILE"` | Env var used when the path is not set explicitly |
| `gitlab.secure` | boolean | `true` | Verify server certificates (`connect.rejectUnauthorized`) |
| `gitlab.proxy` | boolean | `false` | Route API requests through standard `http_proxy`/`https_proxy`/`no_proxy` env vars |
| `gitlab.assets` | any \| null | `null` | Glob patterns of assets to attach |
| `gitlab.useIdsForUrls` | boolean | `false` | Use numeric IDs in asset URLs. **Required for GitLab ≥ 17.2** |
| `gitlab.useGenericPackageRepositoryForAssets` | boolean | `false` | Upload assets to the Generic Package Registry instead of Markdown uploads |
| `gitlab.genericPackageRepositoryName` | string | `"release-it"` | Package name for the Generic Package Registry |
| `gitlab.origin` | string \| null | `null` | Base URL for the API (default `https://${repo.host}`) |
| `gitlab.skipChecks` | boolean | `false` | Skip token and milestone checks |
| `gitlab.repoId` | string \| number \| null | `null` | Numeric project ID instead of the URL-encoded path |
| `gitlab.autoGenerate` | boolean | `false` | Present in `schema/gitlab.json` and CLI parser |
| `gitlab.preRelease` | boolean | `false` | Present in `schema/gitlab.json` and CLI parser. **`docs/gitlab-releases.md` states GitLab Releases do not support pre-releases or drafts** |
| `gitlab.draft` | boolean | `false` | Present in `schema/gitlab.json` and CLI parser. Same caveat as `preRelease` |

Sources: `config/release-it.json`, `schema/gitlab.json`, `docs/gitlab-releases.md`.

```json
{
  "gitlab": {
    "release": true,
    "milestones": ["${version}"],
    "assets": ["dist/*.dmg"],
    "useIdsForUrls": true,
    "tokenHeader": "PRIVATE-TOKEN"
  }
}
```

### 2.6 Increment / pre-release keys

| Key | Type | Default | Meaning | Source |
|-----|------|---------|---------|--------|
| `increment` | string | `"patch"` (help) | `major`/`minor`/`patch`/`pre*` or explicit version | `lib/cli.js:15` |
| `preRelease` | boolean \| string | — | `true` starts a pre-release; a string sets the id | `lib/args.js:116` |
| `preReleaseId` | string | — | Pre-release id when `preRelease` is boolean | `lib/args.js:68` |
| `preReleaseBase` | string | — | Base number for the pre-release counter | `lib/args.js:67` |
| `snapshot` | boolean \| string | — | Snapshot mode; a string hard-codes several git/npm options | `lib/config.js:134-141` |

At runtime these are collapsed into an internal `version` object by `expandPreReleaseShorthand`
(`lib/config.js:123-143`):
`{ increment, isPreRelease, preReleaseId, preReleaseBase }`.

> `version` is **not** a user-facing config key. It is reserved: the CLI `--version` flag and this
> internal object share the name.

### 2.7 `hooks.*`

Format: `[prefix]:[hook]` or `[prefix]:[plugin]:[hook]`.

| Part | Values | Source |
|------|--------|--------|
| prefix | `before`, `after` | `types/hooks.d.ts` |
| plugin | `version`, `git`, `npm`, `github`, `gitlab` (any plugin namespace, including external) | `types/hooks.d.ts` |
| hook | `init`, `bump`, `release` | `types/hooks.d.ts` |

Each value is a `string` or `string[]` (run in order). The shipped schema's regex is
`^(before|after):((version|git|npm|github|gitlab):)?(init|bump|release)$`.

| Key | Notes |
|-----|-------|
| `before:init`, `after:init` | Around plugin init |
| `before:bump`, `after:bump` | Around the version bump (`after:bump` is the usual build hook) |
| `before:release`, `after:release` | Around the release step |
| `before:<plugin>:<hook>`, `after:<plugin>:<hook>` | Per-plugin lifecycle, e.g. `after:git:release` |

`README.md` also documents the internal aliases `init`, `beforeBump`, `bump`, `beforeRelease`,
`release`/`afterRelease`, noting that hooks such as `before:beforeRelease` "look weird and are usually
not useful in practice".

Available template variables in hooks: `version`, `latestVersion`, `changelog`, `name`,
`repo.remote`, `repo.protocol`, `repo.host`, `repo.owner`, `repo.repository`, `repo.project`,
`branchName`, `releaseUrl`. All are available in every hook **except** that the additional variables
are not available in the `init` hook. Use `--verbose` to log hook output.

```json
{
  "hooks": {
    "before:init": ["npm run lint", "npm test"],
    "after:bump": "npm run build",
    "after:git:release": "echo After git push, before github release",
    "after:release": "echo Successfully released ${name} v${version} to ${repo.repository}."
  }
}
```

### 2.8 `plugins.*`

An object keyed by plugin module name. The value is the plugin's config object — or a 2-tuple
`[namespace, options]` to give the plugin a custom namespace (`lib/plugin/factory.js:58-72`).

```json
{
  "plugins": {
    "@release-it/conventional-changelog": {
      "preset": "angular",
      "infile": "CHANGELOG.md"
    }
  }
}
```

Plugin config keys can also be set on the CLI: `--plugins.<name>.<key>=<value>` (§ CLI reference).

---

## 3. Shipped defaults file — `config/release-it.json` (verbatim)

Reproduced exactly as shipped in release-it 21.1.1. Anything you do not override stays at these values.

```json
{
  "quiet": false,
  "hooks": {},
  "git": {
    "changelog": "git log --pretty=format:\"* %s (%h)\" ${from}...${to}",
    "requireCleanWorkingDir": true,
    "requireBranch": false,
    "requireUpstream": true,
    "requireCommits": false,
    "requireCommitsFail": true,
    "commitsPath": "",
    "addUntrackedFiles": false,
    "commit": true,
    "commitMessage": "Release ${version}",
    "commitArgs": [],
    "tag": true,
    "tagExclude": null,
    "tagName": null,
    "tagMatch": null,
    "getLatestTagFromAllRefs": false,
    "tagAnnotation": "Release ${version}",
    "tagArgs": [],
    "push": true,
    "pushArgs": ["--follow-tags"],
    "pushRepo": ""
  },
  "npm": {
    "publish": true,
    "publishPath": ".",
    "publishArgs": [],
    "publishPackageManager": "npm",
    "tag": null,
    "stage": false,
    "otp": null,
    "ignoreVersion": false,
    "allowSameVersion": false,
    "versionArgs": [],
    "skipChecks": false,
    "timeout": 10
  },
  "github": {
    "release": false,
    "releaseName": "Release ${version}",
    "releaseNotes": null,
    "autoGenerate": false,
    "preRelease": false,
    "draft": false,
    "tokenRef": "GITHUB_TOKEN",
    "assets": null,
    "host": null,
    "timeout": 0,
    "proxy": null,
    "skipChecks": false,
    "web": false,
    "comments": {
      "submit": false,
      "issue": ":rocket: _This issue has been resolved in v${version}. See [${releaseName}](${releaseUrl}) for release notes._",
      "pr": ":rocket: _This pull request is included in v${version}. See [${releaseName}](${releaseUrl}) for release notes._"
    }
  },
  "gitlab": {
    "release": false,
    "releaseName": "Release ${version}",
    "releaseNotes": null,
    "milestones": [],
    "tokenRef": "GITLAB_TOKEN",
    "tokenHeader": "Private-Token",
    "certificateAuthorityFile": null,
    "secure": true,
    "proxy": false,
    "assets": null,
    "useIdsForUrls": false,
    "useGenericPackageRepositoryForAssets": false,
    "genericPackageRepositoryName": "release-it",
    "origin": null,
    "skipChecks": false,
    "repoId": null
  }
}
```

### Keys present in the schemas/types but NOT in the defaults file

| Key | Default per schema/types | Note |
|-----|--------------------------|------|
| `github.makeLatest` | `true` | Absent from `config/release-it.json`, so the effective runtime default comes from the API/schema |
| `github.discussionCategoryName` | `false` | Schema types it as string; types/CLI treat it as mixed |
| `github.update` | — | CLI-only flag; not in `config/release-it.json` |
| `gitlab.autoGenerate` | `false` | In `schema/gitlab.json` only |
| `gitlab.preRelease`, `gitlab.draft` | `false` | In `schema/gitlab.json` only; docs say GitLab has no pre-release/draft support |
| `gitlab.certificateAuthorityFileRef` | `"CI_SERVER_TLS_CA_FILE"` | In `schema/gitlab.json` only |
| `verbose` | — | Documented in `README.md` (`verbose: 2` ≡ `-VV`) but not in the defaults |

---

## 4. Environment variables

### 4.1 Variables release-it reads

| Variable | Maps to config key | Default | Source |
|----------|--------------------|---------|--------|
| `GITHUB_TOKEN` | `github.tokenRef` | `"GITHUB_TOKEN"` | `config/release-it.json`; `lib/plugin/GitRelease.js:28-29` |
| `GITLAB_TOKEN` | `gitlab.tokenRef` | `"GITLAB_TOKEN"` | `config/release-it.json`; `lib/plugin/GitRelease.js:28-29` |
| *(any name)* | `github.tokenRef` / `gitlab.tokenRef` | — | Set `tokenRef` to read a differently named var, e.g. `github.tokenRef="RELEASE_IT_GITHUB_TOKEN"` |
| `CI_SERVER_TLS_CA_FILE` | `gitlab.certificateAuthorityFileRef` | `"CI_SERVER_TLS_CA_FILE"` | `schema/gitlab.json`; `lib/plugin/gitlab/GitLab.js:22` |
| `GITHUB_ACTIONS` | — (behaviour) | — | When set, GitHub auth/collaborator checks are skipped | `lib/plugin/github/GitHub.js:70-71` |
| `GITHUB_ACTOR` | — (behaviour) | — | Used as the `username` context under GitHub Actions | `lib/plugin/github/GitHub.js:71` |
| `NODE_DEBUG` | — (behaviour) | — | `NODE_DEBUG=release-it:*` prints configuration and error details | `README.md`; `lib/util.js:50` |
| `http_proxy` / `https_proxy` / `no_proxy` (either case) | `gitlab.proxy` | `false` (opt-in) | Only read when `gitlab.proxy: true` | `docs/gitlab-releases.md` |

Token resolution is literal: `return process.env[tokenRef] || null;`
(`lib/plugin/GitRelease.js:28-29`).

```bash
export GITHUB_TOKEN="<your-token>"          # read via github.tokenRef (default "GITHUB_TOKEN")
export GITLAB_TOKEN="<your-token>"          # read via gitlab.tokenRef (default "GITLAB_TOKEN")
NODE_DEBUG=release-it:* release-it --dry-run
```

The two variables are read by name only — `github.tokenRef` and `gitlab.tokenRef`
rename the variable that is read, so the value can be any opaque string. A classic
GitHub personal access token carries the prefix `ghp` followed by `_`, a GitLab
token the prefix `glpat` followed by `-`; the pipeline's redactor removes both
shapes from every message it prints.

### 4.2 Variables that do NOT exist

| Claimed variable | Finding |
|------------------|---------|
| `RELEASE_IT_PLUGINS` | **Not read by release-it.** A recursive grep for `RELEASE_IT_` across every shipped `.js`/`.json`/`.ts`/`.md` file in `release-it@21.1.1` returns **zero matches**. |
| `RELEASE_IT_CONFIG` | **Not read by release-it.** Additionally disabled at the c12 layer by `envName: false` (`lib/config.js:158`), which is exactly the option that would enable an `RELEASE_IT_*` config env var. |
| any other `RELEASE_IT_*` | Not read. |

Plugins are enabled through the `plugins` config key (§2.8) or the CLI (`--plugins.<name>.<key>`),
never through an environment variable.

---

## 5. Config surface summary

| Category | Where configured |
|----------|------------------|
| Version increment | positional / `--increment` / `--preRelease*` / `increment` |
| Git | `git.*` (22 keys) |
| npm | `npm.*` (13 keys) |
| GitHub Releases | `github.*` (18 keys incl. `comments.*`) |
| GitLab Releases | `gitlab.*` (21 keys) |
| Hooks | `hooks.<prefix>:<plugin?>:<hook>` |
| External plugins | `plugins.<module>` and `--plugins.*` |
| Output | `quiet`, `verbose` |
| Remote inheritance | `extends` |
| Credentials | env vars named by `tokenRef` |
