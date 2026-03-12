import sys
import os
import re
import time
import hashlib
import uuid
import shutil
from collections import deque
from datetime import datetime, UTC

from PySide6.QtWidgets import (
    QApplication,
    QMainWindow,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QLineEdit,
    QComboBox,
    QProgressBar,
    QCheckBox,
    QFrame,
    QStackedWidget,
    QScrollArea,
    QToolButton,
    QMessageBox,
    QFileDialog,
    QButtonGroup,
    QGraphicsDropShadowEffect,
    QStyle,
    QStyleOptionButton,
    QStylePainter,
    QSizePolicy,
    QDialog,
    QDialogButtonBox,
    QTextEdit,
    QProgressDialog,
    QGraphicsOpacityEffect,
    QSystemTrayIcon,
    QMenu
)
from PySide6.QtCore import Qt, Signal, QObject, QThread, QSettings, QSize, QUrl, QTimer, QStandardPaths, QPropertyAnimation, Property, QEasingCurve, QEvent
from PySide6.QtGui import QIcon, QPixmap, QDesktopServices, QColor, QFont, QPalette, QAction

from ui_style import style, dark_style
from downloader import is_valid_youtube_url, is_playlist_url
from history_manager import load_history, remove_history, clear_history, save_history
from app_config import (
    APP_NAME,
    APP_ORG,
    APP_VERSION,
    DEFAULT_UPDATE_MANIFEST_URL,
    UPDATE_INSTALLER_NAME,
    THUMB_DIR,
    app_data_dir,
    app_dir,
    ensure_dir,
    get_icon_path,
    compare_versions,
    extract_update_info
)
from errors import humanize_error
from logging_utils import get_logger
from ui.widgets import FadingTextButton, PasteButton
from ui.dialogs import TermsDialog
from ui.pages import PagesMixin
from workers import UpdateWorker, UpdateDownloadWorker, FetchWorker, DownloadWorker
import queue_manager

_log = get_logger()
MAX_COOKIE_FILE_BYTES = 5 * 1024 * 1024
THUMB_CACHE_DAYS = 30
LIBRARY_PAGE_SIZE = 10


def _default_download_dir():
    path = QStandardPaths.writableLocation(QStandardPaths.DownloadLocation)
    if path:
        return path
    home = os.path.expanduser("~")
    if home:
        return os.path.join(home, "Downloads")
    return os.getcwd()


 


