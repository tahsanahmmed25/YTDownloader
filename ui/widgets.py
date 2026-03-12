from PySide6.QtWidgets import QPushButton, QToolButton, QStyle, QStyleOptionButton, QStylePainter
from PySide6.QtCore import Qt, QPropertyAnimation, Property
from PySide6.QtGui import QColor, QPalette


class FadingTextButton(QPushButton):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._text_opacity = 1.0
        self._display_text = self.text()
        self._fade_out = None
        self._fade_in = None

    def textOpacity(self):
        return self._text_opacity

    def setTextOpacity(self, value):
        self._text_opacity = float(value)
        self.update()

    textOpacity = Property(float, textOpacity, setTextOpacity)

    def animateText(self, text):
        if self._display_text == text:
            if self._text_opacity < 1.0:
                self._text_opacity = 1.0
                self.update()
            return
        if self._fade_out:
            self._fade_out.stop()
        if self._fade_in:
            self._fade_in.stop()

        self._fade_out = QPropertyAnimation(self, b"textOpacity", self)
        self._fade_out.setDuration(120)
        self._fade_out.setStartValue(self._text_opacity)
        self._fade_out.setEndValue(0.0)

        self._fade_in = QPropertyAnimation(self, b"textOpacity", self)
        self._fade_in.setDuration(160)
        self._fade_in.setStartValue(0.0)
        self._fade_in.setEndValue(1.0)

        def _after_out():
            self._display_text = text
            QPushButton.setText(self, text)
            self._fade_in.start()

        self._fade_out.finished.connect(_after_out)
        self._fade_out.start()

    def setText(self, text):
        self._display_text = text
        QPushButton.setText(self, text)
        self.update()

    def paintEvent(self, event):
        opt = QStyleOptionButton()
        self.initStyleOption(opt)
        display_text = self._display_text if self._display_text is not None else opt.text
        opt.text = ""

        painter = QStylePainter(self)
        painter.drawControl(QStyle.CE_PushButton, opt)

        if self.objectName() == "PrimaryButton":
            color = QColor(255, 255, 255)
            if not (opt.state & QStyle.State_Enabled):
                color.setAlpha(180)
        else:
            if opt.state & QStyle.State_Enabled:
                color = opt.palette.color(QPalette.Active, QPalette.ButtonText)
            else:
                color = opt.palette.color(QPalette.Disabled, QPalette.ButtonText)

        painter.setOpacity(self._text_opacity)
        painter.setPen(color)
        painter.drawText(opt.rect, Qt.AlignCenter, display_text)


class PasteButton(QToolButton):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setObjectName("PasteButton")
        self.setText("Paste")
        self.setToolButtonStyle(Qt.ToolButtonTextOnly)
        self.setCursor(Qt.PointingHandCursor)
        self.setFixedHeight(40)
        self.setFixedWidth(84)
