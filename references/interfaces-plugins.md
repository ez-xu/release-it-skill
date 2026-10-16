# release-it — Plugin Interface Reference

**Version documented: release-it 21.1.1** (upstream `release-it/release-it` `main`; `package.json` `"version": "21.1.1"`).
Stock upstream — the `ez-xu/release-it` fork has zero custom commits (`ahead_by=0`).

Grounding sources: `lib/plugin/Plugin.js`, `lib/plugin/factory.js`, `lib/plugin/GitRelease.js`,
`lib/plugin/GitBase.js`, `lib/index.js`, `config/release-it.json`, `types/config.d.ts`, `docs/plugins.md`, `README.md`.

---

## 1. What a plugin is

release-it is a pluggable task runner. Internally it uses the **same** plugin architecture for its
own Git / GitHub / GitLab / npm / version support (`lib/plugin/factory.js`):

```js
const pluginNames = ['npm', 'git', 'github', 'gitlab', 'version'];
const plugins = { version: Version, git: Git, gitlab: GitLab, github: GitHub, npm: npm };
```

Internal plugin enablement (`static isEnabled`):

| Internal plugin | Enabled when |
|---|---|
| `git` | `options !== false` and cwd is a Git repo (`isGitRepo()`) |
| `github` | `options.release` |
| `gitlab` | `options.release` |
| `npm` | package.json found (npm plugin `static isEnabled`) |
| `version` | always |

---

## 2. Declaring a plugin in config

Plugins are **local modules or external npm packages**. Config shape (`types/config.d.ts`):
`plugins?: Record<string, Record<string, any>>`.

```json
{
  "plugins": {
    "release-it-plugin": { "key": "value" },
    "./scripts/release-it-plugin.js": { "key": "value" }
  }
}
```

The key is passed **verbatim** into `await import(pluginName)` — so it is either an npm package name
or a path. `release-it` itself is resolved relative to the consuming project.

### 2.1 Key → namespace mapping

`getPluginName` (`lib/plugin/factory.js`):

```js
export const getPluginName = pluginName => {
  if (pluginName.startsWith('.')) {
    return path.parse(pluginName).name;
  }
  return pluginName;
};
```

| Config key | Namespace |
|---|---|
| `"@release-it/bumper"` | `"@release-it/bumper"` |
| `"release-it-plugin"` | `"release-it-plugin"` |
| `"./scripts/release-it-plugin.js"` | `"release-it-plugin"` (path basename, extension stripped) |

The namespace is what you use in `this.namespace`, in the plugin's own context key, and in
`before:<namespace>:<hook>` / `after:<namespace>:<hook>` shell hooks.
Note the namespace is **not** derived from the module's package name — a package whose real name
differs from the config key is namespaced under the config key.

### 2.2 Loading and options resolution (`getPlugins`)

```js
for (const [pluginName, pluginConfig] of Object.entries(context.plugins)) {
  const [name, Plugin] = await load(pluginName);
  const [namespace, options] = pluginConfig.length === 2 ? pluginConfig : [name, pluginConfig];
  config.setContext({ [namespace]: options });
  if (await Plugin.isEnabled(options)) {
    const instance = new Plugin({ namespace, options: config.getContext(), container });
    ...
  }
}
```

* `load(pluginName)` tries, in order: `await import(pluginName)` → `await import(path.join(process.cwd(), pluginName))`
  → `await import(url.pathToFileURL(require.resolve(pluginName, { paths: [process.cwd()] })))`.
  Each failure is `debug()`-logged. `module.default` is taken as the plugin class.
* `pluginConfig.length === 2` allows the array form `[namespace, options]`; otherwise the namespace is
  the derived `name` and the options are the config object.
* After construction the plugin is **replaced** by its `disablePlugin()` targets:

```js
disabledPlugins.push(...pluginNames.filter(p => castArray(Plugin.disablePlugin(options)).includes(p)));
```

* Internal plugins are then instantiated in fixed order `npm → git → github → gitlab → version`,
  skipping any listed in `disabledPlugins`.
* `getPlugins` returns `[enabledPlugins, enabledExternalPlugins]` — **internal first**.
  `lib/index.js` then builds `let plugins = [...external, ...internal];`

> **`RELEASE_IT_PLUGINS` — `unverified`.** No such identifier exists in release-it 21.1.1.
> A GitHub code search for `RELEASE_IT_PLUGINS repo:release-it/release-it` returns `total_count: 0`,
> and no occurrence appears in `lib/`, `docs/`, `README.md`, or `types/`. There is no environment
> variable in stock release-it that registers plugins; plugins are registered **only** through the
> `plugins` config key (or the `--plugins.*` CLI form).

