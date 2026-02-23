from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import json
import yaml


DEFAULT_EXCLUDES = [
    ".git/",
    "venv/",
    ".venv/",
    "__pycache__/",
    "*.pyc",
    "build/",
    "dist/",
]


@dataclass(slots=True)
class SourceConfig:
    source: Path
    target: Path | None = None
    additional_excludes: list[str] = field(default_factory=list)


@dataclass(slots=True)
class JobConfig:
    name: str
    fallback_target: Path
    sources: list[SourceConfig]
    delete_extraneous: bool = False
    include_git_info_exclude: bool = True
    include_global_git_ignore: bool = False
    create_target_dirs_if_missing: bool = False
    additional_excludes: list[str] = field(default_factory=list)
    follow_symlinks: bool = False
    compare_by: str = "mtime+size"


@dataclass(slots=True)
class AppConfig:
    jobs: list[JobConfig]


def _as_path(value: Any, field_name: str) -> Path:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field_name} must be a non-empty string path")
    return Path(value).expanduser()


def _as_bool(value: Any, field_name: str, default: bool) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    raise ValueError(f"{field_name} must be a boolean")


def _as_list_of_strings(value: Any, field_name: str, default: list[str] | None = None) -> list[str]:
    if value is None:
        return list(default or [])
    if not isinstance(value, list) or any(not isinstance(item, str) for item in value):
        raise ValueError(f"{field_name} must be a list of strings")
    return [item for item in value if item.strip()]


def _load_raw_config(config_path: Path) -> dict[str, Any]:
    if not config_path.exists():
        raise ValueError(f"Config file does not exist: {config_path}")

    suffix = config_path.suffix.lower()
    text = config_path.read_text(encoding="utf-8")
    if suffix in {".yml", ".yaml"}:
        loaded = yaml.safe_load(text)
    elif suffix == ".json":
        loaded = json.loads(text)
    else:
        raise ValueError("Config file must be .yaml/.yml or .json")

    if not isinstance(loaded, dict):
        raise ValueError("Config root must be an object")
    return loaded


def load_config(config_path: Path) -> AppConfig:
    raw = _load_raw_config(config_path)
    raw_jobs = raw.get("jobs")
    if not isinstance(raw_jobs, list) or not raw_jobs:
        raise ValueError("Config must contain non-empty 'jobs' list")

    jobs: list[JobConfig] = []
    names: set[str] = set()

    for index, raw_job in enumerate(raw_jobs):
        if not isinstance(raw_job, dict):
            raise ValueError(f"jobs[{index}] must be an object")

        name = raw_job.get("name")
        if not isinstance(name, str) or not name.strip():
            raise ValueError(f"jobs[{index}].name must be a non-empty string")
        if name in names:
            raise ValueError(f"Duplicate job name: {name}")
        names.add(name)

        fallback_target = _as_path(raw_job.get("fallbackTarget"), f"jobs[{index}].fallbackTarget")

        raw_sources = raw_job.get("sources")
        if not isinstance(raw_sources, list) or not raw_sources:
            raise ValueError(f"jobs[{index}].sources must be a non-empty list")

        job_sources: list[SourceConfig] = []
        for source_idx, raw_source in enumerate(raw_sources):
            if not isinstance(raw_source, dict):
                raise ValueError(f"jobs[{index}].sources[{source_idx}] must be an object")
            source_path = _as_path(
                raw_source.get("source"), f"jobs[{index}].sources[{source_idx}].source"
            )
            raw_target = raw_source.get("target")
            target_path = _as_path(raw_target, f"jobs[{index}].sources[{source_idx}].target") if raw_target else None
            source_excludes = _as_list_of_strings(
                raw_source.get("additionalExcludes"),
                f"jobs[{index}].sources[{source_idx}].additionalExcludes",
                default=[],
            )
            job_sources.append(
                SourceConfig(
                    source=source_path,
                    target=target_path,
                    additional_excludes=source_excludes,
                )
            )

        compare_by = raw_job.get("compareBy", "mtime+size")
        if compare_by not in {"mtime+size", "size", "hash"}:
            raise ValueError(
                f"jobs[{index}].compareBy must be one of: mtime+size, size, hash"
            )

        additional_excludes = _as_list_of_strings(
            raw_job.get("additionalExcludes"), f"jobs[{index}].additionalExcludes", default=DEFAULT_EXCLUDES
        )

        jobs.append(
            JobConfig(
                name=name,
                fallback_target=fallback_target,
                sources=job_sources,
                delete_extraneous=_as_bool(
                    raw_job.get("deleteExtraneous"), f"jobs[{index}].deleteExtraneous", default=False
                ),
                include_git_info_exclude=_as_bool(
                    raw_job.get("includeGitInfoExclude"),
                    f"jobs[{index}].includeGitInfoExclude",
                    default=True,
                ),
                include_global_git_ignore=_as_bool(
                    raw_job.get("includeGlobalGitIgnore"),
                    f"jobs[{index}].includeGlobalGitIgnore",
                    default=False,
                ),
                create_target_dirs_if_missing=_as_bool(
                    raw_job.get("createTargetDirsIfMissing"),
                    f"jobs[{index}].createTargetDirsIfMissing",
                    default=False,
                ),
                additional_excludes=additional_excludes,
                follow_symlinks=_as_bool(
                    raw_job.get("followSymlinks"), f"jobs[{index}].followSymlinks", default=False
                ),
                compare_by=compare_by,
            )
        )

    return AppConfig(jobs=jobs)


def resolve_target_for_source(job: JobConfig, source: SourceConfig) -> Path:
    if source.target is not None:
        return source.target
    source_name = source.source.name
    if not source_name:
        raise ValueError(f"Cannot infer source name for fallback target: {source.source}")
    return job.fallback_target / source_name


def get_job(config: AppConfig, job_name: str | None) -> list[JobConfig]:
    if not job_name:
        return config.jobs
    matched = [job for job in config.jobs if job.name == job_name]
    if not matched:
        raise ValueError(f"No job named '{job_name}' found")
    return matched
