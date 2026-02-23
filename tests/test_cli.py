from pathlib import Path

from odrepomon.cli import EXIT_PARTIAL_FAILURES, EXIT_SUCCESS, main


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def test_run_source_filter_by_folder_name_runs_single_source(tmp_path: Path, capsys) -> None:
    src_one = tmp_path / "repo-one"
    src_work = tmp_path / "work"
    _write(src_one / "a.txt", "1")
    _write(src_work / "b.txt", "2")

    config_file = tmp_path / "cfg.yaml"
    config_file.write_text(
        f"""
jobs:
  - name: j
    fallbackTarget: {str(tmp_path / 'fallback').replace('\\', '/')}
    includeGlobalGitIgnore: false
    includeGitInfoExclude: false
    sources:
      - source: {str(src_one).replace('\\', '/')}
      - source: {str(src_work).replace('\\', '/')}
""".strip(),
        encoding="utf-8",
    )

    exit_code = main([
        "run",
        "--config",
        str(config_file),
        "--source",
        "work",
        "--dry-run",
    ])

    output = capsys.readouterr().out
    assert exit_code == EXIT_SUCCESS
    assert str(src_work) in output
    assert str(src_one) not in output


def test_run_source_filter_missing_returns_partial_failure(tmp_path: Path, capsys) -> None:
    src_one = tmp_path / "repo-one"
    _write(src_one / "a.txt", "1")

    config_file = tmp_path / "cfg.yaml"
    config_file.write_text(
        f"""
jobs:
  - name: j
    fallbackTarget: {str(tmp_path / 'fallback').replace('\\', '/')}
    includeGlobalGitIgnore: false
    includeGitInfoExclude: false
    sources:
      - source: {str(src_one).replace('\\', '/')}
""".strip(),
        encoding="utf-8",
    )

    exit_code = main([
        "run",
        "--config",
        str(config_file),
        "--source",
        "work",
        "--dry-run",
    ])

    err = capsys.readouterr().err
    assert exit_code == EXIT_PARTIAL_FAILURES
    assert "no source matched filter 'work'" in err


def test_list_source_filter_by_folder_name_lists_single_source(tmp_path: Path, capsys) -> None:
    src_one = tmp_path / "repo-one"
    src_work = tmp_path / "work"
    _write(src_one / "a.txt", "1")
    _write(src_work / "b.txt", "2")

    config_file = tmp_path / "cfg.yaml"
    config_file.write_text(
        f"""
jobs:
  - name: j
    fallbackTarget: {str(tmp_path / 'fallback').replace('\\', '/')}
    sources:
      - source: {str(src_one).replace('\\', '/')}
      - source: {str(src_work).replace('\\', '/')}
""".strip(),
        encoding="utf-8",
    )

    exit_code = main([
        "list",
        "--config",
        str(config_file),
        "--source",
        "work",
    ])

    output = capsys.readouterr().out
    assert exit_code == EXIT_SUCCESS
    assert "createTargetDirsIfMissing=false" in output
    assert str(src_work) in output
    assert str(src_one) not in output


def test_list_source_filter_missing_returns_partial_failure(tmp_path: Path, capsys) -> None:
    src_one = tmp_path / "repo-one"
    _write(src_one / "a.txt", "1")

    config_file = tmp_path / "cfg.yaml"
    config_file.write_text(
        f"""
jobs:
  - name: j
    fallbackTarget: {str(tmp_path / 'fallback').replace('\\', '/')}
    sources:
      - source: {str(src_one).replace('\\', '/')}
""".strip(),
        encoding="utf-8",
    )

    exit_code = main([
        "list",
        "--config",
        str(config_file),
        "--source",
        "work",
    ])

    err = capsys.readouterr().err
    assert exit_code == EXIT_PARTIAL_FAILURES
    assert "no source matched filter 'work'" in err


def test_validate_config_prints_job_summary(tmp_path: Path, capsys) -> None:
    src_one = tmp_path / "repo-one"
    _write(src_one / "a.txt", "1")

    config_file = tmp_path / "cfg.yaml"
    config_file.write_text(
        f"""
jobs:
  - name: j
    fallbackTarget: {str(tmp_path / 'fallback').replace('\\', '/')}
    createTargetDirsIfMissing: true
    sources:
      - source: {str(src_one).replace('\\', '/')}
""".strip(),
        encoding="utf-8",
    )

    exit_code = main([
        "validate-config",
        "--config",
        str(config_file),
    ])

    output = capsys.readouterr().out
    assert exit_code == EXIT_SUCCESS
    assert "job=j" in output
    assert "sources=1" in output
    assert "createTargetDirsIfMissing=true" in output
