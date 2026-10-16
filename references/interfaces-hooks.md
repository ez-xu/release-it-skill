# release-it — Hooks (Shell Command Hooks) Reference

**Version documented: release-it 21.1.1** (upstream `release-it/release-it` `main`).
Stock upstream — the `ez-xu/release-it` fork has zero custom commits (`ahead_by=0`).

Grounding sources: `lib/index.js` (`runHook`, `runLifeCycleHook`), `lib/shell.js`, `lib/spinner.js`,
`lib/util.js` (`format`, `parseGitUrl`), `lib/plugin/GitBase.js`, `lib/plugin/GitRelease.js`,
`lib/config.js`, `config/release-it.json`, `types/hooks.d.ts`, `README.md#hooks`, `docs/ci.md`.

---

## 1. Hook name grammar

```
[prefix]:[hook]                 e.g. before:init, after:release
[prefix]:[plugin]:[hook]        e.g. after:git:release, before:npm:bump, after:my-plugin:bump
```

| Part | Allowed values |
|---|---|
| `prefix` | `before` or `after` |
| `plugin` | any plugin namespace — core: `version`, `git`, `npm`, `github`, `gitlab`; or an external plugin's namespace (see `interfaces-plugins.md` §2.1) |
| `hook` | `init`, `beforeBump`, `bump`, `beforeRelease`, `release`, `afterRelease` |

`README.md` states the full set verbatim: *"the full list of hooks is actually: `init`, `beforeBump`,
`bump`, `beforeRelease`, `release` or `afterRelease`."*

> **Stale type:** `types/hooks.d.ts` in 21.1.1 only declares `HookName = 'init' | 'bump' | 'release'`
> and enumerates only `before|after (:plugin:) init|bump|release`. That union is **incomplete** — the
> runtime accepts `beforeBump`, `beforeRelease` and `afterRelease` as well (see §2), and the README
> documents them. The `Hooks` interface does not use an index signature, so TS users cannot type a
> valid `"after:release"` against it without widening.

---

## 2. Emission order — exactly when each hook fires

`lib/index.js` builds the hook name from the lifecycle loop:

```js
const runHook = async (...name) => {
  const scripts = hooks[name.join(':')];
  if (!scripts || !scripts.length) return;
  const context = config.getContext();
  const external = true;
  for (const script of castArray(scripts)) {
    const task = () => shell.exec(script, { external }, context);
    await spinner.show({ task, label: script, context, external });
  }
};

const runLifeCycleHook = async (plugin, name, ...args) => {
  if (plugin === plugins.at(0)) await runHook('before', name);
  await runHook('before', plugin.namespace, name);
  const willHookRun = (await plugin[name](...args)) !== false;
  if (willHookRun) {
    await runHook('after', plugin.namespace, name);
  }
  if (plugin === plugins.at(-1)) await runHook('after', name);
};
```

So **per plugin, per lifecycle method**, the emission order is:

1. `before:<lifecycle>` — **only when the plugin is first in the current plugin list**
2. `before:<namespace>:<lifecycle>`
3. *(the plugin method itself runs)*
4. `after:<namespace>:<lifecycle>` — **skipped if the plugin method returned `false`**
5. `after:<lifecycle>` — **only when the plugin is last in the current plugin list**

Because the plugin list is `[...external, ...internal]` for the first part of the run and
`[...internal, ...external]` for `release`/`afterRelease`, the plugin that counts as "first"/"last"
for steps 1 and 5 **differs per phase**:

| Lifecycle methods | Plugin list | `before:<x>` fires on | `after:<x>` fires on |
|---|---|---|---|
| `init`, `beforeBump`, `bump`, `beforeRelease` | `[external..., internal...]` | first **external** plugin | last **internal** plugin (`version`) |
| `release`, `afterRelease` | `[internal..., external...]` | first **internal** plugin (`npm`) | last **external** plugin |

If no external plugins are configured, the list is just the enabled internal plugins in
`npm → git → github → gitlab → version` order.

### 2.1 Hooks that are NEVER emitted

