from PyQt6.QtWidgets import QDialog, QVBoxLayout

class PublishDialog(QDialog):

    def __init__(self, parent=None):
        self.setup_ui()

    def setup_ui(self):
        self.setWindowTitle("Project Publisher")
        self.setMinimumSize(600, 400)

        self.layout = QVBoxLayout()