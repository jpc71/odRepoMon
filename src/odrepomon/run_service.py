from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import logging

from odrepomon.config import JobConfig, SourceConfig, get_job, load_config, resolve_target_for_source
from odrepomon.mirror_engine import MirrorRunOptions, mirror_source
from odrepomon.models import MirrorStats


EXIT_SUCCESS = 0
EXIT_RUNTIME_OR_CONFIG_ERROR = 1
EXIT_PARTIAL_FAILURES = 2
EXIT_INVALID_CONFIG = 3


@dataclass(slots=True)
class RunSummary:
    copied: int = 0
    skipped: int = 0
    failed: int = 0
    deleted: int = 0
    processed_sources: int = 0
    partial_failures: bool = False

    def absorb(self, stats: MirrorStats) -> None:
        self.copied += stats.copied
        self.skipped += stats.skipped
        self.failed += stats.failed
        self.deleted += stats.deleted
        self.processed_sources += 1
        if stats.failed:
            self.partial_failures = True


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


def run_mirror_jobs(
    config_path: Path,
    job_name: str | None = None,
    source_filter: str | None = None,
    dry_run: bool = False,
    continue_on_error: bool = True,
    logger: logging.Logger | None = None,
) -> tuple[int, RunSummary]:
    log = logger or logging.getLogger("odrepomon.run")

    try:
        config = load_config(config_path)
        jobs = get_job(config, job_name)
    except Exception as exc:
        log.error("Config/runtime error: %s", exc)
        return EXIT_INVALID_CONFIG, RunSummary(partial_failures=True)

    summary = RunSummary()
    options = MirrorRunOptions(dry_run=dry_run, continue_on_error=continue_on_error)

    for job in jobs:
        selected_sources, error_message = _select_sources(job, source_filter)
        if error_message:
            log.error("%s", error_message)
            summary.partial_failures = True
            continue

        for source_cfg in selected_sources:
            target = resolve_target_for_source(job, source_cfg)
            try:
                stats = mirror_source(job, source_cfg, options)
                summary.absorb(stats)
                log.info(
                    "[%s] %s -> %s | copied=%s skipped=%s deleted=%s failed=%s",
                    job.name,
                    source_cfg.source,
                    target,
                    stats.copied,
                    stats.skipped,
                    stats.deleted,
                    stats.failed,
                )
            except Exception as exc:
                summary.partial_failures = True
                log.error("[%s] failed for source %s: %s", job.name, source_cfg.source, exc)
                if not continue_on_error:
                    return EXIT_RUNTIME_OR_CONFIG_ERROR, summary

    exit_code = EXIT_PARTIAL_FAILURES if summary.partial_failures else EXIT_SUCCESS
    return exit_code, summary