The shell-hook machinery is invoked **only** through `runLifeCycleHook`, which is called only for the
six names in the table above. Therefore **no `before:`/`after:` hook ever fires for the getter
methods** `getName`, `getLatestVersion`, `getChangelog`, `getIncrement`,
`getIncrementedVersionCI`, `getIncrementedVersion`.

Those six go straight through `reduceUntil(plugins, plugin => plugin.getX())` with no hook wrapper.
Consequence: there is no hook around version determination, so a project that needs to inject a
version must do it through a plugin, `--increment=<explicit>`, or the `before:init` hook.

### 2.2 Full hook-name enumeration

For each lifecycle `L ∈ {init, beforeBump, bump, beforeRelease, release, afterRelease}`:

| Form | Example | Notes |
|---|---|---|
| `before:L` | `before:init`, `before:bump`, `before:release` | Fires once per lifecycle (guarded by first-in-list). |
| `after:L` | `after:init`, `after:bump`, `after:release` | Fires once per lifecycle (guarded by last-in-list). |
| `before:<ns>:L` | `before:git:bump`, `before:npm:release` | `<ns>` ∈ `version`, `git`, `npm`, `github`, `gitlab`, or an external plugin namespace. |
| `after:<ns>:L` | `after:git:release`, `after:github:release`, `after:my-plugin:bump` | Skipped when the plugin method returns `false`. |

Total possible hook keys: `6 lifecycles × 2 prefixes × (1 + N namespaces)`.
The README notes that mechanically-valid but useless keys exist — *"hooks like
`before:beforeRelease` look weird and are usually not useful in practice."*

Documented `README.md` example set includes: `before:init`, `after:my-plugin:bump`, `after:bump`,
`after:git:release`, `after:release`. `docs/ci.md` uses `before:init` for
`git fetch --prune --prune-tags origin`.

---

## 3. What a hook does at runtime

