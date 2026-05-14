# styles.py

MAIN_WINDOW_STYLE = """
QMainWindow {
    background-color: #f4f5f7;
}

QMenuBar {
    background-color: #ffffff;
    border-bottom: 1px solid #d9dde3;
}

QWidget#mainContent {
    background-color: #f4f5f7;
}

QWidget#sectionHeader {
    margin-top: 4px;
}

QLabel#sectionTitle {
    color: #20242a;
    font-size: 18px;
    font-weight: 700;
}

QLabel#sectionSubtitle {
    color: #66707c;
    font-size: 12px;
}

QWidget#buildTargetGroup {
    background-color: transparent;
}

QWidget#buildTargetGroupHeader {
    background-color: #e8edf3;
    border: 1px solid #cfd6df;
    border-radius: 6px;
}

QWidget#buildTargetBuildList {
    background-color: transparent;
    border-left: 3px solid #cfd6df;
}

QLabel#groupTitle {
    color: #20242a;
    font-size: 14px;
    font-weight: 700;
}

QLabel#groupMeta {
    color: #66707c;
    font-size: 12px;
}

QFrame#mainPanel,
QWidget#buildCard {
    background-color: #ffffff;
    border: 1px solid #d9dde3;
    border-radius: 6px;
}

QWidget#buildRow {
    background-color: #ffffff;
    border: 1px solid #cfd6df;
    border-radius: 0;
}

QLabel#primaryText {
    color: #20242a;
    font-size: 13px;
    font-weight: 700;
}

QLabel#secondaryText {
    color: #59636f;
    font-size: 12px;
}

QLabel#fieldLabel {
    color: #59636f;
    font-size: 12px;
}

QLabel#emptyState {
    color: #66707c;
    font-size: 13px;
    padding: 28px;
}

QLineEdit,
QComboBox {
    background-color: #ffffff;
    border: 1px solid #c7cdd6;
    border-radius: 4px;
    color: #20242a;
    min-height: 24px;
    padding: 2px 8px;
}

QLineEdit:focus,
QComboBox:focus {
    border-color: #3a6ea5;
}

QPushButton {
    background-color: #ffffff;
    border: 1px solid #b8c0ca;
    border-radius: 4px;
    color: #20242a;
    min-height: 24px;
    padding: 3px 10px;
}

QPushButton:hover {
    background-color: #f0f3f7;
    border-color: #9da8b5;
}

QPushButton:pressed {
    background-color: #e3e8ef;
}

QPushButton:disabled {
    background-color: #eef0f3;
    border-color: #d3d8df;
    color: #8a939e;
}

QPushButton#primaryButton {
    background-color: #236192;
    border-color: #236192;
    color: #ffffff;
    font-weight: 700;
}

QPushButton#primaryButton:hover {
    background-color: #1d527d;
}

QPushButton#ghostButton {
    background-color: transparent;
}

QPushButton#dangerButton {
    color: #9f1d20;
}

QPushButton#dangerButton:hover {
    background-color: #fff1f1;
    border-color: #c84d4f;
}

QScrollArea {
    background-color: transparent;
    border: 0;
}

QScrollArea > QWidget > QWidget {
    background-color: transparent;
}
"""
