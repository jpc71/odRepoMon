from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any
import json


@dataclass(slots=True)
class AgentSettings:
    config_path: Path
    schedule_enabled: bool = False
    schedule_minutes: int = 30
    job_filter: str | None = None
    source_filter: str | None = None
    dry_run: bool = False
    continue_on_error: bool = True

    def normalized(self) -> "AgentSettings":
        job_filter = self.job_filter.strip() if self.job_filter else None
        source_filter = self.source_filter.strip() if self.source_filter else None
        schedule_minutes = max(1, int(self.schedule_minutes))
        return AgentSettings(
            config_path=self.config_path,
            schedule_enabled=bool(self.schedule_enabled),
            schedule_minutes=schedule_minutes,
            job_filter=job_filter or None,
            source_filter=source_filter or None,
            dry_run=bool(self.dry_run),
            continue_on_error=bool(self.continue_on_error),
        )


def default_state_dir() -> Path:
    return Path.home() / ".odrepomon"


def default_state_file() -> Path:
    return default_state_dir() / "agent-state.json"


def default_log_file() -> Path:
    return default_state_dir() / "agent.log"


def save_agent_settings(settings: AgentSettings, state_file: Path) -> None:
    normalized = settings.normalized()
    state_file.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "configPath": str(normalized.config_path),
        "scheduleEnabled": normalized.schedule_enabled,
        "scheduleMinutes": normalized.schedule_minutes,
        "jobFilter": normalized.job_filter,
        "sourceFilter": normalized.source_filter,
        "dryRun": normalized.dry_run,
        "continueOnError": normalized.continue_on_error,
    }
    state_file.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _as_bool(value: Any, default: bool) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    return default


def _as_int(value: Any, default: int) -> int:
    if value is None:
        return default
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _as_optional_str(value: Any) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        return None
    stripped = value.strip()
    return stripped or None


def load_agent_settings(state_file: Path, default_config_path: Path) -> AgentSettings:
    if not state_file.exists():
        return AgentSettings(config_path=default_config_path).normalized()

    text = state_file.read_text(encoding="utf-8")
    raw = json.loads(text)
    if not isinstance(raw, dict):
        raise ValueError("Agent settings file must be a JSON object")

    loaded = AgentSettings(
        config_path=Path(raw.get("configPath") or default_config_path),
        schedule_enabled=_as_bool(raw.get("scheduleEnabled"), default=False),
        schedule_minutes=_as_int(raw.get("scheduleMinutes"), default=30),
        job_filter=_as_optional_str(raw.get("jobFilter")),
        source_filter=_as_optional_str(raw.get("sourceFilter")),
        dry_run=_as_bool(raw.get("dryRun"), default=False),
        continue_on_error=_as_bool(raw.get("continueOnError"), default=True),
    )
    return loaded.normalized()