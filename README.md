# odRepoMon - Git Repository Monitor for OneDrive

[![Packaging](https://github.com/jpc71/odRepoMon/actions/workflows/packaging.yml/badge.svg)](https://github.com/jpc71/odRepoMon/actions/workflows/packaging.yml)

**odRepoMon** is a gitignore-aware backup utility that mirrors your active Git repositories to cloud storage locations like OneDrive. It intelligently copies only the files that matter—respecting `.gitignore` rules to exclude build artifacts, dependencies, caches, and other generated content that should not be backed up.

The project is designed to be easy to run day-to-day: install it in user space (no admin required), launch from the Start Menu, and manage it from a Windows tray icon. From that tray menu, you can run a sync on demand, open settings, toggle scheduled sync behavior, and jump directly to config or log files without needing to remember command-line flags.

When you need more control, the built-in settings window provides a straightforward interface for schedule options, filters, dry-run mode, and live log visibility. Configure multiple source directories and destinations once, then let odRepoMon run quietly in the background while keeping your cloud backup lean and focused on source code rather than folders like `node_modules`, `.venv`, build outputs, or IDE metadata.

It works well for developers who want reliable, selective backups with minimal maintenance: preview changes with dry-run, click Run now when needed, or leave scheduled sync enabled and let it operate automatically.

## License

This project is licensed under **GNU GPL v3 or later** (`GPL-3.0-or-later`).
See [LICENSE](LICENSE) for the full text.

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

This installs two commands:

- `mirror` (CLI)
- `odrepomon-agent` (Windows task tray agent)

No admin permissions are required. The agent runs in user mode, stores state/log files under your user profile (`~/.odrepomon`), and uses an internal timer for scheduling.

## Windows Easy Install (non-dev users)

Use the bundled installer (no admin required):

1. Double-click [scripts/windows/install-user.cmd](scripts/windows/install-user.cmd)
2. It installs into `%LOCALAPPDATA%/odRepoMon` (user-space only)
3. It creates a Start Menu shortcut: `odRepoMon Agent`

Optional logon task (starts agent automatically when you login):

```powershell
scripts\windows\install-user.cmd -EnableStartup
```

This creates a user-level scheduled task (no admin required) that runs at logon.

Reinstall/refresh existing user install without prompt:

```powershell
scripts\windows\install-user.cmd -Force
```

After install, start the tray agent by either:

- Start Menu shortcut `odRepoMon Agent`
- [scripts/windows/launch-agent.cmd](scripts/windows/launch-agent.cmd)

Uninstall (no admin required):

- Double-click [scripts/windows/uninstall-user.cmd](scripts/windows/uninstall-user.cmd)
- Or run `scripts\windows\uninstall-user.cmd`
- Silent uninstall (no prompt): `scripts\windows\uninstall-user.cmd -Force`

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
- `mirror agent --config mirror-config.yaml`

## Task Tray Agent (Windows)

For everyday use, the tray agent is the easiest way to run odRepoMon. Start it once, then manage syncing from the system tray without keeping a terminal open.

Start it from your normal user shell:

```powershell
odrepomon-agent --config mirror-config.yaml
```

Or launch it from the Start Menu shortcut created by the installer (`odRepoMon Agent`).

Common tray menu actions:

- Run now (on-demand)
- Open settings
- Toggle scheduled run
- Dry-run toggle
- Open config and log files
- Toggle launch-at-login for current user (no admin)
- Quit

The settings window (opened from tray) includes:

- Editable configuration path
- Schedule interval and run options
- Job/source filters
- Live run log output

`--source` selects one configured source within each selected job. You can pass either the full source path or a unique folder name (for example, `work`).

`mirror validate-config` now prints a per-job summary including source count, fallback target, and `createTargetDirsIfMissing`.

`mirror list` prints each job with the `createTargetDirsIfMissing` state and the resolved source-to-target mapping (`explicit` or `fallback`).

If `--source` matches multiple entries by folder name in the same job, command output returns a partial failure and asks for full source path.

## Exit codes

- `0` success
- `1` runtime/config error
- `2` partial failures
- `3` invalid config
