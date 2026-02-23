# odRepoMon

Gitignore-aware one-way mirror utility (source -> destination), designed for backing up active repositories into OneDrive-friendly locations.

## Features

- Multiple source directories per job
- Explicit target per source OR fallback target per job
- `.gitignore`-aware filtering (root + nested)
- Optional `.git/info/exclude` and optional global git ignore support
- Dry-run mode
- Optional delete-extraneous mode
- Optional target-directory pre-creation mode
- Source filtering by full path or unique folder name

## Install

From the project root:

```powershell
pip install -e .
```

## Quick Start

```powershell
mirror validate-config --config mirror-config.yaml
mirror list --config mirror-config.yaml --job work-repos --source work
mirror run --config mirror-config.yaml --job work-repos --source work --dry-run
# optional real run (writes files)
mirror run --config mirror-config.yaml --job work-repos --source work
```

## Config

See `mirror-config.yaml` for a working example.

### Key behavior

- Each job has a `fallbackTarget`.
- Each job can set `createTargetDirsIfMissing: true` to pre-create resolved target roots.
- Each source can define `target`.
- If a source omits `target`, destination becomes:
  - `<fallbackTarget>/<source-folder-name>`

### Config keys

Job-level keys:

- `name` (required)
- `fallbackTarget` (required)
- `sources` (required, non-empty list)
- `createTargetDirsIfMissing` (optional, default `false`)
- `deleteExtraneous` (optional, default `false`)
- `includeGitInfoExclude` (optional, default `true`)
- `includeGlobalGitIgnore` (optional, default `false`)
- `followSymlinks` (optional, default `false`)
- `compareBy` (optional, one of `mtime+size`, `size`, `hash`; default `mtime+size`)
- `additionalExcludes` (optional list of patterns)

Source-level keys:

- `source` (required)
- `target` (optional)
- `additionalExcludes` (optional list of patterns)

## CLI

- `mirror validate-config --config mirror-config.yaml`
- `mirror list --config mirror-config.yaml`
- `mirror list --config mirror-config.yaml --job work-repos --source work`
- `mirror run --config mirror-config.yaml --dry-run`
- `mirror run --config mirror-config.yaml --job work-repos`
- `mirror run --config mirror-config.yaml --job work-repos --source work --dry-run`

`--source` selects one configured source within each selected job. You can pass either the full source path or a unique folder name (for example, `work`).

`mirror validate-config` now prints a per-job summary including source count, fallback target, and `createTargetDirsIfMissing`.

`mirror list` prints each job with the `createTargetDirsIfMissing` state and the resolved source-to-target mapping (`explicit` or `fallback`).

If `--source` matches multiple entries by folder name in the same job, command output returns a partial failure and asks for full source path.

## Exit codes

- `0` success
- `1` runtime/config error
- `2` partial failures
- `3` invalid config
