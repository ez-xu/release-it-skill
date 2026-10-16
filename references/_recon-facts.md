# `_recon-facts.md` — Evidence record for the release-it skill reference docs

Scope: this file records **how** the two reference documents were grounded, so any claim can be
re-checked or refuted. It is evidence, not documentation.

---

## 1. Version documented

| Fact | Value | How it was established |
|------|-------|------------------------|
| **Documented version** | **`release-it` 21.1.1** | `npm view release-it version` → `21.1.1` |
| npm `latest` dist-tag | `21.1.1` | `npm view release-it dist-tags --json` → `{"release-it-14":"14.14.3","next":"20.0.0-1","latest":"21.1.1"}` |
| Newest published versions | `… 21.0.2, 21.0.3, 21.1.0, 21.1.1` | `npm view release-it versions --json` |
| Upstream `main` matches | yes | Local sparse clone of `main`; its `package.json` reports `"version": "21.1.1"` |
| Node engine requirement | `^22.22.2 \|\| ^24.15.0 \|\| >=26.0.0` | `_probe/node_modules/release-it/package.json` |
| Fork status | **stock upstream** — `ez-xu/release-it` is a plain fork with `ahead_by=0` (established by the requester) | Documented as stock upstream release-it |

---

## 2. Local materials actually used

Two independent local copies were created and read (no reliance on a single fetch):

