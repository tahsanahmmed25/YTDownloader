from PySide6.QtWidgets import (
    QWidget, QLabel, QPushButton, QToolButton, QStyle, QStyleOptionButton,
    QStylePainter, QGraphicsOpacityEffect, QSizePolicy, QFrame, QAbstractButton,
    QProgressBar, QComboBox
)
from PySide6.QtCore import Qt, QPropertyAnimation, Property, QTimer, QSize, QRectF, QPointF, QEasingCurve, QAbstractAnimation
from PySide6.QtGui import QColor, QPalette, QPainter, QPen, QLinearGradient, QBrush, QPainterPath, QFont

from ui_style import DARK, LIGHT


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
        super().__init__(parent)
        self._full_text = ""
        self._offset = 0
        self._timer = QTimer(self)
        self._timer.setInterval(25)  # ~40fps scroll
        self._timer.timeout.connect(self._tick)
        self._pause_timer = QTimer(self)
        self._pause_timer.setSingleShot(True)
        self._pause_timer.timeout.connect(self._resume)
        self.setFixedHeight(20)
        self.setWordWrap(False)
        self.destroyed.connect(self._stop_timers)
        if text:
            self.set_full_text(text)

    def _stop_timers(self):
        try:
            self._timer.stop()
        except Exception:
            pass
        try:
            self._pause_timer.stop()
        except Exception:
            pass

    def hideEvent(self, event):
        super().hideEvent(event)
        self._stop_timers()

    def showEvent(self, event):
        super().showEvent(event)
        # Delay to let the layout assign a real width first
        QTimer.singleShot(200, self._check_and_start)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        # Re-evaluate scroll whenever width changes
        QTimer.singleShot(100, self._check_and_start)

    def set_full_text(self, text: str):
        self._full_text = text
        self._offset = 0
        self._stop_timers()
        self.update()
        # Wait for layout, then check if scrolling is needed
        QTimer.singleShot(600, self._check_and_start)

    def setText(self, text: str):
        self.set_full_text(text)

    def _check_and_start(self):
        if self.width() <= 0:
            # Widget not laid out yet — retry in 200ms
            QTimer.singleShot(200, self._check_and_start)
            return
        if not self._full_text:
            return
        fm = self.fontMetrics()
        self._text_width = fm.horizontalAdvance(self._full_text)
        if self._text_width > self.width():
            self._offset = 0
            self._timer.stop()
            self._pause_timer.stop()
            self._pause_timer.start(2000)   # 2 second pause then scroll
        else:
            self._timer.stop()
            self._pause_timer.stop()
            self._offset = 0
            self.update()

    def _resume(self):
        fm = self.fontMetrics()
        if fm.horizontalAdvance(self._full_text) > max(self.width(), 1):
            self._timer.start()

    def _tick(self):
        fm = self.fontMetrics()
        text_w = fm.horizontalAdvance(self._full_text)
        w = max(self.width(), 1)
        if text_w <= w:
            self._timer.stop()
            self._offset = 0
            self.update()
            return
        self._offset += 1
        if self._offset > text_w + 30:
            # Fully scrolled off — reset and pause before re-scrolling
            self._timer.stop()
            self._offset = 0
            self._pause_timer.start(1500)
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.TextAntialiasing, True)
        painter.setFont(self.font())
        painter.setPen(self.palette().color(QPalette.WindowText))
        painter.setClipRect(self.rect())
        painter.drawText(
            -self._offset, 0,
            self.width() + self._offset + 300,
            self.height(),
            Qt.AlignVCenter | Qt.AlignLeft,
            self._full_text,
        )
        painter.end()


