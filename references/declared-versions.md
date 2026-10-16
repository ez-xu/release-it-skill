# Declared versions

`release-it` derives a version from the latest tag plus an increment, and it refuses a
version that is not semantic. Firmware and embedded releases are usually named differently —
they carry a board, a customer, a date and a build id:

```
5.1.7.12_weiyuan_G200464803_20261016_8aef61de
3.3.0.7_feature_modbus-regs_G5_20261012_0de3e49f
```

`ez-xu/release-it` adds support for exactly these strings. This skill treats such a string as
a **declared version**: it is carried unchanged, never compared with anything, and never
incremented. Anything `release-it` would silently rewrite is refused instead, with the
corrected command.

## When a version counts as declared

The rule is the fork's own, in `lib/plugin/version/Version.js`:

```js
const coercedVersion = !isValidVersion && normalizeFull(coerce(increment));
if (coercedVersion) {
  if (typeof increment !== 'string') return coercedVersion;
  if (increment.startsWith(coercedVersion) && /^[.-]?\d/.test(increment.slice(coercedVersion.length))) {
    return increment; // Declared version strings are used verbatim instead.
  }
  this.log.warn(`Coerced invalid semver version "${increment}" into "${coercedVersion}".`);
  return coercedVersion;
}
```

`coercedVersion` is `semver.coerce(increment)` padded to three parts. A string is therefore
declared when the coerced value is a **true prefix** of it and the remainder starts with `.`,
`-` or a digit:

| version | coerced | declared? | why |
| --- | --- | --- | --- |
| `5.1.7.12_weiyuan_…` | `5.1.7` | yes | the string starts with `5.1.7`, remainder `.12_weiyuan_…` |
| `3.3.0.7_feature_modbus-regs_…` | `3.3.0` | yes | remainder `.7_feature_…` |
| `V5.1.7.12_weiyuan_…` | `5.1.7` | **no** | `5.1.7` is not a prefix — the leading `V` is in the way |
| `release-2026.1` | `2026.1` | **no** | the string does not start with `2026.1` |
| `1.2.3` | — | semver | an ordinary release |

`scripts/rls_version.py` implements this as `is_declared()`, with `is_semver()`, `coerce()`,
`coercion_of()` and `split_prefix()` alongside it. `resolve_version()` returns the source
`"declared"` for such a version, `"explicit"` for a semantic one, and raises `VersionError`
for a string that release-it would coerce away.

## The leading `V` belongs in the tag, not in the version

A declared version is kept verbatim only when it carries no prefix, because release-it
itself coerces `V5.1.7.12_…`:

```
WARNING Coerced invalid semver version "V5.1.7.12_weiyuan_…" into "5.1.7"
```

The skill therefore splits a leading `v`/`V` off and puts it into `git.tagName`, so the tag
is still **exactly** the string that was declared (`V5.1.7.12_weiyuan_…`) while the version
itself stays verbatim. It warns that it did so, and an explicit `tag_prefix` still wins.

## What release-it does with a declared version

| step | behaviour |
| --- | --- |
| `git.tagName` | verbatim — the tag is the declared string |
| `npm version` / `npm publish` | **fails**: `npm error Invalid version: 5.1.7.12_weiyuan_…`, and the whole run aborts before any commit or tag is written |
| `git.commitMessage`, `git.tagAnnotation` | `${version}` is truncated to the semantic prefix by `parseVersion()` in `lib/utils.js` — `git commit --message Release 5.1.7` |
| the release body | verbatim, from the notes the skill generates |
| the changelog | verbatim |

## What the skill does about it

1. **Switches the npm plugin off** (`--no-npm`, `npm.publish: false`). npm cannot carry a
   non-semver version, and `npm version <v>` would abort the run before the tag exists.
2. **Substitutes `${version}` itself**, in `git.commitMessage`, `git.tagAnnotation` and
   `github.releaseName` / `gitlab.releaseName`, so no template ever reaches release-it's
   truncating `parseVersion()` path.
3. **Requires a runner that carries the fork's fix.** The skill reads the installed
   `lib/plugin/version/Version.js` and looks for `latestIsComparable` (or the
   `Declared version strings are used verbatim` comment). When the fix is missing — and the
   runner is not already `github:ez-xu/release-it` — it falls back to
   `npx --yes github:ez-xu/release-it` and records `fallback_from`. If nothing can be shown
   to support the version it refuses with exit 2.
4. **Relaxes the manifest rules.** A firmware repository normally has no `package.json`; for
   a declared version an unreadable manifest is a warning, not a blocker, and the manifest
   version is not compared.
5. **Blocks only on exact equality.** Ordering cannot be verified between two declared
   versions, so no increment can be derived and the skill blocks only when the manifest
   already holds exactly this version (a version is never released twice).
6. **Reports honestly what it could not prove.** `manifest-version` and `commit-subject` are
   reported as `skipped` with their reason rather than passed, and the package link is
   recorded as empty, because no registry page can exist for this release.

With the npm plugin off nothing changes in the repository, so release-it creates **no**
release commit — it tags the commit that is already at `HEAD`. That is why
`commit-subject` is skipped for a declared version.

## Running it

```bash
cat > spec.json <<'JSON'
{
  "mode": "release",
  "repo": ".",
  "version": "5.1.7.12_weiyuan_G200464803_20261016_8aef61de",
  "publish": false
}
JSON

python3 scripts/run_pipeline.py --input spec.json --output release-report.json
```

A declared version always runs with `publish: false`, whatever the spec says. To check what
would happen first, add `"dry_run": true` or use `"mode": "plan"` and read the generated
`release-plan.json`: it carries `"version_source": "declared"`, the resolved `tag`, the
`release_it` block with `supports_declared`, and every warning above.

Install the fork once so no `npx` download is needed per release:

```bash
npm install --global github:ez-xu/release-it
```
