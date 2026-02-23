from pathlib import Path

from odrepomon.agent_settings import AgentSettings, load_agent_settings, save_agent_settings


def test_agent_settings_round_trip(tmp_path: Path) -> None:
    state_file = tmp_path / "agent-state.json"
    expected = AgentSettings(
        config_path=tmp_path / "mirror-config.yaml",
        schedule_enabled=True,
        schedule_minutes=15,
        job_filter="work-repos",
        source_filter="work",
        dry_run=True,
        continue_on_error=False,
    )

    save_agent_settings(expected, state_file)
    loaded = load_agent_settings(state_file, default_config_path=tmp_path / "fallback.yaml")

    assert loaded.config_path == expected.config_path
    assert loaded.schedule_enabled is True
    assert loaded.schedule_minutes == 15
    assert loaded.job_filter == "work-repos"
    assert loaded.source_filter == "work"
    assert loaded.dry_run is True
    assert loaded.continue_on_error is False


def test_agent_settings_defaults_when_file_missing(tmp_path: Path) -> None:
    state_file = tmp_path / "missing.json"
    default_config = tmp_path / "mirror-config.yaml"

    loaded = load_agent_settings(state_file, default_config_path=default_config)

    assert loaded.config_path == default_config
    assert loaded.schedule_enabled is False
    assert loaded.schedule_minutes == 30
    assert loaded.job_filter is None
    assert loaded.source_filter is None