# ── BrandIcon ────────────────────────────────────────────────────────────────
class BrandIcon(QWidget):
    def __init__(self, size=28, parent=None):
        super().__init__(parent)
        self.setFixedSize(size, size)

    def paintEvent(self, event):
        from ui.themes import get_theme, DEFAULT_THEME
        win = self.window()
        theme_name = getattr(win, 'current_theme_name', DEFAULT_THEME)
        dark = getattr(win, 'dark_mode', False)
        theme = get_theme(theme_name)

        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        rect = QRectF(0, 0, self.width(), self.height())

        # Rounded square background using accent color
        accent = QColor(theme["accent_dark"] if dark else theme["accent_light"])
        path = QPainterPath()
        path.addRoundedRect(rect, 7, 7)
        painter.fillPath(path, accent)

        # Calculate perceptual luminance (0–255)
        luminance = (
            0.299 * accent.red() +
            0.587 * accent.green() +
            0.114 * accent.blue()
        )
        # Use dark arrow on light backgrounds, white arrow on dark backgrounds
        arrow_color = QColor("#1a1a1a") if luminance > 140 else QColor("#ffffff")

        # Draw download arrow icon centered
        painter.setPen(QPen(arrow_color, 2.0, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
        cx = self.width() / 2
        cy = self.height() / 2
        # Arrow shaft
        painter.drawLine(QPointF(cx, cy - 5), QPointF(cx, cy + 3))
        # Arrow head
        painter.drawLine(QPointF(cx - 4, cy - 1), QPointF(cx, cy + 3))
        painter.drawLine(QPointF(cx + 4, cy - 1), QPointF(cx, cy + 3))
        # Base line
        painter.drawLine(QPointF(cx - 5, cy + 5), QPointF(cx + 5, cy + 5))
        painter.end()


# ── DownloadButton ────────────────────────────────────────────────────────────
class DownloadButton(QPushButton):
    def __init__(self, text="", parent=None):
        super().__init__(text, parent)
        self.setObjectName("StartDownloadButton")
        self.setCursor(Qt.PointingHandCursor)
        self.setFixedHeight(42)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        
        from PySide6.QtWidgets import QGraphicsDropShadowEffect
        self.shadow_effect = QGraphicsDropShadowEffect(self)
        self.shadow_effect.setBlurRadius(18)
        self.shadow_effect.setOffset(0, 4)
        self.shadow_effect.setColor(QColor(124, 58, 237, 76))
        self.setGraphicsEffect(self.shadow_effect)

    def _get_theme(self):
        from ui.themes import get_theme, DEFAULT_THEME
        win = self.window()
        name = getattr(win, 'current_theme_name', DEFAULT_THEME)
        dark = getattr(win, 'dark_mode', False)
        return get_theme(name), dark

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, True)
        painter.setRenderHint(QPainter.TextAntialiasing, True)
        
        theme, dark_mode = self._get_theme()
        t = DARK if dark_mode else LIGHT
        
        if self.isEnabled():
            rect = self.rect()
            grad = QLinearGradient(rect.left(), 0, rect.right(), 0)
            grad.setColorAt(0.0, QColor(theme["grad_start"]))
            grad.setColorAt(1.0, QColor(theme["grad_end"]))
            painter.setBrush(QBrush(grad))
            self.shadow_effect.setEnabled(True)
            
            accent_color = QColor(theme["accent_dark"] if dark_mode else theme["accent_light"])
            accent_color.setAlpha(76)
            self.shadow_effect.setColor(QColor(0, 0, 0, 150) if dark_mode else accent_color)
            text_color = QColor("#ffffff")
            icon_color = QColor("#ffffff")
        else:
            bg_color = QColor(t["bg_hover"])
            self.shadow_effect.setEnabled(False)
            text_color = QColor(t["text_tertiary"])
            icon_color = QColor(t["text_tertiary"])
            painter.setBrush(bg_color)
            
        painter.setPen(Qt.NoPen)
        painter.drawRoundedRect(self.rect(), 11, 11)
        
        from PySide6.QtGui import QFont
        font = QFont("Segoe UI", 10)
        font.setPixelSize(12)
        font.setBold(True)
        font.setLetterSpacing(QFont.AbsoluteSpacing, 0.12)
        painter.setFont(font)
        
        display_text = self.text()
        metrics = painter.fontMetrics()
        text_width = metrics.horizontalAdvance(display_text)
        
        icon_width = 10
        gap = 7
        total_width = icon_width + gap + text_width
        
        start_x = (self.width() - total_width) / 2
        text_y = (self.height() + metrics.ascent() - metrics.descent()) / 2
        
        icon_y = (self.height() - 12) / 2
        painter.setPen(QPen(icon_color, 1.8, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
        painter.drawLine(start_x + 5, icon_y + 1, start_x + 5, icon_y + 8)
        painter.drawLine(start_x + 2, icon_y + 5, start_x + 5, icon_y + 8)
        painter.drawLine(start_x + 8, icon_y + 5, start_x + 5, icon_y + 8)
        painter.drawLine(start_x + 2, icon_y + 11, start_x + 8, icon_y + 11)
        
        painter.setPen(text_color)
        painter.drawText(start_x + icon_width + gap, text_y, display_text)


# ── DownloadProgressBar ───────────────────────────────────────────────────────
class DownloadProgressBar(QProgressBar):
    def __init__(self, dark_mode=False, parent=None):
        super().__init__(parent)
        self.dark_mode = dark_mode
        self.setTextVisible(False)
        self.setFixedHeight(5)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, True)
        
        dark_mode = getattr(self.window(), "dark_mode", False)
        t = DARK if dark_mode else LIGHT
        
        bg_color = QColor(t["progress_track"])
        painter.setBrush(bg_color)
        painter.setPen(Qt.NoPen)
        painter.drawRoundedRect(self.rect(), 3, 3)
        
        val = self.value()
        min_val = self.minimum()
        max_val = self.maximum()
        if max_val - min_val <= 0:
            return
            
        progress_pct = (val - min_val) / (max_val - min_val)
        chunk_w = int(self.width() * progress_pct)
        if chunk_w <= 0:
            return
            
        chunk_rect = QRectF(0, 0, chunk_w, self.height())
        fill_color = QColor(t["progress_fill"])
        
        painter.setBrush(fill_color)
        painter.drawRoundedRect(chunk_rect, 3, 3)


# ── ToggleSwitch ──────────────────────────────────────────────────────────────
class ToggleSwitch(QAbstractButton):
    def __init__(self, dark_mode=False, parent=None):
        super().__init__(parent)
        self.setCheckable(True)
        self.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        self.setFixedSize(38, 20)
        self.dark_mode = dark_mode
        self._knob_x = 2
        
        self._anim = QPropertyAnimation(self, b"knobX", self)
        self._anim.setDuration(150)
        self._anim.setEasingCurve(QEasingCurve.OutCubic)

    def getKnobX(self):
        return self._knob_x

    def setKnobX(self, value):
        self._knob_x = int(value)
        self.update()

    knobX = Property(int, getKnobX, setKnobX)

    def nextCheckState(self):
        super().nextCheckState()
        self._animate(self.isChecked())

    def setChecked(self, checked):
        super().setChecked(checked)
        self._animate(checked)

    def _animate(self, checked):
        self._anim.stop()
        self._anim.setStartValue(self._knob_x)
        self._anim.setEndValue(22 if checked else 2)
        self._anim.start()

    def _get_theme(self):
        from ui.themes import get_theme, DEFAULT_THEME
        win = self.window()
        name = getattr(win, 'current_theme_name', DEFAULT_THEME)
        dark = getattr(win, 'dark_mode', False)
        return get_theme(name), dark

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, True)
        
        theme, dark = self._get_theme()
        on_color = QColor(theme["accent_dark"] if dark else theme["accent_light"])
        off_color = QColor("#d0d0d0" if not dark else "#3a3a3a")
        track_color = on_color if self.isChecked() else off_color
        
        rect = QRectF(0, 0, 38, 20)
        painter.setBrush(track_color)
        painter.setPen(Qt.NoPen)
        painter.drawRoundedRect(rect, 10, 10)
        
        painter.setBrush(QColor(0, 0, 0, 33))
        painter.drawEllipse(self._knob_x, 4, 14, 14)
        
        painter.setBrush(QColor("#ffffff"))
        painter.drawEllipse(self._knob_x, 3, 14, 14)


# ── ToastFrame ────────────────────────────────────────────────────────────────
class ToastFrame(QFrame):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("Toast")
        self._effect = QGraphicsOpacityEffect(self)
        self.setGraphicsEffect(self._effect)
        self._effect.setOpacity(0.0)

    def getOpacity(self):
        return self._effect.opacity()

    def setOpacity(self, val):
        self._effect.setOpacity(val)

    windowOpacity = Property(float, getOpacity, setOpacity)


# ── NavButton ─────────────────────────────────────────────────────────────────
class NavButton(QPushButton):
    def __init__(self, text="", parent=None):
        super().__init__(text, parent)
        self.setObjectName("NavButton")
        self.setCheckable(True)
        self.setFocusPolicy(Qt.NoFocus)
        self.setCursor(Qt.PointingHandCursor)
        self.icon_char = ""
        self.label_text = ""

    def _get_theme(self):
        from ui.themes import get_theme, DEFAULT_THEME
        win = self.window()
        name = getattr(win, 'current_theme_name', DEFAULT_THEME)
        dark = getattr(win, 'dark_mode', False)
        return get_theme(name), dark

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        rect = QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5)
        radius = 6
        is_active = self.property("active") == "true"

        theme, dark = self._get_theme()

        # Background: always transparent
        path = QPainterPath()
        path.addRoundedRect(rect, radius, radius)
        painter.fillPath(path, QColor("transparent"))

        if is_active:
            # Accent gradient border
            grad = QLinearGradient(rect.left(), rect.top(), rect.right(), rect.bottom())
            grad.setColorAt(0.0, QColor(theme["nav_border_dark"] if dark else theme["nav_border_light"]))
            grad.setColorAt(1.0, QColor(theme["grad_end"]))
            pen = QPen(QBrush(grad), 1.0)
            painter.setPen(pen)
        else:
            # Subtle neutral border — always present on ALL nav items
            subtle = QColor("#d0d0d0") if not dark else QColor("#2e2e2e")
            painter.setPen(QPen(subtle, 1.0))

        painter.drawRoundedRect(rect, radius, radius)

        # High contrast text colors
        if is_active:
            text_color = QColor(theme["nav_active_text_dark"] if dark else theme["nav_active_text_light"])
        else:
            text_color = QColor("#3a3a3a" if not dark else "#b0b0b0")

        icon_rect = QRectF(rect.left() + 10, rect.top(), 20, rect.height())
        text_rect = QRectF(rect.left() + 30, rect.top(), rect.width() - 34, rect.height())

        # Bolder active icon size and color
        icon_font = QFont(self.font())
        if is_active:
            icon_font.setPixelSize(15)
            icon_font.setWeight(QFont.Medium)
            icon_color = QColor(theme["accent_dark"] if dark else theme["accent_light"])
        else:
            icon_font.setPixelSize(14)
            icon_font.setWeight(QFont.Normal)
            icon_color = QColor("#3a3a3a") if not dark else QColor("#b0b0b0")

        painter.setFont(icon_font)
        painter.setPen(icon_color)
        painter.drawText(icon_rect, Qt.AlignVCenter | Qt.AlignLeft, self.icon_char if hasattr(self, 'icon_char') else '')

        label_font = QFont(self.font())
        label_font.setPixelSize(14)
        painter.setFont(label_font)
        painter.setPen(text_color)
        painter.drawText(text_rect, Qt.AlignVCenter | Qt.AlignLeft, self.label_text if hasattr(self, 'label_text') else self.text())
        painter.end()


