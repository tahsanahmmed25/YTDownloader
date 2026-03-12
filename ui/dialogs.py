from PySide6.QtWidgets import QDialog, QVBoxLayout, QLabel, QTextEdit, QDialogButtonBox


class TermsDialog(QDialog):
    def __init__(self, text, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Terms & Privacy")
        self.resize(640, 520)

        layout = QVBoxLayout(self)
        intro = QLabel("Please review and accept to continue using the app.")
        intro.setWordWrap(True)
        layout.addWidget(intro)

        body = QTextEdit()
        body.setReadOnly(True)
        body.setPlainText(text)
        layout.addWidget(body, 1)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok
            | QDialogButtonBox.StandardButton.Cancel
        )
        layout.addWidget(buttons)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
