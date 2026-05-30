from PySide6.QtWidgets import QDialog, QVBoxLayout, QLabel, QTextEdit, QDialogButtonBox
from ui_style import style, dark_style

class TermsDialog(QDialog):
    def __init__(self, text, dark_mode=False, parent=None):
        super().__init__(parent)
        self.setStyleSheet(dark_style if dark_mode else style)
        self.setWindowTitle("Terms & Privacy")
        self.resize(640, 520)

        layout = QVBoxLayout(self)

        body = QTextEdit()
        body.setReadOnly(True)
        body.setPlainText(text)
        layout.addWidget(body, 1)

        buttons = QDialogButtonBox()
        ok_btn = buttons.addButton("OK", QDialogButtonBox.ButtonRole.AcceptRole)
        cancel_btn = buttons.addButton("Cancel", QDialogButtonBox.ButtonRole.RejectRole)
        layout.addWidget(buttons)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)


class CookiesHelpDialog(QDialog):
    def __init__(self, text, dark_mode=False, parent=None):
        super().__init__(parent)
        self.setStyleSheet(dark_style if dark_mode else style)
        self.setWindowTitle("How To Add Cookies")
        self.resize(600, 420)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        body = QTextEdit()
        body.setReadOnly(True)
        body.setPlainText(text)
        layout.addWidget(body, 1)

        buttons = QDialogButtonBox()
        buttons.addButton("OK", QDialogButtonBox.ButtonRole.AcceptRole)
        layout.addWidget(buttons)
        buttons.accepted.connect(self.accept)

