from __future__ import annotations

import argparse
import importlib
from pathlib import Path
import sys

from odrepomon.config import JobConfig, SourceConfig, get_job, load_config, resolve_target_for_source
from odrepomon.mirror_engine import MirrorRunOptions, mirror_source
from odrepomon.models import MirrorStats


EXIT_SUCCESS = 0
EXIT_RUNTIME_OR_CONFIG_ERROR = 1
EXIT_PARTIAL_FAILURES = 2
EXIT_INVALID_CONFIG = 3


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="mirror", description="Gitignore-aware one-way mirror")
    subparsers = parser.add_subparsers(dest="command", required=True)

    run_parser = subparsers.add_parser("run", help="Run mirror jobs")
    run_parser.add_argument("--config", required=True, type=Path)
    run_parser.add_argument("--job", help="Run only one job by name")
    run_parser.add_argument(
        "--source",
        help="Run only one configured source (full path or unique folder name)",
    )
    run_parser.add_argument("--dry-run", action="store_true")
    run_parser.add_argument("--continue-on-error", action="store_true", default=True)

    validate_parser = subparsers.add_parser("validate-config", help="Validate config")
    validate_parser.add_argument("--config", required=True, type=Path)

    list_parser = subparsers.add_parser("list", help="List jobs and source target mappings")
    list_parser.add_argument("--config", required=True, type=Path)
    list_parser.add_argument("--job", help="List only one job by name")
    list_parser.add_argument(
        "--source",
        help="List only one configured source (full path or unique folder name)",
    )

    agent_parser = subparsers.add_parser("agent", help="Start the task tray agent")
    agent_parser.add_argument("--config", type=Path, default=Path.cwd() / "mirror-config.yaml")
    agent_parser.add_argument("--state-file", type=Path, default=None)

    return parser


def _print_stats(job_name: str, source: Path, target: Path, stats: MirrorStats) -> None:
    print(
        f"[{job_name}] {source} -> {target} | copied={stats.copied} skipped={stats.skipped} "
        f"deleted={stats.deleted} failed={stats.failed}"
    )


def _select_sources(
    job: JobConfig,
    source_filter: str | None,
) -> tuple[list[SourceConfig], str | None]:
    if not source_filter:
        return job.sources, None

    exact = [source_cfg for source_cfg in job.sources if str(source_cfg.source) == source_filter]
    if exact:
        return exact, None

    by_name = [source_cfg for source_cfg in job.sources if source_cfg.source.name == source_filter]
    if len(by_name) > 1:
        return [], f"[{job.name}] source filter '{source_filter}' is ambiguous; use full source path"
    if len(by_name) == 1:
        return by_name, None

    return [], f"[{job.name}] no source matched filter '{source_filter}'"


def cmd_validate(config_path: Path) -> int:
    try:
        config = load_config(config_path)
    except Exception as exc:
        print(f"Invalid config: {exc}", file=sys.stderr)
        return EXIT_INVALID_CONFIG

    print(f"Valid config: {config_path} ({len(config.jobs)} job(s))")
    for job in config.jobs:
        print(
            f"  - job={job.name} "
            f"sources={len(job.sources)} "
            f"fallbackTarget={job.fallback_target} "
            f"createTargetDirsIfMissing={str(job.create_target_dirs_if_missing).lower()}"
        )
    return EXIT_SUCCESS


def cmd_list(config_path: Path, job_name: str | None, source_filter: str | None) -> int:
    try:
        config = load_config(config_path)
        jobs = get_job(config, job_name)
    except Exception as exc:
        print(f"Invalid config: {exc}", file=sys.stderr)
        return EXIT_INVALID_CONFIG

    partial_failures = False

    for job in jobs:
        selected_sources, error_message = _select_sources(job, source_filter)
        if error_message:
            print(error_message, file=sys.stderr)
            partial_failures = True
            continue

        print(
            f"job: {job.name} "
            f"(createTargetDirsIfMissing={str(job.create_target_dirs_if_missing).lower()})"
        )
        for source_cfg in selected_sources:
            resolved_target = resolve_target_for_source(job, source_cfg)
            marker = "explicit" if source_cfg.target else "fallback"
            print(f"  - {source_cfg.source} -> {resolved_target} ({marker})")
    return EXIT_PARTIAL_FAILURES if partial_failures else EXIT_SUCCESS


def cmd_run(
    config_path: Path,
    job_name: str | None,
    source_filter: str | None,
    dry_run: bool,
    continue_on_error: bool,
) -> int:
    try:
        config = load_config(config_path)
        jobs = get_job(config, job_name)
    except Exception as exc:
        print(f"Config/runtime error: {exc}", file=sys.stderr)
        return EXIT_RUNTIME_OR_CONFIG_ERROR

    partial_failures = False
    options = MirrorRunOptions(dry_run=dry_run, continue_on_error=continue_on_error)

    for job in jobs:
        selected_sources, error_message = _select_sources(job, source_filter)
        if error_message:
            print(error_message, file=sys.stderr)
            partial_failures = True
            continue

        for source_cfg in selected_sources:
            target = resolve_target_for_source(job, source_cfg)
            try:
                stats = mirror_source(job, source_cfg, options)
                _print_stats(job.name, source_cfg.source, target, stats)
                if stats.failed:
                    partial_failures = True
            except Exception as exc:
                print(
                    f"[{job.name}] failed for source {source_cfg.source}: {exc}",
                    file=sys.stderr,
                )
                partial_failures = True
                if not continue_on_error:
                    return EXIT_RUNTIME_OR_CONFIG_ERROR

    return EXIT_PARTIAL_FAILURES if partial_failures else EXIT_SUCCESS


def cmd_agent(config_path: Path, state_file: Path | None) -> int:
    try:
        tray_agent = importlib.import_module("odrepomon.tray_agent")
    except ModuleNotFoundError as exc:
        missing = exc.name or "unknown"
        print(
            (
                f"Failed to load tray agent dependency: {missing}. "
                "Reinstall dependencies in your active environment with: pip install -e ."
            ),
            file=sys.stderr,
        )
        return EXIT_RUNTIME_OR_CONFIG_ERROR
    except Exception as exc:
        print(f"Failed to load tray agent: {exc}", file=sys.stderr)
        return EXIT_RUNTIME_OR_CONFIG_ERROR

    argv = ["--config", str(config_path)]
    if state_file is not None:
        argv.extend(["--state-file", str(state_file)])
    return int(tray_agent.main(argv))


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)

    if args.command == "validate-config":
        return cmd_validate(args.config)
    if args.command == "list":
        return cmd_list(
            config_path=args.config,
            job_name=args.job,
            source_filter=args.source,
        )
    if args.command == "run":
        return cmd_run(
            config_path=args.config,
            job_name=args.job,
            source_filter=args.source,
            dry_run=args.dry_run,
            continue_on_error=args.continue_on_error,
        )
    if args.command == "agent":
        return cmd_agent(
            config_path=args.config,
            state_file=args.state_file,
        )

    parser.print_help()
    return EXIT_RUNTIME_OR_CONFIG_ERROR


if __name__ == "__main__":
    raise SystemExit(main())
