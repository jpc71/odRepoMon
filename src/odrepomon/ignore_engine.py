from __future__ import annotations

from pathlib import Path
from typing import Iterable

import pathspec

from odrepomon.config import JobConfig, SourceConfig


def _read_ignore_lines(path: Path) -> list[str]:
    try:
        return path.read_text(encoding="utf-8").splitlines()
    except FileNotFoundError:
        return []
    except OSError:
        return []


def _prefix_pattern(prefix: str, pattern: str) -> str:
    if not pattern or pattern.startswith("#"):
        return pattern

    negate = pattern.startswith("!")
    core = pattern[1:] if negate else pattern

    if core.startswith("/"):
        mapped = f"{prefix}{core}" if prefix else core
    else:
        mapped = f"{prefix}/{core}" if prefix else core

    return f"!{mapped}" if negate else mapped


def _collect_nested_gitignore_patterns(source_root: Path) -> list[str]:
    patterns: list[str] = []
    for gitignore in source_root.rglob(".gitignore"):
        if ".git" in gitignore.parts:
            continue
        rel_parent = gitignore.parent.relative_to(source_root)
        rel_prefix = rel_parent.as_posix().strip(".")
        for line in _read_ignore_lines(gitignore):
            stripped = line.strip()
            if not stripped:
                continue
            patterns.append(_prefix_pattern(rel_prefix, line))
    return patterns


def _global_git_ignore_path() -> Path | None:
    candidate_files = [
        Path.home() / ".config" / "git" / "ignore",
        Path.home() / ".gitignore_global",
    ]
    for candidate in candidate_files:
        if candidate.exists():
            return candidate
    return None


class IgnoreEngine:
    def __init__(self, patterns: Iterable[str]) -> None:
        self._spec = pathspec.PathSpec.from_lines("gitignore", patterns)

    def is_ignored(self, relative_path: Path, is_dir: bool = False) -> bool:
        unix_path = relative_path.as_posix()
        candidate = f"{unix_path}/" if is_dir and not unix_path.endswith("/") else unix_path
        return self._spec.match_file(candidate)



def build_ignore_engine(job: JobConfig, source_cfg: SourceConfig) -> IgnoreEngine:
    source_root = source_cfg.source

    patterns: list[str] = []
    patterns.extend(job.additional_excludes)
    patterns.extend(source_cfg.additional_excludes)

    patterns.extend(_collect_nested_gitignore_patterns(source_root))

    if job.include_git_info_exclude:
        patterns.extend(_read_ignore_lines(source_root / ".git" / "info" / "exclude"))

    if job.include_global_git_ignore:
        global_ignore = _global_git_ignore_path()
        if global_ignore:
            patterns.extend(_read_ignore_lines(global_ignore))

    patterns.append(".git/")

    return IgnoreEngine(patterns)