---

## 3. The exact set of methods release-it calls on a plugin

Verbatim from `lib/plugin/Plugin.js` — these are the **12 lifecycle methods plus 2 statics**, all
no-ops by default:

```js
class Plugin {
  static isEnabled() { return true; }
  static disablePlugin() { return null; }
  constructor({ namespace, options = {}, container = {} } = {}) { ... }
  getInitialOptions(options, namespace) { return options[namespace] || {}; }
  init() {}
  getName() {}
  getLatestVersion() {}
  getChangelog() {}
  getIncrement() {}
  getIncrementedVersionCI() {}
  getIncrementedVersion() {}
  beforeBump() {}
  bump() {}
  beforeRelease() {}
  release() {}
  afterRelease() {}
}
```

Constructor-assigned instance properties available to every method:
`this.namespace`, `this.options` (frozen), `this.context = {}`, `this.config`, `this.log`,
`this.shell`, `this.spinner`, `this.prompt`, `this.debug`.

### 3.1 Lifecycle order and arguments actually passed by `lib/index.js`

| # | Method | Args passed by release-it | Resolution | `before:`/`after:` hooks fire? |
|---|---|---|---|---|
| 1 | `init()` | — | every plugin, in list order | **yes** |
| 2 | `getName()` | — | `reduceUntil` — first non-undefined wins | no |
| 3 | `getLatestVersion()` | — | `reduceUntil`; result `\|\| '0.0.0'` | no |
| 4 | `getChangelog(latestVersion)` | `latestVersion` | `reduceUntil` | no |
| 5 | `getIncrement(incrementBase)` | `{ latestVersion, increment, isPreRelease, preReleaseId, preReleaseBase }` | `reduceUntil` | no |
| 6 | `getIncrementedVersionCI(incrementBase)` | same object | `reduceUntil` | no |
| 7 | `getIncrementedVersion(incrementBase)` | same object | `reduceUntil` | no |
| 8 | `beforeBump()` | — | every plugin | **yes** |
| 9 | `bump(version)` | `version` (string) | every plugin | **yes** |
| 10 | `beforeRelease()` | — | every plugin | **yes** |
| 11 | `release()` | — | every plugin, **reversed list** | **yes** |
| 12 | `afterRelease()` | — | every plugin, **reversed list** | **yes** |

Actual loop bodies:

```js
for (const plugin of plugins) { await runLifeCycleHook(plugin, 'init'); }

const name = await reduceUntil(plugins, plugin => plugin.getName());
const latestVersion = (await reduceUntil(plugins, plugin => plugin.getLatestVersion())) || '0.0.0';
const changelog = await reduceUntil(plugins, plugin => plugin.getChangelog(latestVersion));
...
incrementBase.increment = await reduceUntil(plugins, plugin => plugin.getIncrement(incrementBase));
version = await reduceUntil(plugins, plugin => plugin.getIncrementedVersionCI(incrementBase));
...
version = version || (await reduceUntil(plugins, plugin => plugin.getIncrementedVersion(incrementBase)));

for (const hook of ['beforeBump', 'bump', 'beforeRelease']) {
  for (const plugin of plugins) {
    const args = hook === 'bump' ? [version] : [];
    await runLifeCycleHook(plugin, hook, ...args);
  }
}

plugins = [...internal, ...external];

for (const hook of ['release', 'afterRelease']) {
  for (const plugin of plugins) { await runLifeCycleHook(plugin, hook); }
}
```

**Getter resolution is `reduceUntil`** (`lib/util.js`) — it iterates and breaks at the **first truthy
result**, so a plugin returning a truthy value short-circuits every later plugin *and* the core
plugin. A plugin returning `undefined`/`null`/`''` yields to the next one. Because
`plugins = [...external, ...internal]`, **custom plugins always get first say** on
`name`, `latestVersion`, `changelog`, `increment`, `version`.

`release`/`afterRelease` iterate the **reversed** list (`internal` first, `external` last), so custom
plugins run after the core plugins — this is what makes deployment hooks and success notifications
work.

### 3.2 Method contracts (`docs/plugins.md`)

