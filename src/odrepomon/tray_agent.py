from __future__ import annotations

import argparse
from collections import deque
from datetime import datetime, timedelta
import logging
from logging.handlers import RotatingFileHandler
import os
from pathlib import Path
import threading
import tkinter as tk
from tkinter import filedialog, messagebox, simpledialog, ttk
import traceback

from PIL import Image, ImageDraw
import pystray

from odrepomon.agent_settings import (
    AgentSettings,
    default_log_file,
    default_state_file,
    save_agent_settings,
    load_agent_settings,
)
from odrepomon.run_service import run_mirror_jobs


class InMemoryLogHandler(logging.Handler):
    def __init__(self, max_lines: int = 400) -> None:
        super().__init__()
        self._lines: deque[str] = deque(maxlen=max_lines)
        self._lock = threading.Lock()

    def emit(self, record: logging.LogRecord) -> None:
        line = self.format(record)
        with self._lock:
            self._lines.append(line)

    def read_lines(self) -> list[str]:
        with self._lock:
            return list(self._lines)


class TrayAgent:
    def __init__(self, config_path: Path, state_file: Path | None = None) -> None:
        self.state_file = state_file or default_state_file()
        self.log_file = default_log_file()
        self.settings = load_agent_settings(self.state_file, default_config_path=config_path)

        self._lock = threading.Lock()
        self._stop_event = threading.Event()
        self._wake_scheduler_event = threading.Event()
        self._run_in_progress = False
        self._last_run_at: datetime | None = None
        self._next_run_at: datetime | None = None

        self.logger = logging.getLogger("odrepomon.agent")
        self.logger.setLevel(logging.INFO)
        self.logger.propagate = False
        self._configure_logging()

        self.icon = pystray.Icon("odrepomon-agent", self._create_icon(), "odRepoMon Agent", self._build_menu())
        self.scheduler_thread = threading.Thread(target=self._scheduler_loop, daemon=True)

        self.ui_root: tk.Tk | None = None
        self.ui_text: tk.Text | None = None
        self.ui_vars: dict[str, tk.Variable] = {}

    def _configure_logging(self) -> None:
        self.log_file.parent.mkdir(parents=True, exist_ok=True)
        for handler in list(self.logger.handlers):
            self.logger.removeHandler(handler)

        formatter = logging.Formatter("%(asctime)s %(levelname)s %(message)s")

        file_handler = RotatingFileHandler(self.log_file, maxBytes=1_000_000, backupCount=3, encoding="utf-8")
        file_handler.setFormatter(formatter)
        self.logger.addHandler(file_handler)

        self.memory_handler = InMemoryLogHandler(max_lines=500)
        self.memory_handler.setFormatter(formatter)
        self.logger.addHandler(self.memory_handler)

    def _create_icon(self) -> Image.Image:
        image = Image.new("RGBA", (64, 64), (28, 28, 30, 255))
        draw = ImageDraw.Draw(image)
        draw.rectangle((8, 8, 56, 56), outline=(120, 180, 255, 255), width=3)
        draw.rectangle((16, 20, 48, 44), fill=(120, 180, 255, 255))
        draw.rectangle((20, 24, 44, 40), fill=(28, 28, 30, 255))
        return image

    def _build_menu(self) -> pystray.Menu:
        return pystray.Menu(
            pystray.MenuItem("Run now", self._menu_run_now),
            pystray.MenuItem(
                lambda _: f"Scheduled run: {'On' if self.settings.schedule_enabled else 'Off'}",
                self._menu_toggle_schedule,
            ),
            pystray.MenuItem(
                lambda _: f"Schedule interval: {self.settings.schedule_minutes} min",
                self._menu_set_schedule_minutes,
            ),
            pystray.MenuItem(
                lambda _: (
                    "Job filter: (all)"
                    if not self.settings.job_filter
                    else f"Job filter: {self.settings.job_filter}"
                ),
                self._menu_set_job_filter,
            ),
            pystray.MenuItem(
                lambda _: (
                    "Source filter: (all)"
                    if not self.settings.source_filter
                    else f"Source filter: {self.settings.source_filter}"
                ),
                self._menu_set_source_filter,
            ),
            pystray.MenuItem(
                lambda _: f"Dry run: {'On' if self.settings.dry_run else 'Off'}",
                self._menu_toggle_dry_run,
            ),
            pystray.MenuItem("Open interface", self._menu_open_ui),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("Open config", self._menu_open_config),
            pystray.MenuItem("Open log", self._menu_open_log),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem(
                lambda _: (
                    "Launch at login (current user): On"
                    if self._startup_script_path().exists()
                    else "Launch at login (current user): Off"
                ),
                self._menu_toggle_startup,
            ),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("Quit", self._menu_quit),
        )

    def run(self) -> None:
        self.logger.info("Agent starting (non-admin user mode)")
        self._recalculate_next_run()
        self.scheduler_thread.start()
        self.icon.run()

    def stop(self) -> None:
        self.logger.info("Agent stopping")
        self._stop_event.set()
        self._wake_scheduler_event.set()
        self.icon.stop()

    def _notify(self, message: str) -> None:
        try:
            self.icon.notify(message, "odRepoMon")
        except Exception:
            self.logger.debug("Tray notification unavailable")

    def _save_settings(self) -> None:
        with self._lock:
            save_agent_settings(self.settings, self.state_file)
            self._recalculate_next_run()
        self.icon.update_menu()

    def _recalculate_next_run(self) -> None:
        if not self.settings.schedule_enabled:
            self._next_run_at = None
            return
        now = datetime.now()
        if self._last_run_at is None:
            self._next_run_at = now + timedelta(minutes=self.settings.schedule_minutes)
            return
        self._next_run_at = self._last_run_at + timedelta(minutes=self.settings.schedule_minutes)
        if self._next_run_at <= now:
            self._next_run_at = now

    def _scheduler_loop(self) -> None:
        while not self._stop_event.is_set():
            with self._lock:
                enabled = self.settings.schedule_enabled
                next_run_at = self._next_run_at

            if not enabled or next_run_at is None:
                self._wake_scheduler_event.wait(1.0)
                self._wake_scheduler_event.clear()
                continue

            delay_seconds = max(0.0, (next_run_at - datetime.now()).total_seconds())
            woke = self._wake_scheduler_event.wait(delay_seconds)
            self._wake_scheduler_event.clear()
            if woke:
                continue

            self._run_now("scheduled")

    def _run_now(self, trigger: str) -> None:
        with self._lock:
            if self._run_in_progress:
                self.logger.warning("Run skipped: another run is in progress")
                self._notify("Run skipped: already running")
                return
            self._run_in_progress = True

        def _worker() -> None:
            try:
                self.logger.info(
                    "Run started (%s): config=%s jobFilter=%s sourceFilter=%s dryRun=%s",
                    trigger,
                    self.settings.config_path,
                    self.settings.job_filter or "(all)",
                    self.settings.source_filter or "(all)",
                    self.settings.dry_run,
                )
                exit_code, summary = run_mirror_jobs(
                    config_path=self.settings.config_path,
                    job_name=self.settings.job_filter,
                    source_filter=self.settings.source_filter,
                    dry_run=self.settings.dry_run,
                    continue_on_error=self.settings.continue_on_error,
                    logger=self.logger,
                )
                self.logger.info(
                    "Run completed: exit=%s sources=%s copied=%s skipped=%s deleted=%s failed=%s",
                    exit_code,
                    summary.processed_sources,
                    summary.copied,
                    summary.skipped,
                    summary.deleted,
                    summary.failed,
                )
                self._notify(
                    f"Run complete: copied={summary.copied}, skipped={summary.skipped}, failed={summary.failed}"
                )
            except Exception:
                self.logger.error("Unhandled error during run:\n%s", traceback.format_exc())
                self._notify("Run failed. See log for details.")
            finally:
                with self._lock:
                    self._run_in_progress = False
                    self._last_run_at = datetime.now()
                    self._recalculate_next_run()

        threading.Thread(target=_worker, daemon=True).start()

    def _menu_run_now(self, icon: pystray.Icon, item: pystray.MenuItem) -> None:
        self._run_now("on-demand")

    def _menu_toggle_schedule(self, icon: pystray.Icon, item: pystray.MenuItem) -> None:
        with self._lock:
            self.settings.schedule_enabled = not self.settings.schedule_enabled
        self._save_settings()
        self._wake_scheduler_event.set()
        self.logger.info("Scheduled run %s", "enabled" if self.settings.schedule_enabled else "disabled")

    def _menu_set_schedule_minutes(self, icon: pystray.Icon, item: pystray.MenuItem) -> None:
        value = simpledialog.askinteger(
            "Schedule interval",
            "Run every N minutes (>=1)",
            minvalue=1,
            initialvalue=self.settings.schedule_minutes,
        )
        if value is None:
            return
        with self._lock:
            self.settings.schedule_minutes = value
        self._save_settings()
        self._wake_scheduler_event.set()
        self.logger.info("Schedule interval updated: %s minute(s)", value)

    def _menu_set_job_filter(self, icon: pystray.Icon, item: pystray.MenuItem) -> None:
        current = self.settings.job_filter or ""
        value = simpledialog.askstring(
            "Job filter",
            "Job name filter (blank = all jobs)",
            initialvalue=current,
        )
        if value is None:
            return
        with self._lock:
            self.settings.job_filter = value.strip() or None
        self._save_settings()
        self.logger.info("Job filter updated: %s", self.settings.job_filter or "(all)")

    def _menu_set_source_filter(self, icon: pystray.Icon, item: pystray.MenuItem) -> None:
        current = self.settings.source_filter or ""
        value = simpledialog.askstring(
            "Source filter",
            "Source filter (folder name or full source path, blank = all)",
            initialvalue=current,
        )
        if value is None:
            return
        with self._lock:
            self.settings.source_filter = value.strip() or None
        self._save_settings()
        self.logger.info("Source filter updated: %s", self.settings.source_filter or "(all)")

    def _menu_toggle_dry_run(self, icon: pystray.Icon, item: pystray.MenuItem) -> None:
        with self._lock:
            self.settings.dry_run = not self.settings.dry_run
        self._save_settings()
        self.logger.info("Dry run %s", "enabled" if self.settings.dry_run else "disabled")

    def _menu_open_ui(self, icon: pystray.Icon, item: pystray.MenuItem) -> None:
        threading.Thread(target=self._open_ui_thread, daemon=True).start()

    def _menu_open_config(self, icon: pystray.Icon, item: pystray.MenuItem) -> None:
        self._open_in_shell(self.settings.config_path)

    def _menu_open_log(self, icon: pystray.Icon, item: pystray.MenuItem) -> None:
        self._open_in_shell(self.log_file)

    def _menu_toggle_startup(self, icon: pystray.Icon, item: pystray.MenuItem) -> None:
        script_path = self._startup_script_path()
        if script_path.exists():
            script_path.unlink(missing_ok=True)
            self.logger.info("Disabled launch-at-login for current user")
        else:
            script_path.parent.mkdir(parents=True, exist_ok=True)
            cmd = self._startup_command()
            script_path.write_text(cmd, encoding="utf-8")
            self.logger.info("Enabled launch-at-login for current user")
        self.icon.update_menu()

    def _menu_quit(self, icon: pystray.Icon, item: pystray.MenuItem) -> None:
        self.stop()

    def _open_in_shell(self, path: Path) -> None:
        try:
            os.startfile(str(path))  # type: ignore[attr-defined]
        except Exception as exc:
            self.logger.error("Failed to open path %s: %s", path, exc)
            self._notify(f"Open failed: {path}")

    def _startup_script_path(self) -> Path:
        appdata = os.environ.get("APPDATA")
        if appdata:
            return (
                Path(appdata)
                / "Microsoft"
                / "Windows"
                / "Start Menu"
                / "Programs"
                / "Startup"
                / "odrepomon-agent.cmd"
            )
        return Path.home() / ".config" / "autostart" / "odrepomon-agent.cmd"

    def _startup_command(self) -> str:
        config_arg = f'--config "{self.settings.config_path}"'
        return f'@echo off\nstart "" odrepomon-agent {config_arg}\n'

    def _open_ui_thread(self) -> None:
        if self.ui_root is not None:
            self.ui_root.after(0, self.ui_root.lift)
            return

        root = tk.Tk()
        root.title("odRepoMon Agent")
        root.geometry("860x600")

        self.ui_root = root
        self._build_ui(root)
        self._refresh_log_view()

        def _on_close() -> None:
            self.ui_root = None
            self.ui_text = None
            self.ui_vars.clear()
            root.destroy()

        root.protocol("WM_DELETE_WINDOW", _on_close)
        root.mainloop()

    def _build_ui(self, root: tk.Tk) -> None:
        frame = ttk.Frame(root, padding=12)
        frame.pack(fill=tk.BOTH, expand=True)

        self.ui_vars["config"] = tk.StringVar(value=str(self.settings.config_path))
        self.ui_vars["schedule_enabled"] = tk.BooleanVar(value=self.settings.schedule_enabled)
        self.ui_vars["schedule_minutes"] = tk.StringVar(value=str(self.settings.schedule_minutes))
        self.ui_vars["job_filter"] = tk.StringVar(value=self.settings.job_filter or "")
        self.ui_vars["source_filter"] = tk.StringVar(value=self.settings.source_filter or "")
        self.ui_vars["dry_run"] = tk.BooleanVar(value=self.settings.dry_run)
        self.ui_vars["continue_on_error"] = tk.BooleanVar(value=self.settings.continue_on_error)

        row = 0
        ttk.Label(frame, text="Config file").grid(row=row, column=0, sticky="w")
        config_entry = ttk.Entry(frame, textvariable=self.ui_vars["config"], width=80)
        config_entry.grid(row=row, column=1, sticky="ew", padx=6)
        ttk.Button(frame, text="Browse", command=self._ui_pick_config).grid(row=row, column=2, sticky="ew")

        row += 1
        ttk.Checkbutton(frame, text="Enable scheduled run", variable=self.ui_vars["schedule_enabled"]).grid(
            row=row, column=0, sticky="w"
        )
        ttk.Label(frame, text="Every minutes").grid(row=row, column=1, sticky="w", padx=6)
        ttk.Entry(frame, textvariable=self.ui_vars["schedule_minutes"], width=8).grid(row=row, column=1, sticky="e")

        row += 1
        ttk.Label(frame, text="Job filter").grid(row=row, column=0, sticky="w")
        ttk.Entry(frame, textvariable=self.ui_vars["job_filter"], width=24).grid(row=row, column=1, sticky="w", padx=6)

        row += 1
        ttk.Label(frame, text="Source filter").grid(row=row, column=0, sticky="w")
        ttk.Entry(frame, textvariable=self.ui_vars["source_filter"], width=40).grid(row=row, column=1, sticky="w", padx=6)

        row += 1
        ttk.Checkbutton(frame, text="Dry run", variable=self.ui_vars["dry_run"]).grid(row=row, column=0, sticky="w")
        ttk.Checkbutton(frame, text="Continue on error", variable=self.ui_vars["continue_on_error"]).grid(
            row=row, column=1, sticky="w", padx=6
        )

        row += 1
        actions = ttk.Frame(frame)
        actions.grid(row=row, column=0, columnspan=3, sticky="ew", pady=(8, 8))
        ttk.Button(actions, text="Save settings", command=self._ui_save_settings).pack(side=tk.LEFT)
        ttk.Button(actions, text="Run now", command=lambda: self._run_now("on-demand"), width=12).pack(side=tk.LEFT, padx=6)
        ttk.Button(actions, text="Open config", command=lambda: self._open_in_shell(self.settings.config_path)).pack(side=tk.LEFT)
        ttk.Button(actions, text="Open log", command=lambda: self._open_in_shell(self.log_file)).pack(side=tk.LEFT, padx=6)

        row += 1
        ttk.Label(frame, text="Logs").grid(row=row, column=0, sticky="w")

        row += 1
        text = tk.Text(frame, wrap="word", height=22)
        text.grid(row=row, column=0, columnspan=3, sticky="nsew")
        scrollbar = ttk.Scrollbar(frame, orient="vertical", command=text.yview)
        scrollbar.grid(row=row, column=3, sticky="ns")
        text.configure(yscrollcommand=scrollbar.set)

        self.ui_text = text
        frame.columnconfigure(1, weight=1)
        frame.rowconfigure(row, weight=1)

    def _ui_pick_config(self) -> None:
        selected = filedialog.askopenfilename(
            title="Select mirror config",
            filetypes=[("YAML", "*.yaml *.yml"), ("JSON", "*.json"), ("All files", "*.*")],
        )
        if selected and "config" in self.ui_vars:
            self.ui_vars["config"].set(selected)

    def _ui_save_settings(self) -> None:
        try:
            config_path = Path(str(self.ui_vars["config"].get())).expanduser()
            schedule_minutes = int(str(self.ui_vars["schedule_minutes"].get()).strip())
            if schedule_minutes < 1:
                raise ValueError("Schedule minutes must be >= 1")

            with self._lock:
                self.settings = AgentSettings(
                    config_path=config_path,
                    schedule_enabled=bool(self.ui_vars["schedule_enabled"].get()),
                    schedule_minutes=schedule_minutes,
                    job_filter=str(self.ui_vars["job_filter"].get()).strip() or None,
                    source_filter=str(self.ui_vars["source_filter"].get()).strip() or None,
                    dry_run=bool(self.ui_vars["dry_run"].get()),
                    continue_on_error=bool(self.ui_vars["continue_on_error"].get()),
                ).normalized()

            self._save_settings()
            self._wake_scheduler_event.set()
            self.logger.info("Settings updated from interface")
            messagebox.showinfo("odRepoMon", "Settings saved")
        except Exception as exc:
            messagebox.showerror("odRepoMon", f"Failed to save settings: {exc}")

    def _refresh_log_view(self) -> None:
        if self.ui_root is None or self.ui_text is None:
            return

        lines = self.memory_handler.read_lines()
        content = "\n".join(lines[-300:])
        self.ui_text.delete("1.0", tk.END)
        self.ui_text.insert(tk.END, content)
        self.ui_text.see(tk.END)
        self.ui_root.after(2000, self._refresh_log_view)


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(prog="odrepomon-agent", description="odRepoMon task tray agent")
    parser.add_argument("--config", type=Path, default=Path.cwd() / "mirror-config.yaml")
    parser.add_argument("--state-file", type=Path, default=None)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    agent = TrayAgent(config_path=args.config, state_file=args.state_file)
    agent.run()
    return 0
