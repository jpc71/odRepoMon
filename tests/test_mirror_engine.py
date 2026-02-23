from pathlib import Path

from odrepomon.config import JobConfig, SourceConfig
from odrepomon.mirror_engine import MirrorRunOptions, mirror_source


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def test_mirror_source_honors_gitignore_and_dry_run(tmp_path: Path) -> None:
    source = tmp_path / "repo"
    destination = tmp_path / "dest"

    _write(source / ".gitignore", "ignored.log\nsubdir/ignored.txt\n")
    _write(source / "keep.txt", "hello")
    _write(source / "ignored.log", "skip")
    _write(source / "subdir" / "kept.txt", "ok")
    _write(source / "subdir" / "ignored.txt", "skip")

    job = JobConfig(
        name="job",
        fallback_target=tmp_path / "fallback",
        sources=[SourceConfig(source=source, target=destination)],
        include_global_git_ignore=False,
        include_git_info_exclude=False,
    )

    stats = mirror_source(job, job.sources[0], MirrorRunOptions(dry_run=True))

    assert stats.copied == 3
    assert stats.skipped == 2
    assert not (destination / "keep.txt").exists()


def test_mirror_source_copies_expected_files(tmp_path: Path) -> None:
    source = tmp_path / "repo"
    destination = tmp_path / "dest"

    _write(source / ".gitignore", "*.tmp\n")
    _write(source / "app.py", "print('ok')")
    _write(source / "notes.tmp", "ignore")
    _write(source / ".git" / "HEAD", "ref: refs/heads/main")

    job = JobConfig(
        name="job",
        fallback_target=tmp_path / "fallback",
        sources=[SourceConfig(source=source, target=destination)],
        include_global_git_ignore=False,
        include_git_info_exclude=False,
    )

    stats = mirror_source(job, job.sources[0], MirrorRunOptions(dry_run=False))

    assert stats.copied == 2
    assert (destination / "app.py").exists()
    assert (destination / ".gitignore").exists()
    assert not (destination / "notes.tmp").exists()
    assert not (destination / ".git" / "HEAD").exists()


def test_source_directory_with_multiple_repos_is_mirrored(tmp_path: Path) -> None:
    source_work = tmp_path / "work"
    target_work = tmp_path / "onedrive-work"

    _write(source_work / "repoA" / ".gitignore", "build/\n")
    _write(source_work / "repoA" / "README.md", "A")
    _write(source_work / "repoA" / "build" / "artifact.bin", "ignore")
    _write(source_work / "repoB" / "main.py", "print('B')")

    job = JobConfig(
        name="work-repos",
        fallback_target=tmp_path / "fallback",
        sources=[SourceConfig(source=source_work, target=target_work)],
        include_global_git_ignore=False,
        include_git_info_exclude=False,
    )

    stats = mirror_source(job, job.sources[0], MirrorRunOptions(dry_run=False))

    assert stats.copied == 3
    assert (target_work / "repoA" / "README.md").exists()
    assert not (target_work / "repoA" / "build" / "artifact.bin").exists()
    assert (target_work / "repoB" / "main.py").exists()


def test_create_target_dirs_if_missing_creates_empty_target_root(tmp_path: Path) -> None:
    source = tmp_path / "empty-repo"
    source.mkdir(parents=True, exist_ok=True)
    destination = tmp_path / "new-target-root"

    job = JobConfig(
        name="job",
        fallback_target=tmp_path / "fallback",
        sources=[SourceConfig(source=source, target=destination)],
        include_global_git_ignore=False,
        include_git_info_exclude=False,
        create_target_dirs_if_missing=True,
    )

    stats = mirror_source(job, job.sources[0], MirrorRunOptions(dry_run=False))

    assert stats.copied == 0
    assert destination.exists()
    assert destination.is_dir()


def test_without_create_target_dirs_if_missing_empty_target_root_is_not_created(tmp_path: Path) -> None:
    source = tmp_path / "empty-repo"
    source.mkdir(parents=True, exist_ok=True)
    destination = tmp_path / "new-target-root"

    job = JobConfig(
        name="job",
        fallback_target=tmp_path / "fallback",
        sources=[SourceConfig(source=source, target=destination)],
        include_global_git_ignore=False,
        include_git_info_exclude=False,
        create_target_dirs_if_missing=False,
    )

    stats = mirror_source(job, job.sources[0], MirrorRunOptions(dry_run=False))

    assert stats.copied == 0
    assert not destination.exists()
