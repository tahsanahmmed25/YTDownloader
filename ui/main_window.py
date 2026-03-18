import sys
import os
import re
import time
import hashlib
import uuid
import shutil
from collections import deque
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
from PySide6.QtCore import Qt, Signal, QObject, QThread, QSettings, QSize, QUrl, QTimer, QStandardPaths, QPropertyAnimation, QParallelAnimationGroup, Property, QEasingCurve, QEvent, QPoint, Slot
from PySide6.QtGui import QIcon, QPixmap, QDesktopServices, QColor, QFont, QPalette, QAction

from ui_style import style, dark_style
from downloader import is_valid_youtube_url, is_playlist_url, normalize_youtube_url, get_playlist_entries
from history_manager import load_history, remove_history, clear_history
from app_config import (
    APP_NAME,
    APP_ORG,
    APP_VERSION,
    DEFAULT_UPDATE_MANIFEST_URL,
    LEGACY_UPDATE_MANIFEST_URL,
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
from ui.widgets import FadingTextButton, PasteButton, MarqueeLabel
from ui.dialogs import TermsDialog
from ui.pages import PagesMixin
from workers import UpdateWorker, UpdateDownloadWorker, FetchWorker, PlaylistWorker, DownloadWorker
import queue_manager

_log = get_logger()
MAX_COOKIE_FILE_BYTES = 5 * 1024 * 1024
THUMB_CACHE_DAYS = 30
LIBRARY_PAGE_SIZE = 6


def _default_download_dir():
    path = QStandardPaths.writableLocation(QStandardPaths.DownloadLocation)
    if path:
        return path
    home = os.path.expanduser("~")
    if home:
        return os.path.join(home, "Downloads")
    return os.getcwd()


 


class Downloader(QMainWindow, PagesMixin):
    dialog_requested = Signal(str, str, object)
    _TASK_STALL_SECONDS = 240
    _PLAYLIST_TASK_STALL_SECONDS = 900
    _FINALIZE_STALL_SECONDS = 420
    _CANCEL_GRACE_MS = 4500

    def __init__(self):
        super().__init__()

        self.setWindowTitle("Simple Youtube Downloader by Tahsan")
        self.resize(960, 544)
        self.setMinimumSize(920, 500)
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
        self.restricted_mode = self.settings.value("restricted_mode", False, type=bool)
        self.browser_auth_source = self.settings.value("browser_auth_source", "", type=str)
        self.browser_auth_profile = self.settings.value("browser_auth_profile", "", type=str)
        self.browser_auth_enabled = self.settings.value("browser_auth_enabled", False, type=bool)
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
        self.max_concurrent_downloads = max(1, min(10, self.max_concurrent_downloads))
        self.speed_limit_kbps = self.settings.value("speed_limit_kbps", 0, type=int)
        try:
            self.speed_limit_kbps = int(self.speed_limit_kbps)
        except Exception:
            self.speed_limit_kbps = 0
        if self.speed_limit_kbps < 0:
            self.speed_limit_kbps = 0

        self.proxy_url = self.settings.value("proxy_url", "", type=str)

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
        if self.update_manifest_url == LEGACY_UPDATE_MANIFEST_URL:
            self.update_manifest_url = DEFAULT_UPDATE_MANIFEST_URL
            self.settings.setValue("update_manifest_url", self.update_manifest_url)
            if self.update_url_404_value == LEGACY_UPDATE_MANIFEST_URL:
                self.update_url_404_value = ""
                self.update_url_404_disabled = False
                self.settings.setValue("update_url_404_value", "")
                self.settings.setValue("update_url_404_disabled", False)

        self._fetch_thread = None
        self._fetch_worker = None
        self._playlist_fetch_thread = None
        self._playlist_fetch_worker = None
        self._pending_playlist_request = None
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
        self._toast_anchor = None
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
        self._playlist_sessions = {}
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
        self.nav_history_btn = None
        self._open_dialogs = []
        self._reset_requested = False
        self._task_last_activity = {}
        self._active_fade_removals = 0
        self._task_watchdog = QTimer(self)
        self._task_watchdog.setInterval(2000)
        self._task_watchdog.timeout.connect(self._check_stalled_tasks)
        self._task_watchdog.start()
        self._cancel_grace_timer = QTimer(self)
        self._cancel_grace_timer.setSingleShot(True)
        self._cancel_grace_timer.timeout.connect(self._force_cleanup_active_tasks)
        self._library_nav_pulse_timer = QTimer(self)
        self._library_nav_pulse_timer.setInterval(650)
        self._library_nav_pulse_timer.timeout.connect(self._toggle_library_nav_pulse)
        self.dialog_requested.connect(self._show_dialog_on_ui_thread, Qt.QueuedConnection)

        self._build_ui()
        self._update_global_progress()
        self._update_downloads_header()
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
        self.page_history = self._build_history_page()
        self.page_options = self._build_options_page()
        self.page_cookies = self._build_cookies_page()
        self.page_about = self._build_about_page()

        self.pages.addWidget(self.page_downloader)
        self.pages.addWidget(self.page_library)
        self.pages.addWidget(self.page_history)
        self.pages.addWidget(self.page_options)
        self.pages.addWidget(self.page_cookies)
        self.pages.addWidget(self.page_about)
        self.pages.currentChanged.connect(self._on_page_changed)

        self._add_nav_button(sidebar_layout, "Downloader", self.page_downloader, True)
        self.nav_library_btn = self._add_nav_button(sidebar_layout, "Library", self.page_library, False)
        self.nav_history_btn = self._add_nav_button(sidebar_layout, "History", self.page_history, False)
        self._add_nav_button(sidebar_layout, "Preferences", self.page_options, False)
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
        btn.setFocusPolicy(Qt.NoFocus)
        btn.setCursor(Qt.ArrowCursor)
        btn.clicked.connect(lambda: self.pages.setCurrentWidget(page))
        self.nav_group.addButton(btn)
        layout.addWidget(btn)
        return btn

    def _apply_shadow(self, widget, blur, alpha, y_offset):
        effect = QGraphicsDropShadowEffect(self)
        effect.setBlurRadius(blur)
        soft_alpha = max(24, min(120, int(alpha * 0.72)))
        effect.setColor(QColor(18, 31, 48, soft_alpha))
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
        if self._toast_anchor and self._toast_anchor.isVisible():
            anchor_top_left = self._toast_anchor.mapTo(root, QPoint(0, 0))
            x = anchor_top_left.x() + self._toast_anchor.width() + 10
            y = anchor_top_left.y() + (self._toast_anchor.height() - self.toast.height()) // 2
            x = max(margin, min(x, root.width() - self.toast.width() - margin))
            y = max(margin, min(y, root.height() - self.toast.height() - margin))
        else:
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
        self._reset_requested = False
        self._playlist_sessions.clear()
        self._clear_non_active_downloads()
        self._request_cancel_all_downloads("Stopping...")
        self.close()

    def _show_toast(self, message, variant="info", duration=3000, anchor_widget=None):
        if not self.toast or not self.toast_label:
            return
        if self._toast_active:
            self._toast_queue.append((message, variant, duration, anchor_widget))
            return
        self._toast_active = True
        self._toast_anchor = anchor_widget
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
            self._toast_anchor = None
            self._toast_active = False
            if self._toast_queue:
                next_msg, next_variant, next_duration, next_anchor = self._toast_queue.popleft()
                QTimer.singleShot(
                    60,
                    lambda: self._show_toast(next_msg, next_variant, next_duration, next_anchor)
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
            self._sync_downloads_panel_height()
            panel_cap = max(260, self.height() - 90)
            target = max(136, min(panel_cap, self.downloads_panel.sizeHint().height()))
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
            # Keep the downloads card visible in Library with empty-state text.
            if hasattr(self, "library_empty_label"):
                self.downloads_panel.setVisible(True)
                self._sync_downloads_panel_height()
                return
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

    def _thread_is_running(self, thread):
        if thread is None:
            return False
        try:
            return bool(thread.isRunning())
        except RuntimeError:
            return False
        except Exception:
            return False

    def _has_running_download_threads(self):
        for thread in list(self._download_threads.values()):
            if self._thread_is_running(thread):
                return True
        return False

    def _flash_library_nav(self):
        self._update_library_nav_state()

    def _on_page_changed(self, _index):
        self._update_library_nav_state()

    def _toggle_library_nav_pulse(self):
        if not getattr(self, "nav_library_btn", None):
            return
        current = bool(self.nav_library_btn.property("pulse"))
        self.nav_library_btn.setProperty("pulse", not current)
        self.nav_library_btn.style().unpolish(self.nav_library_btn)
        self.nav_library_btn.style().polish(self.nav_library_btn)

    def _make_cookie_status_row(self, trailing_widget=None):
        row = QHBoxLayout()
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(8)
        row.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        dot = QLabel()
        dot.setFixedSize(12, 12)
        dot.setStyleSheet("border-radius: 6px; background: #f39c12;")
        status = QLabel("Not loaded")
        status.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Preferred)
        row.addWidget(dot)
        row.addWidget(status)
        row.addStretch(1)
        if trailing_widget is not None:
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
        frame.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        frame.setMinimumWidth(0)
        layout = QVBoxLayout(frame)
        layout.setContentsMargins(10, 8, 10, 8)
        layout.setSpacing(4)

        top_row = QHBoxLayout()
        top_row.setSpacing(8)
        title_label = MarqueeLabel(title)
        title_label.setObjectName("LibraryTitle")
        title_label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        title_label.setMinimumWidth(0)
        title_label.setMinimumHeight(22)
        status_label = QLabel("Downloading...")
        status_label.setObjectName("MutedText")
        status_label.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        status_label.setMinimumWidth(90)
        status_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
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
        pause_btn.setFixedWidth(110)
        pause_btn.setFixedHeight(30)
        pause_btn.clicked.connect(self._on_pause_button_clicked)
        cancel_btn = QPushButton("Cancel")
        cancel_btn.setObjectName("GhostButton")
        cancel_btn.setFixedWidth(110)
        cancel_btn.setFixedHeight(30)
        cancel_btn.clicked.connect(self._on_cancel_button_clicked)
        open_btn = QPushButton("Open Folder")
        open_btn.setObjectName("GhostButton")
        open_btn.setFixedWidth(110)
        open_btn.setFixedHeight(30)
        open_btn.setVisible(False)
        open_btn.clicked.connect(lambda: self._open_folder(self.download_dir))
        top_row.addWidget(title_label, 1)
        top_row.addWidget(status_label)
        top_row.addWidget(status_icon)
        layout.addLayout(top_row)

        progress = QProgressBar()
        progress.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        progress.setMinimumWidth(0)
        progress.setValue(0)
        layout.addWidget(progress)

        info_row = QHBoxLayout()
        info_row.setSpacing(6)
        speed_label = QLabel("Speed: -")
        size_label = QLabel("Downloaded: -")
        speed_label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        speed_label.setMinimumWidth(0)
        speed_label.setMaximumWidth(160)
        size_label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        size_label.setMinimumWidth(0)
        size_label.setMaximumWidth(260)
        info_row.addWidget(speed_label)
        info_row.addSpacing(8)
        info_row.addWidget(size_label)
        layout.addLayout(info_row)

        actions_row = QHBoxLayout()
        actions_row.setSpacing(6)
        actions_row.addStretch(1)
        actions_row.addWidget(pause_btn)
        actions_row.addWidget(cancel_btn)
        actions_row.addWidget(open_btn)
        layout.addLayout(actions_row)

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
            "cancel_btn": cancel_btn,
            "open_btn": open_btn
        }
        frame._download_item = item
        return item

    def _on_pause_button_clicked(self):
        btn = self.sender()
        task_id = btn.property("task_id") if btn else None
        if not task_id:
            return
        self._on_task_pause_clicked(task_id)

    def _on_cancel_button_clicked(self):
        btn = self.sender()
        task_id = btn.property("task_id") if btn else None
        if not task_id:
            return
        self._on_task_cancel_clicked(task_id)

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
        if item.get("cancel_btn"):
            item["cancel_btn"].setEnabled(True)
            item["cancel_btn"].setVisible(True)
            item["cancel_btn"].setText("Cancel")
        item["open_btn"].setVisible(False)

    def _show_error_dialog(self, title, message):
        _log.warning("%s: %s", title, message)
        self._show_dialog_async(title, message, QMessageBox.Warning)

    def _show_message_dialog(self, title, message, icon=QMessageBox.Information):
        self._show_dialog_async(title, message, icon)

    def _show_dialog_async(self, title, message, icon):
        icon_obj = icon if icon is not None else QMessageBox.Warning
        self.dialog_requested.emit(title or "Message", message or "", icon_obj)

    @Slot(str, str, object)
    def _show_dialog_on_ui_thread(self, title, message, icon_obj):
        box = QMessageBox(self)
        box.setAttribute(Qt.WA_DeleteOnClose, True)
        try:
            if isinstance(icon_obj, QMessageBox.Icon):
                box.setIcon(icon_obj)
            elif hasattr(icon_obj, "value"):
                box.setIcon(QMessageBox.Icon(icon_obj.value))
            elif isinstance(icon_obj, int):
                box.setIcon(QMessageBox.Icon(icon_obj))
            else:
                box.setIcon(QMessageBox.Warning)
        except Exception:
            box.setIcon(QMessageBox.Warning)
        msg = message or ""
        box.setWindowTitle(title or "Message")
        if "Traceback" in msg or len(msg) > 380:
            first_line = msg.splitlines()[0] if msg else "Something went wrong."
            box.setText(first_line)
            box.setDetailedText(msg)
        else:
            box.setText(msg)
        if (title or "") == "How To Add Cookies":
            box.setMinimumWidth(680)
            box.setMinimumHeight(460)
        self._style_message_box(box)
        self._open_dialogs.append(box)
        box.finished.connect(lambda _=0, b=box: self._open_dialogs.remove(b) if b in self._open_dialogs else None)
        box.open()

    def _show_message_dialog_blocking(self, title, message, icon=QMessageBox.Information):
        box = QMessageBox(self)
        box.setIcon(icon)
        box.setWindowTitle(title)
        box.setText(message)
        self._style_message_box(box)
        box.exec()

    def _style_message_box(self, box):
        if self.dark_mode:
            box.setStyleSheet(
                "QDialog, QMessageBox { background: #1f2633; color: #e6edf3; }"
                "QLabel { color: #e6edf3; }"
                "QTextEdit { background: #202939; color: #e6edf3; "
                "border: 1px solid rgba(230,237,243,0.2); border-radius: 8px; }"
                "QPushButton { background: rgba(25,32,45,0.85); "
                "border: 1px solid rgba(230,237,243,0.2); "
                "border-radius: 8px; padding: 6px 12px; color: #e6edf3; }"
                "QPushButton:hover { background: rgba(79,141,255,0.18); "
                "border: 1px solid rgba(79,141,255,0.55); }"
            )
        else:
            box.setStyleSheet(
                "QDialog, QMessageBox { background: #fdfdfe; color: #1f2a36; }"
                "QLabel { color: #1f2a36; }"
                "QTextEdit { background: #ffffff; color: #1f2a36; "
                "border: 1px solid rgba(31,42,54,0.2); border-radius: 8px; }"
                "QPushButton { background: rgba(253,253,254,0.92); "
                "border: 1px solid rgba(31,42,54,0.2); "
                "border-radius: 8px; padding: 6px 12px; color: #1f2a36; }"
                "QPushButton:hover { background: rgba(79,141,255,0.12); "
                "border: 1px solid rgba(79,141,255,0.45); }"
            )

    def _apply_theme(self):
        self.setStyleSheet(dark_style if self.dark_mode else style)
        self._apply_combo_popup_theme()

    def _apply_combo_popup_theme(self):
        combo = getattr(self, "browser_auth_combo", None)
        if not combo:
            return
        view = combo.view()
        if not view:
            return
        if self.dark_mode:
            view.setStyleSheet(
                "QListView {"
                " background: #1f2633;"
                " border: 1px solid rgba(230, 237, 243, 0.2);"
                " color: #e6edf3;"
                " selection-background-color: rgba(79, 141, 255, 0.3);"
                " selection-color: #ffffff;"
                "}"
                "QListView::item { padding: 6px 10px; }"
            )
        else:
            view.setStyleSheet(
                "QListView {"
                " background: #f7f9fc;"
                " border: 1px solid rgba(31, 42, 54, 0.2);"
                " color: #1f2a36;"
                " selection-background-color: rgba(79, 141, 255, 0.22);"
                " selection-color: #1f2a36;"
                "}"
                "QListView::item { padding: 6px 10px; }"
            )

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
        
        # Always include Auto (Best)
        options = [self._default_qualities[0]] # "Auto (Best)"
        
        if available:
            # Add all available qualities that aren't already represented by "Auto"
            for opt in available:
                if opt not in options:
                    options.append(opt)
        
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
        self._reorder_download_rows()
        total = self._layout_widget_count(self.active_downloads_layout) + self._layout_widget_count(self.completed_downloads_layout)
        self.downloads_header.setText(f"Downloads ({total})")
        if hasattr(self, "library_empty_label") and self.library_empty_label:
            self.library_empty_label.setVisible(total == 0)
        if hasattr(self, "downloads_panel") and self.downloads_panel:
            self.downloads_panel.setVisible(True)
        if hasattr(self, "reset_btn_downloads") and self.reset_btn_downloads:
            self.reset_btn_downloads.setEnabled(total > 0)
        self._sync_downloads_panel_height(total)
        self._update_library_nav_state()

    def _reorder_download_rows(self):
        if not hasattr(self, "active_downloads_layout") or self.active_downloads_layout is None:
            return
        if getattr(self, "_active_fade_removals", 0) > 0:
            return
        pending_idx = {
            task.get("id"): i
            for i, task in enumerate(self._pending_tasks)
        }
        active_idx = {
            task_id: i
            for i, task_id in enumerate(self._active_tasks.keys())
        }
        paused_idx = {
            task_id: i
            for i, task_id in enumerate(self._paused_tasks.keys())
        }

        tasks = []
        seen = set()
        for task in self._active_tasks.values():
            tid = task.get("id")
            if tid and tid not in seen:
                tasks.append(task)
                seen.add(tid)
        for task in self._pending_tasks:
            tid = task.get("id")
            if tid and tid not in seen:
                tasks.append(task)
                seen.add(tid)
        for task in self._paused_tasks.values():
            tid = task.get("id")
            if tid and tid not in seen:
                tasks.append(task)
                seen.add(tid)

        def _sort_key(task):
            tid = task.get("id")
            state = (task.get("state") or "").lower()
            if state in ("active", "pausing", "finalizing", "stalled"):
                return (0, active_idx.get(tid, 0))
            if state == "queued":
                return (1, pending_idx.get(tid, 0))
            if state == "paused":
                return (2, paused_idx.get(tid, 0))
            return (3, 0)

        tasks.sort(key=_sort_key)

        widgets = []
        while self.active_downloads_layout.count():
            item = self.active_downloads_layout.takeAt(0)
            if not item:
                continue
            w = item.widget()
            if w:
                widgets.append(w)
                try:
                    w.setParent(None)
                except Exception:
                    pass

        for task in tasks:
            item = task.get("item") or {}
            frame = item.get("frame")
            if frame:
                try:
                    self.active_downloads_layout.addWidget(frame)
                except Exception:
                    pass

        # Any detached widgets not referenced by tasks go back to the pool.
        for w in widgets:
            keep = False
            for task in tasks:
                if (task.get("item") or {}).get("frame") is w:
                    keep = True
                    break
            if not keep and hasattr(w, "_download_item"):
                if w._download_item not in self._download_item_pool:
                    self._download_item_pool.append(w._download_item)
            elif not keep:
                w.deleteLater()

    def _sync_downloads_panel_height(self, total_items=None):
        if not hasattr(self, "downloads_scroll") or not hasattr(self, "downloads_panel"):
            return
        if total_items is None:
            total_items = self._layout_widget_count(self.active_downloads_layout) + self._layout_widget_count(self.completed_downloads_layout)
        max_visible = max(260, self.height() - 120)
        desired = 132 + max(0, total_items) * 118
        if total_items <= 0:
            scroll_h = 160
        else:
            scroll_h = min(max_visible, desired)

        self.downloads_scroll.setMinimumHeight(min(scroll_h, 160))
        self.downloads_scroll.setMaximumHeight(max_visible)
        self.downloads_scroll.setFixedHeight(scroll_h)

        if self.downloads_panel.isVisible():
            panel_cap = max(320, self.height() - 90)
            panel_h = max(136, min(panel_cap, self.downloads_panel.sizeHint().height()))
            self.downloads_panel.setMaximumHeight(panel_h)

    def _update_library_nav_state(self):
        if not getattr(self, "nav_library_btn", None):
            return
        active = bool(self._active_tasks or self._pending_tasks or self._paused_tasks)
        in_library = self.pages.currentWidget() == self.page_library
        should_pulse = active and not in_library

        self.nav_library_btn.setProperty("activeDownloads", False)
        if should_pulse:
            if not self._library_nav_pulse_timer.isActive():
                self.nav_library_btn.setProperty("pulse", True)
                self.nav_library_btn.style().unpolish(self.nav_library_btn)
                self.nav_library_btn.style().polish(self.nav_library_btn)
                self._library_nav_pulse_timer.start()
        else:
            if self._library_nav_pulse_timer.isActive():
                self._library_nav_pulse_timer.stop()
            self.nav_library_btn.setProperty("pulse", False)
            self.nav_library_btn.style().unpolish(self.nav_library_btn)
            self.nav_library_btn.style().polish(self.nav_library_btn)

    def _touch_task_activity(self, task_id):
        if not task_id:
            return
        self._task_last_activity[task_id] = time.time()

    def _clear_task_activity(self, task_id):
        if not task_id:
            return
        self._task_last_activity.pop(task_id, None)

    def _recycle_task_frame(self, task):
        if not task:
            return
        item = task.get("item") or {}
        frame = item.get("frame")
        if not frame:
            return
        for layout in (
            getattr(self, "active_downloads_layout", None),
            getattr(self, "completed_downloads_layout", None)
        ):
            if not layout:
                continue
            try:
                layout.removeWidget(frame)
            except Exception:
                pass
        try:
            frame.setParent(None)
        except Exception:
            pass
        if hasattr(frame, "_download_item") and frame._download_item not in self._download_item_pool:
            self._download_item_pool.append(frame._download_item)

    def _remove_active_item_with_fade(self, task):
        if not task:
            return
        item = task.get("item") or {}
        frame = item.get("frame")
        if not frame:
            return
        if getattr(frame, "_fade_remove_anim", None):
            return
        frame._fading_out = True
        self._active_fade_removals += 1
        start_h = frame.height()
        if start_h <= 0:
            try:
                start_h = frame.sizeHint().height()
            except Exception:
                start_h = 96
        if start_h <= 0:
            start_h = 96
        frame.setMaximumHeight(start_h)
        effect = QGraphicsOpacityEffect(frame)
        effect.setOpacity(1.0)
        frame.setGraphicsEffect(effect)
        fade_anim = QPropertyAnimation(effect, b"opacity", self)
        fade_anim.setDuration(190)
        fade_anim.setStartValue(1.0)
        fade_anim.setEndValue(0.0)
        fade_anim.setEasingCurve(QEasingCurve.OutCubic)

        slide_anim = QPropertyAnimation(frame, b"maximumHeight", self)
        slide_anim.setDuration(220)
        slide_anim.setStartValue(start_h)
        slide_anim.setEndValue(0)
        slide_anim.setEasingCurve(QEasingCurve.InOutCubic)

        group = QParallelAnimationGroup(self)
        group.addAnimation(fade_anim)
        group.addAnimation(slide_anim)

        if not hasattr(self, "_fading_tasks"):
            self._fading_tasks = []
        self._fading_tasks.append(task)

        def _finalize():
            try:
                frame.setGraphicsEffect(None)
            except Exception:
                pass
            try:
                frame.setMaximumHeight(16777215)
            except Exception:
                pass
            if self.active_downloads_layout:
                try:
                    self.active_downloads_layout.removeWidget(frame)
                except Exception:
                    pass
            try:
                frame.setParent(None)
            except Exception:
                pass
            if hasattr(frame, "_download_item") and frame._download_item not in self._download_item_pool:
                self._download_item_pool.append(frame._download_item)
            frame._fading_out = False
            self._active_fade_removals = max(0, self._active_fade_removals - 1)
            self._update_downloads_header()
            frame._fade_remove_anim = None
            if hasattr(self, "_fading_tasks") and task in self._fading_tasks:
                self._fading_tasks.remove(task)

        group.finished.connect(_finalize)
        frame._fade_remove_anim = group
        group.start()

    def _clear_non_active_downloads(self):
        for task in list(self._pending_tasks):
            self._clear_task_activity(task.get("id"))
            self._recycle_task_frame(task)
        self._pending_tasks.clear()
        for task in list(self._paused_tasks.values()):
            self._clear_task_activity(task.get("id"))
            self._recycle_task_frame(task)
        self._paused_tasks.clear()
        self._persist_queue()
        self._update_downloads_header()
        self._update_global_progress()

    def _mark_task_failed(self, task_id):
        task = self._active_tasks.pop(task_id, None)
        self._clear_task_activity(task_id)
        if not task:
            return False
        payload = task.get("payload") or {}
        session_id = payload.get("playlist_session_id") or ""
        item = task.get("item") or {}
        try:
            if item.get("status"):
                item["status"].setText("")
            if item.get("status_icon"):
                self._set_status_icon(item["status_icon"], "failed", "✕")
                self._animate_status_icon(item)
            if item.get("pause_btn"):
                item["pause_btn"].setText("Failed")
                item["pause_btn"].setDisabled(True)
            if item.get("cancel_btn"):
                item["cancel_btn"].setText("Failed")
                item["cancel_btn"].setDisabled(True)
                item["cancel_btn"].setVisible(False)
            if item.get("frame") and self.active_downloads_layout:
                self.active_downloads_layout.removeWidget(item["frame"])
            if item.get("frame") and self.completed_downloads_layout:
                self.completed_downloads_layout.insertWidget(0, item["frame"])
        except Exception:
            _log.exception("UI update failed while marking task %s failed", task_id)
        self._update_downloads_header()
        self._update_global_progress()
        self._persist_queue()
        if session_id:
            self._pump_playlist_session(session_id)
        else:
            self._start_next_downloads()
        self._maybe_finalize_reset()
        return True

    def _request_cancel_all_downloads(self, reason_text=""):
        for worker in list(self._download_workers.values()):
            if worker and hasattr(worker, "request_cancel"):
                try:
                    worker.request_cancel()
                except Exception:
                    pass
        for task in self._active_tasks.values():
            item = task.get("item") or {}
            status = item.get("status")
            pause_btn = item.get("pause_btn")
            cancel_btn = item.get("cancel_btn")
            if status:
                status.setText(reason_text or "Cancelling...")
            if pause_btn:
                pause_btn.setEnabled(False)
            if cancel_btn:
                cancel_btn.setEnabled(False)
        if self._active_tasks:
            self._cancel_grace_timer.start(self._CANCEL_GRACE_MS)

    def _force_cleanup_active_tasks(self):
        stale_ids = list(self._active_tasks.keys())
        if not stale_ids:
            self._maybe_finalize_reset()
            return
        for task_id in stale_ids:
            worker = self._download_workers.get(task_id)
            if worker and hasattr(worker, "request_cancel"):
                try:
                    worker.request_cancel()
                except Exception:
                    pass
            thread = self._download_threads.get(task_id)
            if self._thread_is_running(thread):
                try:
                    thread.quit()
                except Exception:
                    pass
            self._mark_task_failed(task_id)
        if self._reset_requested:
            self._show_toast("Active downloads were stopped.", variant="info")
        else:
            self._show_error_dialog(
                "Error",
                "Some downloads were force-stopped because they were not responding."
            )

    def _check_stalled_tasks(self):
        try:
            if not self._active_tasks:
                return
            now = time.time()
            stale = []
            for task_id, task in list(self._active_tasks.items()):
                state = (task.get("state") or "").lower()
                if state == "stalled":
                    continue
                last = self._task_last_activity.get(task_id)
                if last is None:
                    continue
                payload = task.get("payload") or {}
                is_playlist_task = bool(payload.get("download_playlist"))
                if not is_playlist_task and payload.get("playlist_session_id"):
                    is_playlist_task = True
                if state == "finalizing":
                    base = (
                        self._PLAYLIST_TASK_STALL_SECONDS
                        if is_playlist_task
                        else self._TASK_STALL_SECONDS
                    )
                    threshold = max(self._FINALIZE_STALL_SECONDS, base)
                else:
                    threshold = (
                        self._PLAYLIST_TASK_STALL_SECONDS
                        if is_playlist_task
                        else self._TASK_STALL_SECONDS
                    )
                if (now - last) >= threshold:
                    stale.append(task_id)
            if not stale:
                return
            for task_id in stale:
                task = self._active_tasks.get(task_id)
                if task:
                    task["state"] = "stalled"
                    item = task.get("item") or {}
                    pause_btn = item.get("pause_btn")
                    if pause_btn:
                        pause_btn.setEnabled(False)
                    status = item.get("status")
                    if status:
                        status.setText("Not responding...")
                    payload = task.get("payload") or {}
                    is_playlist_task = bool(payload.get("download_playlist"))
                    if not is_playlist_task and payload.get("playlist_session_id"):
                        is_playlist_task = True
                else:
                    is_playlist_task = False
                threshold = (
                    self._PLAYLIST_TASK_STALL_SECONDS
                    if is_playlist_task
                    else self._TASK_STALL_SECONDS
                )
                _log.warning("Task %s stalled for %ss; cancelling.", task_id, threshold)
                worker = self._download_workers.get(task_id)
                if worker and hasattr(worker, "request_cancel"):
                    try:
                        worker.request_cancel()
                    except Exception:
                        pass
                self._mark_task_failed(task_id)
            self._show_toast(
                "A stalled download was skipped. Continuing with next items.",
                variant="warning",
                duration=2600,
                anchor_widget=self.nav_library_btn
            )
        except Exception:
            _log.exception("Unhandled exception in _check_stalled_tasks")

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
        if not self.restricted_mode:
            return False
        return bool(self._effective_cookie_file() or self._effective_browser_auth())

    def _maybe_show_cookie_reminder(self):
        if not self.restricted_mode:
            return
        if self._cookies_loaded():
            return
        self._show_toast(
            "Restricted Mode is on, but no browser auth is connected. "
            "Go to Cookies tab to connect your browser.",
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
                shell=False,
                creationflags=0x08000000 # subprocess.CREATE_NO_WINDOW
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

    def _fit_cover_pixmap(self, pixmap, target_size):
        if pixmap.isNull():
            return self._placeholder_pixmap(target_size)
        scaled = pixmap.scaled(
            target_size,
            Qt.KeepAspectRatioByExpanding,
            Qt.SmoothTransformation
        )
        x = max((scaled.width() - target_size.width()) // 2, 0)
        y = max((scaled.height() - target_size.height()) // 2, 0)
        return scaled.copy(x, y, target_size.width(), target_size.height())

    def _set_preview_thumbnail(self, pixmap):
        if not hasattr(self, "thumbnail") or not self.thumbnail:
            return
        target = self.thumbnail.size()
        self.thumbnail.setPixmap(self._fit_cover_pixmap(pixmap, target))

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
            self._set_combo_items(self.format_combo, ["Auto"])
            self._set_combo_items(self.quality, ["Auto (Best)"])
            self.format_combo.setEnabled(False)
            self.quality.setEnabled(False)
        else:
            self.url_input.setPlaceholderText("Paste YouTube link...")
            self.format_combo.setEnabled(self._info_ready and self.format_combo.count() > 0)
            self.quality.setEnabled(self._info_ready and self.quality.count() > 0)
        self._on_url_changed("")

    def refresh_library(self):
        self._clear_layout(self.library_layout)
        history = load_history()
        invalid_ids = [item.get("id") for item in history if not (item.get("filepath") or "").strip()]
        for item_id in invalid_ids:
            if item_id:
                remove_history(item_id)
        if invalid_ids:
            history = load_history()
        history = sorted(
            history,
            key=lambda x: (x.get("added_at") or ""),
            reverse=True
        )
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
        # Widgets inside library_layout are deleted by _clear_layout().
        # Never reuse a previous cached QPushButton reference across renders.
        self._library_load_more_btn = None
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
            try:
                self.library_layout.addWidget(self._library_load_more_btn)
            except RuntimeError:
                # Fallback: recreate if Qt already deleted the cached instance.
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
        layout.setContentsMargins(6, 6, 6, 6)
        layout.setSpacing(8)

        thumb_btn = QToolButton()
        thumb_btn.setObjectName("ThumbButton")
        thumb_btn.setToolButtonStyle(Qt.ToolButtonIconOnly)
        thumb_btn.setFixedSize(100, 56)
        thumb_btn.setIconSize(QSize(100, 56))
        thumb_btn.setCursor(Qt.PointingHandCursor)
        thumb_btn.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)

        thumb_path = item.get("thumb_path") or ""
        if thumb_path and os.path.exists(thumb_path):
            pix = QPixmap(thumb_path)
        else:
            pix = self._placeholder_pixmap(QSize(100, 56))
        thumb_btn.setIcon(QIcon(self._fit_cover_pixmap(pix, QSize(100, 56))))
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
        if self._thread_is_running(self._fetch_thread):
            return
        quality = self.quality.currentText().strip() or "Auto (Best)"
        container = (self.format_combo.currentText().strip() or "auto").lower()

        self._info_ready = False
        self._active_url = normalize_youtube_url(url, keep_playlist=is_playlist)
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

        cookiefile = self._effective_cookie_file()
        browser_auth = self._effective_browser_auth()

        self._fetch_thread = QThread()
        self._fetch_worker = FetchWorker(
            url,
            cookiefile,
            browser_auth=browser_auth,
            allow_playlist=is_playlist,
            quality=quality,
            container=container
        )
        self._fetch_worker.moveToThread(self._fetch_thread)

        self._fetch_thread.started.connect(self._fetch_worker.run)
        self._fetch_worker.info_ready.connect(self.on_info_ready, Qt.QueuedConnection)
        self._fetch_worker.error.connect(self.on_fetch_error, Qt.QueuedConnection)
        self._fetch_worker.cookie_lock.connect(self._on_cookie_lock, Qt.QueuedConnection)
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
        try:
            self.url_input.setCursorPosition(0)
            self.url_input.deselect()
        except Exception:
            pass
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
            self._set_preview_thumbnail(pix)
        else:
            self.thumbnail.setPixmap(self._placeholder_pixmap(self.thumbnail.size()))

        self._apply_format_options(available_formats)
        self._apply_quality_options(available_qualities)
        self._apply_subtitle_options(available_subtitles)
        if self._active_is_playlist:
            self._set_combo_items(self.format_combo, ["Auto"])
            self._set_combo_items(self.quality, ["Auto (Best)"])
            self.format_combo.setEnabled(False)
            self.quality.setEnabled(False)
        if (not self._active_is_playlist) and (not available_formats or not available_qualities):
            if not self._cookies_loaded():
                self._show_toast(
                    "Limited format/quality info detected. "
                    "Add cookies in the Cookies tab for better availability.",
                    variant="warning",
                    duration=3200
                )
        self._info_ready = True
        self.download_btn.setEnabled(True)
        self._set_config_enabled(True)
        self._sync_download_button_text()

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
        self._sync_download_button_text()

    def _on_cookie_lock(self, browser_name, msg):
        self._handle_browser_lock_restart(browser_name, msg, retry_cb=self._fetch_info)

    def _on_download_cookie_lock(self, task_id, browser_name, msg):
        # We don't autostart because the task is now probably failed/stopped
        self._handle_browser_lock_restart(browser_name, msg, retry_cb=None)

    def _handle_browser_lock_restart(self, browser_name, details, retry_cb=None):
        _log.warning("Browser lock detected for %s: %s", browser_name, details)
        from PySide6.QtWidgets import QMessageBox
        msg_box = QMessageBox(self)
        display_name = browser_name.capitalize()
        msg_box.setWindowTitle(f"{display_name} Locked")
        msg_box.setText(f"YouTube requires cookies from {display_name}, but the browser is currently open and locking them.")
        msg_box.setInformativeText(f"Would you like to close {display_name} now to proceed? (Make sure to save your work first!)")
        msg_box.setStandardButtons(QMessageBox.Yes | QMessageBox.No)
        msg_box.setDefaultButton(QMessageBox.Yes)
        msg_box.setIcon(QMessageBox.Warning)
        
        ret = msg_box.exec()
        if ret == QMessageBox.Yes:
            if self._kill_browser(browser_name):
                display_name = browser_name.capitalize()
                self._show_toast(f"{display_name} closed. Retrying...", variant="success")
                if retry_cb:
                    QTimer.singleShot(1500, retry_cb)
            else:
                display_name = browser_name.capitalize()
                self._show_error_dialog("Error", f"Could not automatically close {display_name}. Please close it manually and try again.")
        else:
            display_name = browser_name.capitalize()
            self.on_fetch_error(f"Authentication failed because {display_name} is open.")

    def _kill_browser(self, name):
        try:
            name_lower = name.lower()
            if "chrome" in name_lower:
                proc_name = "chrome.exe"
            elif "edge" in name_lower:
                proc_name = "msedge.exe"
            elif "firefox" in name_lower:
                proc_name = "firefox.exe"
            elif "brave" in name_lower:
                proc_name = "brave.exe"
            elif "opera" in name_lower:
                proc_name = "opera.exe"
            elif "vivaldi" in name_lower:
                proc_name = "vivaldi.exe"
            else:
                # Fallback: try the name directly
                proc_name = f"{name_lower}.exe"
            
            import subprocess
            subprocess.run(["taskkill", "/F", "/IM", proc_name], capture_output=True, creationflags=0x08000000)
            return True
        except Exception as e:
            _log.error("Failed to kill browser %s: %s", name, e)
            return False

    # ---------- DOWNLOAD ----------
    def start_download(self):
        try:
            _log.info("start_download clicked")
            url = (self._active_url or "").strip()
            quality = self.quality.currentText().strip() or "Auto (Best)"
            container = (self.format_combo.currentText().strip() or "auto").lower()
            cookiefile = self._effective_cookie_file()
            browser_auth = self._effective_browser_auth()
            _log.info(
                "start_download entered url=%s playlist=%s restricted=%s",
                url,
                self._active_is_playlist,
                self.restricted_mode
            )

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
                self._show_error_dialog("Error", "Not enough free disk space for this download.")
                return

            rate_limit = None
            if self.speed_limit_kbps and self.speed_limit_kbps > 0:
                rate_limit = int(self.speed_limit_kbps) * 1024

            if self._active_is_playlist:
                self._start_playlist_download(
                    url,
                    subtitles=subtitles,
                    subtitles_langs=subtitles_langs,
                    embed_subs=embed_subs,
                    rate_limit=rate_limit,
                    cookiefile=cookiefile,
                    browser_auth=browser_auth
                )
                self._info_ready = False
                self._sync_download_button_text()
                return

            payload = {
                "url": url,
                "quality": quality,
                "container": container,
                "subtitles": subtitles,
                "subtitles_langs": subtitles_langs,
                "embed_subs": embed_subs,
                "download_playlist": False,
                "playlist_start": 1,
                "playlist_end": 0,
                "playlist_batch_size": 0,
                "skip_unavailable": True,
                "playlist_session_id": "",
                "rate_limit": rate_limit,
                "download_dir": self.download_dir,
                "cookiefile": cookiefile,
                "browser_auth": browser_auth,
                "proxy": self.proxy_url,
            }

            title_text = self.title.text().replace("Title: ", "").strip()
            if not title_text or title_text == "-":
                title_text = url

            self._queue_download(payload, title_text)
            self._info_ready = False
            self._sync_download_button_text()

        except Exception:
            import traceback
            tb = traceback.format_exc()
            _log.exception("Unhandled exception in start_download")
            self._show_error_dialog("Download Start Error", tb)

    def _playlist_task_count(self, session_id):
        if not session_id:
            return 0
        count = 0
        for task in self._pending_tasks:
            if (task.get("payload") or {}).get("playlist_session_id") == session_id:
                count += 1
        for task in self._active_tasks.values():
            if (task.get("payload") or {}).get("playlist_session_id") == session_id:
                count += 1
        for task in self._paused_tasks.values():
            if (task.get("payload") or {}).get("playlist_session_id") == session_id:
                count += 1
        return count

    def _enqueue_playlist_items(self, session_id):
        session = self._playlist_sessions.get(session_id)
        if not session:
            return 0
        added = 0
        visible_limit = 5
        in_system = self._playlist_task_count(session_id)
        total = len(session["entries"])
        while in_system < visible_limit and session["next_index"] < total:
            entry = session["entries"][session["next_index"]]
            session["next_index"] += 1
            in_system += 1
            added += 1

            payload = dict(session["payload_template"])
            payload["url"] = entry.get("url") or ""
            payload["playlist_session_id"] = session_id
            payload["playlist_item_index"] = session["next_index"]
            payload["playlist_item_total"] = total
            title_text = entry.get("title") or payload["url"] or f"Playlist item {session['next_index']}"
            self._queue_download(payload, title_text, announce=False, autostart=False)
        return added

    def _pump_playlist_session(self, session_id):
        if not session_id:
            self._start_next_downloads()
            return
        session = self._playlist_sessions.get(session_id)
        if not session:
            self._start_next_downloads()
            return
        playlist_title = session.get("title") or "Playlist"
        self._enqueue_playlist_items(session_id)
        finished_listing = session["next_index"] >= len(session["entries"])
        if finished_listing and self._playlist_task_count(session_id) == 0:
            self._playlist_sessions.pop(session_id, None)
            self._show_toast(
                f"Playlist finished: {playlist_title}",
                variant="info",
                duration=2600,
                anchor_widget=self.nav_library_btn
            )
        self._start_next_downloads()

    def _start_playlist_download(self, playlist_url, subtitles, subtitles_langs, embed_subs, rate_limit,
                                 cookiefile="", browser_auth=None):
        if self._playlist_sessions:
            self._show_error_dialog(
                "Error",
                "A playlist download is already running. Please wait for it to finish or reset first."
            )
            return
        if self._playlist_fetch_thread and self._playlist_fetch_thread.isRunning():
            self._show_error_dialog("Error", "Playlist fetch is already running.")
            return

        playlist_url = normalize_youtube_url(playlist_url, keep_playlist=True)
        self._pending_playlist_request = {
            "url": playlist_url,
            "subtitles": subtitles,
            "subtitles_langs": subtitles_langs,
            "embed_subs": embed_subs,
            "rate_limit": rate_limit,
            "cookiefile": cookiefile,
            "browser_auth": browser_auth
        }

        self._playlist_fetch_thread = QThread()
        self._playlist_fetch_worker = PlaylistWorker(
            playlist_url,
            cookiefile,
            browser_auth=browser_auth
        )
        self._playlist_fetch_worker.moveToThread(self._playlist_fetch_thread)

        self._playlist_fetch_thread.started.connect(self._playlist_fetch_worker.run)
        self._playlist_fetch_worker.completed.connect(self._on_playlist_info_ready, Qt.QueuedConnection)
        self._playlist_fetch_worker.error.connect(self._on_playlist_info_error, Qt.QueuedConnection)
        self._playlist_fetch_worker.finished.connect(self._playlist_fetch_thread.quit)
        self._playlist_fetch_worker.finished.connect(self._playlist_fetch_worker.deleteLater)
        self._playlist_fetch_thread.finished.connect(self._playlist_fetch_thread.deleteLater)
        self._playlist_fetch_thread.finished.connect(self._on_playlist_fetch_done)

        self._show_toast(
            "Reading playlist…",
            variant="info",
            duration=1800,
            anchor_widget=self.nav_library_btn
        )
        _log.info("Starting playlist fetch for %s", playlist_url)
        self._playlist_fetch_thread.start()

    def _on_playlist_info_ready(self, playlist_info):
        try:
            request = self._pending_playlist_request or {}
            entries = (playlist_info or {}).get("entries") or []
            if not entries:
                self._show_error_dialog("Error", "No downloadable videos found in this playlist.")
                return

            session_id = uuid.uuid4().hex
            self._playlist_sessions[session_id] = {
                "title": (playlist_info or {}).get("title") or "Playlist",
                "entries": entries,
                "next_index": 0,
                "payload_template": {
                    "quality": "Auto (Best)",
                    "container": "auto",
                    "subtitles": request.get("subtitles", False),
                    "subtitles_langs": request.get("subtitles_langs", ""),
                    "embed_subs": request.get("embed_subs", True),
                    "download_playlist": False,
                    "playlist_start": 1,
                    "playlist_end": 0,
                    "playlist_batch_size": 0,
                    "skip_unavailable": True,
                    "playlist_session_id": session_id,
                    "rate_limit": request.get("rate_limit"),
                    "download_dir": self.download_dir,
                    "cookiefile": request.get("cookiefile") or "",
                    "browser_auth": request.get("browser_auth"),
                    "proxy": self.proxy_url,
                }
            }

            self._enqueue_playlist_items(session_id)
            self._update_downloads_header()
            self._show_downloads_panel(True)
            self._flash_library_nav()
            self._show_toast(
                f"Playlist queued: {len(entries)} videos. Downloads will continue in Library.",
                variant="info",
                duration=2800,
                anchor_widget=self.nav_library_btn
            )
            self._persist_queue()
            self._start_next_downloads()
        finally:
            self._pending_playlist_request = None

    def _on_playlist_info_error(self, msg):
        user_msg = humanize_error(msg, cookies_loaded=self._cookies_loaded())
        self._show_error_dialog("Error", f"Failed to read playlist:\n{user_msg}")
        self._pending_playlist_request = None

    def _on_playlist_fetch_done(self):
        self._playlist_fetch_thread = None
        self._playlist_fetch_worker = None

    def _queue_download(self, payload, title_text, announce=True, autostart=True):
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
        item["pause_btn"].setText("Pause")
        item["pause_btn"].setEnabled(False)
        item["pause_btn"].setProperty("task_id", task_id)
        if item.get("cancel_btn"):
            item["cancel_btn"].setText("Cancel")
            item["cancel_btn"].setEnabled(True)
            item["cancel_btn"].setVisible(True)
            item["cancel_btn"].setProperty("task_id", task_id)
        self.active_downloads_layout.insertWidget(0, item["frame"])
        self._pending_tasks.append(task)
        self._update_downloads_header()
        self._show_downloads_panel(True)
        self._update_global_progress()
        if announce:
            self._flash_library_nav()
            self._show_toast(
                "Download started. Progress is in Library.",
                variant="info",
                duration=2200,
                anchor_widget=self.nav_library_btn
            )
        self._persist_queue()
        if autostart:
            self._start_next_downloads()

    def _start_next_downloads(self):
        has_playlist_pipeline = any(
            (task.get("payload") or {}).get("playlist_session_id")
            for task in self._pending_tasks
        ) or any(
            (task.get("payload") or {}).get("playlist_session_id")
            for task in self._active_tasks.values()
        )
        concurrent_limit = 1 if has_playlist_pipeline else self.max_concurrent_downloads

        while len(self._active_tasks) < concurrent_limit and self._pending_tasks:
            task = self._pending_tasks.pop(0)
            self._start_task(task)
        self._update_global_progress()
        self._persist_queue()

    def _start_task(self, task):
        try:
            task_id = task["id"]
            payload = task["payload"]
            _log.info("Starting task %s for url=%s", task_id, payload.get("url"))

            task["state"] = "active"
            self._touch_task_activity(task_id)
            item = task["item"]
            item["status"].setText("Downloading...")
            self._set_status_icon(item["status_icon"], "active", "")
            item["pause_btn"].setText("Pause")
            item["pause_btn"].setEnabled(True)
            if item.get("cancel_btn"):
                item["cancel_btn"].setText("Cancel")
                item["cancel_btn"].setEnabled(True)
                item["cancel_btn"].setVisible(True)

            thread = QThread()
            worker = DownloadWorker(
                task_id,
                payload["url"],
                payload["quality"],
                payload.get("cookiefile") or "",
                payload.get("browser_auth"),
                payload.get("download_dir") or self.download_dir,
                download_playlist=payload.get("download_playlist", False),
                playlist_start=payload.get("playlist_start", 1),
                playlist_end=payload.get("playlist_end", 0),
                playlist_batch_size=payload.get("playlist_batch_size", 0),
                skip_unavailable=payload.get("skip_unavailable", True),
                container=payload.get("container", "auto"),
                subtitles=payload.get("subtitles", False),
                subtitles_langs=payload.get("subtitles_langs", ""),
                embed_subtitles=payload.get("embed_subs", True),
                rate_limit=payload.get("rate_limit"),
                proxy=payload.get("proxy"),
            )
            _log.info("Worker created for task %s", task_id)
            worker.moveToThread(thread)
            worker.setProperty("task_id", task_id)
            thread.setProperty("task_id", task_id)

            thread.started.connect(worker.run)
            worker.progress.connect(self.update_progress, Qt.QueuedConnection)
            worker.error.connect(self.on_download_error, Qt.QueuedConnection)
            worker.cookie_lock.connect(self._on_download_cookie_lock, Qt.QueuedConnection)
            worker.completed.connect(self.on_download_complete, Qt.QueuedConnection)
            worker.paused.connect(self.on_download_paused, Qt.QueuedConnection)
            worker.oauth2_prompt.connect(self.on_oauth2_prompt, Qt.QueuedConnection)
            worker.finished.connect(thread.quit)
            worker.finished.connect(worker.deleteLater)
            # Use task_id capture to avoid relying on sender() after deletion.
            thread.finished.connect(
                lambda tid=task_id: self._on_task_thread_finished(tid),
                Qt.QueuedConnection
            )

            self._download_threads[task_id] = thread
            self._download_workers[task_id] = worker
            self._active_tasks[task_id] = task

            _log.info("About to start QThread for task %s", task_id)
            thread.start()
            _log.info("QThread started for task %s", task_id)
            self._update_global_progress()

        except Exception:
            import traceback
            tb = traceback.format_exc()
            _log.exception("Unhandled exception in _start_task")
            try:
                task_id = task.get("id")
            except Exception:
                task_id = None
            if task_id and task_id in self._active_tasks:
                self._mark_task_failed(task_id)
            self._show_error_dialog("Task Start Error", tb)

    @Slot(str, str)
    def on_oauth2_prompt(self, task_id, msg):
        try:
            worker = self._download_workers.get(task_id)
            if not worker:
                return
            dialog = QMessageBox(self)
            dialog.setIcon(QMessageBox.Information)
            dialog.setWindowTitle("OAuth2 Authentication Required")
            dialog.setText("YouTube requires device-level authentication.")
            dialog.setInformativeText(f"{msg}\n\nClick OK once you have linked the code in your browser.")
            dialog.setStandardButtons(QMessageBox.Ok | QMessageBox.Cancel)
            if dialog.exec() == QMessageBox.Cancel:
                if hasattr(worker, "request_cancel"):
                    try:
                        worker.request_cancel()
                    except Exception:
                        pass
        except Exception:
            _log.exception("Unhandled exception showing OAuth2 prompt")

    @Slot()
    def _on_download_thread_finished(self):
        try:
            thread = self.sender()
            task_id = thread.property("task_id") if thread else None
            if not task_id:
                return
            _log.info("Download thread finished for task %s", task_id)
            self._on_task_thread_finished(task_id)
        except Exception:
            _log.exception("Unhandled exception in _on_download_thread_finished")

    def _on_task_pause_clicked(self, task_id):
        if task_id in self._active_tasks:
            worker = self._download_workers.get(task_id)
            task = self._active_tasks.get(task_id)
            if worker and task:
                task["state"] = "pausing"
                task["item"]["status"].setText("Pausing...")
                task["item"]["pause_btn"].setText("Resume")
                task["item"]["pause_btn"].setEnabled(False)
                worker.request_pause()
            return
        if task_id in self._paused_tasks:
            task = self._paused_tasks.pop(task_id)
            task["state"] = "queued"
            task["item"]["status"].setText("Queued")
            task["item"]["pause_btn"].setText("Pause")
            task["item"]["pause_btn"].setEnabled(False)
            self._pending_tasks.append(task)
            self._update_global_progress()
            self._persist_queue()
            self._start_next_downloads()
            return
        # queued remove
        for idx, task in enumerate(self._pending_tasks):
            if task["id"] == task_id:
                item = task["item"]
                if item and item.get("frame"):
                    item["frame"].setParent(None)
                removed = self._pending_tasks.pop(idx)
                self._update_downloads_header()
                self._update_global_progress()
                self._persist_queue()
                session_id = (removed.get("payload") or {}).get("playlist_session_id") or ""
                if session_id:
                    self._pump_playlist_session(session_id)
                return

    def _on_task_cancel_clicked(self, task_id):
        if task_id in self._active_tasks:
            task = self._active_tasks.get(task_id)
            worker = self._download_workers.get(task_id)
            if task:
                item = task.get("item") or {}
                if item.get("status"):
                    item["status"].setText("Cancelling...")
                if item.get("pause_btn"):
                    item["pause_btn"].setEnabled(False)
                if item.get("cancel_btn"):
                    item["cancel_btn"].setEnabled(False)
            if worker and hasattr(worker, "request_cancel"):
                try:
                    worker.request_cancel()
                except Exception:
                    pass
            title = (task or {}).get("title") or "Download"
            self._mark_task_failed(task_id)
            self._show_toast(
                f"Cancelled: {title}",
                variant="warning",
                duration=1600,
                anchor_widget=self.nav_library_btn
            )
            return

        if task_id in self._paused_tasks:
            task = self._paused_tasks.pop(task_id)
            self._clear_task_activity(task_id)
            self._recycle_task_frame(task)
            self._update_downloads_header()
            self._update_global_progress()
            self._persist_queue()
            session_id = (task.get("payload") or {}).get("playlist_session_id") or ""
            if session_id:
                self._pump_playlist_session(session_id)
            else:
                self._start_next_downloads()
            return

        for idx, task in enumerate(self._pending_tasks):
            if task.get("id") != task_id:
                continue
            removed = self._pending_tasks.pop(idx)
            self._clear_task_activity(task_id)
            self._recycle_task_frame(removed)
            self._update_downloads_header()
            self._update_global_progress()
            self._persist_queue()
            session_id = (removed.get("payload") or {}).get("playlist_session_id") or ""
            if session_id:
                self._pump_playlist_session(session_id)
            else:
                self._start_next_downloads()
            return

    def on_download_paused(self, task_id):
        task = self._active_tasks.pop(task_id, None)
        self._clear_task_activity(task_id)
        if not task:
            return
        task["state"] = "paused"
        item = task.get("item") or {}
        try:
            if item.get("status"):
                item["status"].setText("Paused")
            if item.get("status_icon"):
                self._set_status_icon(item["status_icon"], "active", "")
            if item.get("pause_btn"):
                item["pause_btn"].setText("Resume")
                item["pause_btn"].setEnabled(True)
            if item.get("cancel_btn"):
                item["cancel_btn"].setText("Cancel")
                item["cancel_btn"].setEnabled(True)
        except Exception:
            _log.exception("UI update failed while pausing task %s", task_id)
        self._paused_tasks[task_id] = task
        self._update_global_progress()
        self._start_next_downloads()
        self._maybe_finalize_reset()

    def on_download_complete(self, task_id, items):
        task = self._active_tasks.pop(task_id, None)
        self._clear_task_activity(task_id)
        if not task:
            return
        payload = task.get("payload") or {}
        session_id = payload.get("playlist_session_id") or ""
        try:
            self.refresh_library()
            item = task.get("item") or {}
            if item.get("status"):
                item["status"].setText("")
            if item.get("status_icon"):
                self._set_status_icon(item["status_icon"], "done", "✓")
            if item.get("pause_btn"):
                item["pause_btn"].setText("Completed")
                item["pause_btn"].setDisabled(True)
            if item.get("cancel_btn"):
                item["cancel_btn"].setVisible(False)
                item["cancel_btn"].setDisabled(True)
            if item.get("open_btn"):
                item["open_btn"].setVisible(True)
            if item.get("progress"):
                item["progress"].setValue(100)
            if task.get("downloaded") is not None and item.get("size"):
                downloaded_text = round(task["downloaded"] / (1024 * 1024), 2)
                total = task.get("total")
                if total:
                    total_text = round(total / (1024 * 1024), 2)
                    item["size"].setText(f"Downloaded: {downloaded_text} MB / {total_text} MB")
                else:
                    item["size"].setText(f"Downloaded: {downloaded_text} MB")
            self._remove_active_item_with_fade(task)
            done_title = (task.get("title") or "Download finished").strip()
            if not session_id:
                self._show_toast(
                    f"Download completed: {done_title}",
                    variant="info",
                    duration=2600,
                    anchor_widget=self.nav_library_btn
                )
            if self._tray and self._tray.isVisible():
                app_in_foreground = (
                    QApplication.applicationState() == Qt.ApplicationActive
                    and self.isVisible()
                    and not self.isMinimized()
                )
                if not app_in_foreground:
                    self._tray.showMessage(
                        "Download complete",
                        task.get("title") or "Download finished",
                        QSystemTrayIcon.Information,
                        2000
                    )
        except Exception:
            _log.exception("UI update failed while completing task %s", task_id)
        self._update_global_progress()
        self._update_downloads_header()
        self._persist_queue()
        if session_id:
            self._pump_playlist_session(session_id)
        else:
            self._start_next_downloads()
        self._sync_download_button_text()
        self._maybe_finalize_reset()

    def on_download_error(self, task_id, msg):
        try:
            if task_id not in self._active_tasks:
                _log.info("Ignoring late error for inactive task %s: %s", task_id, msg)
                return
            task = self._active_tasks.get(task_id) or {}
            payload = task.get("payload") or {}
            session_id = payload.get("playlist_session_id") or ""
            clean = re.sub(r"\x1b\[[0-9;]*m", "", msg)
            _log.error("Download error: %s", clean)
            user_msg = humanize_error(clean, cookies_loaded=self._cookies_loaded())
            if session_id:
                self._show_toast(
                    f"Skipped one playlist item: {user_msg}",
                    variant="warning",
                    duration=2500,
                    anchor_widget=self.nav_library_btn
                )
                self._mark_task_failed(task_id)
                return
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
            self._mark_task_failed(task_id)
        except Exception:
            _log.exception("Unhandled exception in on_download_error for task %s", task_id)

    def _on_task_thread_finished(self, task_id):
        self._download_workers.pop(task_id, None)
        thread = self._download_threads.pop(task_id, None)
        if thread:
            try:
                thread.deleteLater()
            except Exception:
                pass
        self._clear_task_activity(task_id)
        # If a worker exits without completed/error/paused, prevent queue deadlock.
        if task_id in self._active_tasks:
            _log.warning(
                "Task %s thread finished without terminal signal; waiting for queued signals.",
                task_id
            )
            QTimer.singleShot(200, lambda tid=task_id: self._finalize_task_if_still_active(tid))
            return
        self._start_next_downloads()
        self._maybe_finalize_reset()

    def _finalize_task_if_still_active(self, task_id):
        if task_id in self._active_tasks:
            _log.warning(
                "Task %s still active after thread finished; marking task failed.",
                task_id
            )
            self._mark_task_failed(task_id)
            return
        self._maybe_finalize_reset()

    @Slot(str, float, object, object, object)
    def update_progress(self, task_id, percent, speed=None, downloaded=None, total=None):
        try:
            value = int(percent)
        except Exception:
            value = 0
        value = max(0, min(100, value))
        task = self._active_tasks.get(task_id)
        if not task:
            return
        self._touch_task_activity(task_id)
        task["downloaded"] = downloaded if downloaded is not None else task.get("downloaded")
        task["total"] = total if total is not None else task.get("total")
        item = task.get("item") or {}
        try:
            if item.get("progress"):
                item["progress"].setValue(value)
            if value >= 100 and task.get("state") in ("active", "pausing"):
                task["state"] = "finalizing"
                task["finalizing_since"] = time.time()
                status = item.get("status")
                if status and status.text().strip() in ("Downloading...", "Not responding..."):
                    status.setText("Finalizing...")

            downloaded_text = None
            if downloaded is not None:
                downloaded_text = round(downloaded / (1024 * 1024), 2)

            total_text = None
            if total:
                total_text = round(total / (1024 * 1024), 2)

            if item.get("size"):
                if downloaded_text is not None and total_text is not None:
                    item["size"].setText(f"Downloaded: {downloaded_text} MB / {total_text} MB")
                elif downloaded_text is not None:
                    item["size"].setText(f"Downloaded: {downloaded_text} MB")

            if speed and item.get("speed"):
                item["speed"].setText(f"Speed: {speed}")
        except Exception:
            _log.exception("UI progress update failed for task %s", task_id)
            return
        self._update_global_progress()

    def _update_global_progress(self):
        self._sync_download_button_text()
        if not hasattr(self, "progress") or self.progress is None:
            return

        active_tasks = list(self._active_tasks.values())
        pending_count = len(self._pending_tasks)

        if not active_tasks and pending_count == 0:
            self.progress.setValue(0)
            self.progress.setFormat("0%")
            return

        downloaded_sum = 0.0
        total_sum = 0.0
        has_totals = False
        fallback_values = []

        for task in active_tasks:
            downloaded = task.get("downloaded")
            total = task.get("total")
            if downloaded is not None and total:
                try:
                    d_val = float(downloaded)
                    t_val = float(total)
                except Exception:
                    d_val = None
                    t_val = None
                if d_val is not None and t_val and t_val > 0:
                    downloaded_sum += max(0.0, d_val)
                    total_sum += t_val
                    has_totals = True
                    continue

            item = task.get("item") or {}
            progress_bar = item.get("progress")
            if progress_bar is not None:
                try:
                    fallback_values.append(int(progress_bar.value()))
                except Exception:
                    pass

        if has_totals and total_sum > 0:
            percent = int(max(0, min(100, (downloaded_sum / total_sum) * 100)))
        elif fallback_values:
            percent = int(max(0, min(100, sum(fallback_values) / len(fallback_values))))
        else:
            percent = 0

        task_total = len(active_tasks) + pending_count
        if task_total > 0 and pending_count > 0:
            percent = int(percent * (len(active_tasks) / task_total))

        self.progress.setValue(percent)
        state_bits = []
        if active_tasks:
            state_bits.append(f"{len(active_tasks)} active")
        if pending_count:
            state_bits.append(f"{pending_count} queued")
        suffix = f" ({', '.join(state_bits)})" if state_bits else ""
        self.progress.setFormat(f"{percent}%{suffix}")

    def _sync_download_button_text(self):
        if not hasattr(self, "download_btn") or self.download_btn is None:
            return
        if self._info_ready and self.download_btn.isEnabled():
            target = "Download"
        else:
            has_pipeline = bool(self._active_tasks or self._pending_tasks or self._paused_tasks)
            target = "Downloading..." if has_pipeline else "Start Download"
        self._animate_button_text(self.download_btn, target)

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
        # Prevent placeholder history items when app restarts with a non-empty queue.
        queue_manager.clear_queue()

    def _reset_download_ui(self):
        self._animate_button_text(self.download_btn, "Start Download")
        if getattr(self, "progress", None):
            self.progress.setValue(0)
            self.progress.setFormat("0%")
        self._last_progress_value = 0

    def _maybe_finalize_reset(self):
        if not self._active_tasks and self._cancel_grace_timer.isActive():
            self._cancel_grace_timer.stop()
        if self._reset_requested and not self._active_tasks and not self._has_running_download_threads():
            self._reset_requested = False
            self.reset_ui()

    def reset_ui(self):
        if self._thread_is_running(self._fetch_thread):
            worker = getattr(self, "_fetch_worker", None)
            if worker and hasattr(worker, "request_cancel"):
                try:
                    worker.request_cancel()
                except Exception:
                    pass
            return
        if self._active_tasks:
            self._reset_requested = True
            # Cancel the full pipeline: active + queued + paused + playlist session state.
            self._playlist_sessions.clear()
            self._clear_non_active_downloads()
            self._request_cancel_all_downloads("Cancelling...")
            self._show_toast("Stopping active downloads...", variant="info")
            return
        self._reset_requested = False
        if self._cancel_grace_timer.isActive():
            self._cancel_grace_timer.stop()
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
        if getattr(self, "progress", None):
            self.progress.setValue(0)
            self.progress.setFormat("0%")
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
        self._playlist_sessions.clear()
        self._task_last_activity.clear()
        # Do not clear thread/worker maps here. Late thread-finished signals can still arrive
        # during cancellation, and dropping references too early can trigger QThread lifetime errors.
        self._download_threads = {
            tid: t for tid, t in self._download_threads.items() if self._thread_is_running(t)
        }
        self._download_workers = {
            tid: w for tid, w in self._download_workers.items() if tid in self._download_threads
        }
        queue_manager.clear_queue()
        self._show_downloads_panel(False)
        self._expand_details()
        self._clear_downloads_list()
        self.active_download_item = None
        self._update_global_progress()

    def _read_clipboard_text(self):
        try:
            return QApplication.clipboard().text().strip()
        except Exception:
            return ""

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
        self.max_concurrent_downloads = max(1, min(10, value))
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

    def _on_proxy_changed(self, text):
        self.proxy_url = text.strip()
        self.settings.setValue("proxy_url", self.proxy_url)

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
                self.url_input.setCursorPosition(0)
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
        if self._thread_is_running(self._update_thread):
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
        elif box.clickedButton() == exit_btn:
            self.close()

    def _on_no_update(self):
        if getattr(self, "_update_manual", False):
            self._show_message_dialog("Updates", "You're on the latest version.")

    def _on_update_error(self, msg):
        _log.error("Update error: %s", msg)
        if "404" in (msg or ""):
            self.update_url_404_disabled = True
            self.update_url_404_value = (self.update_manifest_url or "").strip()
            self.settings.setValue("update_url_404_disabled", True)
            self.settings.setValue("update_url_404_value", self.update_url_404_value)
            self.check_updates_on_startup = False
            self.settings.setValue("check_updates_on_startup", False)
            if hasattr(self, "check_updates_cb"):
                self.check_updates_cb.setChecked(False)
            self._show_toast(
                "Update URL is not reachable (404). Startup update checks are paused.",
                variant="warning",
                duration=5000
            )
            if getattr(self, "_update_manual", False):
                self._show_message_dialog(
                    "Updates",
                    "Update endpoint returned 404.\n"
                    "If your GitHub repo is private, make it public before testing updates.",
                    QMessageBox.Warning
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

        if self._thread_is_running(self._update_download_thread):
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
            self._show_toast(
                "Update downloaded. Installer opened. You can continue using the app.",
                variant="info",
                duration=2800
            )
        except Exception:
            self._show_message_dialog(
                "Updates",
                f"Update downloaded to:\n{path}"
            )
        # Do not close the app automatically during background update downloads.

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
        if not self.restricted_mode:
            self.restricted_mode = True
            self.settings.setValue("restricted_mode", True)
        self.update_cookie_indicator()
        self._show_message_dialog("Cookies", "Cookies file set.")

    def clear_cookies_file(self):
        self.cookie_file = ""
        self.settings.remove("cookie_file")
        self.update_cookie_indicator()
        self._show_message_dialog("Cookies", "Cookies file cleared.")

    def _effective_cookie_file(self):
        if not self.restricted_mode:
            return ""
        if self._cookie_is_valid(self.cookie_file):
            return self.cookie_file
        return ""

    def _effective_browser_auth(self):
        if not self.restricted_mode or not self.browser_auth_enabled:
            return None
        source = (self.browser_auth_source or "").strip().lower()
        profile = (self.browser_auth_profile or "").strip()
        if not source:
            return None
        if source == "auto":
            return ["chrome", "edge", "firefox", "brave", "opera"]
        if profile:
            return f"{source}:{profile}"
        return source

    def update_cookie_indicator(self):
        effective_file = self._effective_cookie_file()
        effective_browser = self._effective_browser_auth()
        for indicator, status in self.cookie_status_widgets:
            if effective_browser:
                indicator.setStyleSheet("border-radius: 6px; background: #2ecc71;")
                status.setText("Browser connected")
            elif effective_file:
                indicator.setStyleSheet("border-radius: 6px; background: #2ecc71;")
                status.setText("Cookies file loaded")
            else:
                indicator.setStyleSheet("border-radius: 6px; background: #f39c12;")
                status.setText("Browser not connected" if self.restricted_mode else "Normal mode")
        if hasattr(self, "restricted_mode_cb"):
            self.restricted_mode_cb.setChecked(self.restricted_mode)
        if hasattr(self, "browser_profile_input") and self.browser_auth_profile:
            self.browser_profile_input.setText(self.browser_auth_profile)
        if hasattr(self, "diagnostics_label"):
            mode_label = "Restricted" if self.restricted_mode else "Normal"
            if effective_browser:
                auth_label = "Browser auth"
            elif effective_file:
                auth_label = "Cookies file"
            else:
                auth_label = "None"
            browser_label = self.browser_auth_source or "auto"
            self.diagnostics_label.setText(
                f"Diagnostics: Mode={mode_label} | Auth={auth_label} | Browser={browser_label}"
            )
        self._sync_restricted_controls()

    def _sync_restricted_controls(self):
        enabled = bool(self.restricted_mode)
        for widget_name in (
            "browser_auth_combo",
            "browser_profile_input",
            "browser_connect_btn",
            "browser_disconnect_btn",
            "set_cookies_btn",
            "clear_cookies_btn",
        ):
            widget = getattr(self, widget_name, None)
            if widget:
                widget.setEnabled(enabled)
        if hasattr(self, "restricted_status_label"):
            auth_state = "connected" if self._cookies_loaded() else "not connected"
            mode_label = "Restricted mode" if self.restricted_mode else "Normal mode"
            self.restricted_status_label.setText(f"{mode_label} — Browser auth {auth_state}")

    def _on_restricted_mode_toggle(self, checked):
        self.restricted_mode = bool(checked)
        self.settings.setValue("restricted_mode", self.restricted_mode)
        if not self.restricted_mode:
            self._show_toast(
                "Normal mode enabled: cookies will not be used.",
                variant="info",
                duration=2400
            )
        self.update_cookie_indicator()

    def _connect_browser_auth(self):
        source = ""
        profile = ""
        if hasattr(self, "browser_auth_combo"):
            source = (self.browser_auth_combo.currentData() or "").strip().lower()
        if hasattr(self, "browser_profile_input"):
            profile = (self.browser_profile_input.text() or "").strip()

        if not source:
            self._show_error_dialog("Browser Auth", "Please choose a browser.")
            return

        self.browser_auth_source = source
        self.browser_auth_profile = profile
        self.browser_auth_enabled = True
        self.restricted_mode = True
        self.settings.setValue("browser_auth_source", self.browser_auth_source)
        self.settings.setValue("browser_auth_profile", self.browser_auth_profile)
        self.settings.setValue("browser_auth_enabled", True)
        self.settings.setValue("restricted_mode", True)
        self.update_cookie_indicator()
        self._show_message_dialog("Browser Auth", "Browser auth connected.")

    def _disconnect_browser_auth(self):
        self.browser_auth_enabled = False
        self.settings.setValue("browser_auth_enabled", False)
        self.update_cookie_indicator()
        self._show_message_dialog("Browser Auth", "Browser auth disconnected.")

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
            "Normal mode works for public videos without cookies.\n\n"
            "Manual cookies (cookies.txt):\n"
            "1. Install a cookies export extension in your browser.\n"
            "2. Log in to YouTube and export cookies in Netscape format.\n"
            "3. Save the file as cookies.txt.\n"
            "4. In the Cookies tab, click “Set Cookies File” and select it.\n"
            "5. Keep the file private and refresh it when it expires.\n\n"
            "Do not share your cookies with anyone."
        )

    def closeEvent(self, event):
        if self._task_watchdog.isActive():
            self._task_watchdog.stop()
        if self._cancel_grace_timer.isActive():
            self._cancel_grace_timer.stop()
        if self._library_nav_pulse_timer.isActive():
            self._library_nav_pulse_timer.stop()
        running_download_threads = any(
            self._thread_is_running(thread)
            for thread in self._download_threads.values()
        )
        has_downloads = bool(
            self._active_tasks or self._pending_tasks or self._paused_tasks or running_download_threads
        )
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

        for thread in (
            self._fetch_thread,
            self._update_thread,
            self._update_download_thread
        ):
            if self._thread_is_running(thread):
                try:
                    thread.quit()
                    thread.wait(2000)
                except Exception:
                    pass

        for thread in list(self._download_threads.values()):
            if self._thread_is_running(thread):
                try:
                    thread.quit()
                    if not thread.wait(3000):
                        _log.warning("Force terminating a stuck download thread.")
                        thread.terminate()
                        thread.wait(1000)
                except Exception:
                    pass

        self._persist_queue()
        event.accept()


