# release-it — Programmatic Node API Reference

**Version documented: release-it 21.1.1** (upstream `release-it/release-it` `main`).
Stock upstream — the `ez-xu/release-it` fork has zero custom commits (`ahead_by=0`).

Grounding sources: `lib/index.js`, `lib/config.js`, `lib/plugin/Plugin.js`, `lib/plugin/version/Version.js`,
`lib/shell.js`, `lib/spinner.js`, `lib/log.js`, `package.json`, `types/index.d.ts`, `types/config.d.ts`,
`bin/release-it.js`, `docs/recipes/programmatic.md`, `docs/dry-runs.md`, `README.md`.

---

## 1. Package shape

`package.json` (`release-it@21.1.1`):

```json
{
  "type": "module",
  "bin": { "release-it": "bin/release-it.js" },
  "exports": {
    ".": { "types": "./types/index.d.ts", "import": "./lib/index.js", "require": "./lib/index.js" },
    "./package.json": "./package.json",
    "./test/util/index.js": "./test/util/index.js"
  },
  "types": "./types/index.d.ts",
  "engines": { "node": "^22.22.2 || ^24.15.0 || >=26.0.0" }
}
```

**ESM only** (`"type": "module"`). The `require` condition points at the same ESM file, so
`require('release-it')` only works on a Node that can `require(esm)` (Node ≥ 22.12 / ≥ 23), and only
for the synchronous parts. Prefer `import`.

### 1.1 Exact exports (`lib/index.js`, lines 157–161)

```js
export default runTasks;

export { default as Config } from './config.js';

export { default as Plugin } from './plugin/Plugin.js';
```

| Export | Kind | What it is |
|---|---|---|
| `default` | `async function runTasks(opts, di)` | The whole release process. This is what `docs/recipes/programmatic.md` imports as `release`. |
| `Config` | class | Configuration resolver (option merging, context, flags). |
| `Plugin` | class | Base class for plugins. Subclass it: `import { Plugin } from 'release-it'`. |

`types/index.d.ts` is effectively a stub:

```ts
declare module 'release-it';

export type { Config } from './config.d';
```

It declares the module and re-exports the `Config` *interface* from `types/config.d.ts`. There are no
declarations for `runTasks` or `Plugin` — the API is untyped in 21.1.1.

### 1.2 Documented import form

```js
import release from 'release-it';

release(options).then(output => {
  console.log(output);
  // { version, latestVersion, name, changelog }
});
```

Named imports work the same way:

```js
import release, { Config, Plugin } from 'release-it';
import { Config, Plugin } from 'release-it';
```

---

## 2. `runTasks(opts, di)` — the entry point

```js
const runTasks = async (opts, di) => { ... }
```

### 2.1 Parameters

| Param | Type | Required | Notes |
|---|---|---|---|
| `opts` | `object` | yes | Configuration overrides, same shape as the config file. Passed straight into `new Config(opts)`. |
| `di` | `object` | no | Dependency-injection overrides. `Object.assign(container, di)` runs first, then each member is lazily defaulted. |

`opts` is **the config document**, not a subset. Every key documented in
`interfaces-config.md` and every plugin section (`git`, `npm`, `github`, `gitlab`, `hooks`, `plugins`)
is valid here, and takes **higher precedence** than the config file
(`defu({}, constructorConfig, { ci: isCI }, localConfig, defaultConfig)`).

Three `opts` keys have constructor-level meaning because `Config` reads them directly:

| Key | Effect (`lib/config.js`) |
|---|---|
| `config` | `false` → skip loading a config file entirely (`resolveFile()` returns `false`). `true` → use `'.release-it'`. String → that path. Default `'.release-it'`. |
| `configDir` | Working directory for config resolution. Default `process.cwd()`. |
| `extends` | `false` → do not resolve `extends`. Otherwise handed to [c12]. |

### 2.2 Dependency-injection container (`di`)