# ── StatusBadge ───────────────────────────────────────────────────────────────
class StatusBadge(QLabel):
    def __init__(self, text="", parent=None):
        super().__init__(parent)
        self.setAlignment(Qt.AlignCenter)
        self._item_pct = None
        self._item_prog = None
        self._item_speed = None
        self.setText(text)

    def setText(self, text):
        super().setText(text)
        txt = (text or "").lower()
        if not txt or "downloading..." in txt:
            self.hide()
            if self._item_pct:
                self._item_pct.show()
            if self._item_prog:
                self._item_prog.show()
            if self._item_speed:
                self._item_speed.show()
        else:
            self.show()
            is_paused = "pause" in txt
            if "done" in txt or "complete" in txt or "finished" in txt:
                self.setObjectName("BadgeSuccess")
                super().setText("Done")
            elif "fail" in txt or "error" in txt or "stall" in txt:
                self.setObjectName("BadgeError")
                super().setText("Failed")
            elif "warn" in txt or "cancel" in txt:
                self.setObjectName("BadgeWarning")
                super().setText("Failed")
            elif is_paused:
                self.setObjectName("BadgeWarning")
                super().setText("Paused")
            else:
                self.setObjectName("BadgeNeutral")
                super().setText("Queued")
            
            if self._item_pct:
                self._item_pct.hide()
            if self._item_prog:
                if is_paused:
                    self._item_prog.show()
                else:
                    self._item_prog.hide()
            if self._item_speed:
                self._item_speed.hide()
            
            self.style().unpolish(self)
            self.style().polish(self)


