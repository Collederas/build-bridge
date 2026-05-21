from __future__ import annotations

import logging
import os
import signal
import subprocess
import sys
import webbrowser
from enum import Enum
from pathlib import Path
from typing import Dict, Iterable

from PyQt6.QtCore import QProcess, QProcessEnvironment, QTimer, pyqtSignal
from PyQt6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from build_bridge.core.publisher.upload_spec import UploadSpec
from build_bridge.models import StoreEnum


_STEAM_2FA_MARKERS = (
    "two-factor",
    "steam guard",
    "mobile authenticator",
    "please confirm",
)
_STEAM_LOGIN_OK_MARKER = "to steam public...ok"
_WAITING_2FA_AFTER_SECONDS = 4


class PaneState(Enum):
    PENDING = "Pending"
    RUNNING = "Running"
    WAITING_2FA = "Confirm on phone"
    SUCCESS = "Success"
    FAILED = "Failed"
    CANCELLED = "Cancelled"


_TERMINAL_STATES = {PaneState.SUCCESS, PaneState.FAILED, PaneState.CANCELLED}


def _kill_process_tree(pid: int) -> None:
    """Force-kill a process and all of its descendants.

    QProcess.terminate() is a no-op for console apps on Windows (they have no
    message loop to receive WM_CLOSE), and QProcess.kill() only kills the
    immediate process. steamcmd bootstraps child processes, and butler can spawn
    helpers — killing the parent alone leaves them running and the upload
    continues. taskkill /T walks the tree.
    """
    if pid <= 0:
        return
    try:
        if sys.platform == "win32":
            CREATE_NO_WINDOW = 0x08000000
            subprocess.run(
                ["taskkill", "/F", "/T", "/PID", str(pid)],
                creationflags=CREATE_NO_WINDOW,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                timeout=5,
            )
        else:
            # Don't killpg: QProcess doesn't put children in their own group,
            # so getpgid(pid) returns our own group and we'd SIGKILL ourselves.
            try:
                os.kill(pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
    except Exception as exc:
        logging.info(f"Failed to kill process tree for pid {pid}: {exc}")


class UploadPane(QWidget):
    """One pane = one publish to one store. Owns its QProcess. Non-modal."""

    finished = pyqtSignal(bool)
    state_changed = pyqtSignal()

    def __init__(self, spec: UploadSpec, parent: QWidget | None = None):
        super().__init__(parent)
        self.spec = spec
        self._state = PaneState.PENDING
        self._log_buffer: str = ""
        self._tailed_log_positions: Dict[Path, int] = {}
        self._announced_log_files: set[Path] = set()
        self._login_seen = False

        self.process: QProcess | None = None

        self._log_tail_timer = QTimer(self)
        self._log_tail_timer.setInterval(500)
        self._log_tail_timer.timeout.connect(self._poll_tailed_logs)

        self._2fa_timer = QTimer(self)
        self._2fa_timer.setSingleShot(True)
        self._2fa_timer.timeout.connect(self._maybe_flip_to_waiting_2fa)

        self._setup_ui()

    # ------------------------------------------------------------------ UI

    def _setup_ui(self):
        self.setObjectName("uploadPane")
        outer = QVBoxLayout(self)
        outer.setContentsMargins(8, 8, 8, 8)
        outer.setSpacing(6)

        header = QHBoxLayout()
        header.setSpacing(8)

        self.title_label = QLabel(self.spec.title)
        font = self.title_label.font()
        font.setBold(True)
        self.title_label.setFont(font)
        header.addWidget(self.title_label, 1)

        self.status_label = QLabel(self._state.value)
        self.status_label.setObjectName("paneStatusBadge")
        header.addWidget(self.status_label)

        self.cancel_button = QPushButton("Cancel")
        self.cancel_button.setObjectName("ghostButton")
        self.cancel_button.clicked.connect(self.cancel)
        self.cancel_button.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        header.addWidget(self.cancel_button)

        outer.addLayout(header)

        info_lines = [f"{k}: {v}" for k, v in self.spec.display_info.items()]
        if info_lines:
            info_label = QLabel("   ".join(info_lines))
            info_label.setObjectName("secondaryText")
            info_label.setWordWrap(True)
            outer.addWidget(info_label)

        self.log_display = QTextEdit()
        self.log_display.setReadOnly(True)
        self.log_display.setLineWrapMode(QTextEdit.LineWrapMode.NoWrap)
        self.log_display.setFontFamily("monospace")
        self.log_display.setMinimumHeight(180)
        outer.addWidget(self.log_display, 1)

        self.actions_row = QHBoxLayout()
        self.actions_row.setSpacing(6)
        self.actions_row.addStretch(1)

        self.open_folder_button = QPushButton("Open build folder")
        self.open_folder_button.setObjectName("ghostButton")
        self.open_folder_button.clicked.connect(self._open_build_folder)
        self.open_folder_button.setVisible(False)
        self.actions_row.addWidget(self.open_folder_button)

        self.open_store_button = QPushButton("Open store page")
        self.open_store_button.setObjectName("ghostButton")
        self.open_store_button.clicked.connect(self._open_store_page)
        self.open_store_button.setVisible(False)
        self.actions_row.addWidget(self.open_store_button)

        outer.addLayout(self.actions_row)

    # --------------------------------------------------------------- state

    @property
    def state(self) -> PaneState:
        return self._state

    def is_terminal(self) -> bool:
        return self._state in _TERMINAL_STATES

    def _set_state(self, new_state: PaneState):
        if new_state == self._state:
            return
        self._state = new_state
        self.status_label.setText(new_state.value)
        self.status_label.setProperty("paneState", new_state.name.lower())
        self.status_label.style().unpolish(self.status_label)
        self.status_label.style().polish(self.status_label)

        if self.is_terminal():
            self.cancel_button.setVisible(False)
            self._show_post_actions(success=new_state == PaneState.SUCCESS)

        self.state_changed.emit()

    def _show_post_actions(self, success: bool):
        if success and self.spec.build_folder:
            self.open_folder_button.setVisible(True)
        if success and self.spec.store_page_url:
            self.open_store_button.setVisible(True)

    # --------------------------------------------------------------- start

    def start(self):
        if self._state != PaneState.PENDING:
            return

        self._append("Starting...")
        self._append(f"Executable: {self.spec.executable}")
        self._append("-" * 20)

        if self.spec.pre_run is not None:
            try:
                self.spec.pre_run()
            except Exception as exc:
                self._append(f"[pre-run error] {exc}")
                self._set_state(PaneState.FAILED)
                self.finished.emit(False)
                return

        if not self.spec.executable or not Path(self.spec.executable).exists():
            self._append(
                f"[error] Executable not found: '{self.spec.executable}'."
            )
            self._set_state(PaneState.FAILED)
            self.finished.emit(False)
            return

        self.process = QProcess(self)
        env = QProcessEnvironment.systemEnvironment()
        if self.spec.environment:
            for k, v in self.spec.environment.items():
                env.insert(k, v)
        self.process.setProcessEnvironment(env)
        self.process.setProcessChannelMode(QProcess.ProcessChannelMode.MergedChannels)
        self.process.readyReadStandardOutput.connect(self._read_stdout)
        self.process.finished.connect(self._handle_finished)
        self.process.errorOccurred.connect(self._handle_error)

        if self.spec.working_directory:
            self.process.setWorkingDirectory(self.spec.working_directory)

        self._initialize_tailed_logs()
        self.process.start(str(self.spec.executable), self.spec.arguments)

        if not self.process.waitForStarted(5000):
            self._append(f"[error] Process failed to start: {self.process.errorString()}")
            self._set_state(PaneState.FAILED)
            self.finished.emit(False)
            return

        self._set_state(PaneState.RUNNING)
        if self.spec.log_files or self.spec.log_directories:
            self._log_tail_timer.start()
        if self.spec.store == StoreEnum.steam:
            self._2fa_timer.start(_WAITING_2FA_AFTER_SECONDS * 1000)

    # ---------------------------------------------------------- cancellation

    def cancel(self):
        if self.is_terminal():
            return
        if self.process is None or self.process.state() == QProcess.ProcessState.NotRunning:
            self._set_state(PaneState.CANCELLED)
            self.finished.emit(False)
            return

        self._append("-" * 20)
        self._append("Cancelling...")
        # Mark cancelled before tearing the process down, so _handle_finished
        # (which may fire synchronously from kill/waitForFinished) takes the
        # cancelled branch instead of running success_checker against a partial
        # log.
        self._set_state(PaneState.CANCELLED)

        pid = int(self.process.processId())
        _kill_process_tree(pid)
        # Reap QProcess's own bookkeeping so finished() fires and the handle
        # is cleaned up.
        self.process.kill()
        self.process.waitForFinished(2000)

    # --------------------------------------------------------------- output

    def _read_stdout(self):
        if not self.process:
            return
        data = self.process.readAllStandardOutput().data()
        try:
            output = data.decode("utf-8", errors="replace")
        except UnicodeDecodeError:
            output = data.decode("latin-1", errors="replace")
        if not output:
            return

        self._log_buffer += output
        self._append(output.rstrip())

        if self.spec.store == StoreEnum.steam:
            self._maybe_update_steam_state(output.lower())

    def _maybe_update_steam_state(self, lower_chunk: str):
        if _STEAM_LOGIN_OK_MARKER in lower_chunk or _STEAM_LOGIN_OK_MARKER in self._log_buffer.lower():
            if not self._login_seen:
                self._login_seen = True
                self._2fa_timer.stop()
                if self._state == PaneState.WAITING_2FA:
                    self._set_state(PaneState.RUNNING)
            return

        if any(marker in lower_chunk for marker in _STEAM_2FA_MARKERS):
            if self._state == PaneState.RUNNING:
                self._set_state(PaneState.WAITING_2FA)

    def _maybe_flip_to_waiting_2fa(self):
        if self._state == PaneState.RUNNING and not self._login_seen:
            self._set_state(PaneState.WAITING_2FA)

    def _append(self, text: str):
        self.log_display.append(text)
        scrollbar = self.log_display.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())

    # ---------------------------------------------------------- log tailing

    def _initialize_tailed_logs(self):
        for path in self._iter_log_paths():
            if path.exists() and path.is_file():
                self._tailed_log_positions[path] = path.stat().st_size

    def _iter_log_paths(self) -> Iterable[Path]:
        seen: set[Path] = set()
        for p in self.spec.log_files:
            resolved = Path(p).resolve()
            if resolved not in seen:
                seen.add(resolved)
                yield resolved
        for d in self.spec.log_directories:
            directory = Path(d)
            if not directory.exists() or not directory.is_dir():
                continue
            for path in directory.glob("*.log"):
                if path.is_file():
                    resolved = path.resolve()
                    if resolved not in seen:
                        seen.add(resolved)
                        yield resolved

    def _poll_tailed_logs(self):
        for path in self._iter_log_paths():
            try:
                current_size = path.stat().st_size
                previous = self._tailed_log_positions.get(path, 0)
                if current_size < previous:
                    previous = 0
                if current_size <= previous:
                    self._tailed_log_positions[path] = previous
                    continue

                with path.open("rb") as f:
                    f.seek(previous)
                    data = f.read()

                self._tailed_log_positions[path] = current_size
                output = data.decode("utf-8", errors="replace")
                if not output:
                    continue

                if path not in self._announced_log_files:
                    self._append(f"[Log file] {path}")
                    self._announced_log_files.add(path)

                self._log_buffer += output
                self._append(output.rstrip())
            except OSError as e:
                logging.info(f"Could not tail log file '{path}': {e}")

    # ---------------------------------------------------------- termination

    def _handle_finished(self, exit_code: int, exit_status: QProcess.ExitStatus):
        if self.process is None:
            return

        self._log_tail_timer.stop()
        self._2fa_timer.stop()
        self._poll_tailed_logs()

        if self._state == PaneState.CANCELLED:
            self.finished.emit(False)
            return

        status_str = (
            "Normal Exit"
            if exit_status == QProcess.ExitStatus.NormalExit
            else "Crash Exit"
        )
        self._append("-" * 20)
        self._append(f"Process finished. Exit Code: {exit_code}, Status: {status_str}")

        try:
            success = self.spec.success_checker(exit_code, self._log_buffer)
        except Exception as exc:
            self._append(f"[error] Success check raised: {exc}")
            success = False

        if success:
            self._append("Operation reported as SUCCESSFUL.")
            self._set_state(PaneState.SUCCESS)
            if self.spec.on_success is not None:
                try:
                    self.spec.on_success()
                except Exception as exc:
                    logging.info(f"on_success hook failed: {exc}")
        else:
            self._append("Operation reported as FAILED or incomplete.")
            self._set_state(PaneState.FAILED)

        self.finished.emit(success)

    def _handle_error(self, error: QProcess.ProcessError):
        self._append(f"[process error] {error}")
        if not self.is_terminal():
            self._set_state(PaneState.FAILED)
            self.finished.emit(False)

    # -------------------------------------------------------- post-success

    def _open_build_folder(self):
        folder = self.spec.build_folder
        if not folder or not os.path.isdir(folder):
            return
        try:
            if os.name == "nt":
                os.startfile(folder)  # type: ignore[attr-defined]
            else:
                subprocess.Popen(["open", folder])
        except Exception as exc:
            logging.info(f"Could not open folder '{folder}': {exc}")

    def _open_store_page(self):
        if self.spec.store_page_url:
            webbrowser.open(self.spec.store_page_url)

    # -------------------------------------------------------------- cleanup

    def shutdown(self):
        self._log_tail_timer.stop()
        self._2fa_timer.stop()
        if self.process and self.process.state() != QProcess.ProcessState.NotRunning:
            try:
                self.process.readyReadStandardOutput.disconnect()
            except TypeError:
                pass
            pid = int(self.process.processId())
            _kill_process_tree(pid)
            self.process.kill()
            self.process.waitForFinished(1500)
        self.process = None