class Downloader(QMainWindow, PagesMixin):

    def __init__(self):
        super().__init__()

        self.setWindowTitle("Simple Youtube Downloader by Tahsan")
        self.resize(960, 560)
        self.setMinimumSize(940, 520)
        self.setMaximumSize(1200, 720)
        self.menuBar().hide()

        icon_path = get_icon_path()
        if icon_path:
            self.setWindowIcon(QIcon(icon_path))

        self._default_formats = ["Auto", "MP4", "MKV", "WEBM"]
        self._default_qualities = ["Auto (Best)", "720p", "1080p", "2K", "4K"]

        self.settings = QSettings(APP_ORG, APP_NAME)
        self.dark_mode = self.settings.value("dark_mode", False, type=bool)
        self._apply_theme()
        self.show_thumbnail = self.settings.value("show_thumbnail", True, type=bool)
        self.cookie_file = self.settings.value("cookie_file", "", type=str)
        if self.cookie_file and not self._cookie_is_valid(self.cookie_file):
            self.cookie_file = ""
            self.settings.remove("cookie_file")

        self.download_dir = self.settings.value("download_dir", "", type=str)
        if not self.download_dir or not os.path.isdir(self.download_dir):
            self.download_dir = _default_download_dir()
        ensure_dir(self.download_dir)
        self.settings.setValue("download_dir", self.download_dir)
        self.max_concurrent_downloads = self.settings.value(
            "max_concurrent_downloads",
            2,
            type=int
        )
        try:
            self.max_concurrent_downloads = int(self.max_concurrent_downloads)
        except Exception:
            self.max_concurrent_downloads = 2
        self.max_concurrent_downloads = max(1, min(5, self.max_concurrent_downloads))
        self.speed_limit_kbps = self.settings.value("speed_limit_kbps", 0, type=int)
        try:
            self.speed_limit_kbps = int(self.speed_limit_kbps)
        except Exception:
            self.speed_limit_kbps = 0
        if self.speed_limit_kbps < 0:
            self.speed_limit_kbps = 0

        self.update_manifest_url = self.settings.value(
            "update_manifest_url",
            DEFAULT_UPDATE_MANIFEST_URL,
            type=str
        )
        self.check_updates_on_startup = self.settings.value(
            "check_updates_on_startup",
            True,
            type=bool
        )
        self.auto_download_updates = self.settings.value(
            "auto_download_updates",
            False,
            type=bool
        )
        self.skip_update_version = self.settings.value(
            "skip_update_version",
            "",
            type=str
        )
        self.update_url_404_disabled = self.settings.value(
            "update_url_404_disabled",
            False,
            type=bool
        )
        self.update_url_404_value = self.settings.value(
            "update_url_404_value",
            "",
            type=str
        )

        self._fetch_thread = None
        self._fetch_worker = None
        self._download_threads = {}
        self._download_workers = {}
        self._active_tasks = {}
        self._pending_tasks = []
        self._paused_tasks = {}
        self._update_thread = None
        self._update_worker = None
        self._update_download_thread = None
        self._update_download_worker = None
        self._update_progress_dialog = None
        self._last_downloaded_bytes = None
        self._last_total_bytes = None
        self._estimated_size_mb = None

        self.cookie_status_widgets = []
        self._download_reset_timer = QTimer(self)
        self._download_reset_timer.setSingleShot(True)
        self._download_reset_timer.timeout.connect(self._reset_download_ui)
        self.toast = None
        self.toast_label = None
        self._toast_effect = None
        self._toast_anim_in = None
        self._toast_anim_out = None
        self._toast_queue = deque()
        self._toast_active = False
        self._downloads_anim = None
        self.details_full_height = None
        self._details_anim = None
        self.active_download_item = None
        self._resume_payload = None
        self._is_paused = False
        self._last_progress_value = 0
        self._config_anim = None
        self._info_ready = False
        self._active_url = ""
        self._active_is_playlist = False
        self._download_item_pool = []
        self._library_items = []
        self._library_visible_count = 0
        self._library_load_more_btn = None
        self._library_page_size = LIBRARY_PAGE_SIZE
        self._library_search_text = ""
        self._tray = None
        self._tray_menu = None
        self._force_quit = False
        self.nav_library_btn = None

        self._build_ui()
        QTimer.singleShot(0, self._init_details_height)
        self.update_cookie_indicator()
        self.refresh_library()
        QTimer.singleShot(0, self._load_persistent_queue)
        self._init_tray()

        QTimer.singleShot(150, self._show_terms_if_needed)
        if self.check_updates_on_startup:
            QTimer.singleShot(250, self.start_update_check)
        QTimer.singleShot(400, self._maybe_show_cookie_reminder)
        QTimer.singleShot(600, self._check_ffmpeg_on_startup)

    def _build_ui(self):
        root = QWidget()
        root_layout = QHBoxLayout(root)
        root_layout.setContentsMargins(16, 16, 16, 16)
        root_layout.setSpacing(16)

        self.sidebar = QFrame()
        self.sidebar.setObjectName("Sidebar")
        sidebar_layout = QVBoxLayout(self.sidebar)
        sidebar_layout.setContentsMargins(16, 16, 16, 16)
        sidebar_layout.setSpacing(10)

        brand = QLabel("YTDownloader")
        brand.setObjectName("Brand")
        sidebar_layout.addWidget(brand)

        self.nav_group = QButtonGroup(self)
        self.nav_group.setExclusive(True)

        self.pages = QStackedWidget()

        self.page_downloader = self._build_downloader_page()
        self.page_library = self._build_library_page()
        self.page_options = self._build_options_page()
        self.page_cookies = self._build_cookies_page()
        self.page_about = self._build_about_page()

        self.pages.addWidget(self.page_downloader)
        self.pages.addWidget(self.page_library)
        self.pages.addWidget(self.page_options)
        self.pages.addWidget(self.page_cookies)
        self.pages.addWidget(self.page_about)

        self._add_nav_button(sidebar_layout, "Downloader", self.page_downloader, True)
        self.nav_library_btn = self._add_nav_button(sidebar_layout, "Library", self.page_library, False)
        self._add_nav_button(sidebar_layout, "Options", self.page_options, False)
        self._add_nav_button(sidebar_layout, "Cookies", self.page_cookies, False)
        self._add_nav_button(sidebar_layout, "About", self.page_about, False)

        sidebar_layout.addStretch(1)

        root_layout.addWidget(self.sidebar)
        root_layout.addWidget(self.pages, 1)

        self.setCentralWidget(root)
        self._apply_shadow(self.sidebar, 30, 140, 6)

        self.toast = QFrame(root)
        self.toast.setObjectName("Toast")
        toast_layout = QHBoxLayout(self.toast)
        toast_layout.setContentsMargins(14, 10, 14, 10)
        toast_layout.setSpacing(8)
        self.toast_label = QLabel("")
        self.toast_label.setObjectName("ToastLabel")
        self.toast_label.setWordWrap(True)
        toast_layout.addWidget(self.toast_label)
        self.toast.hide()

        self._toast_effect = QGraphicsOpacityEffect(self.toast)
        self._toast_effect.setOpacity(0.0)
        self.toast.setGraphicsEffect(self._toast_effect)

    def _add_nav_button(self, layout, label, page, checked):
        btn = QPushButton(label)
        btn.setObjectName("NavButton")
        btn.setCheckable(True)
        btn.setChecked(checked)
        btn.setCursor(Qt.ArrowCursor)
        btn.clicked.connect(lambda: self.pages.setCurrentWidget(page))
        self.nav_group.addButton(btn)
        layout.addWidget(btn)
        return btn

    def _apply_shadow(self, widget, blur, alpha, y_offset):
        effect = QGraphicsDropShadowEffect(self)
        effect.setBlurRadius(blur)
        effect.setColor(QColor(0, 0, 0, alpha))
        effect.setOffset(0, y_offset)
        widget.setGraphicsEffect(effect)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._position_toast()

    def changeEvent(self, event):
        super().changeEvent(event)

    def _position_toast(self):
        if not self.toast:
            return
        root = self.centralWidget()
        if not root:
            return
        margin = 20
        max_width = max(260, min(560, root.width() - margin * 2))
        self.toast.setFixedWidth(max_width)
        self.toast.adjustSize()
        x = (root.width() - self.toast.width()) // 2
        y = margin
        self.toast.move(max(x, margin), max(y, margin))

    def _init_tray(self):
        if not QSystemTrayIcon.isSystemTrayAvailable():
            return
        self._tray = QSystemTrayIcon(self)
        icon = self.windowIcon()
        if icon and not icon.isNull():
            self._tray.setIcon(icon)
        menu = QMenu()
        show_action = QAction("Show", self)
        show_action.triggered.connect(self._show_from_tray)
        quit_action = QAction("Quit", self)
        quit_action.triggered.connect(self._exit_app)
        menu.addAction(show_action)
        menu.addAction(quit_action)
        self._tray.setContextMenu(menu)
        self._tray.activated.connect(self._on_tray_activated)
        self._tray.show()

    def _on_tray_activated(self, reason):
        if reason == QSystemTrayIcon.Trigger:
            self._show_from_tray()

    def _show_from_tray(self):
        self.showNormal()
        self.raise_()
        self.activateWindow()

    def _exit_app(self):
        self._force_quit = True
        self.close()

    def _show_toast(self, message, variant="info", duration=3000):
        if not self.toast or not self.toast_label:
            return
        if self._toast_active:
            self._toast_queue.append((message, variant, duration))
            return
        self._toast_active = True
        self.toast_label.setText(message)
        self.toast.setProperty("variant", variant)
        self.toast.style().unpolish(self.toast)
        self.toast.style().polish(self.toast)
        self._position_toast()
        self.toast.show()
        self.toast.raise_()

        if self._toast_anim_in:
            self._toast_anim_in.stop()
        if self._toast_anim_out:
            self._toast_anim_out.stop()

        self._toast_effect.setOpacity(0.0)
        self._toast_anim_in = QPropertyAnimation(self._toast_effect, b"opacity", self)
        self._toast_anim_in.setDuration(180)
        self._toast_anim_in.setStartValue(0.0)
        self._toast_anim_in.setEndValue(1.0)

        self._toast_anim_out = QPropertyAnimation(self._toast_effect, b"opacity", self)
        self._toast_anim_out.setDuration(180)
        self._toast_anim_out.setStartValue(1.0)
        self._toast_anim_out.setEndValue(0.0)
        def _on_hide():
            self.toast.hide()
            self._toast_active = False
            if self._toast_queue:
                next_msg, next_variant, next_duration = self._toast_queue.popleft()
                QTimer.singleShot(
                    60,
                    lambda: self._show_toast(next_msg, next_variant, next_duration)
                )
        self._toast_anim_out.finished.connect(_on_hide)

        def _schedule_hide():
            QTimer.singleShot(duration, self._toast_anim_out.start)

        self._toast_anim_in.finished.connect(_schedule_hide)
        self._toast_anim_in.start()

    def _init_details_height(self):
        if not hasattr(self, "details_container") or not self.details_container:
            return
        self.details_full_height = self.details_container.sizeHint().height()
        if self.details_full_height:
            self.details_container.setMaximumHeight(self.details_full_height)

    def _collapse_details(self):
        if not self.details_container:
            return
        if self.details_full_height is None:
            self._init_details_height()
        start = self.details_container.maximumHeight()
        end = 0
        if start == end:
            return
        self._details_anim = QPropertyAnimation(self.details_container, b"maximumHeight", self)
        self._details_anim.setDuration(280)
        self._details_anim.setStartValue(start)
        self._details_anim.setEndValue(end)
        self._details_anim.setEasingCurve(QEasingCurve.InOutCubic)
        self._details_anim.start()

    def _expand_details(self):
        if not self.details_container:
            return
        if self.details_full_height is None:
            self._init_details_height()
        start = self.details_container.maximumHeight()
        end = self.details_full_height or self.details_container.sizeHint().height()
        if start == end:
            return
        self._details_anim = QPropertyAnimation(self.details_container, b"maximumHeight", self)
        self._details_anim.setDuration(280)
        self._details_anim.setStartValue(start)
        self._details_anim.setEndValue(end)
        self._details_anim.setEasingCurve(QEasingCurve.InOutCubic)
        self._details_anim.start()

    def _show_downloads_panel(self, show=True):
        if not hasattr(self, "downloads_panel"):
            return
        if show:
            self.downloads_panel.setVisible(True)
            self.downloads_panel.raise_()
            target = max(140, self.downloads_panel.sizeHint().height())
            self.downloads_panel.setMaximumHeight(0)
            start = 0
            if self._downloads_anim:
                self._downloads_anim.stop()
            self._downloads_anim = QPropertyAnimation(self.downloads_panel, b"maximumHeight", self)
            self._downloads_anim.setDuration(260)
            self._downloads_anim.setStartValue(start)
            self._downloads_anim.setEndValue(target)
            self._downloads_anim.setEasingCurve(QEasingCurve.OutCubic)
            self._downloads_anim.start()
        else:
            if not self.downloads_panel.isVisible():
                return
            if self._downloads_anim:
                self._downloads_anim.stop()
            start = self.downloads_panel.maximumHeight()
            if start <= 0:
                self.downloads_panel.hide()
                return
            self._downloads_anim = QPropertyAnimation(self.downloads_panel, b"maximumHeight", self)
            self._downloads_anim.setDuration(220)
            self._downloads_anim.setStartValue(start)
            self._downloads_anim.setEndValue(0)
            self._downloads_anim.setEasingCurve(QEasingCurve.InOutCubic)
            def _hide_panel():
                self.downloads_panel.hide()
                self.downloads_panel.setMaximumHeight(0)
            self._downloads_anim.finished.connect(_hide_panel)
            self._downloads_anim.start()

    def _set_config_enabled(self, enabled):
        if not hasattr(self, "config_content") or not self.config_content:
            return
        self.config_content.setEnabled(bool(enabled))
        self.config_content.setVisible(True)

    def _set_config_visible(self, visible, animate=True):
        self._set_config_enabled(visible)

    def _set_status_icon(self, label, state, text):
        if not label:
            return
        label.setProperty("status", state)
        label.setText(text)
        label.style().unpolish(label)
        label.style().polish(label)

    def _make_cookie_status_row(self, trailing_widget=None):
        row = QHBoxLayout()
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(6)
        row.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        label = QLabel("Cookies:")
        label.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Preferred)
        dot = QLabel()
        dot.setFixedSize(12, 12)
        dot.setStyleSheet("border-radius: 6px; background: #f39c12;")
        status = QLabel("Not loaded")
        status.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Preferred)
        row.addWidget(label)
        row.addWidget(dot)
        row.addWidget(status)
        if trailing_widget is not None:
            row.addStretch(1)
            row.addWidget(trailing_widget)
        self.cookie_status_widgets.append((dot, status))
        return row

    def _create_download_item(self, title):
        if hasattr(self, "_download_item_pool") and self._download_item_pool:
            item = self._download_item_pool.pop()
            self._reset_download_item(item, title)
            return item
        frame = QFrame()
        frame.setObjectName("LibraryCard")
        layout = QVBoxLayout(frame)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(6)

        top_row = QHBoxLayout()
        title_label = QLabel(title)
        title_label.setObjectName("LibraryTitle")
        status_label = QLabel("Downloading...")
        status_label.setObjectName("MutedText")
        status_icon = QLabel("")
        status_icon.setObjectName("StatusIcon")
        status_icon.setFixedWidth(18)
        status_icon.setAlignment(Qt.AlignCenter)
        self._set_status_icon(status_icon, "active", "")
        status_effect = QGraphicsOpacityEffect(status_icon)
        status_effect.setOpacity(1.0)
        status_icon.setGraphicsEffect(status_effect)
        pause_btn = QPushButton("Pause")
        pause_btn.setObjectName("GhostButton")
        pause_btn.setFixedWidth(80)
        open_btn = QPushButton("Open Folder")
        open_btn.setObjectName("GhostButton")
        open_btn.setVisible(False)
        open_btn.clicked.connect(lambda: self._open_folder(self.download_dir))
        top_row.addWidget(title_label, 1)
        top_row.addWidget(status_label)
        top_row.addWidget(status_icon)
        top_row.addWidget(pause_btn)
        top_row.addWidget(open_btn)
        layout.addLayout(top_row)

        progress = QProgressBar()
        progress.setValue(0)
        layout.addWidget(progress)

        info_row = QHBoxLayout()
        speed_label = QLabel("Speed: -")
        size_label = QLabel("Downloaded: -")
        info_row.addWidget(speed_label)
        info_row.addSpacing(12)
        info_row.addWidget(size_label)
        info_row.addStretch(1)
        layout.addLayout(info_row)

        item = {
            "frame": frame,
            "title": title_label,
            "status": status_label,
            "status_icon": status_icon,
            "status_effect": status_effect,
            "progress": progress,
            "speed": speed_label,
            "size": size_label,
            "pause_btn": pause_btn,
            "open_btn": open_btn
        }
        frame._download_item = item
        return item

    def _reset_download_item(self, item, title):
        if not item:
            return
        item["title"].setText(title)
        item["status"].setText("Downloading...")
        self._set_status_icon(item["status_icon"], "active", "")
        item["progress"].setValue(0)
        item["speed"].setText("Speed: -")
        item["size"].setText("Downloaded: -")
        item["pause_btn"].setEnabled(True)
        item["pause_btn"].setText("Pause")
        item["open_btn"].setVisible(False)

    def _show_error_dialog(self, title, message):
        _log.warning("%s: %s", title, message)
        box = QMessageBox(self)
        box.setIcon(QMessageBox.Warning)
        box.setWindowTitle(title)
        box.setText(message)
        self._style_message_box(box)
        box.exec()

    def _show_message_dialog(self, title, message, icon=QMessageBox.Information):
        box = QMessageBox(self)
        box.setIcon(icon)
        box.setWindowTitle(title)
        box.setText(message)
        self._style_message_box(box)
        box.exec()

    def _style_message_box(self, box):
        box.setStyleSheet(
            "QDialog, QMessageBox { background: #f7f4ee; }"
            "QLabel { color: #1f2a36; }"
            "QPushButton { background: #ffffff; border: 1px solid rgba(31,42,54,40);"
            " border-radius: 8px; padding: 4px 12px; }"
        )

    def _apply_theme(self):
        self.setStyleSheet(dark_style if self.dark_mode else style)

    def _on_dark_mode_toggle(self, checked):
        self.dark_mode = bool(checked)
        self.settings.setValue("dark_mode", self.dark_mode)
        self._apply_theme()

    def _set_combo_items(self, combo, options):
        if not combo:
            return
        current = combo.currentText()
        combo.blockSignals(True)
        combo.clear()
        combo.addItems(options)
        if current in options:
            combo.setCurrentText(current)
        elif options:
            combo.setCurrentIndex(0)
        combo.blockSignals(False)
        combo.setEnabled(bool(options))

    def _apply_format_options(self, available):
        if available is None:
            self._set_combo_items(self.format_combo, [])
            return
        if available:
            options = [self._default_formats[0]] + [
                opt for opt in self._default_formats[1:] if opt in available
            ]
            if len(options) == 1:
                options = [self._default_formats[0]]
        else:
            options = [self._default_formats[0]]
        self._set_combo_items(self.format_combo, options)

    def _apply_quality_options(self, available):
        if available is None:
            self._set_combo_items(self.quality, [])
            return
        if available:
            options = [self._default_qualities[0]] + [
                opt for opt in self._default_qualities[1:] if opt in available
            ]
            if len(options) == 1:
                options = [self._default_qualities[0]]
        else:
            options = [self._default_qualities[0]]
        self._set_combo_items(self.quality, options)

    def _apply_subtitle_options(self, available):
        if not hasattr(self, "subs_lang") or self.subs_lang is None:
            return
        self.subs_lang.blockSignals(True)
        self.subs_lang.clear()
        if not available:
            self.subs_lang.addItem("Not available")
            self.subs_lang.setEnabled(False)
        else:
            self.subs_lang.addItem("Any")
            for lang in available:
                self.subs_lang.addItem(lang)
            self.subs_lang.setEnabled(True)
        self.subs_lang.blockSignals(False)

    def _clear_format_quality(self):
        self._set_combo_items(self.format_combo, [])
        self._set_combo_items(self.quality, [])
        self._apply_subtitle_options([])

    def _layout_widget_count(self, layout):
        count = 0
        if not layout:
            return 0
        for i in range(layout.count()):
            item = layout.itemAt(i)
            if item and item.widget():
                count += 1
        return count

    def _update_downloads_header(self):
        if not hasattr(self, "downloads_header"):
            return
        total = self._layout_widget_count(self.active_downloads_layout) + self._layout_widget_count(self.completed_downloads_layout)
        self.downloads_header.setText(f"Downloads ({total})")
        self._update_library_nav_state()

    def _update_library_nav_state(self):
        if not getattr(self, "nav_library_btn", None):
            return
        active = bool(self._active_tasks or self._pending_tasks or self._paused_tasks)
        self.nav_library_btn.setProperty("activeDownloads", active)
        self.nav_library_btn.style().unpolish(self.nav_library_btn)
        self.nav_library_btn.style().polish(self.nav_library_btn)

    def _animate_status_icon(self, item):
        if not item:
            return
        effect = item.get("status_effect")
        if not effect:
            return
        effect.setOpacity(0.0)
        anim = QPropertyAnimation(effect, b"opacity", self)
        anim.setDuration(220)
        anim.setStartValue(0.0)
        anim.setEndValue(1.0)
        anim.setEasingCurve(QEasingCurve.OutCubic)
        anim.start()
        item["status_anim"] = anim

    def _cookies_loaded(self):
        return bool(self._effective_cookie_file())

    def _maybe_show_cookie_reminder(self):
        if self._cookies_loaded():
            return
        self._show_toast(
            "Cookies are not loaded. Some videos require cookies. "
            "Go to Cookies tab to add them.",
            variant="warning"
        )

    def _is_cookie_related_error(self, msg):
        if not msg:
            return False
        lowered = msg.lower()
        markers = (
            "sign in",
            "login",
            "cookies",
            "confirm your age",
            "members only",
            "private video",
            "this video is private",
            "this video is available to",
            "account is required",
            "http error 403",
            "http error 429"
        )
        return any(m in lowered for m in markers)

    def _is_ffmpeg_missing_error(self, msg):
        lowered = (msg or "").lower()
        return "ffmpeg" in lowered and "not installed" in lowered

    def _find_ffmpeg(self):
        which = shutil.which("ffmpeg")
        if which and os.path.exists(which):
            return which
        candidates = [
            os.path.join(app_dir(), "ffmpeg.exe"),
            os.path.join(os.getcwd(), "ffmpeg.exe")
        ]
        for path in candidates:
            if path and os.path.exists(path):
                return path
        return None

    def _check_ffmpeg_on_startup(self):
        if self._find_ffmpeg():
            return
        self._show_toast(
            "FFmpeg is not installed. Some downloads need it. "
            "Go to Options -> Downloads to install essentials.",
            variant="warning"
        )

    def _run_install_essentials(self):
        script = os.path.join(app_dir(), "install_essentials.ps1")
        if not os.path.exists(script):
            self._show_error_dialog(
                "Essentials",
                "install_essentials.ps1 not found. "
                "Please reinstall the app."
            )
            return
        try:
            import subprocess
            subprocess.run(
                [
                    os.path.join(
                        os.environ.get("SystemRoot", "C:\\Windows"),
                        "System32",
                        "WindowsPowerShell",
                        "v1.0",
                        "powershell.exe"
                    ),
                    "-ExecutionPolicy",
                    "Bypass",
                    "-File",
                    script,
                    "-TargetDir",
                    app_dir()
                ],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                check=False,
                shell=False
            )
            self._show_toast(
                "Installing essentials in the background...",
                variant="info"
            )
        except Exception:
            _log.exception("Failed to run install_essentials.ps1")
            self._show_error_dialog(
                "Essentials",
                "Failed to start install_essentials.ps1. "
                "Please run it manually from the app folder."
            )

    def _terms_text(self):
        return (
            "Terms & Privacy\n"
            "\n"
            "1. Purpose\n"
            "This app is provided as-is for personal use. You are responsible for\n"
            "complying with platform rules and local laws.\n"
            "\n"
            "2. Cookies & Account Data\n"
            "Cookies you load are used locally on your device to access content.\n"
            "The app never uploads cookie files. Do not share cookies with anyone.\n"
            "\n"
            "3. Updates\n"
            "The app checks for updates using the URL you provide. Optional updates\n"
            "may be skipped. Required updates may block usage until updated.\n"
            "\n"
            "4. Analytics\n"
            "This version does not collect analytics or tracking data.\n"
            "\n"
            "5. Security\n"
            "No software can be made completely unhackable. This app minimizes risk\n"
            "by keeping cookies local and avoiding sensitive data collection unless\n"
            "you explicitly enable it.\n"
        )

    def _version_text(self):
        return APP_VERSION

    def _show_terms_if_needed(self):
        accepted = self.settings.value("terms_accepted", False, type=bool)
        if accepted:
            return
        dialog = TermsDialog(self._terms_text(), self)
        if dialog.exec() == QDialog.Accepted:
            self.settings.setValue("terms_accepted", True)
        else:
            self.close()

    def show_terms_dialog(self):
        dialog = TermsDialog(self._terms_text(), self)
        dialog.exec()

    def _animate_button_text(self, button, text):
        if isinstance(button, FadingTextButton):
            button.animateText(text)
            return
        if button.text() != text:
            button.setText(text)

    def _clear_layout(self, layout):
        while layout.count():
            item = layout.takeAt(0)
            widget = item.widget()
            if widget:
                widget.deleteLater()

    def _clear_downloads_list(self):
        if hasattr(self, "active_downloads_layout"):
            self._drain_download_layout(self.active_downloads_layout)
        if hasattr(self, "completed_downloads_layout"):
            self._drain_download_layout(self.completed_downloads_layout)
        self._update_downloads_header()

    def _drain_download_layout(self, layout):
        if not layout:
            return
        while layout.count():
            item = layout.takeAt(0)
            widget = item.widget() if item else None
            if widget and hasattr(widget, "_download_item"):
                if hasattr(self, "_download_item_pool"):
                    self._download_item_pool.append(widget._download_item)
                widget.setParent(None)
            elif widget:
                widget.deleteLater()

    def _placeholder_pixmap(self, size):
        pix = QPixmap(size)
        pix.fill(QColor(223, 231, 242))
        return pix

    def _open_folder(self, path):
        if not path:
            return
        target = path
        if os.path.isfile(path):
            target = os.path.dirname(path)
        if target and os.path.exists(target):
            QDesktopServices.openUrl(QUrl.fromLocalFile(target))
            return
        self._show_message_dialog("Folder missing", "The folder was not found.", QMessageBox.Warning)

    def _on_show_thumbnail_toggle(self, checked):
        self.show_thumbnail = bool(checked)
        self.settings.setValue("show_thumbnail", self.show_thumbnail)
        if hasattr(self, "thumbnail"):
            self.thumbnail.setVisible(self.show_thumbnail)

    def _on_url_changed(self, _text):
        if self._info_ready:
            self._info_ready = False
            self.download_btn.setEnabled(False)
            self._set_config_enabled(False)
            self._clear_format_quality()
        self._estimated_size_mb = None

    def _on_playlist_toggle(self, checked):
        self._active_is_playlist = bool(checked)
        if checked:
            self.url_input.setPlaceholderText("Download entire playlist...")
        else:
            self.url_input.setPlaceholderText("Paste YouTube link...")
        self._on_url_changed("")

    def refresh_library(self):
        self._clear_layout(self.library_layout)
        history = load_history()
        self._library_items = history
        self._library_visible_count = 0
        self._cleanup_thumbnails()
        self._render_library_page()

    def _on_library_search_changed(self, text):
        self._library_search_text = (text or "").strip().lower()
        self._library_visible_count = 0
        self._render_library_page()

    def _render_library_page(self):
        self._clear_layout(self.library_layout)
        history = self._library_items or []
        if self._library_search_text:
            q = self._library_search_text
            history = [
                item for item in history
                if q in (item.get("title") or "").lower()
                or q in (item.get("added_at") or "").lower()
            ]
        if not history:
            empty = QLabel("No downloads yet.")
            empty.setObjectName("MutedText")
            self.library_layout.addWidget(empty)
            self.library_layout.addStretch(1)
            return

        end = min(self._library_visible_count + self._library_page_size, len(history))
        for item in history[:end]:
            self.library_layout.addWidget(self._build_library_item(item))
        self._library_visible_count = end

        if self._library_visible_count < len(history):
            if not self._library_load_more_btn:
                self._library_load_more_btn = QPushButton("Load more")
                self._library_load_more_btn.setObjectName("GhostButton")
                self._library_load_more_btn.clicked.connect(self._load_more_library)
            self.library_layout.addWidget(self._library_load_more_btn)
        self.library_layout.addStretch(1)

    def _load_more_library(self):
        self._library_visible_count = min(
            self._library_visible_count + self._library_page_size,
            len(self._library_items)
        )
        self._render_library_page()

    def _build_library_item(self, item):
        card = QFrame()
        card.setObjectName("LibraryCard")
        card.setContextMenuPolicy(Qt.CustomContextMenu)
        card.customContextMenuRequested.connect(
            lambda pos, i=item, w=card: self._show_library_context_menu(i, w, pos)
        )
        layout = QHBoxLayout(card)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(12)

        thumb_btn = QToolButton()
        thumb_btn.setObjectName("ThumbButton")
        thumb_btn.setToolButtonStyle(Qt.ToolButtonIconOnly)
        thumb_btn.setIconSize(QSize(160, 90))

        thumb_path = item.get("thumb_path") or ""
        if thumb_path and os.path.exists(thumb_path):
            pix = QPixmap(thumb_path)
        else:
            pix = self._placeholder_pixmap(QSize(160, 90))
        thumb_btn.setIcon(QIcon(pix))
        thumb_btn.clicked.connect(lambda: self.play_history_item(item))

        info_layout = QVBoxLayout()
        title = QLabel(item.get("title") or "Unknown")
        title.setObjectName("LibraryTitle")
        info_layout.addWidget(title)

        filepath = item.get("filepath") or ""
        if filepath:
            info_layout.addWidget(QLabel(os.path.basename(filepath)))
        else:
            missing = QLabel("File path not available")
            missing.setObjectName("MutedText")
            info_layout.addWidget(missing)

        btn_row = QHBoxLayout()
        open_btn = QPushButton("Open Folder")
        open_btn.setObjectName("GhostButton")
        if filepath:
            open_btn.clicked.connect(lambda: self._open_folder(filepath))
        else:
            open_btn.setEnabled(False)
        btn_row.addWidget(open_btn)

        remove_btn = QPushButton("Remove")
        remove_btn.setObjectName("GhostButton")
        remove_btn.clicked.connect(lambda: self.remove_history_item(item, delete_file=False))
        btn_row.addWidget(remove_btn)

        delete_btn = QPushButton("Delete File")
        delete_btn.setObjectName("GhostButton")
        delete_btn.clicked.connect(lambda: self.remove_history_item(item, delete_file=True))
        btn_row.addWidget(delete_btn)
        btn_row.addStretch(1)
        info_layout.addLayout(btn_row)
        info_layout.addStretch(1)

        layout.addWidget(thumb_btn)
        layout.addLayout(info_layout, 1)
        return card

    def _show_library_context_menu(self, item, widget, pos):
        menu = QMenu(self)
        filepath = item.get("filepath") or ""
        if filepath and os.path.exists(filepath):
            open_action = menu.addAction("Open Folder")
            open_action.triggered.connect(lambda: self._open_folder(filepath))
        remove_action = menu.addAction("Remove from history")
        remove_action.triggered.connect(lambda: self.remove_history_item(item, delete_file=False))
        delete_action = menu.addAction("Delete file & history")
        delete_action.triggered.connect(lambda: self.remove_history_item(item, delete_file=True))
        menu.exec(widget.mapToGlobal(pos))

    def play_history_item(self, item):
        filepath = item.get("filepath") or ""
        if filepath and os.path.exists(filepath):
            QDesktopServices.openUrl(QUrl.fromLocalFile(filepath))
            return
        self._show_message_dialog("File missing", "The downloaded file was not found.", QMessageBox.Warning)

    def remove_history_item(self, item, delete_file=False):
        item_id = item.get("id")
        if item_id:
            if delete_file:
                filepath = item.get("filepath") or ""
                if filepath and os.path.exists(filepath):
                    try:
                        os.remove(filepath)
                    except Exception as exc:
                        _log.warning("Failed to delete file %s: %s", filepath, exc)
            remove_history(item_id)
            thumb_path = item.get("thumb_path")
            if thumb_path and os.path.exists(thumb_path):
                try:
                    os.remove(thumb_path)
                except Exception as exc:
                    _log.warning("Failed to remove thumbnail %s: %s", thumb_path, exc)
            self.refresh_library()

    def clear_library(self):
        clear_history()
        self._clear_thumbnails()
        self.refresh_library()

    # ---------- FETCH VIDEO INFO ----------
    def fetch_info(self):
        url = self.url_input.text().strip()
        if not url:
            return
        if not is_valid_youtube_url(url):
            self._show_error_dialog("Error", "Please enter a valid YouTube link.")
            return
        is_playlist = bool(getattr(self, "playlist_toggle", None) and self.playlist_toggle.isChecked())
        if is_playlist and not is_playlist_url(url):
            self._show_error_dialog("Error", "Please enter a valid playlist link.")
            return
        if self._fetch_thread and self._fetch_thread.isRunning():
            return
        quality = self.quality.currentText().strip() or "Auto (Best)"
        container = (self.format_combo.currentText().strip() or "auto").lower()

        self._info_ready = False
        self._active_url = url
        self._active_is_playlist = is_playlist
        self.download_btn.setEnabled(False)
        self._set_config_enabled(False)
        self.fetch_btn.setEnabled(False)
        if hasattr(self, "fetch_spinner"):
            self.fetch_spinner.setVisible(True)
        try:
            self.url_input.setCursorPosition(0)
            self.url_input.deselect()
        except Exception:
            pass
        self.title.setText("Title: -")
        self.size.setText("Estimated size: -")
        self.thumbnail.setPixmap(self._placeholder_pixmap(self.thumbnail.size()))
        self._clear_format_quality()

        self._fetch_thread = QThread()
        self._fetch_worker = FetchWorker(
            url,
            self.cookie_file,
            allow_playlist=is_playlist,
            quality=quality,
            container=container
        )
        self._fetch_worker.moveToThread(self._fetch_thread)

        self._fetch_thread.started.connect(self._fetch_worker.run)
        self._fetch_worker.info_ready.connect(self.on_info_ready, Qt.QueuedConnection)
        self._fetch_worker.error.connect(self.on_fetch_error, Qt.QueuedConnection)
        self._fetch_worker.finished.connect(self._fetch_thread.quit)
        self._fetch_worker.finished.connect(self._fetch_worker.deleteLater)
        self._fetch_thread.finished.connect(self._fetch_thread.deleteLater)
        self._fetch_thread.finished.connect(self._on_fetch_done)

        self._animate_button_text(self.fetch_btn, "Analyzing...")
        self._fetch_thread.start()

    def _clear_fetch_refs(self):
        self._fetch_worker = None
        self._fetch_thread = None

    def _on_fetch_done(self):
        self.fetch_btn.setEnabled(True)
        if hasattr(self, "fetch_spinner"):
            self.fetch_spinner.setVisible(False)
        self._animate_button_text(self.fetch_btn, "Analyze")
        self._clear_fetch_refs()

    def on_info_ready(self,
                      title,
                      size,
                      thumb_bytes,
                      available_formats=None,
                      available_qualities=None,
                      available_subtitles=None):
        self.title.setText(f"Title: {title}")
        if size == "Unknown":
            self.size.setText("Estimated size: Unknown")
            self._estimated_size_mb = None
        else:
            self.size.setText(f"Estimated size: ~{size} MB")
            try:
                self._estimated_size_mb = float(size)
            except Exception:
                self._estimated_size_mb = None

        if thumb_bytes:
            pix = QPixmap()
            pix.loadFromData(thumb_bytes)
            target = self.thumbnail.size()
            self.thumbnail.setPixmap(
                pix.scaled(target, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            )
        else:
            self.thumbnail.setPixmap(self._placeholder_pixmap(self.thumbnail.size()))

        self._apply_format_options(available_formats)
        self._apply_quality_options(available_qualities)
        self._apply_subtitle_options(available_subtitles)
        self._info_ready = True
        self.download_btn.setEnabled(True)
        self._set_config_enabled(True)

    def on_fetch_error(self, msg):
        clean = re.sub(r"\x1b\[[0-9;]*m", "", msg)
        _log.error("Fetch error: %s", clean)
        if not self._cookies_loaded() and self._is_cookie_related_error(clean):
            self._show_toast(
                "Cookies are not loaded. Some videos require cookies. "
                "Go to Cookies tab to add them.",
                variant="warning"
            )
        user_msg = humanize_error(clean, cookies_loaded=self._cookies_loaded())
        self._show_error_dialog("Error", f"Failed to fetch info:\n{user_msg}")
        self._info_ready = False
        self._estimated_size_mb = None
        self.download_btn.setEnabled(False)
        self._set_config_enabled(False)

    # ---------- DOWNLOAD ----------
    def start_download(self):
        url = (self._active_url or "").strip()
        quality = self.quality.currentText().strip() or "Auto (Best)"
        container = (self.format_combo.currentText().strip() or "auto").lower()

        if not url:
            return
        if not is_valid_youtube_url(url):
            self._show_error_dialog("Error", "Please enter a valid YouTube link.")
            return
        if not self._info_ready:
            return

        subtitles = self.subs_checkbox.isChecked()
        subtitles_langs = ""
        if hasattr(self, "subs_lang") and self.subs_lang and self.subs_lang.isEnabled():
            current = (self.subs_lang.currentText() or "").strip()
            if current and current.lower() not in ("any", "not available"):
                subtitles_langs = current
        embed_subs = self.embed_subs_checkbox.isChecked()
        if self._estimated_size_mb and not self._has_enough_disk_space(self._estimated_size_mb):
            self._show_error_dialog(
                "Error",
                "Not enough free disk space for this download."
            )
            return

        rate_limit = None
        if self.speed_limit_kbps and self.speed_limit_kbps > 0:
            rate_limit = int(self.speed_limit_kbps) * 1024

        payload = {
            "url": url,
            "quality": quality,
            "container": container,
            "subtitles": subtitles,
            "subtitles_langs": subtitles_langs,
            "embed_subs": embed_subs,
            "download_playlist": self._active_is_playlist,
            "rate_limit": rate_limit,
            "download_dir": self.download_dir
        }
        title_text = self.title.text().replace("Title: ", "").strip()
        if not title_text or title_text == "-":
            title_text = url
        self._queue_download(payload, title_text)

    def _queue_download(self, payload, title_text):
        task_id = uuid.uuid4().hex
        task = {
            "id": task_id,
            "payload": payload,
            "title": title_text,
            "state": "queued",
            "downloaded": None,
            "total": None
        }
        item = self._create_download_item(title_text)
        task["item"] = item
        item["status"].setText("Queued")
        self._set_status_icon(item["status_icon"], "active", "")
        item["pause_btn"].setText("Remove")
        item["pause_btn"].setEnabled(True)
        item["pause_btn"].clicked.connect(lambda _=False, tid=task_id: self._on_task_pause_clicked(tid))
        self.active_downloads_layout.addWidget(item["frame"])
        self._pending_tasks.append(task)
        self._update_downloads_header()
        self._collapse_details()
        QTimer.singleShot(280, lambda: self._show_downloads_panel(True))
        self._persist_queue()
        self._start_next_downloads()

    def _start_next_downloads(self):
        while len(self._active_tasks) < self.max_concurrent_downloads and self._pending_tasks:
            task = self._pending_tasks.pop(0)
            self._start_task(task)
        self._persist_queue()

    def _start_task(self, task):
        task_id = task["id"]
        payload = task["payload"]
        task["state"] = "active"
        item = task["item"]
        item["status"].setText("Downloading...")
        self._set_status_icon(item["status_icon"], "active", "")
        item["pause_btn"].setText("Pause")
        item["pause_btn"].setEnabled(True)

        thread = QThread()
        worker = DownloadWorker(
            payload["url"],
            payload["quality"],
            self.cookie_file,
            payload.get("download_dir") or self.download_dir,
            download_playlist=payload["download_playlist"],
            container=payload["container"],
            subtitles=payload["subtitles"],
            subtitles_langs=payload["subtitles_langs"],
            embed_subtitles=payload["embed_subs"],
            rate_limit=payload.get("rate_limit")
        )
        worker.moveToThread(thread)

        thread.started.connect(worker.run)
        worker.progress.connect(
            lambda p, s, d, t, tid=task_id: self.update_progress(tid, p, s, d, t),
            Qt.QueuedConnection
        )
        worker.error.connect(
            lambda msg, tid=task_id: self.on_download_error(tid, msg),
            Qt.QueuedConnection
        )
        worker.completed.connect(
            lambda items, tid=task_id: self.on_download_complete(tid, items),
            Qt.QueuedConnection
        )
        worker.paused.connect(
            lambda tid=task_id: self.on_download_paused(tid),
            Qt.QueuedConnection
        )
        worker.finished.connect(thread.quit)
        worker.finished.connect(worker.deleteLater)
        thread.finished.connect(thread.deleteLater)

        self._download_threads[task_id] = thread
        self._download_workers[task_id] = worker
        self._active_tasks[task_id] = task

        thread.start()

    def _on_task_pause_clicked(self, task_id):
        if task_id in self._active_tasks:
            worker = self._download_workers.get(task_id)
            task = self._active_tasks.get(task_id)
            if worker and task:
                task["state"] = "pausing"
                task["item"]["status"].setText("Pausing...")
                worker.request_pause()
            return
        if task_id in self._paused_tasks:
            task = self._paused_tasks.pop(task_id)
            task["state"] = "queued"
            task["item"]["status"].setText("Queued")
            task["item"]["pause_btn"].setText("Remove")
            self._pending_tasks.append(task)
            self._persist_queue()
            self._start_next_downloads()
            return
        # queued remove
        for idx, task in enumerate(self._pending_tasks):
            if task["id"] == task_id:
                item = task["item"]
                if item and item.get("frame"):
                    item["frame"].setParent(None)
                self._pending_tasks.pop(idx)
                self._update_downloads_header()
                self._persist_queue()
                return

    def on_download_paused(self, task_id):
        task = self._active_tasks.pop(task_id, None)
        if not task:
            return
        self._download_workers.pop(task_id, None)
        self._download_threads.pop(task_id, None)
        item = task["item"]
        task["state"] = "paused"
        item["status"].setText("Paused")
        self._set_status_icon(item["status_icon"], "active", "")
        item["pause_btn"].setText("Resume")
        item["pause_btn"].setEnabled(True)
        self._paused_tasks[task_id] = task
        self._start_next_downloads()

    def on_download_complete(self, task_id, items):
        task = self._active_tasks.pop(task_id, None)
        if not task:
            return
        self._download_workers.pop(task_id, None)
        self._download_threads.pop(task_id, None)
        self.refresh_library()
        item = task["item"]
        item["status"].setText("")
        self._set_status_icon(item["status_icon"], "done", "✓")
        self._animate_status_icon(item)
        item["pause_btn"].setDisabled(True)
        item["open_btn"].setVisible(True)
        item["progress"].setValue(100)
        if task.get("downloaded") is not None:
            downloaded_text = round(task["downloaded"] / (1024 * 1024), 2)
            total = task.get("total")
            if total:
                total_text = round(total / (1024 * 1024), 2)
                item["size"].setText(f"Downloaded: {downloaded_text} MB / {total_text} MB")
            else:
                item["size"].setText(f"Downloaded: {downloaded_text} MB")
        if self.active_downloads_layout:
            self.active_downloads_layout.removeWidget(item["frame"])
            self.completed_downloads_layout.addWidget(item["frame"])
        if self._tray and self._tray.isVisible():
            self._tray.showMessage("Download complete", task.get("title") or "Download finished", QSystemTrayIcon.Information, 2000)
        self._update_downloads_header()
        self._persist_queue()
        self._start_next_downloads()

    def on_download_error(self, task_id, msg):
        clean = re.sub(r"\x1b\[[0-9;]*m", "", msg)
        _log.error("Download error: %s", clean)
        user_msg = humanize_error(clean, cookies_loaded=self._cookies_loaded())
        if self._is_ffmpeg_missing_error(clean):
            self._show_error_dialog(
                "Error",
                f"Download failed:\n{user_msg}"
            )
        else:
            if not self._cookies_loaded() and self._is_cookie_related_error(clean):
                self._show_toast(
                    "Cookies are not loaded. Some videos require cookies. "
                    "Go to Cookies tab to add them.",
                    variant="warning"
                )
            self._show_error_dialog("Error", f"Download failed:\n{user_msg}")

        task = self._active_tasks.pop(task_id, None)
        if task:
            self._download_workers.pop(task_id, None)
            self._download_threads.pop(task_id, None)
            item = task["item"]
            item["status"].setText("")
            self._set_status_icon(item["status_icon"], "failed", "✕")
            self._animate_status_icon(item)
            item["pause_btn"].setDisabled(True)
            if self.active_downloads_layout:
                self.active_downloads_layout.removeWidget(item["frame"])
                self.completed_downloads_layout.addWidget(item["frame"])
            self._update_downloads_header()
        self._persist_queue()
        self._start_next_downloads()

    def update_progress(self, task_id, percent, speed=None, downloaded=None, total=None):
        try:
            value = int(percent)
        except Exception:
            value = 0
        value = max(0, min(100, value))
        task = self._active_tasks.get(task_id)
        if not task:
            return
        task["downloaded"] = downloaded if downloaded is not None else task.get("downloaded")
        task["total"] = total if total is not None else task.get("total")
        item = task["item"]
        item["progress"].setValue(value)

        downloaded_text = None
        if downloaded is not None:
            downloaded_text = round(downloaded / (1024 * 1024), 2)

        total_text = None
        if total:
            total_text = round(total / (1024 * 1024), 2)

        if downloaded_text is not None and total_text is not None:
            item["size"].setText(f"Downloaded: {downloaded_text} MB / {total_text} MB")
        elif downloaded_text is not None:
            item["size"].setText(f"Downloaded: {downloaded_text} MB")

        if speed:
            item["speed"].setText(f"Speed: {speed}")

    def _has_enough_disk_space(self, estimated_mb):
        if not estimated_mb:
            return True
        try:
            free = shutil.disk_usage(self.download_dir).free
        except Exception:
            return True
        required = int(float(estimated_mb) * 1024 * 1024)
        buffer = 200 * 1024 * 1024
        return free >= (required + buffer)

    def _persist_queue(self):
        tasks = []
        for task in self._pending_tasks:
            tasks.append({
                "id": task["id"],
                "title": task["title"],
                "payload": task["payload"],
                "state": task.get("state", "queued")
            })
        for task in self._paused_tasks.values():
            tasks.append({
                "id": task["id"],
                "title": task["title"],
                "payload": task["payload"],
                "state": "paused"
            })
        for task in self._active_tasks.values():
            tasks.append({
                "id": task["id"],
                "title": task["title"],
                "payload": task["payload"],
                "state": "active"
            })
        queue_manager.save_queue(tasks)

    def _load_persistent_queue(self):
        if not hasattr(queue_manager, "load_queue"):
            return
        items = queue_manager.load_queue()
        if not items:
            return
        for saved in items:
            payload = saved.get("payload") or {}
            title_text = saved.get("title") or payload.get("url") or "Download"
            history_item = {
                "title": title_text,
                "url": payload.get("url") or "",
                "filepath": "",
                "thumb_path": "",
                "added_at": datetime.now(UTC).isoformat()
            }
            save_history(history_item)
        queue_manager.clear_queue()
        self.refresh_library()

    def _reset_download_ui(self):
        self._animate_button_text(self.download_btn, "Start Download")
        self.progress.setValue(0)
        self._last_progress_value = 0

    def reset_ui(self):
        if self._fetch_thread and self._fetch_thread.isRunning():
            return
        if self._active_tasks:
            return
        if self._download_reset_timer.isActive():
            self._download_reset_timer.stop()
        self.fetch_btn.setEnabled(True)
        self.fetch_btn.setText("Analyze")
        if hasattr(self, "fetch_spinner"):
            self.fetch_spinner.setVisible(False)
        self.download_btn.setEnabled(False)
        self._reset_download_ui()
        self.url_input.clear()
        self.title.setText("Title: -")
        self.size.setText("Estimated size: -")
        self._last_downloaded_bytes = None
        self._last_total_bytes = None
        self._last_progress_value = 0
        self.progress.setValue(0)
        self.thumbnail.clear()
        self.thumbnail.setPixmap(self._placeholder_pixmap(self.thumbnail.size()))
        self._clear_format_quality()
        self.subs_checkbox.setChecked(False)
        self.embed_subs_checkbox.setChecked(False)
        self._apply_subtitle_options([])
        self._active_url = ""
        self._active_is_playlist = False
        if hasattr(self, "playlist_toggle"):
            self.playlist_toggle.setChecked(False)
        self._pending_tasks.clear()
        self._paused_tasks.clear()
        self._active_tasks.clear()
        self._download_threads.clear()
        self._download_workers.clear()
        queue_manager.clear_queue()
        self._show_downloads_panel(False)
        self._expand_details()
        self._clear_downloads_list()
        self.active_download_item = None

    def _read_clipboard_text(self):
        try:
            return QApplication.clipboard().text().strip()
        except Exception:
            return ""
        self._resume_payload = None
        self._is_paused = False
        self._info_ready = False
        self._set_config_enabled(False)

    def change_download_dir(self):
        start_dir = self.download_dir or _default_download_dir()
        path = QFileDialog.getExistingDirectory(
            self,
            "Select download folder",
            start_dir
        )
        if not path:
            return
        self.download_dir = path
        ensure_dir(self.download_dir)
        self.settings.setValue("download_dir", self.download_dir)
        if hasattr(self, "download_dir_input"):
            self.download_dir_input.setText(self.download_dir)

    def _on_max_concurrent_changed(self, value):
        try:
            value = int(value)
        except Exception:
            value = 1
        self.max_concurrent_downloads = max(1, min(5, value))
        self.settings.setValue("max_concurrent_downloads", self.max_concurrent_downloads)
        self._start_next_downloads()

    def _on_speed_limit_changed(self, value):
        try:
            value = int(value)
        except Exception:
            value = 0
        if value < 0:
            value = 0
        self.speed_limit_kbps = value
        self.settings.setValue("speed_limit_kbps", self.speed_limit_kbps)

    def _clear_thumbnails(self):
        if not os.path.exists(THUMB_DIR):
            return
        for name in os.listdir(THUMB_DIR):
            path = os.path.join(THUMB_DIR, name)
            try:
                if os.path.isfile(path):
                    os.remove(path)
            except Exception:
                pass

    def _cleanup_thumbnails(self):
        if not os.path.exists(THUMB_DIR):
            return
        keep = set()
        for item in self._library_items or []:
            thumb_path = item.get("thumb_path") if isinstance(item, dict) else ""
            if thumb_path:
                keep.add(os.path.abspath(thumb_path))

        now = time.time()
        max_age = THUMB_CACHE_DAYS * 24 * 60 * 60
        for name in os.listdir(THUMB_DIR):
            path = os.path.join(THUMB_DIR, name)
            try:
                if not os.path.isfile(path):
                    continue
                abs_path = os.path.abspath(path)
                age = now - os.path.getmtime(path)
                if abs_path not in keep or age > max_age:
                    os.remove(path)
            except Exception as exc:
                _log.warning("Failed to clean thumbnail %s: %s", path, exc)
        try:
            if not os.listdir(THUMB_DIR):
                os.rmdir(THUMB_DIR)
        except Exception:
            pass

    def _paste_from_clipboard(self):
        text = self._read_clipboard_text()
        if text:
            if hasattr(self, "url_input"):
                self.url_input.setText(text)
                self.url_input.setFocus()

    # ---------- UPDATES ----------
    def _on_update_check_toggle(self, checked):
        self.check_updates_on_startup = bool(checked)
        self.settings.setValue("check_updates_on_startup", self.check_updates_on_startup)

    def _on_auto_update_toggle(self, checked):
        self.auto_download_updates = bool(checked)
        self.settings.setValue("auto_download_updates", self.auto_download_updates)

    def _on_update_url_changed(self):
        if not hasattr(self, "update_url_input"):
            return
        self.update_manifest_url = self.update_url_input.text().strip()
        self.settings.setValue("update_manifest_url", self.update_manifest_url)
        if self.update_url_404_disabled:
            self.update_url_404_disabled = False
            self.update_url_404_value = ""
            self.settings.setValue("update_url_404_disabled", False)
            self.settings.setValue("update_url_404_value", "")

    def start_update_check(self, manual=False):
        if self._update_thread and self._update_thread.isRunning():
            return
        url = (self.update_manifest_url or "").strip()
        if not url:
            if manual:
                self._show_message_dialog(
                    "Updates",
                    "Update manifest URL is not set yet."
                )
            return
        if (
            not manual
            and self.update_url_404_disabled
            and self.update_url_404_value == url
        ):
            return
        if not url.lower().startswith("https://"):
            if manual:
                self._show_message_dialog(
                    "Updates",
                    "For security, update checks require HTTPS.",
                    QMessageBox.Warning
                )
            return

        self._update_manual = manual
        self._update_thread = QThread()
        self._update_worker = UpdateWorker(url, APP_VERSION, extract_update_info, compare_versions)
        self._update_worker.moveToThread(self._update_thread)

        self._update_thread.started.connect(self._update_worker.run)
        self._update_worker.update_available.connect(self._on_update_available)
        self._update_worker.update_required.connect(self._on_update_required)
        self._update_worker.no_update.connect(self._on_no_update)
        self._update_worker.error.connect(self._on_update_error)
        self._update_worker.finished.connect(self._update_thread.quit)
        self._update_worker.finished.connect(self._update_worker.deleteLater)
        self._update_thread.finished.connect(self._update_thread.deleteLater)
        self._update_thread.finished.connect(self._clear_update_refs)

        self._update_thread.start()

    def _clear_update_refs(self):
        self._update_worker = None
        self._update_thread = None

    def _on_update_available(self, info):
        latest = info.get("latest_version") or ""
        if latest and latest == self.skip_update_version and not self._update_manual:
            return

        if self.auto_download_updates:
            self._download_and_install_update(info, required=False)
            return

        message = f"Update available: v{latest}"
        if info.get("release_notes"):
            message += f"\n\n{info.get('release_notes')}"

        box = QMessageBox(self)
        box.setWindowTitle("Update Available")
        box.setText(message)
        update_btn = box.addButton("Update Now", QMessageBox.AcceptRole)
        skip_btn = box.addButton("Skip", QMessageBox.RejectRole)
        self._style_message_box(box)
        box.exec()
        if box.clickedButton() == update_btn:
            self._download_and_install_update(info, required=False)
        elif box.clickedButton() == skip_btn and latest:
            self.skip_update_version = latest
            self.settings.setValue("skip_update_version", latest)

    def _on_update_required(self, info):
        latest = info.get("latest_version") or ""
        message = f"Update required to continue. Latest version: v{latest}"
        if info.get("release_notes"):
            message += f"\n\n{info.get('release_notes')}"
        box = QMessageBox(self)
        box.setWindowTitle("Update Required")
        box.setText(message)
        update_btn = box.addButton("Update Now", QMessageBox.AcceptRole)
        exit_btn = box.addButton("Exit", QMessageBox.RejectRole)
        self._style_message_box(box)
        box.exec()
        if box.clickedButton() == update_btn:
            self._download_and_install_update(info, required=True)
        else:
            self.close()

    def _on_no_update(self):
        if getattr(self, "_update_manual", False):
            self._show_message_dialog("Updates", "You're on the latest version.")

    def _on_update_error(self, msg):
        _log.error("Update error: %s", msg)
        if (
            not getattr(self, "_update_manual", False)
            and "404" in (msg or "")
        ):
            self.update_url_404_disabled = True
            self.update_url_404_value = (self.update_manifest_url or "").strip()
            self.settings.setValue("update_url_404_disabled", True)
            self.settings.setValue("update_url_404_value", self.update_url_404_value)
            self._show_toast(
                "Update URL returned 404. Auto update checks are paused "
                "until you change the update URL.",
                variant="warning",
                duration=5000
            )
            return
        if getattr(self, "_update_manual", False):
            self._show_message_dialog("Updates", f"Update check failed:\n{msg}", QMessageBox.Warning)

    def _download_and_install_update(self, info, required=False):
        url = info.get("installer_url") or ""
        if not url:
            self._show_message_dialog("Updates", "Installer URL is missing.", QMessageBox.Warning)
            return
        expected_hash = (info.get("installer_sha256") or "").strip()
        if not re.fullmatch(r"[0-9a-fA-F]{64}", expected_hash):
            self._show_message_dialog(
                "Updates",
                "Blocked update: installer hash is missing or invalid. "
                "Publish installer_sha256 in release metadata.",
                QMessageBox.Warning
            )
            return
        if not url.lower().startswith("https://"):
            self._show_message_dialog(
                "Updates",
                "For security, installer downloads require HTTPS.",
                QMessageBox.Warning
            )
            return

        dest_dir = os.path.join(app_data_dir(), "updates")
        ensure_dir(dest_dir)
        dest_path = os.path.join(dest_dir, UPDATE_INSTALLER_NAME)

        if self._update_download_thread and self._update_download_thread.isRunning():
            return

        self._update_progress_dialog = QProgressDialog(
            "Downloading update...",
            None,
            0,
            100,
            self
        )
        self._update_progress_dialog.setWindowTitle("Updates")
        self._update_progress_dialog.setWindowModality(Qt.ApplicationModal)
        self._update_progress_dialog.setCancelButton(None)
        self._update_progress_dialog.setAutoClose(True)
        self._update_progress_dialog.setAutoReset(True)
        self._style_message_box(self._update_progress_dialog)
        self._update_progress_dialog.show()

        self._update_download_thread = QThread()
        self._update_download_worker = UpdateDownloadWorker(
            url,
            dest_path,
            expected_sha256=expected_hash
        )
        self._update_download_worker.moveToThread(self._update_download_thread)

        self._update_download_thread.started.connect(self._update_download_worker.run)
        self._update_download_worker.progress.connect(self._on_update_download_progress)
        self._update_download_worker.completed.connect(self._on_update_download_complete)
        self._update_download_worker.error.connect(self._on_update_download_error)
        self._update_download_worker.finished.connect(self._update_download_thread.quit)
        self._update_download_worker.finished.connect(self._update_download_worker.deleteLater)
        self._update_download_thread.finished.connect(self._update_download_thread.deleteLater)
        self._update_download_thread.finished.connect(self._clear_update_download_refs)

        self._update_download_thread.start()

    def _on_update_download_progress(self, percent):
        if hasattr(self, "_update_progress_dialog") and self._update_progress_dialog:
            self._update_progress_dialog.setValue(percent)

    def _on_update_download_complete(self, path):
        if hasattr(self, "_update_progress_dialog") and self._update_progress_dialog:
            self._update_progress_dialog.close()
        try:
            os.startfile(path)
        except Exception:
            self._show_message_dialog(
                "Updates",
                f"Update downloaded to:\n{path}"
            )
        self.close()

    def _on_update_download_error(self, msg):
        if hasattr(self, "_update_progress_dialog") and self._update_progress_dialog:
            self._update_progress_dialog.close()
        _log.error("Update download error: %s", msg)
        self._show_message_dialog("Updates", f"Download failed:\n{msg}", QMessageBox.Warning)

    def _clear_update_download_refs(self):
        self._update_download_worker = None
        self._update_download_thread = None
        self._update_progress_dialog = None

    # ---------- COOKIES ----------
    def set_cookies_file(self):
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Select cookies.txt",
            "",
            "Cookies (*.txt);;All Files (*)"
        )
        if not path:
            return
        if not self._cookie_is_valid(path):
            self._show_error_dialog(
                "Cookies",
                "Invalid cookies file. Please select a valid cookies.txt "
                f"(max {MAX_COOKIE_FILE_BYTES // (1024 * 1024)} MB)."
            )
            return
        self.cookie_file = path
        self.settings.setValue("cookie_file", path)
        self.update_cookie_indicator()
        self._show_message_dialog("Cookies", "Cookies file set.")

    def clear_cookies_file(self):
        self.cookie_file = ""
        self.settings.remove("cookie_file")
        self.update_cookie_indicator()
        self._show_message_dialog("Cookies", "Cookies file cleared.")

    def _effective_cookie_file(self):
        if self._cookie_is_valid(self.cookie_file):
            return self.cookie_file
        default_cookie = os.path.join(os.getcwd(), "cookies.txt")
        if self._cookie_is_valid(default_cookie):
            return default_cookie
        return ""

    def update_cookie_indicator(self):
        effective = self._effective_cookie_file()
        for indicator, status in self.cookie_status_widgets:
            if effective:
                indicator.setStyleSheet("border-radius: 6px; background: #2ecc71;")
                status.setText("Loaded")
            else:
                indicator.setStyleSheet("border-radius: 6px; background: #f39c12;")
                status.setText("Not loaded")

    def _cookie_is_valid(self, path):
        if not path or not os.path.exists(path):
            return False
        try:
            size = os.path.getsize(path)
        except Exception:
            return False
        if size <= 0 or size > MAX_COOKIE_FILE_BYTES:
            return False
        return True

    def show_cookies_help(self):
        self._show_message_dialog(
            "How To Add Cookies",
            "1. Log in to YouTube in your browser.\n"
            "2. Export cookies for youtube.com as cookies.txt (Netscape format).\n"
            "3. In the app: Cookies -> Set Cookies File, then select cookies.txt.\n"
            "4. Or place cookies.txt next to the app and it will auto-load.\n"
            "5. The indicator turns green when cookies are loaded.\n\n"
            "Do not share your cookies file with anyone."
        )

    def closeEvent(self, event):
        has_downloads = bool(self._active_tasks or self._pending_tasks or self._paused_tasks)
        if self._tray and self._tray.isVisible() and not self._force_quit and has_downloads:
            self.hide()
            self._tray.showMessage(
                "YTDownloader",
                "Downloads are running in the tray.",
                QSystemTrayIcon.Information,
                1500
            )
            event.ignore()
            return
        for worker in (
            self._fetch_worker,
            self._update_worker,
            self._update_download_worker
        ):
            if worker and hasattr(worker, "request_cancel"):
                try:
                    worker.request_cancel()
                except Exception:
                    pass
        for worker in self._download_workers.values():
            if worker and hasattr(worker, "request_cancel"):
                try:
                    worker.request_cancel()
                except Exception:
                    pass
        self._persist_queue()
        event.accept()