| Method | Contract / expected return |
|---|---|
| `static isEnabled(options)` → Boolean | Enables the plugin based on config or file presence. Default `true`. |
| `static disablePlugin(options)` → String \| String[] | Name(s) of core plugin(s) to disable: one or more of `version`, `git`, `github`, `gitlab`, `npm`. |
| `getInitialOptions(options, pluginName)` → Object | Default returns `options[pluginName] \|\| {}`. Override to pull sibling options. |
| `init()` | Validate prerequisites; gather app/package details. May throw to abort. |
| `getName()` → String | Name of the package being released. |
| `getLatestVersion()` → SemVer | The version prior to this release. |
| `getChangelog(latestVersion)` → String | Changelog for the upcoming release. |
| `getIncrement({latestVersion, increment, isPreRelease, preReleaseId})` → `'major'\|'minor'\|'patch'` | Override the increment used by `getIncrementedVersionCI`. *Internal.* |
| `getIncrementedVersionCI(options)` → SemVer | Next version **without prompting**. *Internal*; exists to expose `version` early (e.g. intro text). |
| `getIncrementedVersion(options)` → SemVer | Next version, prompting the user if it cannot be determined automatically. *Internal.* |
| `beforeBump()` | Prepare / output information for the user to confirm. |
| `bump(version)` | Write the new version into manifests or other files. |
| `beforeRelease()` | Work that must happen after the bump and before `release`; also where changes get staged. |
| `release()` | Main flow. Declare "steps" via `this.step()` → prompts (interactive) or spinners (CI). |
| `afterRelease()` | Post-success details such as a release URL. |

**Returning `false` from any lifecycle method skips that plugin's `after:<namespace>:<method>` and
`after:<method>` hooks** (`lib/index.js`):

```js
const willHookRun = (await plugin[name](...args)) !== false;
if (willHookRun) { await runHook('after', plugin.namespace, name); }
```

All methods may be `async` **except `static disablePlugin()`** (`docs/plugins.md`).

### 3.3 Helper methods on `this`

| Helper | Signature | Behaviour |
|---|---|---|
| `getInitialOptions` | `(options, namespace) → Object` | `options[namespace] \|\| {}` |
| `getContext` | `(path?) → Object` | `merge({}, this.options, this.context)`, optionally deep-`get(path)`. |
| `setContext` | `(context) → void` | `merge(this.context, context)`. Plugin-local runtime data. |
| `exec` | `(command, { options, context = {} } = {}) → Promise<string>` | Runs in the shell with `Object.assign(context, this.config.getContext(), { [this.namespace]: this.getContext() })`. |
| `registerPrompts` | `(prompts) → void` | `this.prompt.register(prompts, this.namespace)` — [@inquirer/prompts] objects. |
| `showPrompt` | `(options) → Promise` | Forces `options.namespace = this.namespace`, then `this.prompt.show(options)`. |
| `step` | `(options) → Promise` | Spinner in CI, prompt when interactive. |

`step()` special case:

```js
const isException = this.config.isPromptOnlyVersion && ['incrementList', 'publish', 'otp'].includes(opts.prompt);
return this.config.isCI && !isException ? this.spinner.show(opts) : this.showPrompt(opts);
```

`this.debug` is `util.debug('release-it:' + namespace)`, so `NODE_DEBUG=release-it:* release-it` prints it.

### 3.4 Dry-run behaviour inside a plugin

`this.exec()` goes through `Shell.execFormattedCommand`, which short-circuits writes:

```js
const isWrite = options.write !== false;
if (isDryRun && isWrite) { this.log.exec(command, { isDryRun }); return Promise.resolve(); }
```

Read-only calls must opt in explicitly: `this.exec('git log', { options: { write: false } })`.

---

## 4. Plugin author interface — what to extend, required vs optional

* Extend `Plugin`, imported from the `release-it` package: `import { Plugin } from 'release-it';`
  (`lib/index.js` does `export { default as Plugin } from './plugin/Plugin.js';`).
* `release-it` must be a **`peerDependency`** (and usually a `devDependency`) of the plugin.
* **No method is required.** Every method in `Plugin` is a no-op, so a plugin may implement any subset.
* `getName` decides the package name used throughout the run; `getLatestVersion` decides the "latest
  version prior to this release". Implementing either puts the plugin ahead of the core plugins.
* `isEnabled(options)` gates the plugin: returning `false` means **no instance is constructed at all**
  (`if (await Plugin.isEnabled(options))`), so no method on it ever runs.
* `disablePlugin(options)` removes core plugins from the run — e.g. `@release-it/conventional-changelog`
  returns `'version'` unless `ignoreRecommendedBump` is set.
* A plugin should return `false` from a lifecycle method it effectively skipped, to suppress the
  matching `after:*` hooks.

Minimal documented example (`docs/plugins.md`):

```js
class MyPlugin extends Plugin {
  getLatestVersion() { return fs.readFileSync('./VERSION', 'utf8').trim(); }
  bump(version) { this.version = version; fs.writeFileSync('./VERSION', version); }
}
```

The docs explicitly note two ordering consequences: if the `npm` plugin is enabled it will bump
`package.json` with the value returned by `getLatestVersion`, and if the `git` plugin is enabled its
`beforeRelease` will stage the changed file so the update lands in the release commit.

