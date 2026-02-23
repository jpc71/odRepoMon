from pathlib import Path

from odrepomon.run_service import EXIT_PARTIAL_FAILURES, EXIT_SUCCESS, run_mirror_jobs


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def test_run_service_runs_job_successfully(tmp_path: Path) -> None:
    src = tmp_path / "repo"
    target = tmp_path / "target"
    _write(src / "a.txt", "1")

    config_file = tmp_path / "cfg.yaml"
    config_file.write_text(
        f"""
jobs:
  - name: j
    fallbackTarget: {str(tmp_path / 'fallback').replace('\\', '/')}
    includeGlobalGitIgnore: false
    includeGitInfoExclude: false
    sources:
      - source: {str(src).replace('\\', '/')}
        target: {str(target).replace('\\', '/')}
""".strip(),
        encoding="utf-8",
    )

    exit_code, summary = run_mirror_jobs(config_path=config_file)

    assert exit_code == EXIT_SUCCESS
    assert summary.processed_sources == 1
    assert summary.copied == 1
    assert summary.failed == 0


def test_run_service_source_filter_missing_returns_partial(tmp_path: Path) -> None:
    src = tmp_path / "repo"
    _write(src / "a.txt", "1")

    config_file = tmp_path / "cfg.yaml"
    config_file.write_text(
        f"""
jobs:
  - name: j
    fallbackTarget: {str(tmp_path / 'fallback').replace('\\', '/')}
    includeGlobalGitIgnore: false
    includeGitInfoExclude: false
    sources:
      - source: {str(src).replace('\\', '/')}
""".strip(),
        encoding="utf-8",
    )

    exit_code, summary = run_mirror_jobs(config_path=config_file, source_filter="missing")

    assert exit_code == EXIT_PARTIAL_FAILURES
    assert summary.processed_sources == 0
    assert summary.partial_failures is True