| Material | Path | Used for |
|----------|------|----------|
| Installed package, pinned to the documented version | `C:\Users\15854\.agents\skills\_sources\release-it-skill\_probe\node_modules\release-it\` (installed with `npm install release-it@21.1.1`) | `lib/args.js`, `lib/cli.js`, `lib/config.js`, `lib/index.js`, `bin/release-it.js`, `lib/plugin/factory.js`, `lib/plugin/github/GitHub.js`, `config/release-it.json`, `schema/*.json`, `types/*.d.ts`, `package.json`, `README.md` |
| Sparse clone of upstream `main` | `C:\Users\15854\.agents\skills\_sources\release-it-skill\_probe\rishallow\` (`git clone --depth 1 --filter=blob:none --sparse`, then `git sparse-checkout set docs config lib schema types`) | `docs/*.md` — used after repeated `raw.githubusercontent.com` failures |

> The parent agent later supplied an equivalent corpus at
> `C:\Users\15854\.agents\skills\_sources\release-it-skill\.build\upstream\`. Its stated ground truth
> (short aliases, single positional, `addNegativeOptions`, dynamic `hooks.*`/`plugins.*`, mixed-typed
> options, `--verbose` collapse, `github.release:false` / `gitlab.release:false` / `npm.publish:true`,
> token env vars) **matches this session's independent findings** — no contradictions were found.

---

## 3. Sources fetched, and what each established

### 3.1 Files read in full (exact paths)

| File | Established |
|------|-------------|
| `lib/args.js` (334 lines) | The **entire** flag surface: `aliases` (`c,d,h,i,v,V`), `booleanOptionNames`, `stringOptionNames`, `arrayOptionNames`, `mixedOptionNames`, `collapsibleArrayOptionNames`, `unsafePathSegments`. Short-flag syntax normalization, quote stripping, dynamic `hooks.*`/`plugins.*` discovery, `addNegativeOptions`, boolean value coercion, `normalizeVerbose`, `setNestedOption`, the single-positional rule, and the short→long mirroring. |
| `lib/cli.js` (42 lines) | The authoritative **help text** (all user-facing flag descriptions and the `[default: "patch"]` claim), and that `--version`/`--help` short-circuit before `runTasks`. |
| `bin/release-it.js` (18 lines) | **Exit codes**: `process.exit(0)` on success, `process.exit(Number.isInteger(code) ? code : 1)` on rejection, and `process.exit(1)` for parse errors. |
| `lib/config.js` (192 lines) | c12 load options (`name:'release-it'`, `configFile:'.release-it'`, `packageJson:true`, `rcFile:false`, `envName:false`), the 5-level `defu` precedence chain, array-replace `createDefu`, `expandPreReleaseShorthand` and its snapshot hard-coding, `resolveFile` (`--config=false` → no file), and every `is*` getter (`isDryRun`, `isIncrement`, `isCI`, `isPromptOnlyVersion`, `isReleaseVersion`, `isChangelog`, `isQuiet`). |
| `lib/index.js` (161 lines) | `--changelog` exit paths (0 with changelog, 1 with "No changelog found"), `--release-version` exit 0, `--only-version` → `config.setCI(true)`, and lifecycle hook ordering. |
| `config/release-it.json` | The **shipped defaults**, reproduced verbatim in `interfaces-config.md` §3. |
| `schema/release-it.json` | Top-level keys, `additionalProperties:false`, boolean-or-object forms for `git`/`npm`/`github`/`gitlab`, the hooks regex `^(before\|after):((version\|git\|npm\|github\|gitlab):)?(init\|bump\|release)$`, and the `quiet` description. |
| `schema/git.json`, `schema/npm.json`, `schema/github.json`, `schema/gitlab.json` | Per-key types and defaults, including keys **absent** from the defaults file (`github.makeLatest`, `gitlab.autoGenerate`, `gitlab.certificateAuthorityFileRef`, …). |
| `types/config.d.ts` (220 lines) | Typed key list with `@default` JSDoc for every `git`/`npm`/`github`/`gitlab` key; the `npm?: {...} \| false` union; `github.releaseNotes` union. |
| `types/hooks.d.ts` (47 lines) | The canonical hook namespace: `HookPrefix`, `InternalPlugin = 'version'\|'git'\|'npm'\|'github'\|'gitlab'`, `HookName = 'init'\|'bump'\|'release'`, and all 36 concrete hook keys. |
| `lib/plugin/factory.js` (89 lines) | Internal plugin order `['npm','git','github','gitlab','version']`, external-plugin loading and `[namespace, options]` tuple form, and `disablePlugin`. |
| `lib/plugin/github/GitHub.js` (head, 120 lines) | `skipChecks` / `tokenRef` / `web` / `update` / `assets` handling, web-fallback warning, `GITHUB_ACTIONS` + `GITHUB_ACTOR` auth bypass, and `isDryRun` short-circuiting auth checks. |
| `lib/plugin/GitRelease.js` (grepped) | `tokenRef` resolution: `return process.env[tokenRef] \|\| null;` (line 29). |
| `package.json` (shipped) | `bin.release-it = bin/release-it.js`, `"type": "module"`, engines, dependency list. |
| `README.md` (shipped copy) | Interactive-vs-CI mode, `--release-version`, `--changelog`, `--no-increment`, `--no-hooks` / `--no-hooks.before:init`, verbose levels (`-V` / `-VV` / `verbose: 2`), `NODE_DEBUG=release-it:*`, hook table, and the exposed template variables. |

### 3.2 Docs fetched (from the sparse clone of `main`)

| Doc | Established |
|-----|-------------|
| `docs/configuration.md` | The config **file name list** (`.release-it.json/.ts/.js/.cjs/.yaml/.yml/.toml` + `package.json` `release-it` key), `--config`, TS `satisfies Config` example, `extends` formats, and the CLI override examples (`--git.requireBranch=main`, `--no-npm.publish`, `--no-plugins.@release-it/keep-a-changelog.strictLatest`). |
| `docs/git.md` | Every `git.*` key, the 6-step default git sequence, `pushRepo` defaulting to `origin`, `tagName`/`tagMatch`/`tagExclude` semantics, `getLatestTagFromAllRefs` behaviour, `--follow-tags` replacement warning, `--no-git`, and `--no-git.requireUpstream` adding `--set-upstream`. |
| `docs/npm.md` | Every `npm.*` key, prerequisite checks, dist-tag derivation (`latest`/`next`, pre-release id), `publishPath`, Trusted Publishing needing `skipChecks: true`, staged publishing, and the `private: true` skip. |
| `docs/github-releases.md` | Every `github.*` key, automated vs manual (web) mode, `GITHUB_TOKEN`-absence fallback, release-notes string/function/object forms, two-step asset publishing, `update` recipe, `makeLatest`, discussions, and comments. |
| `docs/gitlab-releases.md` | Every `gitlab.*` key, token scopes (`api`, `self_rotate`), release-notes forms, milestones, assets, `useIdsForUrls` for GitLab ≥ 17.2, Generic Package Repository, `origin`, CA file, proxy, and the explicit statement that GitLab Releases **do not support pre-releases or drafts**. |
| `docs/ci.md` | CI guidance (SSH vs HTTPS remotes, GitHub Actions, npm `NPM_TOKEN`/`.npmrc`, Travis, Circle, GitLab CI, Alpine) and the "tag already exists" mitigation. |
| `docs/environment-variables.md` | `GITHUB_TOKEN`/`GITLAB_TOKEN` as env vars, dotenv-cli, and that `github.tokenRef="RELEASE_IT_GITHUB_TOKEN"` is only an **example of a custom `tokenRef` name**, not a built-in variable. |
| `docs/dry-runs.md` | Dry-run semantics: read-only commands really execute (`$`), mutating ones print as `!`; `--release-version` and `--changelog`. |
| `docs/plugins.md`, `docs/pre-releases.md`, `docs/changelog.md`, `docs/recipes/programmatic.md` | Plugin API/execution order, pre-release behaviour, changelog usage, programmatic API. |

### 3.3 Empirical verification (executed locally)

The real binary was run from
`C:\Users\15854\.agents\skills\_sources\release-it-skill\_probe\node_modules\release-it\bin\release-it.js`:

| Command | Observed | Confirms |
|---------|----------|----------|
| `--help` | exit `0`, full help text starting `Release It! v21.1.1` | Help text and version |
| `--version` | exit `0`, prints `v21.1.1` | Version short-circuit |
| `--nope` | exit `1`, `ERROR Unknown option '--nope'. To specify a positional argument starting with a '-', place it at the end of the command after '--', …` | Unknown options are **rejected**; parse errors exit `1` |
| `--no-npm` | reached the release flow (exit `1` with `ERROR fatal: your current branch 'master' does not have any commits yet`) | `--no-npm` **is accepted and does not throw a parser error** — negation of plugin names works |
| `--only-version --dry-run` | exit `1`, `ERROR Unknown option '--only-version --dry-run'. …` | Quoting artifact of the test harness (both flags were passed as one shell token), not a release-it limitation. Both flags exist independently in the shipped help text |

### 3.4 Things grepped to prove absence

| Grep target | Scope | Result |
|-------------|-------|--------|
| `metric\|telemetr\|analytics\|amplitude\|posthog` | all shipped `.js`/`.json`/`.ts`/`.md` in `release-it@21.1.1` | **0 matches** — no metrics feature, so no `--disable-metrics`/`--no-metrics` |
| `RELEASE_IT_` | all shipped `.js`/`.json`/`.ts`/`.md` in `release-it@21.1.1` | **0 matches** — no `RELEASE_IT_PLUGINS`, `RELEASE_IT_CONFIG`, etc. |
| `process\.env` | all shipped `.js`/`.ts` | Only: `GITHUB_ACTIONS`, `GITHUB_ACTOR`, `process.env[tokenRef]`, `process.env[certificateAuthorityFileRef]`, `NODE_DEBUG`, and `{ ...process.env }` passthrough in `lib/util.js` |

---

## 4. Explicitly unverified

Items marked `unverified` in the two reference docs, with the reason:

1. **`--disable-metrics` and `--no-metrics` / `--metrics`** — `unverified — does not exist in
   release-it 21.1.1`. No metrics/telemetry code is present (0 grep matches), and no such flag
   appears in `lib/args.js` or the help text. Documented in `interfaces-cli.md` §2.6 as
   non-existent rather than inventing semantics.
2. **`RELEASE_IT_PLUGINS`** — `unverified — not read by release-it 21.1.1`. Zero `RELEASE_IT_`
   occurrences in the entire shipped package; plugins are configured via the `plugins` config key
   and `--plugins.*` CLI flags only.
3. **`RELEASE_IT_CONFIG`** — `unverified — not read by release-it 21.1.1`. Zero occurrences, and
   c12 is explicitly invoked with `envName: false` (`lib/config.js:158`), the very option that would
   enable an `RELEASE_IT_*` config env var.
4. **`RELEASE_IT_GITHUB_TOKEN`** — `unverified — not a built-in variable`. It appears in
   `docs/environment-variables.md` only as a *worked example* of a custom `github.tokenRef` value.
   release-it reads whatever name `tokenRef` holds; there is no built-in `RELEASE_IT_GITHUB_TOKEN`.
5. **`--hooks.<name>` array accumulation across separate CLI invocations** — the parser marks a
   repeated dynamic option as `multiple: true` (`lib/args.js:204-208`), but the end-to-end effect of
   mixing a config-file array with repeated CLI occurrences was not executed. `unverified — parser
   behaviour confirmed by code reading, not by an end-to-end run`.
6. **Numeric exit code `N` from the `({ code }) => …` rejection path** — the code path is certain
   (`bin/release-it.js:17`), but no in-tree throw site was found producing a numeric `code`.
   `unverified — no first-party throw site; reserved for plugins/shell failures`.
7. **`github.makeLatest` effective runtime default** — `schema/github.json` and `types/config.d.ts`
   both say `true`, but the key is **absent** from `config/release-it.json`, so the value actually
   reaching the GitHub API when unset was not observed. `unverified — schema/type default only`.
8. **`gitlab.autoGenerate`, `gitlab.preRelease`, `gitlab.draft`** — present in `schema/gitlab.json`
   and in `lib/args.js`, but absent from `config/release-it.json` and contradicted by
   `docs/gitlab-releases.md` ("GitLab Releases do not support pre-releases or drafts").
   `unverified — schema/parser presence does not prove runtime support`.
9. **`verbose` key placement** — `README.md` says `verbose: 2` in a configuration file equals `-VV`,
   but `verbose` is not in `config/release-it.json`, `schema/release-it.json` (which sets
   `additionalProperties: false`), or `types/config.d.ts`. `unverified — documented in README only;
   a strict schema check could reject it`.
10. **c12's exact file-resolution precedence** between `.release-it.json` vs `.release-it.ts` vs
    `.release-it.yaml` when several exist simultaneously — `docs/configuration.md` lists the file
    names but does not state an order, and c12's own ordering was not inspected.
    `unverified — c12 internal ordering not examined`. The docs list is a list, not a precedence.
11. **`package.json` key aliases for c12** (`release-it` vs `releaseIt`) — only the literal
    `release-it` property is documented by release-it. `unverified — only the documented key was
    treated as supported`.
12. **Whether `--ci --dry-run` is a documented, supported combination** — both flags are independent
    in code and `isDryRun` is read separately everywhere, but no upstream document shows the pair
    combined. `unverified — behaviour inferred from code, no upstream example`.

---

## 5. Notes on tooling failures (not content gaps)

`web_fetch` against `raw.githubusercontent.com` failed repeatedly with
`Error: fs-quality-fetch: could not fetch … (direct: read ECONNRESET)` for `docs/ci.md`,
`docs/plugins.md`, `docs/github-releases.md`, `docs/git.md` and `docs/npm.md` on first attempts.
Workarounds that succeeded, in order:

1. `web_fetch` retry against `https://api.github.com/repos/release-it/release-it/contents/<path>?ref=main`
   returns base64 content (used to recover `docs/ci.md` and `docs/github-releases.md`).
2. **Direct `git clone --depth 1 --filter=blob:none --sparse`** of the upstream repo, then
   `git sparse-checkout set docs config lib schema types` — the most reliable method, and the one
   that supplied all remaining docs.

A later attempt to batch-download the same docs through the GitHub contents API returned HTTP 404
for every file; the clone was used instead. **No content was taken from an unverified source, and no
fact was inferred from a failed fetch.**
