from PySide6.QtWidgets import QWidget, QLabel, QPushButton, QToolButton, QStyle, QStyleOptionButton, QStylePainter
from PySide6.QtCore import Qt, QPropertyAnimation, Property, QTimer, QSize
from PySide6.QtGui import QColor, QPalette, QPainter, QPen


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


class NavRingSpinner(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._angle = 0
        self._timer = QTimer(self)
        self._timer.setInterval(48)
        self._timer.timeout.connect(self._tick)
        self.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.hide()

    def start(self):
        if not self._timer.isActive():
            self._timer.start()
        self.show()
        self.raise_()
        self.update()

    def stop(self):
        if self._timer.isActive():
            self._timer.stop()
        self.hide()
        self._angle = 0

    def _tick(self):
        self._angle = (self._angle + 16) % 360
        self.update()

    def paintEvent(self, event):
        if not self.isVisible():
            return
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, True)
        rect = self.rect().adjusted(3, 3, -3, -3)

        base_pen = QPen(QColor(79, 141, 255, 64), 2.0)
        base_pen.setCapStyle(Qt.RoundCap)
        painter.setPen(base_pen)
        painter.drawEllipse(rect)

        active_pen = QPen(QColor(79, 141, 255, 235), 2.8)
        active_pen.setCapStyle(Qt.RoundCap)
        painter.setPen(active_pen)
        painter.drawArc(rect, int(-self._angle * 16), int(110 * 16))


class MarqueeLabel(QLabel):
    def __init__(self, text="", parent=None):
        super().__init__(text, parent)
        self._full_text = text or ""
        self._offset = 0
        self._gap_px = 36
        self._timer = QTimer(self)
        self._timer.setInterval(30)
        self._timer.timeout.connect(self._tick)
        self.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)

    def setText(self, text):
        self._full_text = text or ""
        self._offset = 0
        super().setText(self._full_text)
        self._update_marquee()
        self.updateGeometry()

    def sizeHint(self):
        base = super().sizeHint()
        return QSize(0, base.height())

    def minimumSizeHint(self):
        base = super().minimumSizeHint()
        return QSize(0, base.height())

    def _tick(self):
        text_w = self.fontMetrics().horizontalAdvance(self._full_text)
        total = text_w + self._gap_px
        if total <= 0:
            return
        self._offset = (self._offset + 1) % total
        self.update()

    def _needs_marquee(self):
        if not self._full_text:
            return False
        text_w = self.fontMetrics().horizontalAdvance(self._full_text)
        return text_w > max(10, self.contentsRect().width() - 2)

    def _update_marquee(self):
        if self._needs_marquee():
            if not self._timer.isActive():
                self._timer.start()
        else:
            if self._timer.isActive():
                self._timer.stop()
            self._offset = 0
            self.update()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._update_marquee()

    def showEvent(self, event):
        super().showEvent(event)
        self._update_marquee()

    def paintEvent(self, event):
        rect = self.contentsRect()
        text = self._full_text or ""
        if not text:
            super().paintEvent(event)
            return

        fm = self.fontMetrics()
        text_w = fm.horizontalAdvance(text)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.TextAntialiasing, True)
        painter.setClipRect(rect)
        painter.setPen(self.palette().color(QPalette.WindowText))

        if not self._needs_marquee():
            baseline = rect.y() + (rect.height() + fm.ascent() - fm.descent()) // 2
            painter.drawText(rect.x(), baseline, text)
            return

        total = text_w + self._gap_px
        baseline = rect.y() + (rect.height() + fm.ascent() - fm.descent()) // 2
        x = rect.x() - self._offset
        while x < rect.right():
            painter.drawText(x, baseline, text)
            x += total
