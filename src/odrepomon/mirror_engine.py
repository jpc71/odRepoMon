from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import os
from pathlib import Path
import shutil
import tempfile

from odrepomon.config import JobConfig, SourceConfig, resolve_target_for_source
from odrepomon.ignore_engine import build_ignore_engine
from odrepomon.models import MirrorStats


@dataclass(slots=True)
class MirrorRunOptions:
    dry_run: bool = False
    continue_on_error: bool = True



def _hash_file(path: Path) -> str:
    digest = sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _should_copy(source_file: Path, destination_file: Path, compare_by: str) -> bool:
    if not destination_file.exists():
        return True

    source_stat = source_file.stat()
    destination_stat = destination_file.stat()

    if compare_by == "size":
        return source_stat.st_size != destination_stat.st_size

    if compare_by == "hash":
        if source_stat.st_size != destination_stat.st_size:
            return True
        return _hash_file(source_file) != _hash_file(destination_file)

    mtime_changed = int(source_stat.st_mtime) != int(destination_stat.st_mtime)
    size_changed = source_stat.st_size != destination_stat.st_size
    return mtime_changed or size_changed


def _safe_copy(source_file: Path, destination_file: Path) -> None:
    destination_file.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(delete=False, dir=str(destination_file.parent)) as tmp:
        tmp_path = Path(tmp.name)
    try:
        shutil.copy2(source_file, tmp_path)
        tmp_path.replace(destination_file)
    finally:
        if tmp_path.exists():
            tmp_path.unlink(missing_ok=True)


def _validate_paths(source_root: Path, destination_root: Path) -> None:
    source_resolved = source_root.resolve()
    destination_resolved = destination_root.resolve()

    if source_resolved == destination_resolved:
        raise ValueError(f"Invalid mapping: source and destination are equal: {source_root}")

    if str(destination_resolved).startswith(str(source_resolved)):
        raise ValueError(
            f"Invalid mapping: destination is inside source, which can recurse: {destination_root}"
        )


def mirror_source(job: JobConfig, source_cfg: SourceConfig, options: MirrorRunOptions) -> MirrorStats:
    source_root = source_cfg.source
    destination_root = resolve_target_for_source(job, source_cfg)

    _validate_paths(source_root, destination_root)

    if not source_root.exists() or not source_root.is_dir():
        raise ValueError(f"Source directory does not exist or is not a directory: {source_root}")

    if job.create_target_dirs_if_missing and not options.dry_run:
        destination_root.mkdir(parents=True, exist_ok=True)

    ignore_engine = build_ignore_engine(job, source_cfg)
    stats = MirrorStats()
    mirrored_relative_files: set[Path] = set()

    for root_str, dirs, files in os.walk(source_root, topdown=True, followlinks=job.follow_symlinks):
        root = Path(root_str)
        root_rel = root.relative_to(source_root)

        kept_dirs: list[str] = []
        for dir_name in dirs:
            rel_path = root_rel / dir_name
            if ignore_engine.is_ignored(rel_path, is_dir=True):
                continue
            kept_dirs.append(dir_name)
        dirs[:] = kept_dirs

        for file_name in files:
            rel_path = root_rel / file_name
            if ignore_engine.is_ignored(rel_path):
                stats.skipped += 1
                continue

            source_file = source_root / rel_path
            destination_file = destination_root / rel_path
            mirrored_relative_files.add(rel_path)

            try:
                should_copy = _should_copy(source_file, destination_file, compare_by=job.compare_by)
                if not should_copy:
                    stats.skipped += 1
                    continue

                if not options.dry_run:
                    _safe_copy(source_file, destination_file)
                stats.copied += 1
            except Exception:
                stats.failed += 1
                if not options.continue_on_error:
                    raise

    if job.delete_extraneous and destination_root.exists():
        for root_str, _, files in os.walk(destination_root, topdown=True):
            root = Path(root_str)
            root_rel = root.relative_to(destination_root)
            for file_name in files:
                rel_path = root_rel / file_name
                if rel_path in mirrored_relative_files:
                    continue
                target_file = destination_root / rel_path
                if options.dry_run:
                    stats.deleted += 1
                    continue
                try:
                    target_file.unlink(missing_ok=True)
                    stats.deleted += 1
                except Exception:
                    stats.failed += 1
                    if not options.continue_on_error:
                        raise

    return stats
