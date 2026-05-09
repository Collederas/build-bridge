from PyQt6.QtCore import Qt
from PyQt6.QtGui import QIcon
from PyQt6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QVBoxLayout,
)

from build_bridge.core.preflight import PreflightResult
from build_bridge.utils.paths import get_resource_path


class PreflightDialog(QDialog):
    def __init__(self, result: PreflightResult, parent=None):
        super().__init__(parent)
        self.result = result
        self.setWindowTitle(result.title)
        self.setMinimumSize(620, 420)
        self.setWindowIcon(QIcon(str(get_resource_path("build_bridge/icons/buildbridge.ico"))))
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)

        if self.result.has_blockers:
            summary = "Fix the blocking checks below before continuing."
        elif self.result.has_warnings:
            summary = "Review the warnings below before continuing."
        else:
            summary = "Everything needed for this action looks ready."

        summary_label = QLabel(summary)
        summary_label.setWordWrap(True)
        summary_label.setStyleSheet("font-weight: bold;")
        layout.addWidget(summary_label)

        checks_list = QListWidget()
        checks_list.setAlternatingRowColors(True)
        checks_list.setWordWrap(True)
        checks_list.setUniformItemSizes(False)

        for issue in self.result.issues:
            item = QListWidgetItem(self._format_issue(issue))
            item.setToolTip(issue.detail)
            item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsSelectable)
            if issue.severity == "error":
                item.setForeground(Qt.GlobalColor.red)
            elif issue.severity == "warning":
                item.setForeground(Qt.GlobalColor.darkYellow)
            else:
                item.setForeground(Qt.GlobalColor.darkGreen)
            checks_list.addItem(item)

        layout.addWidget(checks_list, 1)

        button_box = QDialogButtonBox()
        if self.result.has_blockers:
            close_button = button_box.addButton(QDialogButtonBox.StandardButton.Close)
            close_button.clicked.connect(self.reject)
        else:
            continue_button = button_box.addButton(
                "Continue", QDialogButtonBox.ButtonRole.AcceptRole
            )
            cancel_button = button_box.addButton(QDialogButtonBox.StandardButton.Cancel)
            continue_button.clicked.connect(self.accept)
            cancel_button.clicked.connect(self.reject)

        layout.addWidget(button_box)

    def _format_issue(self, issue):
        prefix = {"ok": "PASS", "warning": "WARN", "error": "FAIL"}.get(
            issue.severity, "INFO"
        )
        if issue.detail:
            return f"{prefix}: {issue.label}\n{issue.detail}"
        return f"{prefix}: {issue.label}"