# ── GradientButton ─────────────────────────────────────────────────────────────
class GradientButton(QPushButton):
    """A QPushButton that paints a left-to-right gradient background.

    Gradient stops: #6d28d9 at 0%, #7c3aed at 40%, #4f8dff at 75%, #06b6d4 at 100%.
    Draws white text centered, with a purple drop-shadow effect.
    """

    def __init__(self, text="", parent=None):
        super().__init__(text, parent)
        self.setObjectName("DownloadButton")
        self.setCursor(Qt.PointingHandCursor)
        self.setFixedHeight(42)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

        from PySide6.QtWidgets import QGraphicsDropShadowEffect
        self._shadow = QGraphicsDropShadowEffect(self)
        self._shadow.setBlurRadius(18)
        self._shadow.setOffset(0, 4)
        self._shadow.setColor(QColor(124, 58, 237, 77))  # rgba(124,58,237,0.30)
        self.setGraphicsEffect(self._shadow)

    def _get_theme(self):
        from ui.themes import get_theme, DEFAULT_THEME
        win = self.window()
        name = getattr(win, 'current_theme_name', DEFAULT_THEME)
        dark = getattr(win, 'dark_mode', False)
        return get_theme(name), dark

    def sizeHint(self):
        base = super().sizeHint()
        fm = self.fontMetrics()
        text_w = fm.horizontalAdvance(self.text()) + 32  # 16px padding each side
        return QSize(max(base.width(), text_w), base.height())

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, True)
        painter.setRenderHint(QPainter.TextAntialiasing, True)

        theme, dark_mode = self._get_theme()
        t = DARK if dark_mode else LIGHT

        if self.isEnabled():
            rect = self.rect()
            grad = QLinearGradient(rect.left(), 0, rect.right(), 0)
            grad.setColorAt(0.0, QColor(theme["grad_start"]))
            grad.setColorAt(1.0, QColor(theme["grad_end"]))
            painter.setBrush(QBrush(grad))
            self._shadow.setEnabled(True)
            self._shadow.setColor(QColor(0, 0, 0, 150) if dark_mode else QColor(13, 148, 136, 77))
            text_color = QColor("#ffffff")
        else:
            bg_color = QColor(t["bg_hover"])
            self._shadow.setEnabled(False)
            text_color = QColor(t["text_tertiary"])
            painter.setBrush(bg_color)

        painter.setPen(Qt.NoPen)
        painter.drawRoundedRect(self.rect(), 11, 11)

        from PySide6.QtGui import QFont
        font = QFont("Segoe UI", 10)
        font.setPixelSize(12)
        font.setBold(True)
        painter.setFont(font)
        painter.setPen(text_color)
        painter.drawText(self.rect(), Qt.AlignCenter, self.text())


