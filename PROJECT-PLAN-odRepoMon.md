# Project Plan: Gitignore-Aware Mirror to OneDrive

## 1) Feasibility Summary

This is feasible and practical.

A mirror tool that copies from a non-OneDrive workspace into a OneDrive destination, while honoring `.gitignore`, avoids OneDrive policy limitations around folder-level exclusions (such as `.git` and `venv`).

Recommended approach:

- Keep active repos outside OneDrive.
- Mirror only selected content into OneDrive on demand or on schedule.
- Use Git ignore file and semantics (not OneDrive policy semantics) as source-of-truth filtering.

## 2) Goals

- Mirror project files to OneDrive with deterministic exclusion behavior.
- Honor `.gitignore` rules (root and nested), plus optional extra excludes.
- Preserve relative paths and timestamps where useful.
- Provide dry-run output and clear logs.
- Support one-way sync (source -> destination), not bidirectional sync.

## 3) Non-Goals (MVP)

- No real-time kernel-level file watcher as a first version.
- No two-way conflict resolution.
- No cloud API integration (use local filesystem destination under OneDrive root).
- No source-control operations (commit/push/pull).

## 4) High-Level Architecture

### Components

1. Config Loader

- Reads YAML/JSON config with one or more mirror jobs.

2. File Enumerator

- Walks source tree.
- Resolves include candidates and metadata.

3. Ignore Engine

- Uses Git-compatible matching to decide keep/skip.
- Supports `.gitignore`, `.git/info/exclude`, optional global excludes.

4. Mirror Engine

- Copies changed/new files.
- Optionally deletes destination files not present in source mirror set.
- Supports safe writes (temp file then rename).

5. Reporter

- Console summary and optional JSON log output.

### Data Flow

Source scan -> ignore decisions -> copy plan -> execute plan -> summary report

## 5) Technology Recommendation

Preferred stack: Python CLI

Why:

- Fast to build cross-platform CLI.
- Strong ecosystem for path handling and testing.
- Easy packaging and task scheduler integration on Windows.

Key libraries:

- `pathspec` for `.gitignore` pattern semantics.
- `typer` or `argparse` for CLI.
- `rich` optional for readable output.

Alternative:

- Go for a single static binary if distribution simplicity becomes priority.

## 6) Proposed Configuration

Example `mirror-config.yaml`:

```yaml
jobs:
  - name: docs-backup
    source: C:/Dev/Projects/OneDriveIgnore
    destination: C:/Users/USERNAME/OneDrive/Backups/OneDriveIgnore
    deleteExtraneous: false
    includeGitInfoExclude: true
    includeGlobalGitIgnore: true
    additionalExcludes:
      - "*.log"
      - "tmp/**"
    followSymlinks: false
```

## 7) CLI Contract (MVP)

- `mirror run --config mirror-config.yaml [--job name] [--dry-run]`
- `mirror validate-config --config mirror-config.yaml`
- `mirror list --config mirror-config.yaml`

Exit codes:

- `0` success
- `1` runtime/config error
- `2` partial copy failures
- `3` invalid config

## 8) Ignore Semantics (Critical)

Rule precedence:

1. Job-level `additionalExcludes`
2. `.gitignore` files from source root and subdirectories
3. `.git/info/exclude` (optional)
4. Global Git ignore file (optional)

Behavior requirements:

- Match Git behavior as closely as practical.
- Never mirror `.git` directory by default.
- Exclude typical environment/build artifacts by default if not already ignored.

## 9) Copy Strategy

For each candidate file:

- Skip if excluded.
- Copy if destination missing.
- Copy if size/hash/mtime indicates change.
- Preserve relative path.
- Ensure destination directory exists.

Optional modes:

- `--compare-by mtime|size|hash` (default `mtime+size` for speed)
- `--delete-extraneous` to prune destination files not in source mirror set

## 10) Reliability, Safety, and Performance

Safety:

- Hard block if destination is inside source to avoid recursion.
- Hard block if source and destination are equal.
- Dry-run first recommendation for every new job.

Reliability:

- Retry transient file errors (small bounded retry).
- Continue-on-error mode with summary of failed files.

Performance:

- Parallel copy workers for large trees.
- Optional content hashing only when needed.

## 11) Windows Operations Plan

Scheduling options:

- Windows Task Scheduler every N minutes.
- On logon trigger.
- Manual run before shutdown.

Suggested task command:

- `python -m repomirror run --config C:\Path\mirror-config.yaml`

Log paths:

- `%LOCALAPPDATA%\RepoMirror\logs\YYYY-MM-DD.log`

## 12) Security and Compliance Considerations

- Do not mirror secrets unless explicitly intended.
- Optional deny-list for sensitive file patterns:
  - `.env`
  - `*.pem`
  - `*.key`
  - `secrets.*`
- Optionally redact or skip large binary artifacts.

## 13) Testing Strategy

Unit tests:

- Ignore matching edge cases.
- Path normalization on Windows separators.
- Config validation and defaults.

Integration tests:

- Fixture repo with nested `.gitignore` files.
- Verify expected copied and excluded file sets.
- Verify dry-run output and delete mode behavior.

Manual tests:

- Large repo (>50k files) baseline runtime.
- Locked file behavior.
- Long path handling.

## 14) MVP Milestones

Milestone 1: Project skeleton

- CLI scaffolding
- Config parsing and validation

Milestone 2: Ignore engine

- `.gitignore` support with fixtures
- Exclusion report

Milestone 3: Mirror engine

- Copy changed files
- Dry-run mode

Milestone 4: Operational hardening

- Logging
- Exit codes
- Error handling and retries

Milestone 5: Windows scheduling docs

- Task Scheduler setup guide

## 15) Backlog After MVP

- File-system watcher mode.
- Optional compression/encryption stage before mirror.
- Multiple destination targets.
- Differential snapshot reports.
- GUI wrapper for non-CLI users.

## 16) Acceptance Criteria

- A sample repo containing `.git`, `venv`, and build artifacts mirrors without copying excluded content.
- Dry-run and real run produce consistent decisions.
- Re-running with no source changes yields near-zero copy operations.
- Logs clearly show copied/skipped/failed counts.

## 17) Suggested Next Step to Start the New Project

1. Initialize a new repo, for example: `RepoMirror`.
2. Build MVP with Python + `pathspec`.
3. Add fixture-based tests before implementing delete mode.
4. Pilot with one real project for 1 week, then expand to more jobs.
