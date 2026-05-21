from __future__ import annotations

from typing import Iterable

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QIcon
from PyQt6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from build_bridge.core.publisher.upload_spec import UploadSpec
from build_bridge.utils.paths import get_resource_path
from build_bridge.views.dialogs.publish_dialog import PaneState, UploadPane


class PublishRunDialog(QWidget):
    """Top-level window that runs N publishes in parallel, one UploadPane each.

    Not a QDialog — this is a real window so the main app stays usable while
    uploads run.
    """

    closed = pyqtSignal(object)  # emits self

    def __init__(self, specs: Iterable[UploadSpec], title: str | None = None):
        super().__init__(None)  # top-level, no parent
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose, True)
        self.setWindowFlag(Qt.WindowType.Window, True)

        self.specs = list(specs)
        if not self.specs:
            raise ValueError("PublishRunDialog requires at least one UploadSpec.")

        if title is None:
            stores = ", ".join(s.store.value for s in self.specs)
            title = f"Publishing — {stores}"
        self.setWindowTitle(title)
        self.setWindowIcon(QIcon(str(get_resource_path("build_bridge/icons/buildbridge.ico"))))
        self.resize(820, 240 * min(len(self.specs), 3))
        self.setMinimumSize(700, 360)

        self.panes: list[UploadPane] = []
        self._setup_ui()

        for pane in self.panes:
            pane.finished.connect(self._on_pane_finished)
            pane.state_changed.connect(self._refresh_aggregate_status)

        # Defer start so the window paints first.
        for pane in self.panes:
            pane.start()
        self._refresh_aggregate_status()

    # ------------------------------------------------------------------ UI

    def _setup_ui(self):
        outer = QVBoxLayout(self)
        outer.setContentsMargins(14, 14, 14, 14)
        outer.setSpacing(10)

        for spec in self.specs:
            pane = UploadPane(spec, parent=self)
            self.panes.append(pane)
            outer.addWidget(pane)

        outer.addStretch(0)

        footer = QHBoxLayout()
        footer.setSpacing(8)

        self.aggregate_label = QLabel("")
        self.aggregate_label.setObjectName("secondaryText")
        self.aggregate_label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        footer.addWidget(self.aggregate_label, 1)

        self.cancel_all_button = QPushButton("Cancel All")
        self.cancel_all_button.setObjectName("dangerButton")
        self.cancel_all_button.clicked.connect(self._cancel_all)
        footer.addWidget(self.cancel_all_button)

        self.close_button = QPushButton("Close")
        self.close_button.setObjectName("primaryButton")
        self.close_button.clicked.connect(self.close)
        self.close_button.setEnabled(False)
        footer.addWidget(self.close_button)

        outer.addLayout(footer)

    # -------------------------------------------------------- lifecycle

    def has_active_panes(self) -> bool:
        return any(not pane.is_terminal() for pane in self.panes)

    def _cancel_all(self):
        for pane in self.panes:
            if not pane.is_terminal():
                pane.cancel()

    def _on_pane_finished(self, _success: bool):
        self._refresh_aggregate_status()

    def _refresh_aggregate_status(self):
        total = len(self.panes)
        done = sum(1 for p in self.panes if p.is_terminal())
        succeeded = sum(1 for p in self.panes if p.state == PaneState.SUCCESS)
        failed = sum(1 for p in self.panes if p.state == PaneState.FAILED)
        cancelled = sum(1 for p in self.panes if p.state == PaneState.CANCELLED)
        waiting_2fa = [p for p in self.panes if p.state == PaneState.WAITING_2FA]

        parts = [f"{done}/{total} done"]
        if succeeded:
            parts.append(f"{succeeded} ok")
        if failed:
            parts.append(f"{failed} failed")
        if cancelled:
            parts.append(f"{cancelled} cancelled")
        if waiting_2fa:
            parts.append(
                "Steam waiting on phone"
                if any(p.spec.store.value == "Steam" for p in waiting_2fa)
                else "waiting"
            )
        self.aggregate_label.setText(" · ".join(parts))

        all_terminal = done == total
        self.close_button.setEnabled(all_terminal)
        self.cancel_all_button.setEnabled(not all_terminal)

    # --------------------------------------------------------- close hook

    def closeEvent(self, event):
        if self.has_active_panes():
            reply = QMessageBox.question(
                self,
                "Uploads still running",
                "One or more uploads are still running. Cancel them and close?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            if reply != QMessageBox.StandardButton.Yes:
                event.ignore()
                return
            self._cancel_all()

        for pane in self.panes:
            pane.shutdown()

        self.closed.emit(self)
        super().closeEvent(event)
