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
from PySide6.QtGui import QIcon, QPixmap, QDesktopServices, QColor, QFont, QPalette, QAction, QPainter, QLinearGradient

from ui_style import style, dark_style, DARK, LIGHT
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
from auth.session_store import restore_proxy_secret, save_proxy_url
from logging_utils import get_logger
from ui.widgets import (
    FadingTextButton, PasteButton, MarqueeLabel, BrandIcon,
    DownloadButton, DownloadProgressBar, ToggleSwitch, ToastFrame,
    NavButton, StatusBadge, SectionLabel, NavCounter, ElidedLabel
)
from ui.dialogs import TermsDialog
from ui.pages import PagesMixin
from ui.themes import DEFAULT_THEME
from workers import UpdateWorker, UpdateDownloadWorker, FetchWorker, PlaylistWorker, DownloadWorker
from updates.manager import custom_update_urls_enabled, validate_update_url
from core.models import (
    TASK_STATE_ACTIVE,
    TASK_STATE_CANCELLING,
    TASK_STATE_COMPLETED,
    TASK_STATE_FAILED,
    TASK_STATE_FINALIZING,
    TASK_STATE_PAUSED,
    TASK_STATE_QUEUED,
    TASK_STATE_STARTING,
)
import queue_manager
import ytdlp_exe_manager
import ffmpeg_manager

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
        QApplication.setFont(QFont("Segoe UI", 11))

        self.setWindowTitle("YT Downloader Pro")
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
        self.current_theme_name = self.settings.value("theme", DEFAULT_THEME)
        self._apply_theme()
        self.show_thumbnail = self.settings.value("show_thumbnail", True, type=bool)
        self.restricted_mode = self.settings.value("restricted_mode", False, type=bool)
        self.browser_auth_source = self.settings.value("browser_auth_source", "", type=str)
        self.browser_auth_profile = self.settings.value("browser_auth_profile", "", type=str)
        self.browser_auth_enabled = self.settings.value("browser_auth_enabled", False, type=bool)
        self.cookie_file = self.settings.value("cookie_file", "", type=str)
        if self.browser_auth_enabled:
            # Older versions marked browser auth as connected before verifying
            # usable login cookies. Force a fresh connection check after update.
            self.browser_auth_enabled = False
            self.settings.setValue("browser_auth_enabled", False)
        if self.cookie_file and not self._cookie_is_valid(self.cookie_file, require_auth=self.restricted_mode):
            self.cookie_file = ""
            self.settings.remove("cookie_file")

        # Auto-restore managed YouTube session (from the system-browser login flow).
        # Only restore if the file actually contains real YouTube auth cookies.
        if not self.cookie_file:
            from ui.session_manager import load_session
            restored = load_session()   # returns '' if file has no auth cookies
            if restored:
                self.cookie_file = restored
                self.settings.setValue("cookie_file", restored)
                if not self.restricted_mode:
                    self.restricted_mode = True
                    self.settings.setValue("restricted_mode", True)
                _log.info("Auto-restored YouTube session from managed storage")
            else:
                # Clear any stale cookie_file reference that might linger in settings
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

        stored_proxy = self.settings.value("proxy_url", "", type=str)
        self.proxy_display_url = save_proxy_url(stored_proxy)
        if self.proxy_display_url != stored_proxy:
            self.settings.setValue("proxy_url", self.proxy_display_url)
        self.proxy_url = restore_proxy_secret(self.proxy_display_url)

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
        if not custom_update_urls_enabled() and self.update_manifest_url != DEFAULT_UPDATE_MANIFEST_URL:
            self.update_manifest_url = DEFAULT_UPDATE_MANIFEST_URL
            self.settings.setValue("update_manifest_url", self.update_manifest_url)

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
        self._ffmpeg_install_thread = None
        self._ffmpeg_install_worker = None
        self._ffmpeg_installed = False
        self._ytdlp_exe_ready = False
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
        self._ui_generation = 0
        self._cancel_cleanup_pending = False
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
        self._collapse_details()
        self._update_global_progress()
        self._update_downloads_header()
        QTimer.singleShot(0, self._init_details_height)
        self.update_cookie_indicator()
        self.refresh_library()
        QTimer.singleShot(0, self._load_persistent_queue)
        self._init_tray()

        QTimer.singleShot(300, self._show_terms_if_needed)
        if self.check_updates_on_startup:
            QTimer.singleShot(250, self.start_update_check)
        QTimer.singleShot(400, self._maybe_show_cookie_reminder)
        QTimer.singleShot(600, self._check_ffmpeg_on_startup)
        QTimer.singleShot(700, self._refresh_essentials_status)
        QTimer.singleShot(800, self._check_ytdlp_exe_on_startup)

    def _build_ui(self):
        root = QWidget()
        root.setObjectName("centralWidget")
        root_layout = QHBoxLayout(root)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)

        self.sidebar = QFrame()
        self.sidebar.setObjectName("Sidebar")
        self.sidebar.setFixedWidth(200)
        sidebar_layout = QVBoxLayout(self.sidebar)
        sidebar_layout.setContentsMargins(10, 14, 10, 14)
        sidebar_layout.setSpacing(2)

        brand_row = QWidget()
        brand_layout = QHBoxLayout(brand_row)
        brand_layout.setContentsMargins(8, 4, 8, 4)
        brand_layout.setSpacing(8)

        # Custom gradient BrandIcon
        self.brand_icon = BrandIcon(28)

        self.brand_name = QLabel("YT DL Pro")
        self.brand_name.setObjectName("BrandName")

        brand_layout.addWidget(self.brand_icon)
        brand_layout.addWidget(self.brand_name)
        brand_layout.addStretch(1)

        sidebar_layout.addWidget(brand_row)
        sidebar_layout.addSpacing(14)

        self.nav_group = QButtonGroup(self)
        self.nav_group.setExclusive(True)
        self._nav_buttons = []

        self.pages = QStackedWidget()

        from ui.pages import ThemesPage
        self.page_downloader = self._build_downloader_page()
        self.page_library = self._build_library_page()
        self.page_history = self._build_history_page()
        self.page_options = self._build_options_page()
        self.page_themes = ThemesPage(self)
        self.page_cookies = self._build_cookies_page()
        self.page_about = self._build_about_page()

        self.pages.addWidget(self.page_downloader)
        self.pages.addWidget(self.page_library)
        self.pages.addWidget(self.page_history)
        self.pages.addWidget(self.page_options)
        self.pages.addWidget(self.page_themes)
        self.pages.addWidget(self.page_cookies)
        self.pages.addWidget(self.page_about)
        self.pages.currentChanged.connect(self._on_page_changed)

        # Group 1: MAIN
        main_label = SectionLabel("MAIN")
        sidebar_layout.addWidget(main_label)
        sidebar_layout.addSpacing(2)

        self.nav_home_btn = self._add_nav_button("Home", self.page_downloader, "home", "⌂")
        
        self.nav_library_btn = self._add_nav_button("Downloads", self.page_library, "downloads", "↓")
        # Add NavCounter to Downloads Button layout
        self.downloads_counter = NavCounter(0)
        self.downloads_counter.setAttribute(Qt.WA_TransparentForMouseEvents)
        self.nav_library_btn.layout().addWidget(self.downloads_counter)

        self.nav_history_btn = self._add_nav_button("History", self.page_history, "history", "⏱")

        sidebar_layout.addSpacing(12)

        # Group 2: SETTINGS
        settings_label = SectionLabel("SETTINGS")
        sidebar_layout.addWidget(settings_label)
        sidebar_layout.addSpacing(2)

        self.nav_pref_btn = self._add_nav_button("Preferences", self.page_options, "preferences", "⚙")
        self.nav_themes_btn = self._add_nav_button("Themes", self.page_themes, "themes", "🎨")
        self.nav_cookies_btn = self._add_nav_button("Restricted Mode", self.page_cookies, "cookies", "🔒")
        self.nav_about_btn = self._add_nav_button("About", self.page_about, "about", "ⓘ")

        sidebar_layout.addStretch(1)

        self.main_panel = QWidget()
        self.main_panel.setObjectName("MainPanel")
        main_panel_layout = QVBoxLayout(self.main_panel)
        main_panel_layout.setContentsMargins(16, 16, 16, 16)
        main_panel_layout.setSpacing(10)
        main_panel_layout.addWidget(self.pages)

        root_layout.addWidget(self.sidebar)
        root_layout.addWidget(self.main_panel, 1)

        self.setCentralWidget(root)
        
        # Linear/Notion style: Flat. Call active state logic and remove shadows
        self.set_active_nav("home")

        self.toast = ToastFrame(self.main_panel)
        toast_layout = QHBoxLayout(self.toast)
        toast_layout.setContentsMargins(14, 10, 14, 10)
        toast_layout.setSpacing(8)
        self.toast_label = QLabel("")
        self.toast_label.setObjectName("ToastLabel")
        self.toast_label.setWordWrap(True)
        toast_layout.addWidget(self.toast_label)
        self.toast.hide()

    def _switch_page(self, page, page_name):
        self.pages.setCurrentWidget(page)
        self.set_active_nav(page_name)
        if page_name == "home":
            self.load_defaults_from_prefs()

    def _add_nav_button(self, label, page, page_name, icon_char=""):
        btn = NavButton("")
        btn.setObjectName("NavButton")
        btn.setProperty("page", page_name)
        btn.setCursor(Qt.PointingHandCursor)
        btn.setFixedHeight(32)
        btn.icon_char = icon_char
        btn.label_text = label

        btn_layout = QHBoxLayout(btn)
        btn_layout.setContentsMargins(10, 0, 10, 0)
        btn_layout.addStretch(1)

        btn.clicked.connect(lambda checked=False, p=page, n=page_name: self._switch_page(p, n))
        self.nav_group.addButton(btn)
        self._nav_buttons.append(btn)
        self.sidebar.layout().addWidget(btn)
        return btn

    def set_active_nav(self, page_name: str):
        for btn in self._nav_buttons:
            is_active = (btn.property("page") == page_name)
            btn.setProperty("active", "true" if is_active else "false")
            btn.style().unpolish(btn)
            btn.style().polish(btn)


    def _apply_shadow(self, widget, blur, alpha, y_offset):
        pass

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._position_toast()

    def changeEvent(self, event):
        super().changeEvent(event)

    def _position_toast(self):
        if not self.toast or not hasattr(self, "main_panel"):
            return
        parent_w = self.main_panel.width()
        margin = 20
        max_width = max(260, min(560, parent_w - margin * 2))
        self.toast.setFixedWidth(max_width)
        self.toast.adjustSize()
        x = (parent_w - self.toast.width()) // 2
        y = 10
        self.toast.move(x, y)

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

        self.toast.setOpacity(0.0)
        self._toast_anim_in = QPropertyAnimation(self.toast, b"windowOpacity", self)
        self._toast_anim_in.setDuration(180)
        self._toast_anim_in.setStartValue(0.0)
        self._toast_anim_in.setEndValue(1.0)

        self._toast_anim_out = QPropertyAnimation(self.toast, b"windowOpacity", self)
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
        pass

    def _collapse_details(self):
        if not hasattr(self, "details_container") or not self.details_container:
            return
        self.details_container.setVisible(False)

    def _expand_details(self):
        if not hasattr(self, "details_container") or not self.details_container:
            return
        self.details_container.setVisible(True)
        self.details_container.setMaximumHeight(9999)

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
            # Keep the active-downloads card visible on the Downloads page with empty-state text.
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

    def _is_cancel_cleanup_blocking(self):
        return bool(self._cancel_cleanup_pending and self._has_running_download_threads())

    def _release_cancel_gate_if_safe(self, start_pending=True):
        if not self._cancel_cleanup_pending:
            return False
        if self._has_running_download_threads():
            return False
        self._cancel_cleanup_pending = False
        self._reset_requested = False
        if self._cancel_grace_timer.isActive():
            self._cancel_grace_timer.stop()
        self._sync_download_button_text()
        if start_pending and self._pending_tasks:
            QTimer.singleShot(0, self._start_next_downloads)
        return True

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
        dot.setStyleSheet("border-radius: 6px; background: #f59e0b;")
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
        return self.build_task_card(title)

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
        item["frame"].setVisible(True)
        item["title"].setText(title)
        item["status"].setText("Downloading...")
        self._set_status_icon(item["status_icon"], "active", "")
        item["progress"].setValue(0)
        if item.get("percentage_label"):
            item["percentage_label"].setText("0%")
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
        # Internal sentinel signals from background threads
        if title == "__ytdlp_ready__":
            self._ytdlp_exe_ready = True
            self._show_toast("yt-dlp is up to date!", variant="success", duration=4000)
            return
        if title == "__ytdlp_updated__":
            self._ytdlp_exe_ready = True
            self._show_toast(f"yt-dlp updated to {message}!", variant="success", duration=5000)
            return
        if title == "__ytdlp_error__":
            self._show_toast(
                f"yt-dlp setup failed: {message}\nDownloads may not work.",
                variant="error",
                duration=8000
            )
            return
        if title == "__ffmpeg_updated__":
            self._ffmpeg_installed = True
            self._show_toast(f"FFmpeg updated to {message}!", variant="success", duration=5000)
            return
        if title == "__ffmpeg_ready__":
            self._ffmpeg_installed = True
            self._on_ffmpeg_completed()
            return
        if title == "__ffmpeg_error__":
            self._show_toast(
                f"FFmpeg setup failed: {message}\nVideo+audio merging may not work.",
                variant="error",
                duration=8000
            )
            return
        if title == "__browser_auth_success__":
            data = icon_obj if isinstance(icon_obj, dict) else {}
            cookie_path = data.get("cookie_path") or message
            source = data.get("source") or self.browser_auth_source or "browser"
            n_auth = data.get("n_auth") or 0
            self.cookie_file = cookie_path
            self.settings.setValue("cookie_file", cookie_path)
            self.restricted_mode = True
            self.settings.setValue("restricted_mode", True)
            # Use the extracted cookies file for downloads instead of repeatedly
            # reading a live browser database that may be locked or keyring-gated.
            self.browser_auth_enabled = False
            self.settings.setValue("browser_auth_enabled", False)
            self.update_cookie_indicator()
            title = "Browser Connected"
            message = (
                f"Successfully connected to {str(source).title()}.\n"
                f"{n_auth} YouTube/Google auth cookie(s) found.\n\n"
                "Restricted videos can now use this saved session."
            )
            icon_obj = QMessageBox.Information
        elif title == "__browser_auth_failed__":
            self.browser_auth_enabled = False
            self.settings.setValue("browser_auth_enabled", False)
            self.update_cookie_indicator()
            title = "Browser Connection Failed"
            icon_obj = QMessageBox.Warning

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
        t = DARK if self.dark_mode else LIGHT
        box.setStyleSheet(
            f"QDialog, QMessageBox {{ background-color: {t['bg_window']}; color: {t['text_primary']}; }}"
            f"QLabel {{ color: {t['text_primary']}; }}"
            f"QTextEdit {{ background-color: {t['bg_surface']}; color: {t['text_primary']}; "
            f"border: 1px solid {t['border']}; border-radius: 8px; }}"
            f"QPushButton {{ background-color: {t['bg_card']}; "
            f"border: 1px solid {t['border']}; "
            f"border-radius: 8px; padding: 6px 12px; color: {t['text_primary']}; }}"
            f"QPushButton:hover {{ background-color: {t['bg_hover']}; "
            f"border: 1px solid {t['accent']}; color: {t['text_primary']}; }}"
        )

    def _apply_theme(self):
        from ui_style import get_stylesheet
        sheet = get_stylesheet(dark=self.dark_mode, theme_name=self.current_theme_name)
        self.setStyleSheet(sheet)
        self._refresh_all_nav_buttons()
        self._apply_combo_popup_theme()

        # Update dark_mode state on custom widgets dynamically
        for widget in self.findChildren(ToggleSwitch):
            widget.dark_mode = self.dark_mode
            widget.update()
        for widget in self.findChildren(DownloadProgressBar):
            widget.dark_mode = self.dark_mode
            widget.update()
        for widget in self.findChildren(BrandIcon):
            widget.dark_mode = self.dark_mode
            widget.update()

    def _refresh_all_nav_buttons(self):
        if not hasattr(self, '_nav_buttons') or not self._nav_buttons:
            return
        for btn in self._nav_buttons:
            btn.style().unpolish(btn)
            btn.style().polish(btn)
            btn.update()
        # Also repaint the brand icon
        if hasattr(self, 'brand_icon'):
            self.brand_icon.update()

    def apply_theme(self, theme_name):
        self.settings.setValue("theme", theme_name)
        self.current_theme_name = theme_name
        self._apply_theme()
        if hasattr(self, 'page_themes') and hasattr(self.page_themes, 'update_card_selection'):
            self.page_themes.update_card_selection()

    def _apply_combo_popup_theme(self):
        combo = getattr(self, "browser_auth_combo", None)
        if not combo:
            return
        view = combo.view()
        if not view:
            return
        t = DARK if self.dark_mode else LIGHT
        view.setStyleSheet(
            f"QListView {{"
            f" background-color: {t['bg_card']};"
            f" border: 1px solid {t['border']};"
            f" color: {t['text_primary']};"
            f" selection-background-color: {t['bg_hover']};"
            f" selection-color: {t['text_primary']};"
            f"}}"
            f"QListView::item {{ padding: 6px 10px; }}"
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
            # Fix 12 — hide subtitle cell when no subtitles are available
            if hasattr(self, "subtitle_lang_cell"):
                self.subtitle_lang_cell.setVisible(False)
        else:
            self.subs_lang.addItem("Any")
            for lang in available:
                self.subs_lang.addItem(lang)
            self.subs_lang.setEnabled(True)
            # Fix 12 — reveal subtitle cell when subtitles are available
            if hasattr(self, "subtitle_lang_cell"):
                self.subtitle_lang_cell.setVisible(True)
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
        active_count = self._layout_widget_count(self.active_downloads_layout)
        total = active_count + self._layout_widget_count(self.completed_downloads_layout)
        
        # Update sidebar downloads badge counter
        if hasattr(self, "downloads_counter"):
            self.downloads_counter.set_count(active_count)
            
        self.downloads_header.setText(f"Active downloads ({total})")
        if hasattr(self, "library_empty_label") and self.library_empty_label:
            self.library_empty_label.setVisible(active_count == 0)
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
        active = bool(
            self._active_tasks
            or self._pending_tasks
            or self._paused_tasks
            or self._is_cancel_cleanup_blocking()
        )
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
            self._release_cancel_gate_if_safe()
            return False
        task["state"] = TASK_STATE_FAILED
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
        self._release_cancel_gate_if_safe()
        return True

    def _request_cancel_all_downloads(self, reason_text=""):
        if self._active_tasks or self._has_running_download_threads():
            self._cancel_cleanup_pending = True
        for worker in list(self._download_workers.values()):
            if worker and hasattr(worker, "request_cancel"):
                try:
                    worker.request_cancel()
                except Exception:
                    pass
        for task in self._active_tasks.values():
            task["state"] = TASK_STATE_CANCELLING
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
        self._sync_download_button_text()

    def _force_cleanup_active_tasks(self):
        stale_ids = list(self._active_tasks.keys())
        if not stale_ids:
            if self._cancel_cleanup_pending:
                for task_id, worker in list(self._download_workers.items()):
                    if worker and hasattr(worker, "request_cancel"):
                        try:
                            worker.request_cancel()
                        except Exception:
                            pass
                    thread = self._download_threads.get(task_id)
                    if self._thread_is_running(thread):
                        try:
                            _log.warning("Force terminating stuck cancelled download thread %s.", task_id)
                            thread.terminate()
                            thread.wait(1000)
                        except Exception:
                            pass
            self._release_cancel_gate_if_safe()
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
        self._release_cancel_gate_if_safe()
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
                    if task.get("state") == TASK_STATE_CANCELLING:
                        continue
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
        """Find ffmpeg on the current platform."""
        import ffmpeg_manager
        return ffmpeg_manager.is_ffmpeg_present()

    def _check_ffmpeg_on_startup(self):
        """Check for ffmpeg on startup; auto-update silently in background."""
        # If ffmpeg is already available (system or managed), mark ready immediately
        if ffmpeg_manager.is_ffmpeg_present():
            _log.info("FFmpeg already present — skipping background check.")
            self._ffmpeg_installed = True
            self._refresh_essentials_status()
            return

        # Not present: start a silent background install (no progress bar — user
        # hasn't visited Preferences yet, so there's no widget to update).
        def _on_done():
            self.dialog_requested.emit("__ffmpeg_ready__", "", None)

        def _on_error(msg):
            _log.warning("FFmpeg background check failed: %s", msg)
            self.dialog_requested.emit("__ffmpeg_error__", msg, None)

        self._ffmpeg_install_thread = ffmpeg_manager.ensure_ffmpeg_background(
            on_done=_on_done,
            on_error=_on_error,
            progress_cb=self._on_ffmpeg_progress
        )

    def _ffmpeg_install_running(self):
        thread = self._ffmpeg_install_thread
        if not thread:
            return False
        if hasattr(thread, "isRunning"):
            try:
                return bool(thread.isRunning())
            except RuntimeError:
                return False
        if hasattr(thread, "is_alive"):
            return bool(thread.is_alive())
        return False

    def _install_ffmpeg_background(self):
        """Start FFmpeg installation in a background thread on first launch."""
        if self._ffmpeg_install_running():
            _log.info("FFmpeg installation already in progress.")
            return

        self._show_toast(
            "Installing FFmpeg essentials in the background...",
            variant="info"
        )

        def _on_done():
            self.dialog_requested.emit("__ffmpeg_ready__", "", None)
            self.dialog_requested.emit("FFmpeg", "FFmpeg installed successfully.", QMessageBox.Information)

        def _on_error(msg):
            self.dialog_requested.emit("__ffmpeg_error__", msg, None)

        self._ffmpeg_install_thread = ffmpeg_manager.ensure_ffmpeg_background(
            on_done=_on_done,
            on_error=_on_error,
            progress_cb=self._on_ffmpeg_progress,
            force=True
        )

    def _on_ffmpeg_progress(self, percent):
        _log.debug("FFmpeg installation progress: %d%%", percent)
        # Capture percent as default arg to avoid closure scoping issues across threads
        def _update(pct=int(percent)):
            if hasattr(self, "essentials_progress"):
                self.essentials_progress.setVisible(True)
                self.essentials_progress.setValue(pct)
            if hasattr(self, "essentials_status_label"):
                self.essentials_status_label.setText(f"Downloading essentials... {pct}%")
        from PySide6.QtCore import QTimer
        QTimer.singleShot(0, _update)

    def _on_ffmpeg_completed(self):
        self._ffmpeg_installed = True
        self._show_toast("FFmpeg installed successfully.", variant="success")
        def _update():
            if hasattr(self, "essentials_progress"):
                self.essentials_progress.setValue(100)
                self.essentials_progress.setVisible(False)
            if hasattr(self, "essentials_status_label"):
                self.essentials_status_label.setText("✅ Essentials are installed.")
            if hasattr(self, "install_essentials_btn"):
                self.install_essentials_btn.setEnabled(False)
        from PySide6.QtCore import QTimer
        QTimer.singleShot(0, _update)

    def _on_ffmpeg_error(self, error_msg):
        _log.error("FFmpeg installation failed: %s", error_msg)
        self._show_toast(
            f"FFmpeg installation failed: {error_msg}",
            variant="error"
        )
        def _update():
            if hasattr(self, "essentials_progress"):
                self.essentials_progress.setVisible(False)
            if hasattr(self, "essentials_status_label"):
                self.essentials_status_label.setText(f"❌ Installation failed: {error_msg}")
        from PySide6.QtCore import QTimer
        QTimer.singleShot(0, _update)

    def _run_install_essentials(self):
        """Manual FFmpeg install from Preferences page."""
        if self._ffmpeg_install_running():
            self._show_toast("FFmpeg installation already in progress.", variant="info")
            return
        if self._find_ffmpeg():
            # Already installed — drive the UI to completed state
            self._on_ffmpeg_completed()
            self._show_toast("FFmpeg is already installed.", variant="success")
            return
        if hasattr(self, "essentials_status_label"):
            self.essentials_status_label.setText("Downloading essentials...")
        if hasattr(self, "essentials_progress"):
            self.essentials_progress.setValue(0)
            self.essentials_progress.setVisible(True)
        self._install_ffmpeg_background()

    def _run_reinstall_essentials(self):
        """Force re-download and re-install FFmpeg regardless of current state."""
        if self._ffmpeg_install_running():
            self._show_toast("FFmpeg installation already in progress.", variant="info")
            return
        if hasattr(self, "essentials_status_label"):
            self.essentials_status_label.setText("Reinstalling essentials...")
        if hasattr(self, "essentials_progress"):
            self.essentials_progress.setValue(0)
            self.essentials_progress.setVisible(True)
        self._show_toast("Reinstalling FFmpeg essentials...", variant="info")
        def _on_done():
            self.dialog_requested.emit("__ffmpeg_ready__", "", None)
        def _on_error(msg):
            self.dialog_requested.emit("__ffmpeg_error__", msg, None)
        self._ffmpeg_install_thread = ffmpeg_manager.ensure_ffmpeg_background(
            on_done=_on_done,
            on_error=_on_error,
            progress_cb=self._on_ffmpeg_progress,
            force=True
        )

    def _run_update_essentials(self):
        """Check if FFmpeg needs updating; update if outdated, report if current."""
        if self._ffmpeg_install_running():
            self._show_toast("FFmpeg installation already in progress.", variant="info")
            return
        if hasattr(self, "essentials_status_label"):
            self.essentials_status_label.setText("Checking for updates...")
        if hasattr(self, "update_essentials_btn"):
            self.update_essentials_btn.setEnabled(False)

        import threading
        def _check():
            try:
                is_latest = ffmpeg_manager.is_ffmpeg_latest()
            except Exception:
                is_latest = None
            def _report():
                if hasattr(self, "update_essentials_btn"):
                    self.update_essentials_btn.setEnabled(True)
                if is_latest is True:
                    if hasattr(self, "essentials_status_label"):
                        self.essentials_status_label.setText("✅ Essentials are already the latest version.")
                    self._show_toast("FFmpeg is already up to date.", variant="success")
                elif is_latest is False:
                    if hasattr(self, "essentials_status_label"):
                        self.essentials_status_label.setText("Update available. Downloading...")
                    if hasattr(self, "essentials_progress"):
                        self.essentials_progress.setValue(0)
                        self.essentials_progress.setVisible(True)
                    self._run_reinstall_essentials()
                else:
                    if hasattr(self, "essentials_status_label"):
                        self.essentials_status_label.setText("Could not check for update. Check your connection.")
            from PySide6.QtCore import QTimer
            QTimer.singleShot(0, _report)
        threading.Thread(target=_check, daemon=True).start()

    # ── yt-dlp.exe auto-download / auto-update ───────────────────────────

    def _refresh_essentials_status(self):
        """Set the essentials status label to reflect current FFmpeg state on startup."""
        if not hasattr(self, "essentials_status_label"):
            return
        if self._find_ffmpeg():
            self.essentials_status_label.setText("✅ Essentials are installed.")
            if hasattr(self, "install_essentials_btn"):
                self.install_essentials_btn.setEnabled(False)
        else:
            self.essentials_status_label.setText("FFmpeg is not installed. Click 'Install Essentials' to download it.")
            if hasattr(self, "install_essentials_btn"):
                self.install_essentials_btn.setEnabled(True)

    def _check_ytdlp_exe_on_startup(self):
        """Check for yt-dlp.exe on startup; download if missing or update if outdated."""
        first_run = not ytdlp_exe_manager.is_exe_present()

        if first_run:
            self._show_toast(
                "Downloading yt-dlp for the first time... This may take a moment.",
                variant="info",
                duration=10000
            )
        else:
            self._ytdlp_exe_ready = True
            _log.info("yt-dlp.exe present at %s; checking for updates...", ytdlp_exe_manager.get_exe_path())

        # Read current version before the update so we can detect if it changed
        version_before = ytdlp_exe_manager._get_local_version()

        def _on_done():
            self._ytdlp_exe_ready = True
            version_after = ytdlp_exe_manager._get_local_version()
            if version_after and version_after != version_before:
                _log.info("yt-dlp.exe updated: %s -> %s", version_before or "?", version_after)
                self.dialog_requested.emit("__ytdlp_updated__", version_after, None)
            else:
                _log.info("yt-dlp.exe is up to date (%s).", version_after or "?")
                if first_run:
                    self.dialog_requested.emit("__ytdlp_ready__", "", None)

        def _on_error(msg):
            _log.error("yt-dlp.exe setup failed: %s", msg)
            self.dialog_requested.emit("__ytdlp_error__", msg, None)

        ytdlp_exe_manager.ensure_ytdlp_exe_background(
            on_done=_on_done,
            on_error=_on_error,
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
        from PySide6.QtGui import QGuiApplication
        if QGuiApplication.platformName() == "offscreen":
            return
        from PySide6.QtWidgets import QApplication
        # Ensure the main window is fully painted and visible before any modal
        # dialog opens — this prevents a blank transient "YTDownloader" window.
        if not self.isVisible():
            self.show()
        self.raise_()
        self.activateWindow()
        QApplication.processEvents()
        accepted = self.settings.value("terms_accepted", False, type=bool)
        if accepted:
            return
        dialog = TermsDialog(self._terms_text(), self.dark_mode, self)
        if dialog.exec() == QDialog.Accepted:
            self.settings.setValue("terms_accepted", True)
        else:
            self.close()

    def show_terms_dialog(self):
        dialog = TermsDialog(self._terms_text(), self.dark_mode, self)
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
            if sys.platform.startswith("linux"):
                import subprocess
                import shutil
                # Prevent xdg-open from launching Brave by explicitly checking
                # common GUI file managers first, then falling back to gio / xdg-open.
                # Crucially, clear PyInstaller's LD_LIBRARY_PATH so system apps don't crash.
                env = os.environ.copy()
                env.pop("LD_LIBRARY_PATH", None)
                for fm in ["nautilus", "dolphin", "nemo", "thunar", "caja", "pcmanfm"]:
                    if shutil.which(fm):
                        try:
                            subprocess.Popen([fm, target], env=env)
                            return
                        except Exception:
                            pass
                
                # Fallback to gio open (GNOME standard)
                if shutil.which("gio"):
                    try:
                        subprocess.Popen(["gio", "open", target], env=env)
                        return
                    except Exception:
                        pass
                
                # Last resort fallback
                try:
                        subprocess.Popen(["xdg-open", target], env=env)
                        return
                except Exception:
                        pass
            QDesktopServices.openUrl(QUrl.fromLocalFile(target))
            return
        self._show_message_dialog("Folder missing", "The folder was not found.", QMessageBox.Warning)

    def _on_show_thumbnail_toggle(self, checked):
        self.show_thumbnail = bool(checked)
        self.settings.setValue("show_thumbnail", self.show_thumbnail)
        if hasattr(self, "thumbnail"):
            self.thumbnail.setVisible(self.show_thumbnail)
        if hasattr(self, "show_thumb_cb") and self.show_thumb_cb.isChecked() != self.show_thumbnail:
            self.show_thumb_cb.blockSignals(True)
            self.show_thumb_cb.setChecked(self.show_thumbnail)
            self.show_thumb_cb.blockSignals(False)
        if hasattr(self, "show_thumbnails_pref_cb") and self.show_thumbnails_pref_cb.isChecked() != self.show_thumbnail:
            self.show_thumbnails_pref_cb.blockSignals(True)
            self.show_thumbnails_pref_cb.setChecked(self.show_thumbnail)
            self.show_thumbnails_pref_cb.blockSignals(False)

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
            empty.setAlignment(Qt.AlignCenter)
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
                self._style_btn(self._library_load_more_btn)
                self._library_load_more_btn.clicked.connect(self._load_more_library)
            try:
                self.library_layout.addWidget(self._library_load_more_btn)
            except RuntimeError:
                # Fallback: recreate if Qt already deleted the cached instance.
                self._library_load_more_btn = QPushButton("Load more")
                self._library_load_more_btn.setObjectName("GhostButton")
                self._style_btn(self._library_load_more_btn)
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
        card.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
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
        title_text = item.get("title") or "Unknown"
        title = ElidedLabel(title_text)
        title.setObjectName("LibraryTitle")
        info_layout.addWidget(title)

        filepath = item.get("filepath") or ""
        if filepath:
            filename = os.path.basename(filepath)
            file_label = ElidedLabel(filename)
            info_layout.addWidget(file_label)
        else:
            missing = ElidedLabel("File path not available")
            missing.setObjectName("MutedText")
            info_layout.addWidget(missing)

        btn_row = QHBoxLayout()
        open_btn = QPushButton("Open Folder")
        open_btn.setObjectName("GhostButton")
        self._style_btn(open_btn)
        if filepath:
            open_btn.clicked.connect(lambda: self._open_folder(filepath))
        else:
            open_btn.setEnabled(False)
        btn_row.addWidget(open_btn)

        remove_btn = QPushButton("Remove")
        remove_btn.setObjectName("GhostButton")
        self._style_btn(remove_btn)
        remove_btn.clicked.connect(lambda: self.remove_history_item(item, delete_file=False))
        btn_row.addWidget(remove_btn)

        delete_btn = QPushButton("Delete File")
        delete_btn.setObjectName("GhostButton")
        self._style_btn(delete_btn)
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
        self._collapse_details()
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

        # Warn the user if FFmpeg is missing and they selected a specific quality.
        # Without FFmpeg, yt-dlp cannot merge split streams, so YouTube only delivers
        # progressive (single-file) streams which are capped at 360p.
        if "auto" not in quality.lower() and not self._find_ffmpeg():
            self._show_toast(
                "⚠️ FFmpeg is not installed — quality is limited to 360p. "
                "Go to Preferences → Install Essentials to fix this.",
                variant="warning",
                duration=8000
            )

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
        self._expand_details()

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
        self._handle_browser_lock_restart(browser_name, msg, retry_cb=self.fetch_info)

    def _on_download_cookie_lock(self, task_id, browser_name, msg):
        # We don't autostart because the task is now probably failed/stopped
        self._handle_browser_lock_restart(browser_name, msg, retry_cb=None)

    def _handle_browser_lock_restart(self, browser_name, details, retry_cb=None):
        _log.warning("Browser lock detected for %s: %s", browser_name, details)
        from PySide6.QtWidgets import QMessageBox
        msg_box = QMessageBox(self)
        display_name = browser_name.capitalize()
        msg_box.setWindowTitle(f"{display_name} Locked")
        targets = ", ".join(self._browser_process_names(browser_name))
        msg_box.setText(f"YouTube requires cookies from {display_name}, but the browser is currently open and locking them.")
        msg_box.setInformativeText(
            f"This will force-close all running {display_name} windows/processes"
            f"{f' ({targets})' if targets else ''}. Save open work first.\n\n"
            "Close the browser now and continue?"
        )
        msg_box.setStandardButtons(QMessageBox.Yes | QMessageBox.No)
        msg_box.setDefaultButton(QMessageBox.No)
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

    def _browser_process_names(self, name):
        name_lower = (name or "").lower()
        if sys.platform == "win32":
            proc_map = {
                "chrome": "chrome.exe",
                "edge": "msedge.exe",
                "firefox": "firefox.exe",
                "brave": "brave.exe",
                "opera": "opera.exe",
                "vivaldi": "vivaldi.exe",
                "chromium": "chromium.exe",
            }
        else:
            proc_map = {
                "chrome": "chrome",
                "edge": "msedge",
                "firefox": "firefox",
                "brave": "brave",
                "opera": "opera",
                "vivaldi": "vivaldi",
                "chromium": "chromium",
            }
        proc_name = next((v for k, v in proc_map.items() if k in name_lower), "")
        if not proc_name and re.fullmatch(r"[A-Za-z0-9._-]+", name_lower):
            proc_name = f"{name_lower}.exe" if sys.platform == "win32" else name_lower
        return [proc_name] if proc_name else []

    def _kill_browser(self, name):
        try:
            import subprocess
            import sys as _sys
            proc_names = self._browser_process_names(name)
            if not proc_names:
                _log.warning("Refusing to force-close unknown browser process name: %s", name)
                return False
            if _sys.platform == "win32":
                for proc_name in proc_names:
                    completed = subprocess.run(
                        ["taskkill", "/F", "/IM", proc_name],
                        capture_output=True,
                        text=True,
                        creationflags=0x08000000
                    )
                    _log.warning("Force-closed browser process %s with exit code %s", proc_name, completed.returncode)
                    if completed.returncode not in (0, 128):
                        return False
            else:
                for proc_name in proc_names:
                    completed = subprocess.run(
                        ["pkill", "-x", proc_name],
                        capture_output=True,
                        text=True,
                    )
                    _log.warning("Force-closed browser process %s with exit code %s", proc_name, completed.returncode)
                    if completed.returncode not in (0, 1):
                        return False
            return True
        except Exception as e:
            _log.warning("Failed to kill browser %s: %s", name, e)
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
                f"Playlist queued: {len(entries)} videos. Progress will continue in Downloads.",
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
            "generation": self._ui_generation,
            "payload": payload,
            "title": title_text,
            "state": TASK_STATE_QUEUED,
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
                "Download started. Progress is in Downloads.",
                variant="info",
                duration=2200,
                anchor_widget=self.nav_library_btn
            )
        self._persist_queue()
        if autostart:
            self._start_next_downloads()

    def _start_next_downloads(self):
        if self._is_cancel_cleanup_blocking():
            self._update_global_progress()
            self._persist_queue()
            return
        self._release_cancel_gate_if_safe(start_pending=False)
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
            if task.get("generation") != self._ui_generation:
                return

            task_id = task["id"]
            payload = task["payload"]
            _log.info("Starting task %s for url=%s", task_id, payload.get("url"))

            task["state"] = TASK_STATE_STARTING
            self._touch_task_activity(task_id)
            item = task["item"]
            item["status"].setText("Starting...")
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
            task["state"] = TASK_STATE_ACTIVE
            item["status"].setText("Downloading...")
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
                task["state"] = TASK_STATE_PAUSED
                task["item"]["status"].setText("Pausing...")
                task["item"]["pause_btn"].setText("Resume")
                task["item"]["pause_btn"].setEnabled(False)
                worker.request_pause()
            return
        if task_id in self._paused_tasks:
            task = self._paused_tasks.pop(task_id)
            task["state"] = TASK_STATE_QUEUED
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
                task["state"] = TASK_STATE_CANCELLING
                self._cancel_cleanup_pending = True
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
            if self._active_tasks:
                self._cancel_grace_timer.start(self._CANCEL_GRACE_MS)
            self._sync_download_button_text()
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
        if not task or task.get("generation") != self._ui_generation:
            return
        task["state"] = TASK_STATE_PAUSED
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

    def on_download_complete(self, task_id, items):
        task = self._active_tasks.pop(task_id, None)
        self._clear_task_activity(task_id)
        if not task or task.get("generation") != self._ui_generation:
            return
        task["state"] = TASK_STATE_COMPLETED
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

        # Re-enable the download button for single-video downloads so the user
        # can immediately download the same video at a different quality without
        # having to re-analyze the URL.
        if not session_id and self._active_url and self._active_url == (self._active_url or ""):
            no_active = not any(
                self._thread_is_running(t) for t in self._download_threads.values()
            )
            if no_active and not self._active_tasks:
                self._info_ready = True
                self.download_btn.setEnabled(True)
                self._set_config_enabled(True)
                self._sync_download_button_text()


    def on_download_error(self, task_id, msg):
        try:
            task = self._active_tasks.get(task_id)
            if not task or task.get("generation") != self._ui_generation:
                _log.info("Ignoring late error for inactive task %s: %s", task_id, msg)
                return
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
        self._release_cancel_gate_if_safe(start_pending=False)
        self._start_next_downloads()

    def _finalize_task_if_still_active(self, task_id):
        if task_id in self._active_tasks:
            _log.warning(
                "Task %s still active after thread finished; marking task failed.",
                task_id
            )
            self._mark_task_failed(task_id)
            return
        self._release_cancel_gate_if_safe()

    @Slot(str, float, object, object, object)
    def update_progress(self, task_id, percent, speed=None, downloaded=None, total=None):
        try:
            value = int(percent)
        except Exception:
            value = 0
        value = max(0, min(100, value))
        task = self._active_tasks.get(task_id)
        if not task or task.get("generation") != self._ui_generation:
            return
        self._touch_task_activity(task_id)
        task["downloaded"] = downloaded if downloaded is not None else task.get("downloaded")
        task["total"] = total if total is not None else task.get("total")
        item = task.get("item") or {}
        try:
            if item.get("progress"):
                item["progress"].setValue(value)
            if value >= 100 and task.get("state") in (TASK_STATE_ACTIVE, TASK_STATE_PAUSED):
                task["state"] = TASK_STATE_FINALIZING
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
                    item["size"].setVisible(True)
                    item["size"].setText(f"{downloaded_text} MB / {total_text} MB")
                elif downloaded_text is not None:
                    item["size"].setVisible(True)
                    item["size"].setText(f"{downloaded_text} MB")

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
        if self._is_cancel_cleanup_blocking():
            target = "Stopping..."
        elif self._info_ready and self.download_btn.isEnabled():
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
                "state": task.get("state", TASK_STATE_QUEUED)
            })
        for task in self._paused_tasks.values():
            tasks.append({
                "id": task["id"],
                "title": task["title"],
                "payload": task["payload"],
                "state": TASK_STATE_PAUSED,
            })
        for task in self._active_tasks.values():
            tasks.append({
                "id": task["id"],
                "title": task["title"],
                "payload": task["payload"],
                "state": task.get("state", TASK_STATE_ACTIVE),
            })
        queue_manager.save_queue(tasks)

    def _restore_queued_task(self, saved):
        if not isinstance(saved, dict):
            return False
        payload = saved.get("payload")
        if not isinstance(payload, dict) or not payload.get("url"):
            return False

        task_id = saved.get("id") or uuid.uuid4().hex
        title_text = saved.get("title") or payload.get("url") or "Queued download"
        saved_state = (saved.get("state") or "queued").lower()
        state = TASK_STATE_PAUSED if saved_state == TASK_STATE_PAUSED else TASK_STATE_QUEUED
        task = {
            "id": task_id,
            "generation": self._ui_generation,
            "payload": payload,
            "title": title_text,
            "state": state,
            "downloaded": None,
            "total": None
        }

        item = self._create_download_item(title_text)
        task["item"] = item
        item["pause_btn"].setProperty("task_id", task_id)
        if item.get("cancel_btn"):
            item["cancel_btn"].setProperty("task_id", task_id)
            item["cancel_btn"].setText("Cancel")
            item["cancel_btn"].setEnabled(True)
            item["cancel_btn"].setVisible(True)
        if state == TASK_STATE_PAUSED:
            item["status"].setText("Paused")
            item["pause_btn"].setText("Resume")
            item["pause_btn"].setEnabled(True)
            self._paused_tasks[task_id] = task
        else:
            item["status"].setText("Queued")
            item["pause_btn"].setText("Pause")
            item["pause_btn"].setEnabled(False)
            self._pending_tasks.append(task)

        self.active_downloads_layout.insertWidget(0, item["frame"])
        return True

    def _load_persistent_queue(self):
        if not hasattr(queue_manager, "load_queue"):
            return
        items = queue_manager.load_queue()
        if not items:
            return
        restored = 0
        for saved in items:
            if self._restore_queued_task(saved):
                restored += 1
        if not restored:
            queue_manager.clear_queue()
            return
        self._update_downloads_header()
        self._show_downloads_panel(True)
        self._update_global_progress()
        self._show_toast(
            f"Restored {restored} queued download(s).",
            variant="info",
            duration=2400,
            anchor_widget=self.nav_library_btn
        )
        QTimer.singleShot(1200, self._start_next_downloads)

    def _reset_download_ui(self):
        self._animate_button_text(self.download_btn, "Start Download")
        if getattr(self, "progress", None):
            self.progress.setValue(0)
            self.progress.setFormat("0%")
        self._last_progress_value = 0

    def reset_ui(self):
        if self._thread_is_running(self._fetch_thread):
            worker = getattr(self, "_fetch_worker", None)
            if worker and hasattr(worker, "request_cancel"):
                try:
                    worker.request_cancel()
                except Exception:
                    pass
            return

        self._ui_generation += 1

        if self._active_tasks or self._has_running_download_threads():
            # Cancel the full pipeline: active + queued + paused + playlist session state.
            self._playlist_sessions.clear()
            self._clear_non_active_downloads()
            self._request_cancel_all_downloads("Cancelling...")
            self._show_toast("Stopping active downloads...", variant="info")

        if self._cancel_grace_timer.isActive() and not self._cancel_cleanup_pending:
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
        self._release_cancel_gate_if_safe(start_pending=False)
        queue_manager.clear_queue()
        self._show_downloads_panel(False)
        self._collapse_details()
        self._clear_downloads_list()
        self.active_download_item = None
        self._update_global_progress()

    def clear_homepage_ui(self):
        """Reset the homepage input/metadata area WITHOUT affecting active downloads.

        This is what the homepage "Reset" button should call — it clears the URL,
        title, thumbnail, and format selectors so the user can paste a new link,
        but never cancels or interferes with running download tasks.
        """
        # Cancel any in-progress metadata fetch (harmless if nothing is running)
        if self._thread_is_running(self._fetch_thread):
            worker = getattr(self, "_fetch_worker", None)
            if worker and hasattr(worker, "request_cancel"):
                try:
                    worker.request_cancel()
                except Exception:
                    pass

        self.fetch_btn.setEnabled(True)
        self.fetch_btn.setText("Analyze")
        if hasattr(self, "fetch_spinner"):
            self.fetch_spinner.setVisible(False)
        self.download_btn.setEnabled(False)
        self._reset_download_ui()
        self.url_input.clear()
        self._collapse_details()
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
        self._info_ready = False
        self._estimated_size_mb = None
        self._sync_download_button_text()


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
        raw = text.strip()
        self.proxy_display_url = save_proxy_url(raw)
        self.proxy_url = restore_proxy_secret(self.proxy_display_url)
        self.settings.setValue("proxy_url", self.proxy_display_url)

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
        if not custom_update_urls_enabled() and self.update_manifest_url != DEFAULT_UPDATE_MANIFEST_URL:
            self.update_manifest_url = DEFAULT_UPDATE_MANIFEST_URL
            self.update_url_input.blockSignals(True)
            self.update_url_input.setText(self.update_manifest_url)
            self.update_url_input.blockSignals(False)
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
        try:
            validate_update_url(url)
        except Exception as exc:
            if manual:
                self._show_message_dialog("Updates", f"Update URL blocked:\n{exc}", QMessageBox.Warning)
            _log.warning("Blocked update URL %s: %s", url, exc)
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
        if "404" in (msg or ""):
            _log.info(
                "Update endpoint returned 404; pausing startup checks for the current release endpoint."
            )
            self.update_url_404_disabled = True
            self.update_url_404_value = (self.update_manifest_url or "").strip()
            self.settings.setValue("update_url_404_disabled", True)
            self.settings.setValue("update_url_404_value", self.update_url_404_value)
            self.check_updates_on_startup = False
            self.settings.setValue("check_updates_on_startup", False)
            if hasattr(self, "check_updates_cb"):
                self.check_updates_cb.setChecked(False)
            if getattr(self, "_update_manual", False):
                self._show_message_dialog(
                    "Updates",
                    "Update endpoint returned 404.\n"
                    "This can happen when release metadata is private or unavailable. "
                    "Startup update checks are paused for this URL.",
                    QMessageBox.Warning
                )
            return
        _log.warning("Update error: %s", msg)
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
            if sys.platform == "win32":
                os.startfile(path)
            else:
                try:
                    current = os.stat(path).st_mode
                    os.chmod(path, current | 0o755)
                except Exception:
                    pass
                QDesktopServices.openUrl(QUrl.fromLocalFile(path))
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
        if not self._cookie_is_valid(path, require_auth=True):
            self._show_error_dialog(
                "Cookies",
                "Invalid cookies file. Please select a Netscape cookies.txt "
                "that contains signed-in YouTube and Google account cookies "
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
        if self._cookie_is_valid(self.cookie_file, require_auth=True):
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
            try:
                from ui.session_manager import get_browser_auto_order
                return get_browser_auto_order()
            except Exception:
                if sys.platform.startswith("linux"):
                    return ["firefox", "chrome", "edge", "brave", "opera", "chromium"]
                return ["chrome", "firefox", "edge", "brave", "opera", "chromium"]
        if profile:
            return f"{source}:{profile}"
        return source

    def update_cookie_indicator(self):
        effective_file = self._effective_cookie_file()
        effective_browser = self._effective_browser_auth()
        for indicator, status in self.cookie_status_widgets:
            if effective_browser:
                indicator.setStyleSheet("border-radius: 6px; background: #10b981;")
                status.setText("Browser connected")
            elif effective_file:
                indicator.setStyleSheet("border-radius: 6px; background: #10b981;")
                status.setText("Cookies file loaded")
            else:
                indicator.setStyleSheet("border-radius: 6px; background: #f59e0b;")
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
        # Keep the "Login to YouTube" status label in sync
        if effective_file or effective_browser:
            self._update_yt_login_ui("done")
        else:
            self._update_yt_login_ui("idle")

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
        self.restricted_mode = True
        self.settings.setValue("browser_auth_source", self.browser_auth_source)
        self.settings.setValue("browser_auth_profile", self.browser_auth_profile)
        self.browser_auth_enabled = False
        self.settings.setValue("browser_auth_enabled", False)
        self.settings.setValue("restricted_mode", True)
        self.update_cookie_indicator()

        # Verify we can actually extract signed-in cookies before showing
        # "connected". The extracted file is then used for downloads.
        self._show_toast("Testing browser connection…", variant="info", duration=3000)
        import threading
        def _test_connection():
            try:
                from ui.session_manager import save_cookies_from_browser, get_auth_cookie_names_in_file
                cookie_path = save_cookies_from_browser(source)
                auth_names = get_auth_cookie_names_in_file(cookie_path)
                n_auth = len(auth_names)
                if n_auth > 0:
                    self.dialog_requested.emit(
                        "__browser_auth_success__",
                        cookie_path,
                        {
                            "source": source,
                            "cookie_path": cookie_path,
                            "n_auth": n_auth,
                        }
                    )
                else:
                    self.dialog_requested.emit(
                        "__browser_auth_failed__",
                        f"Connected to {source.title()}, but no YouTube/Google login cookies were found.\n\n"
                        "Please log in to YouTube in your browser, then click 'Connect Browser' again.",
                        None
                    )
            except Exception as exc:
                err = str(exc)
                _log.warning("Browser auth smoke-test failed for %s: %s", source, err)
                self.dialog_requested.emit("__browser_auth_failed__", err, None)
        t = threading.Thread(target=_test_connection, daemon=True)
        t.start()



    def _disconnect_browser_auth(self):
        self.browser_auth_enabled = False
        self.settings.setValue("browser_auth_enabled", False)
        self.update_cookie_indicator()
        self._show_message_dialog("Browser Auth", "Browser auth disconnected.")

    # ── YouTube dialog-based login ─────────────────────────────────────────

    def _yt_open_login_dialog(self):
        """Open the polished YouTube Login popup dialog."""
        from ui.yt_login_dialog import YouTubeLoginDialog
        browser_name = getattr(self, "browser_auth_source", "") or "auto"
        dlg = YouTubeLoginDialog(
            dark_mode=self.dark_mode,
            initial_browser=browser_name,
            parent=self,
        )
        dlg.accepted.connect(lambda: self._on_yt_login_dialog_accepted(dlg.cookie_path))
        dlg.open()

    def _yt_logout(self):
        """User clicked 'Logout' — clear the managed session."""
        from ui.session_manager import clear_session
        clear_session()
        self.cookie_file = ""
        self.settings.remove("cookie_file")
        self.restricted_mode = False
        self.settings.setValue("restricted_mode", False)
        self.update_cookie_indicator()
        self._update_yt_login_ui("idle")
        self._show_message_dialog("Logged Out", "YouTube session cleared.")

    def _on_yt_login_dialog_accepted(self, cookie_path: str):
        """Called when the YouTubeLoginDialog was accepted with a valid cookie file."""
        _log.info("YouTube login dialog accepted; cookie_path=%s", cookie_path)
        self.cookie_file = cookie_path
        self.settings.setValue("cookie_file", cookie_path)
        self.restricted_mode = True
        self.settings.setValue("restricted_mode", True)
        self.browser_auth_enabled = False
        self.settings.setValue("browser_auth_enabled", False)
        self.update_cookie_indicator()
        self._update_yt_login_ui("done")

    def _update_yt_login_ui(self, state: str):
        """Sync the Login-to-YouTube button label and status label with *state*."""
        login_btn  = getattr(self, "yt_login_btn",         None)
        logout_btn = getattr(self, "yt_logout_btn",        None)
        status_lbl = getattr(self, "yt_login_status_label", None)

        labels = {
            "idle":   "Status: Not connected",
            "done":   "Status: \u2705 Connected",
            "failed": "Status: Login failed \u2014 please try again.",
        }
        if status_lbl:
            status_lbl.setText(labels.get(state, labels["idle"]))

        if login_btn:
            login_btn.setEnabled(True)
        if logout_btn:
            logout_btn.setEnabled(True)



    def _cookie_is_valid(self, path, require_auth=False):
        """Return True only if *path* is a valid, non-empty Netscape cookies file
        that contains at least one actual cookie row. When *require_auth* is
        true, it must also contain YouTube and Google account cookies."""
        if not path or not os.path.exists(path):
            return False
        try:
            size = os.path.getsize(path)
        except Exception:
            return False
        if size <= 0 or size > MAX_COOKIE_FILE_BYTES:
            return False
        # Require at least one real cookie row (7 tab-separated fields).
        # This rejects header-only files that would confuse yt-dlp.
        try:
            with open(path, "r", encoding="utf-8", errors="replace") as fh:
                for line in fh:
                    s = line.strip()
                    if not s or s.startswith("#"):
                        continue
                    if len(s.split("\t")) >= 7:
                        if not require_auth:
                            return True
                        try:
                            from ui.session_manager import has_required_auth_cookies
                            return has_required_auth_cookies(path)
                        except Exception:
                            return True
        except Exception:
            pass
        return False

    def show_cookies_help(self):
        from ui.dialogs import CookiesHelpDialog
        dialog = CookiesHelpDialog(
            "Normal mode works for public videos without cookies.\n\n"
            "Manual cookies (cookies.txt):\n"
            "1. Install a cookies export extension in your browser.\n"
            "2. Log in to YouTube and export YouTube + Google cookies in Netscape format.\n"
            "3. Save the file as cookies.txt.\n"
            "4. In the Cookies tab, click “Set Cookies File” and select it.\n"
            "5. Keep the file private and refresh it when it expires.\n\n"
            "Do not share your cookies with anyone.",
            self.dark_mode,
            self
        )
        dialog.exec()

    def closeEvent(self, event):
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
        if self._task_watchdog.isActive():
            self._task_watchdog.stop()
        if self._cancel_grace_timer.isActive():
            self._cancel_grace_timer.stop()
        if self._library_nav_pulse_timer.isActive():
            self._library_nav_pulse_timer.stop()
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