---

## 5. First-party / notable plugins

Package names and versions verified with `npm view` / `npm search --json "keywords:release-it-plugin"`
(2026-10 snapshot). Implemented lifecycle methods verified by **inspecting each published tarball**,
except where marked.

| Package | Latest | What it adds | Lifecycle methods implemented (verified) |
|---|---|---|---|
| `@release-it/conventional-changelog` | 12.0.2 | Recommended bump from conventional commits, conventional-changelog, writes `CHANGELOG.md` | `static disablePlugin` (returns `'version'`, or `null` if `ignoreRecommendedBump`), `getChangelog(latestVersion)`, `getIncrementedVersion(options)`, `getIncrementedVersionCI(options)`, `bump(version)`, `beforeRelease()` |
| `@release-it/bumper` | 8.0.1 | Read & write the version from/to any file (json, yaml, toml, ini, xml, html, text) | `getLatestVersion()`, `bump(version)` |
| `@release-it/keep-a-changelog` | 8.0.1 | Maintain `CHANGELOG.md` per Keep a Changelog | `init()` (calls `super.init()`), `getChangelog(latestVersion)`, `bump(version)`, `beforeRelease()` |
| `@release-it-plugins/lerna-changelog` | 9.0.0 | Integrates lerna-changelog into the pipeline | `init()`, `getChangelog()`, `beforeRelease()` |
| `@release-it-plugins/workspaces` | 6.0.0 | Bump and publish each configured workspace | `static isEnabled(options)` (`fs.existsSync(ROOT_MANIFEST_PATH) && options !== false`), `init()`, `beforeBump()`, `bump(version)`, `release()`, `afterRelease()` |
| `release-it-lerna-changelog` | 5.0.0 | Deprecated predecessor of `@release-it-plugins/lerna-changelog`; the published README is the redirected lerna-changelog doc | `init()`, `getChangelog()`, `beforeRelease()` |
| `@j-ulrich/release-it-regex-bumper` | 5.6.0 | Regex-based version read/write | `unverified — 404s for main/master README; not inspected` |
| `@csmith/release-it-calver-plugin` | 2026.9.0 | Calendar versioning (calver) | `unverified — README not inspected` |
| `release-it-pnpm` | 4.6.6 | pnpm workspaces, bumpp + changelogithub integration | `unverified — README not inspected` |
| `release-it-git-cliff` | 0.2.0 | git-cliff changelog + next version | `unverified — README not inspected` |
| `@jcamp-code/release-it-changelogen` | listed in README | `@unjs/changelogen` versioning + changelog | `unverified — README not inspected` |
| `@grupoboticario/news-fragments` (npm: `news-fragments`) | 4.5.1 | Changelog file generation | `unverified — README not inspected` |
| `@jcamp-code/release-it-dotnet` | listed in README | `.csproj`/`.props` versioning + NuGet publish | `unverified — README not inspected` |
| `changesets-release-it-plugin` | 0.2.0 | Changesets changelog management | `unverified — README not inspected` |
| `release-it-gitea` | listed in README | Gitea releases + asset upload | `unverified — README not inspected` |
| `release-it-beautiful-changelog` | 0.2.1 | changelogen-based changelog | `unverified — README not inspected` |

`@release-it-plugins/standard-version` — `unverified` — does not exist on npm (`npm view` E404).

The complete, always-current list is the npm keyword search:
<https://www.npmjs.com/search?q=keywords:release-it-plugin>.

---

## 6. Execution-order worked example (`docs/plugins.md`)

Config:

```json
{ "plugins": { "PluginA": {}, "PluginB": {} } }
```

1. `init`: `PluginA` → `PluginB` → core `npm` → `git` → `github` → `gitlab` → `version`.
2. Same order for `getName` and `getLatestVersion`, but with **first-truthy-wins** semantics.
3. `beforeBump`, `bump`, `beforeRelease`: same order.
4. `release` and `afterRelease`: **reversed**.

Documented consequences:

* If `npm` is enabled, `npm.getName()` is the first getter that returns, using `name` from `package.json`.
  If it is not enabled, `git`'s `getName()` infers the name from the remote URL, etc.
* Custom plugin methods run first, so they can override `name`, `latestVersion`, `repo` and `changelog`.

---

## 7. Starter kit

`release-it/plugin-starterkit` — <https://github.com/release-it/plugin-starterkit>.
The closest thing to a reference implementation is the internal plugins under
<https://github.com/release-it/release-it/tree/main/lib/plugin> and the test helper at
`test/util/index.js#L54`.
