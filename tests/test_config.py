from pathlib import Path

from odrepomon.config import JobConfig, SourceConfig, load_config, resolve_target_for_source


def test_resolve_target_for_source_uses_explicit_target() -> None:
    source = SourceConfig(source=Path("C:/src/repo"), target=Path("C:/dest/custom"))
    job = JobConfig(name="j", fallback_target=Path("C:/dest/fallback"), sources=[source])

    resolved = resolve_target_for_source(job, source)

    assert resolved == Path("C:/dest/custom")


def test_resolve_target_for_source_uses_fallback_plus_source_name() -> None:
    source = SourceConfig(source=Path("C:/src/repo-two"))
    job = JobConfig(name="j", fallback_target=Path("C:/dest/fallback"), sources=[source])

    resolved = resolve_target_for_source(job, source)

    assert resolved == Path("C:/dest/fallback/repo-two")


def test_load_config_supports_multiple_sources_and_optional_targets(tmp_path: Path) -> None:
    config_file = tmp_path / "mirror-config.yaml"
    config_file.write_text(
        """
jobs:
  - name: work-repos
    fallbackTarget: C:/Users/jerem/OneDrive/Backups/Repos
    createTargetDirsIfMissing: true
    sources:
      - source: C:/Dev/Projects/repo-one
        target: C:/Users/jerem/OneDrive/Backups/Special/repo-one
      - source: C:/Dev/Projects/repo-two
      - source: C:/Users/jerem/Repos/work
        target: C:/Users/jerem/OneDrive/odRepoMir/work
""".strip(),
        encoding="utf-8",
    )

    loaded = load_config(config_file)

    assert len(loaded.jobs) == 1
    job = loaded.jobs[0]
    assert job.name == "work-repos"
    assert len(job.sources) == 3
    assert job.create_target_dirs_if_missing is True
    assert job.sources[0].target == Path("C:/Users/jerem/OneDrive/Backups/Special/repo-one")
    assert job.sources[1].target is None
    assert job.sources[2].source == Path("C:/Users/jerem/Repos/work")
