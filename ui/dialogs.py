from PySide6.QtWidgets import QDialog, QVBoxLayout, QLabel, QTextEdit, QDialogButtonBox, QGraphicsOpacityEffect
from PySide6.QtCore import QPropertyAnimation, QEasingCurve, Qt
from ui_style import style, dark_style

class TermsDialog(QDialog):
    def __init__(self, text, dark_mode=False, parent=None):
        super().__init__(parent)
        self.setWindowFlags(Qt.Dialog | Qt.WindowTitleHint | Qt.WindowCloseButtonHint)
        self.setStyleSheet(dark_style if dark_mode else style)
        self.setWindowTitle("Terms & Privacy")
        self.resize(640, 520)

        # Setup graphics effect early to prevent initial show flash/flicker
        self.effect = QGraphicsOpacityEffect(self)
        self.effect.setOpacity(0.0)
        self.setGraphicsEffect(self.effect)

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

    def showEvent(self, event):
        super().showEvent(event)
        self._fade_anim = QPropertyAnimation(self.effect, b"opacity")
        self._fade_anim.setDuration(250)
        self._fade_anim.setStartValue(0.0)
        self._fade_anim.setEndValue(1.0)
        self._fade_anim.setEasingCurve(QEasingCurve.OutCubic)
        self._fade_anim.start(QPropertyAnimation.KeepWhenStopped)


class CookiesHelpDialog(QDialog):
    def __init__(self, text, dark_mode=False, parent=None):
        super().__init__(parent)
        self.setWindowFlags(Qt.Dialog | Qt.WindowTitleHint | Qt.WindowCloseButtonHint)
        self.setStyleSheet(dark_style if dark_mode else style)
        self.setWindowTitle("How To Add Cookies")
        self.resize(600, 420)

        # Setup graphics effect early to prevent initial show flash/flicker
        self.effect = QGraphicsOpacityEffect(self)
        self.effect.setOpacity(0.0)
        self.setGraphicsEffect(self.effect)

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

    def showEvent(self, event):
        super().showEvent(event)
        self._fade_anim = QPropertyAnimation(self.effect, b"opacity")
        self._fade_anim.setDuration(250)
        self._fade_anim.setStartValue(0.0)
        self._fade_anim.setEndValue(1.0)
        self._fade_anim.setEasingCurve(QEasingCurve.OutCubic)
        self._fade_anim.start(QPropertyAnimation.KeepWhenStopped)