# ── SectionLabel & NavCounter ──────────────────────────────────────────────────
class SectionLabel(QLabel):
    def __init__(self, text: str, parent=None):
        super().__init__(text.upper(), parent)
        self.setObjectName("SectionLabel")


class NavCounter(QLabel):
    def __init__(self, count: int = 0, parent=None):
        super().__init__(parent)
        self.setObjectName("NavCounter")
        self._count = 0
        self.set_count(count)
        self.setFixedHeight(18)
        self.setMinimumWidth(18)
        self.setAlignment(Qt.AlignCenter)

    def set_count(self, n: int):
        self._count = n
        self.setText(str(n) if n > 0 else "")
        self.setVisible(n > 0)
        # Adjust width based on digit count
        self.setFixedWidth(26 if n >= 10 else 18)
        self.update()

    def paintEvent(self, event):
        if self._count <= 0:
            return
        from ui.themes import get_theme, DEFAULT_THEME
        win = self.window()
        theme_name = getattr(win, 'current_theme_name', DEFAULT_THEME)
        dark = getattr(win, 'dark_mode', False)
        theme = get_theme(theme_name)

        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        rect = QRectF(0, 0, self.width(), self.height())

        # Pill background — accent color
        accent = QColor(theme["accent_dark"] if dark else theme["accent_light"])
        path = QPainterPath()
        path.addRoundedRect(rect, 9, 9)
        painter.fillPath(path, accent)

        # Count text — white, 10px, centered
        painter.setPen(QColor("#ffffff"))
        font = QFont(self.font())
        font.setPixelSize(10)
        font.setWeight(QFont.Medium)
        painter.setFont(font)
        painter.drawText(rect, Qt.AlignCenter, str(self._count))
        painter.end()