| Aspect | Fact (`lib/index.js`, `lib/shell.js`) |
|---|---|
| Kind | **Shell command string only.** Always `shell.exec(script, { external: true }, context)`. JS functions are *not* accepted for `hooks.*` — a function in `hooks` would be passed to `exec()` and is not a string, so it is treated as an argv array and fails. |
| Value type | `string | string[]`. An array runs **sequentially**, each through its own `spinner.show`. |
| `this` context | **None.** Hooks are shell commands, not JS. The only "context" is the template-variable object described in §4. |
| Command options | `{ external: true }` — meaning: not cached (`useCache = !isExternal && options.cache !== false`), and in interactive mode the spinner is force-displayed even when spinners are otherwise disabled. |
| Template rendering | `shell.exec` → `format(command, context)` → [Eta] with tags `['${', '}']`, `autoEscape: false`. Every `${...}` is replaced **before** the command runs. |
| Execution | `exec(command, execOptions)` where `execOptions = options.env ? { env: options.env } : {}` — i.e. **no `env` is set by the hook path**, so hooks inherit `process.env` (Node's default for `child_process.exec`). |
| Working directory | Inherited from the release-it process (`process.cwd()`); never overridden. |
| Output | Captured (not streamed). stdout is logged via `log.verbose(...)`; use `--verbose` / `-V` to see it. |
| Enable/disable | `--no-hooks` skips **all** hooks. `--no-hooks.<name>` disables one, e.g. `--no-hooks.before:init`. |

State that gates the "after" hook: a plugin returning `false` from its lifecycle method suppresses
`after:<ns>:<L>` and, when it is the last plugin, `after:<L>` too. `README.md` puts it as: *"hooks like
`after:git:release` will not run when either the `git push` failed, or when it is configured not to be
executed (e.g. `git.push: false`)."*

---

## 4. Template variables available inside hooks

The context object handed to hooks is exactly `config.getContext()`
(`merge({}, this.options, this.contextOptions)`), so **every configuration option is a variable** —
including all of `config/release-it.json` — plus the following additional variables:

| Variable | Set by | Available from |
|---|---|---|
| `version` | `config.setContext({ name, latestVersion, version, changelog })` | after version resolution |
| `latestVersion` | same | after version resolution |
| `changelog` | same | after version resolution |
| `name` | same | after version resolution |
| `repo.remote`, `repo.protocol`, `repo.host`, `repo.owner`, `repo.repository`, `repo.project` | `GitBase.init()` → `parseGitUrl(remoteUrl)` | during/after `git:init` |
| `branchName` | `GitBase.init()` | during/after `git:init` |
| `remoteUrl` | `GitBase.init()` | during/after `git:init` |
| `latestTag`, `secondLatestTag`, `tagTemplate` | `GitBase.init()` | during/after `git:init` |
| `tagName` | `GitBase.bump(version)` | after the `git:bump` step |
| `releaseUrl` | GitHub / GitLab release plugin | after `release` |

`parseGitUrl` (`lib/util.js`) returns `{ host, owner, project, protocol, remote, repository }` where
`repository = owner + "/" + project`.

**README caveat, verbatim:** *"All variables are available in all hooks. The only exception is that
the additional variables listed above are not yet available in the `init` hook."*
This matters for `before:init`: at that point only static config values are in context — `${version}`,
`${name}`, `${repo.*}` etc. will **not** resolve there.

Where core plugins write those values (`lib/plugin/GitBase.js`):

```js
const branchName = await this.getBranchName();
const repo = parseGitUrl(remoteUrl);
this.setContext({ remoteUrl, branchName, repo });
this.config.setContext({ remoteUrl, branchName, repo });

const latestTag = await this.getLatestTagName();
const secondLatestTag = !this.config.isIncrement ? await this.getSecondLatestTagName(latestTag) : null;
const tagTemplate = this.options.tagName || ((latestTag || '').match(/^v/) ? 'v${version}' : '${version}');
this.config.setContext({ latestTag, secondLatestTag, tagTemplate });
```

> Type in the source: `${version}` is a real placeholder there; write `'v${version}'` literally when
> quoting the JS.

Rendering failure is loud, not silent (`lib/util.js`):

```js
log.error(`Unable to render template with context:\n${template}\n${JSON.stringify(context)}`);
throw error;
```

So a hook referencing an unknown identifier throws and aborts the run rather than passing the raw text
through to the shell.

---

## 5. Environment variables

release-it 21.1.1 exposes **no `RELEASE_IT_*` environment variables** to hooks.

| Claim | Status |
|---|---|
| `RELEASE_IT_*` version/tag variables for hooks | **`unverified` / not present.** `docs/environment-variables.md` documents only `GITHUB_TOKEN` and `GITLAB_TOKEN`; the release-version values are delivered as **template variables** (§4), not env vars. No `RELEASE_IT_` prefix occurs in `lib/`, `types/` or `docs/`. |
| `--ci` sets a CI env var for hooks | **`unverified` — no such assignment found in `lib/config.js` or `lib/index.js`.** CI detection reads `isCI` from the `ci-info` package and merges it into options as `ci: isCI`; it is not re-exported to child processes. |

Environment variables release-it **consumes** (rather than exports):

| Variable | Consumed by | Purpose |
|---|---|---|
| `GITHUB_TOKEN` | GitHub plugin — `github.tokenRef` defaults to `"GITHUB_TOKEN"` (`config/release-it.json`) | GitHub Release / asset auth |
| `GITLAB_TOKEN` | GitLab plugin — `gitlab.tokenRef` defaults to `"GITLAB_TOKEN"` | GitLab Release auth |
| `GITHUB_ACTOR` | GitHub plugin, only `if (process.env.GITHUB_ACTIONS)` | sets the context `username` |
| `NPM_TOKEN` | **not read by release-it**; consumed by the npm CLI via `.npmrc` (`docs/ci.md`) | registry auth |
| `NODE_DEBUG` | `lib/util.js`, `lib/config.js`, `lib/plugin/*` | `NODE_DEBUG=release-it:*` enables namespaced debug output |

Token indirection (`lib/plugin/GitRelease.js`) — the only supported rename mechanism:

```js
get token() {
  const { tokenRef } = this.options;
  return process.env[tokenRef] || null;
}
```

So `github.tokenRef="RELEASE_IT_GITHUB_TOKEN"` makes the plugin read that env var instead. This is a
*configurable variable name*, not a variable release-it defines. If `tokenRef` points at an unset
variable the GitHub plugin warns: `Environment variable "<tokenRef>" is required for automated GitHub Releases.`

Hooks inherit the ambient environment unchanged (`exec` is called with no `env`), so anything already
exported — including `GITHUB_TOKEN` / `GITLAB_TOKEN` / `NPM_TOKEN` — is visible to them.

---

## 6. Failure handling

**A failing hook aborts the release.** There is no catch around the hook invocation:

* `shell.exec` rejects on a non-zero exit code:
  `reject(new Error(stderr || stdout))` (string command) and
  `reject(new Error(stderr || stdout || \`Process exited with code ${code}\`))` (argv command).
* `spinner.show` returns `awaitTask`, i.e. the rejected promise propagates.
* `await runHook(...)` inside `runLifeCycleHook`, and `await runLifeCycleHook(...)` inside the lifecycle
  loops, propagate to the single `try` in `runTasks`:

```js
} catch (err) {
  const { log } = container;
  const errorMessage = err.message || err;
  const logger = log || console;
  err.cause === 'INFO' ? logger.info(errorMessage) : logger.error(errorMessage);
  throw err;
}
```

`runTasks` then rejects; the CLI exits non-zero. In dry-run mode the situation does not arise for
write hooks because they are not executed at all (see §7).

The `git` plugin additionally installs a rollback on `SIGINT` and `process.exit` that deletes the
local tag and `git reset --hard HEAD[~1]` — i.e. a hook that fails part-way through a run can trigger a
rollback of the commit/tag the run already made.

---

## 7. Dry-run behaviour of hooks

`Shell.execFormattedCommand`:

```js
const isWrite = options.write !== false;
...
if (isDryRun && isWrite) {
  this.log.exec(command, { isDryRun });
  return noop;
}
```

Hooks are executed through `shell.exec(script, { external: true }, context)` — **no `write: false`** —
so in `--dry-run` a hook is **printed as `! <command>` and never executed**. This is a hard constraint:
you cannot dry-run a hook.

---

## 8. Worked example

`.release-it.json`:

```json
{
  "git": {
    "commitMessage": "chore: release v${version}"
  },
  "github": {
    "release": true
  },
  "hooks": {
    "before:init": ["npm run lint", "npm test"],
    "after:bump": "npm run build",
    "after:git:release": "echo After git push, before github release",
    "after:release": "echo Successfully released ${name} v${version} to ${repo.repository}."
  }
}
```

What happens, in order:

1. `before:init` — `npm run lint`, then `npm test`. Fires once, before any plugin's `init`, so
   `${version}` and `${repo.*}` are **not** available here.
2. Core plugins `init` (`npm` → `git` → `github` → `gitlab` → `version`). `git:init` populates
   `repo.*`, `branchName`, `latestTag`.
3. Version determination: no hooks fire.
4. `beforeBump` / `bump` for every plugin. `bump` renders `${version}`.
5. `after:bump` — `npm run build`. At this point `tagName` and `version` exist; the Git plugin's own
   `after:git:bump` has already staged changes.
6. `beforeRelease` for every plugin.
7. `release` phase, iterating `[internal, ...external]`: `npm:publish`, then `git:push`, then
   `after:git:release` → `echo After git push, before github release`, then `github:release`.
8. `after:release` — `echo Successfully released <name> v<version> to <owner>/<repo>.` — fires last,
   after the GitHub Release exists, so `${releaseUrl}` is available.

Equivalent command-line form (note the quoting, per `README.md`):

```bash
release-it --'hooks.after:release="echo Successfully released ${name} v${version} to ${repo.repository}."'
```

Disable just the test hook for one run:

```bash
release-it --no-hooks.before:init
```

TOML equivalent (`docs/configuration.md`):

```toml
[hooks]
"before:init" = "npm test"
```

---

## 9. Known limitation

`README.md`: *"Using `@inquirer/prompts` inside custom hook scripts might cause issues (since release-it
also uses this itself)."* Relevant because hooks run as child processes while a prompt may be open.

[Eta]: https://eta.js.org/
[@inquirer/prompts]: https://www.npmjs.com/package/@inquirer/prompts