| Key | Class | Default when absent |
|---|---|---|
| `config` | `Config` | `new Config(opts)` then `await config.init()` |
| `log` | `Logger` | `new Logger({ isCI, isVerbose, verbosityLevel, isDryRun, isQuiet })` |
| `spinner` | `Spinner` | `new Spinner({ container, config })` |
| `prompt` | `Prompt` | `new Prompt({ container: { config } })` |
| `shell` | `Shell` | `new Shell({ container })` |

`config` is always `init()`-ed by `runTasks`, even when injected. This container is the supported seam
for tests (release-it's own tests stub `shell`/`prompt`/`spinner` here).

### 2.3 Return value

Resolves to exactly four fields:

```js
return { name, changelog, latestVersion, version };
```

| Field | Type | When empty |
|---|---|---|
| `name` | `string \| undefined` | no plugin implemented `getName()` |
| `changelog` | `string \| undefined` | no plugin returned a changelog |
| `latestVersion` | `string` | falls back to `'0.0.0'` |
| `version` | `string \| undefined` | **`undefined` when there is nothing to release** — the "No new version to release" path |

The docs' comment (`docs/recipes/programmatic.md`) lists the same four keys:
`// { version, latestVersion, name, changelog }`.

### 2.4 Errors

`runTasks` has a single `try/catch`:

```js
} catch (err) {
  const { log } = container;
  const errorMessage = err.message || err;
  const logger = log || console;
  err.cause === 'INFO' ? logger.info(errorMessage) : logger.error(errorMessage);
  throw err;
}
```

It **logs and re-throws** — the returned promise always rejects on failure. `err.cause === 'INFO'`
(produced by `e(message, docs, fail = false)` in `lib/util.js`) downgrades the log level but still
rejects. Callers must `try/catch`.

### 2.5 Process-exit side effects — important when embedding

`runTasks` calls `process.exit(0)` / `process.exit(1)` directly in three places. If you embed
release-it, these terminate **your** process:

| Condition | Behaviour |
|---|---|
| `opts.changelog` truthy | If a changelog was produced: `console.log(changelog); process.exit(0);` else `log.warn('No changelog found'); process.exit(1);` |
| `opts['release-version']` truthy | If a version resolved: `console.log(version); process.exit(0);` |
| `--only-version` (`config.isPromptOnlyVersion`) | sets `config.setCI(true)` mid-run after the version is known |

`opts.changelog` / `opts['release-version']` are therefore **not** usable as library calls — they are
one-shot CLI printers. For the same information in-process, read the resolved `version` /
`changelog` from the returned object instead.

---

## 3. Public methods — what actually exists

There is **no class-based API** in 21.1.1. `runTasks` is a module-level async function, not a
constructor, and per-run state lives on the injected `Config` instance.

| Documented-surface candidate | Status |
|---|---|
| `releaseIt` | Does not exist — the docs alias `runTasks` as the default import named `release`. |
| `ReleaseIt` (class) | **`unverified` / does not exist.** `lib/index.js` exports no such class; only `Config` and `Plugin` are exported. |
| `init()`, `bump()`, `release()`, `run()`, `runTasks()`, `getLatestVersion()`, `getChangelog()`, `getIncrementedVersion()`, `checkGitStatus()`, `dryRun()` as top-level API | **`unverified` / do not exist as public API.** Each corresponds to a *plugin method* (see `interfaces-plugins.md` §3) or to an internal `Config`/`Release` step, not to an exported function. Use them through a plugin. |
| `runTasks(opts, di)` | **Real.** Default export. |

### 3.1 `Config` — the real, usable class

```js
import { Config } from 'release-it';

const config = new Config(options);   // constructor(config = {})
await config.init();                  // resolves and merges options — REQUIRED before use
```

| Member | Signature | Behaviour |
|---|---|---|
| `constructor` | `(config = {}) → Config` | Stores `config` as `constructorConfig`; `contextOptions = {}`. Does **not** touch the filesystem. |
| `init` | `async () → void` | Loads local config via c12, then `defu({}, constructorConfig, { ci: isCI }, localConfig, defaultConfig)`; expands the pre-release shorthand into `options.version`. |
| `getContext` | `(path?) → Object` | `merge({}, this.options, this.contextOptions)`, optionally `get(path)`. Throws from the `options` getter (`assert(this._options, 'The "options" not resolve yet')`) if `init()` was not awaited. |
| `setContext` | `(options) → void` | `merge(this.contextOptions, options)` — how plugins publish `version`, `repo`, `tagName`, … |
| `setCI` | `(value = true) → void` | Sets `this.options.ci`. |
| `defaultConfig` | getter → object | The built-in `config/release-it.json`. |
| `options` | getter → object | Fully merged options. Asserts `init()` ran. |
| `localConfig` | getter → object | The user's config file only. Asserts `init()` ran. |
| `isDryRun` | getter → boolean | `Boolean(this.options['dry-run'])` |
| `isIncrement` | getter → boolean | `this.options.increment !== false` |
| `isVerbose` | getter → boolean | `Boolean(this.options.verbose)` |
| `verbosityLevel` | getter → number | `this.options.verbose` |
| `isDebug` | getter → boolean | whether `release-it:config` debug is enabled |
| `isQuiet` | getter → boolean | `Boolean(this.options.quiet)` |
| `isCI` | getter → boolean | `Boolean(this.options.ci) \|\| this.isReleaseVersion \|\| this.isChangelog` |
| `isPromptOnlyVersion` | getter → boolean | `this.options['only-version']` |
| `isReleaseVersion` | getter → boolean | `Boolean(this.options['release-version'])` |
| `isChangelog` | getter → boolean | `Boolean(this.options['changelog'])` |

Note `isCI` **also becomes true** whenever `release-version` or `changelog` is set, so those two
one-shot modes never prompt.

### 3.2 `Plugin` — the other real export

Full method inventory is in `interfaces-plugins.md` §3. Programmatic use is simply:

```js
import { Plugin } from 'release-it';

export default class MyPlugin extends Plugin {
  getName() { return 'my-package'; }
  async release() {
    await this.step({ enabled: true, task: () => this.doTask(), label: 'Doing task', prompt: 'my-prompt' });
  }
}
```

---

## 4. `--ci` and the `getIncrementedVersionCI` contract

### 4.1 What `--ci` does

* `docs/ci.md` / `README.md`: *"Use `--ci` to run the process **fully automated without prompts**. The
  configured tasks will be executed as demonstrated … In a Continuous Integration (CI) environment,
  this non-interactive mode is **activated automatically**."*
* Automatic activation is `lib/config.js`:

```js
const merged = defu({}, constructorConfig, { ci: isCI }, localConfig, defaultConfig);
```

  where `isCI` comes from the [`ci-info`] package and is only a **default** — an explicit
  `ci: true/false` in `opts` or in the local config wins.
* Consequences inside the codebase:
  * `Config.isCI` → `true`.
  * `Config.isPromptOnlyVersion` runs `config.setCI(true)` after the version is known.
  * `Plugin.step()` swaps prompts for spinners — **except** for the `incrementList`, `publish` and
    `otp` prompts when `--only-version` is also set.
  * `Version.getIncrementedVersion()` returns `null` instead of prompting when the increment cannot be
    derived: `return version || (isCI ? null : await this.promptIncrementVersion(options));`
  * `Version.incrementVersion()` picks a default increment with no `--increment`:
    `isPreRelease ? 'prepatch' : 'patch'`.
  * `npm` plugin: `stage || (this.config.isCI && !this.config.isPromptOnlyVersion)` and
    `const isInteractive = !stage && (!this.config.isCI || Boolean(this.config.isPromptOnlyVersion));`

### 4.2 Why `getIncrementedVersionCI` exists

`docs/plugins.md`, verbatim emphasis: *"Implement `getIncrementedVersionCI` to provide the next version
**without prompting the user** … This method exists to provide the next `version` to other elements of
the release process **early on**, such as the introduction text."*

Mechanically (`lib/index.js`):

```js
incrementBase.increment = await reduceUntil(plugins, plugin => plugin.getIncrement(incrementBase));
version = await reduceUntil(plugins, plugin => plugin.getIncrementedVersionCI(incrementBase));
...
config.setContext({ name, latestVersion, version, changelog });

if (config.isIncrement) {
  version = version || (await reduceUntil(plugins, plugin => plugin.getIncrementedVersion(incrementBase)));
}

if (version) {
  config.setContext(parseVersion(version));
  ...
}
```

The two-phase design:

| Phase | Method | Purpose |
|---|---|---|
| Early (always) | `getIncrementedVersionCI(incrementBase)` | Must be **non-interactive**. Its result populates `version` in the config context *before* the "🚀 Let's release …" banner and changelog preview, so those render the right version. |
| Fallback (only when `isIncrement` and the CI pass returned nothing) | `getIncrementedVersion(incrementBase)` | May prompt. `Version`'s default implementation returns `null` in CI rather than prompting. |

`incrementBase` is `{ latestVersion, increment, isPreRelease, preReleaseId, preReleaseBase }`.

### 4.3 `--release-version` and `--changelog`

Both force `Config.isCI === true` (via the `isCI` getter) and short-circuit with `process.exit` —
see §2.5. `docs/dry-runs.md`: *"To print the next version without releasing anything, use the
`--release-version` flag. If no next version is available, it prints nothing and exits successfully."*

---

## 5. Dry-run contract at API level

* `opts['dry-run'] = true` (CLI `-d` / `--dry-run`). `Config.isDryRun` reads exactly that key —
  note the **kebab-case with a hyphen**, so from JS it is `release({ 'dry-run': true })`, never `dryRun`.
* Enforcement lives in `Shell`, not in a wrapper:

```js
const isDryRun = this.config.isDryRun;
const isWrite = options.write !== false;
...
if (isDryRun && isWrite) {
  this.log.exec(command, { isDryRun });
  return noop;               // prints "! <command>", runs nothing
}
```

| Behaviour | Detail |
|---|---|
| Write commands | Not executed. Printed as `! git commit --message="Release 0.8.3"`. |
| Read-only commands | Still executed, printed as `$ git rev-parse --git-dir`. Triggered per-command by `{ options: { write: false } }`; core plugins use this for `git rev-parse`, `git describe`, `git rev-list`, etc. (`GitBase.js` uses `const options = { write: false };`). |
| Hook commands | **Not executed** — passed as `{ external: true }` with no `write: false`, so they are treated as writes. |
| Spinner | `isSpinnerDisabled = !config.isCI \|\| config.isVerbose \|\| config.isDryRun \|\| config.isDebug` — a dry run never animates a spinner. |
| `npm publish` | Not shelled out; the npm plugin's `release()` uses `this.step({ enabled: true, ... })` and its task no-ops, logging `Writing changelog…` style messages instead. |
| Return value | A dry run still resolves `{ name, changelog, latestVersion, version }` — it computes the version, so `--release-version --dry-run` prints the planned version. |

There is **no** exported `dryRun()` function; dry-run is purely an option-driven execution mode of
`runTasks`.

---

## 6. Worked examples

### 6.1 Minimal embed — release programmatically

```js
// release.mjs
import release from 'release-it';

try {
  const output = await release({
    increment: 'minor',        // 'major' | 'minor' | 'patch' | 'pre*' | an explicit semver
    ci: true,                  // fully automated, no prompts
    git: {
      commitMessage: 'chore: release v${version}',
      tagName: 'v${version}',
      push: true
    },
    npm: { publish: true },
    github: { release: true }
  });

  console.log(output);
  // { name: 'my-package', changelog: '…', latestVersion: '1.4.2', version: '1.5.0' }

  if (!output.version) {
    console.log('Nothing to release.');
  }
} catch (err) {
  console.error('Release failed:', err.message);
  process.exitCode = 1;        // do NOT process.exit() — runTasks may already have
}
```

### 6.2 Plan without touching anything

```js
import release from 'release-it';

const planned = await release({ 'dry-run': true, ci: true, increment: 'patch' });
console.log(`Latest: ${planned.latestVersion} → Next: ${planned.version}`);
// no writes: every mutating command was printed, not executed
```

Note: `'release-version': true` would print the version and `process.exit(0)`, so prefer the return
value when embedding (§2.5).

### 6.3 Read the resolved configuration

```js
import { Config } from 'release-it';

const config = new Config({ config: '.release-it.ci.json', configDir: process.cwd() });
await config.init();

console.log(config.isCI, config.isDryRun, config.options.git.tagName);
console.log(config.getContext('git.commitMessage'));
config.setContext({ version: '9.9.9' });      // what plugins do
```

### 6.4 Write a plugin and register it

```js
// scripts/slack-notify.js
import { Plugin } from 'release-it';

export default class SlackNotify extends Plugin {
  static isEnabled(options) {
    return Boolean(options.webhook);
  }
  async afterRelease() {
    const { version, releaseUrl } = this.config.getContext();
    if (!version) return false;                       // skips after:* hooks
    await this.exec(`curl -X POST ${this.options.webhook} -d "Released ${version}"`);
  }
}
```

```json
{ "plugins": { "./scripts/slack-notify.js": { "webhook": "https://hooks.slack.com/…" } } }
```

The namespace for a `./`-prefixed key is the file basename without extension — `slack-notify` — which
is what you use for `before:slack-notify:release` / `after:slack-notify:release` hooks.

### 6.5 Inject dependencies (testing)

```js
import release from 'release-it';
import { Config } from 'release-it';

const config = new Config({ ci: true });
const shell = { exec: async () => '' };               // stub every shell call

const out = await release({ increment: 'patch' }, { config, shell });
```

`runTasks` still awaits `config.init()`. Supplying `config` avoids a second config-file read only if
you have already initialised it.

---

## 7. CLI vs API equivalence

`lib/cli.js` is a thin wrapper:

```js
export default async options => {
  if (options.version) { version(); }
  else if (options.help) { help(); }
  else { return runTasks(options); }
  return Promise.resolve();
};
```

where `options` is the parsed argv (`lib/args.js`). So **anything the CLI does is reachable through
`runTasks(options)`**, using the same kebab-case/nested keys the CLI produces
(`'dry-run'`, `'only-version'`, `'release-version'`, `'hooks.before:init'`, `git.requireBranch`, …).
`--version` and `--help` are handled *before* `runTasks` and are not part of the API.

---

## 8. Unverified / non-existent API surface

| Item | Status |
|---|---|
| `ReleaseIt` class | `unverified` — no such export in `lib/index.js` (only default `runTasks`, `Config`, `Plugin`) |
| `releaseIt` named export | `unverified` — the default export is named `runTasks`; the docs alias it as `release` |
| `checkGitStatus()` public API | `unverified` — no such export; git status checks live in the `git` plugin's `init()` |
| `dryRun()` method | `unverified` — dry-run is the `'dry-run'` option, enforced in `Shell` |
| `run()` / `runTasks()` as a *member* of an object | `unverified` — `runTasks` is the module-level default export, not a method |
| `init()` / `bump()` / `release()` / `getLatestVersion()` / `getChangelog()` / `getIncrementedVersion()` as top-level API | `unverified` — these are `Plugin` methods (interfaces-plugins.md §3), reachable only by writing a plugin |
| TypeScript types for `runTasks` / `Plugin` | `unverified` — `types/index.d.ts` is a `declare module 'release-it'` stub exporting only `Config` |

[`ci-info`]: https://www.npmjs.com/package/ci-info
[c12]: https://github.com/unjs/c12