class ElidedLabel(QLabel):
    def __init__(self, text="", parent=None):
        super().__init__(parent)
        self._full_text = text or ""
        self.setMinimumWidth(1)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        self.setWordWrap(False)

    def setText(self, text):
        self._full_text = text or ""
        self.update()

    def text(self):
        return self._full_text

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.TextAntialiasing, True)
        painter.setFont(self.font())
        color = self.palette().color(QPalette.WindowText)
        painter.setPen(color)

        fm = painter.fontMetrics()
        elided = fm.elidedText(self._full_text, Qt.ElideRight, self.width())

        align = self.alignment()
        painter.drawText(self.rect(), align, elided)


# ── PrimaryButton ─────────────────────────────────────────────────────────────
class PrimaryButton(QPushButton):
    def __init__(self, text="", parent=None):
        super().__init__(text, parent)
        self.setObjectName("PrimaryButton")
        self.setCursor(Qt.PointingHandCursor)

    def _get_theme(self):
        from ui.themes import get_theme, DEFAULT_THEME
        win = self.window()
        name = getattr(win, 'current_theme_name', DEFAULT_THEME)
        dark = getattr(win, 'dark_mode', False)
        return get_theme(name), dark

    def sizeHint(self):
        base = super().sizeHint()
        fm = self.fontMetrics()
        text_w = fm.horizontalAdvance(self.text()) + 32  # 16px padding each side
        return QSize(max(base.width(), text_w), base.height())

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        rect = self.rect()
        radius = 8

        theme, dark = self._get_theme()

        path = QPainterPath()
        path.addRoundedRect(QRectF(rect), radius, radius)

        if self.isEnabled():
            grad = QLinearGradient(rect.left(), rect.top(), rect.right(), rect.top())
            grad.setColorAt(0.0, QColor(theme["grad_start"]))
            grad.setColorAt(1.0, QColor(theme["grad_end"]))
            painter.fillPath(path, QBrush(grad))
            painter.setPen(QColor("#ffffff"))
        else:
            t = DARK if dark else LIGHT
            painter.fillPath(path, QBrush(QColor(t["bg_hover"])))
            painter.setPen(QColor(t["text_tertiary"]))

        painter.setFont(self.font())
        painter.drawText(rect, Qt.AlignCenter, self.text())
        painter.end()


class AnimatedComboBox(QComboBox):
    def showPopup(self):
        super().showPopup()
        popup = self.findChild(QFrame)
        if popup:
            effect = QGraphicsOpacityEffect(popup)
            popup.setGraphicsEffect(effect)
            anim = QPropertyAnimation(effect, b"opacity", popup)
            anim.setDuration(150)
            anim.setStartValue(0.0)
            anim.setEndValue(1.0)
            anim.setEasingCurve(QEasingCurve.OutCubic)
            anim.start(QAbstractAnimation.DeleteWhenStopped)




