# styles.py

# Style for PublishProfileEntry widget (card-like appearance, squared)
ENTRY_STYLE = """
QWidget {
    background-color: #f9f9f9;
    border: 1px solid #d3d3d3;
    padding: 5px;
}
"""

# Style for the build label
BUILD_LABEL_STYLE = """
QLabel {
    font-size: 12px;
    font-weight: bold;
    color: #333333;
}
"""

# Style for the "Target Platform" label
PLATFORM_LABEL_STYLE = """
QLabel {
    font-size: 12px;
    font-weight: bold;
    color: #555555;
}
"""

# Style for the refresh button (unstyled, default Windows look with emoji)
REFRESH_BUTTON_STYLE = """
QPushButton {
    /* No custom styling, let Windows default take over */
}
"""

# Style for the browse button (light blue tint, Windows-like)
BROWSE_BUTTON_STYLE = """
QPushButton {
    background-color: #e0e8f0;
    color: #333333;
    border: 1px solid #adadad;
    padding: 5px 10px;
}
QPushButton:hover {
    background-color: #d0d8e0;
}
QPushButton:pressed {
    background-color: #c0c8d0;
}
QPushButton:focus {
    border: 1px solid #666666;
}
"""

# Style for the edit/profile button (light orange tint, Windows-like)
EDIT_BUTTON_STYLE = """
QPushButton {
    background-color: #f0e8e0;
    color: #333333;
    border: 1px solid #adadad;
    padding: 5px 10px;
}
QPushButton:hover {
    background-color: #e0d8d0;
}
QPushButton:pressed {
    background-color: #d0c8c0;
}
QPushButton:focus {
    border: 1px solid #666666;
}
"""

# Style for the publish button (light red tint, Windows-like)
PUBLISH_BUTTON_STYLE = """
QPushButton {
    background-color: #f0e0e0;
    color: #333333;
    border: 1px solid #adadad;
    padding: 5px 10px;
}
QPushButton:hover {
    background-color: #e0d0d0;
}
QPushButton:pressed {
    background-color: #d0c0c0;
}
QPushButton:disabled {
    background-color: #cccccc;
    color: #666666;
}
QPushButton:focus {
    border: 1px solid #666666;
}
"""

# Style for the platform selector dropdown (squared, with visible arrow)
PLATFORM_COMBO_STYLE = """
QComboBox {
    border: 1px solid #cccccc;
    padding: 5px;
    background-color: white;
    color: #333333;
}
QComboBox:hover {
    border: 1px solid #aaaaaa;
}
QComboBox:focus {
    border: 1px solid #666666;
}
QComboBox::drop-down {
    width: 20px;
    border-left: 1px solid #cccccc;
    background-color: #f0f0f0;
}
QComboBox QAbstractItemView {
    border: 1px solid #cccccc;
    background-color: white;
    selection-background-color: #e0e0e0;
}
"""



# Style for the "No builds available" message
EMPTY_MESSAGE_STYLE = """
QLabel {
    font-size: 14px;
    font-style: italic;
    color: #888888;
    padding: 20px;
}
"""