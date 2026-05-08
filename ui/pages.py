from PySide6.QtWidgets import (
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
    QScrollArea,
    QSizePolicy,
    QSpinBox,
    QListView
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont

from ui.widgets import FadingTextButton, PasteButton


class PagesMixin:
    def _build_downloader_page(self):
        page = QWidget()
        page.setObjectName("Page")
        layout = QVBoxLayout(page)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(10)

        input_row = QHBoxLayout()

        self.playlist_toggle = QCheckBox("Playlist")
        self.playlist_toggle.setObjectName("PlaylistToggle")
        self.playlist_toggle.setToolTip(
            "Downloading entire playlist forces Format and Quality to Auto."
        )
        self.playlist_toggle.toggled.connect(self._on_playlist_toggle)

        self.paste_btn = PasteButton()
        self.paste_btn.clicked.connect(self._paste_from_clipboard)
        self.url_input = QLineEdit()
        self.url_input.setObjectName("UrlInput")
        self.url_input.setPlaceholderText("Paste YouTube link...")
        self.url_input.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        self.url_input.setTextMargins(6, 0, 6, 0)
        self.url_input.textChanged.connect(self._on_url_changed)

        self.fetch_btn = FadingTextButton("Analyze")
        self.fetch_btn.setObjectName("PrimaryButton")
        self.fetch_btn.setFixedWidth(150)

        self.fetch_spinner = QProgressBar()
        self.fetch_spinner.setObjectName("FetchBar")
        self.fetch_spinner.setRange(0, 0)
        self.fetch_spinner.setTextVisible(False)
        self.fetch_spinner.setFixedHeight(4)
        self.fetch_spinner.setVisible(False)

        url_wrap = QWidget()
        url_layout = QVBoxLayout(url_wrap)
        url_layout.setContentsMargins(0, 0, 0, 0)
        url_layout.setSpacing(0)
        url_layout.addWidget(self.url_input)
        url_layout.addWidget(self.fetch_spinner)

        input_row.addWidget(self.playlist_toggle)
        input_row.addWidget(self.paste_btn)
        input_row.addWidget(url_wrap, 1)
        input_row.addWidget(self.fetch_btn)
        layout.addLayout(input_row)

        self.details_container = QWidget()
        details_layout = QVBoxLayout(self.details_container)
        details_layout.setContentsMargins(0, 0, 0, 2)
        details_layout.setSpacing(8)

        preview_label = QLabel("Video Preview")
        preview_label.setObjectName("SectionTitle")
        details_layout.addWidget(preview_label)

        preview_card = QFrame()
        preview_card.setObjectName("Card")
        preview_layout = QHBoxLayout(preview_card)
        preview_layout.setContentsMargins(16, 12, 16, 12)
        preview_layout.setSpacing(18)
        preview_layout.setAlignment(Qt.AlignVCenter)

        self.thumbnail = QLabel()
        self.thumbnail.setObjectName("PreviewThumb")
        self.thumbnail.setFixedSize(200, 112)
        self.thumbnail.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        self.thumbnail.setScaledContents(False)
        self.thumbnail.setAlignment(Qt.AlignCenter)
        self.thumbnail.setStyleSheet("border-radius: 12px; background: #dfe7f2;")
        self.thumbnail.setPixmap(self._placeholder_pixmap(self.thumbnail.size()))
        self.thumbnail.setVisible(self.show_thumbnail)
        thumb_wrap = QWidget()
        thumb_wrap_layout = QVBoxLayout(thumb_wrap)
        thumb_wrap_layout.setContentsMargins(0, 0, 0, 0)
        thumb_wrap_layout.setSpacing(0)
        thumb_wrap_layout.addStretch(1)
        thumb_wrap_layout.addWidget(self.thumbnail, 0, Qt.AlignLeft | Qt.AlignVCenter)
        thumb_wrap_layout.addStretch(1)
        preview_layout.addWidget(thumb_wrap, 0, Qt.AlignVCenter)

        info_layout = QVBoxLayout()
        info_layout.setContentsMargins(0, 4, 0, 0)
        info_layout.setSpacing(0)
        self.title = QLabel("Title: -")
        self.title.setObjectName("InfoTitle")
        self.title.setWordWrap(True)
        self.title.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        self.title.setMaximumHeight(42)

        self.size = QLabel("Estimated size: -")
        self.size.setObjectName("InfoSubtle")

        info_layout.addWidget(self.title)
        info_layout.addSpacing(6)
        info_layout.addWidget(self.size)

        info_layout.addSpacing(14)

        info_layout.addStretch(1)

        bottom_row = QHBoxLayout()
        bottom_row.setSpacing(12)
        bottom_row.setAlignment(Qt.AlignBottom)

        self.show_thumb_cb = QCheckBox("Show thumbnail")
        self.show_thumb_cb.setObjectName("ThumbToggle")
        self.show_thumb_cb.setChecked(self.show_thumbnail)
        self.show_thumb_cb.toggled.connect(self._on_show_thumbnail_toggle)
        bottom_row.addWidget(self.show_thumb_cb)

        self.reset_btn = QPushButton("Reset")
        self.reset_btn.setObjectName("GhostButton")
        self.reset_btn.setMinimumHeight(32)
        self.reset_btn.setMinimumWidth(80)
        reset_font = self.reset_btn.font()
        reset_font.setWeight(QFont.Medium)
        self.reset_btn.setFont(reset_font)
        self.reset_btn.clicked.connect(self.clear_homepage_ui)

        bottom_row.addLayout(self._make_cookie_status_row(self.reset_btn))
        info_layout.addLayout(bottom_row)
        preview_layout.addLayout(info_layout, 1)
        preview_layout.setStretch(0, 0)
        preview_layout.setStretch(1, 1)

        preview_wrap = QWidget()
        preview_wrap_layout = QVBoxLayout(preview_wrap)
        preview_wrap_layout.setContentsMargins(22, 8, 22, 8)
        preview_wrap_layout.addWidget(preview_card)
        details_layout.addWidget(preview_wrap)
        self._apply_shadow(preview_card, 22, 96, 0)

        config_label = QLabel("Configuration")
        config_label.setObjectName("SectionTitle")
        details_layout.addWidget(config_label)

        config_card = QFrame()
        config_card.setObjectName("Card")
        config_layout = QVBoxLayout(config_card)
        config_layout.setContentsMargins(16, 16, 16, 16)
        config_layout.setSpacing(10)

        self.config_content = QWidget()
        config_content_layout = QVBoxLayout(self.config_content)
        config_content_layout.setContentsMargins(0, 0, 0, 0)
        config_content_layout.setSpacing(10)

        columns = QHBoxLayout()
        columns.setSpacing(24)

        left_col = QVBoxLayout()
        left_col.setSpacing(10)
        format_row = QHBoxLayout()
        format_row.addWidget(QLabel("Format"))
        self.format_combo = QComboBox()
        format_row.addWidget(self.format_combo, 1)
        left_col.addLayout(format_row)

        quality_row = QHBoxLayout()
        quality_row.addWidget(QLabel("Quality"))
        self.quality = QComboBox()
        quality_row.addWidget(self.quality, 1)
        left_col.addLayout(quality_row)

        right_col = QVBoxLayout()
        right_col.setSpacing(10)
        self.subs_checkbox = QCheckBox("Download subtitles (if available)")
        right_col.addWidget(self.subs_checkbox)

        self.embed_subs_checkbox = QCheckBox("Embed subtitles")
        self.embed_subs_checkbox.setChecked(False)
        right_col.addWidget(self.embed_subs_checkbox)

        lang_row = QHBoxLayout()
        lang_row.addWidget(QLabel("Subtitles language"))
        self.subs_lang = QComboBox()
        self.subs_lang.setToolTip("Examples: en,es | en-US | ja")
        self.subs_lang.setMinimumWidth(180)
        lang_row.addWidget(self.subs_lang, 1)
        right_col.addLayout(lang_row)

        columns.addLayout(left_col, 1)
        columns.addLayout(right_col, 1)
        config_content_layout.addLayout(columns)
        config_layout.addWidget(self.config_content)

        config_wrap = QWidget()
        config_wrap_layout = QVBoxLayout(config_wrap)
        config_wrap_layout.setContentsMargins(22, 8, 22, 8)
        config_wrap_layout.addWidget(config_card)
        details_layout.addWidget(config_wrap)
        self._apply_shadow(config_card, 22, 96, 0)

        layout.addWidget(self.details_container)

        actions_col = QVBoxLayout()
        self.download_btn = FadingTextButton("Start Download")
        self.download_btn.setObjectName("PrimaryButton")
        self.download_btn.setMinimumHeight(36)
        self.download_btn.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.download_btn.setEnabled(False)
        actions_col.addWidget(self.download_btn)
        self.progress = None
        layout.addLayout(actions_col)

        self.fetch_btn.clicked.connect(self.fetch_info)
        self.download_btn.clicked.connect(self.start_download)
        self._clear_format_quality()
        self._set_config_enabled(False)

        return page

    def _build_downloads_panel(self):
        self.downloads_panel = QFrame()
        self.downloads_panel.setObjectName("DownloadsPanel")
        self.downloads_panel.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Preferred)
        self.downloads_panel.setMaximumHeight(300)
        downloads_layout = QVBoxLayout(self.downloads_panel)
        downloads_layout.setContentsMargins(10, 10, 10, 10)
        downloads_layout.setSpacing(6)

        downloads_header_row = QHBoxLayout()
        downloads_header = QLabel("Active downloads (0)")
        downloads_header.setObjectName("CardTitle")
        self.downloads_header = downloads_header
        downloads_header_row.addWidget(downloads_header)
        downloads_header_row.addStretch(1)
        self.reset_btn_downloads = QPushButton("Reset")
        self.reset_btn_downloads.setObjectName("GhostButton")
        self.reset_btn_downloads.setMinimumHeight(30)
        self.reset_btn_downloads.setMinimumWidth(96)
        self.reset_btn_downloads.clicked.connect(self.reset_ui)
        downloads_header_row.addWidget(self.reset_btn_downloads)
        downloads_layout.addLayout(downloads_header_row)

        self.downloads_scroll = QScrollArea()
        self.downloads_scroll.setWidgetResizable(True)
        self.downloads_scroll.setObjectName("GlassScroll")
        self.downloads_scroll.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.downloads_scroll.setMinimumHeight(140)
        self.downloads_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.downloads_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.downloads_container = QWidget()
        self.downloads_container.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        self.downloads_container.setMinimumWidth(0)
        self.downloads_list_layout = QVBoxLayout(self.downloads_container)
        self.downloads_list_layout.setSpacing(8)
        self.downloads_list_layout.setContentsMargins(0, 0, 0, 0)

        self.library_empty_label = QLabel("No active, queued, or paused downloads.")
        self.library_empty_label.setObjectName("MutedText")
        self.library_empty_label.setWordWrap(True)
        self.downloads_list_layout.addWidget(self.library_empty_label)

        self.active_downloads_layout = QVBoxLayout()
        self.active_downloads_layout.setSpacing(8)
        self.downloads_list_layout.addLayout(self.active_downloads_layout)
        self.downloads_list_layout.addSpacing(4)
        self.completed_downloads_layout = QVBoxLayout()
        self.completed_downloads_layout.setSpacing(8)
        self.downloads_list_layout.addLayout(self.completed_downloads_layout)

        self.downloads_scroll.setWidget(self.downloads_container)
        downloads_layout.addWidget(self.downloads_scroll)
        self.downloads_panel.setVisible(True)
        return self.downloads_panel

    def _build_library_page(self):
        page = QWidget()
        page.setObjectName("Page")
        layout = QVBoxLayout(page)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(12)

        title = QLabel("Downloads")
        title.setObjectName("SectionTitle")
        layout.addWidget(title)

        library_card = QFrame()
        library_card.setObjectName("Card")
        library_card_layout = QVBoxLayout(library_card)
        library_card_layout.setContentsMargins(12, 10, 12, 10)
        library_card_layout.setSpacing(8)
        library_card_layout.addWidget(self._build_downloads_panel(), 1)

        layout.addWidget(library_card, 1)
        self._apply_shadow(library_card, 22, 96, 0)
        return page

    def _build_history_page(self):
        page = QWidget()
        page.setObjectName("Page")
        layout = QVBoxLayout(page)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(12)

        header = QHBoxLayout()
        title = QLabel("History")
        title.setObjectName("SectionTitle")
        header.addWidget(title)
        self.library_search = QLineEdit()
        self.library_search.setPlaceholderText("Search history...")
        self.library_search.textChanged.connect(self._on_library_search_changed)
        header.addWidget(self.library_search, 1)
        header.addStretch(1)

        clear_btn = QPushButton("Clear History")
        clear_btn.setObjectName("GhostButton")
        clear_btn.clicked.connect(self.clear_library)
        header.addWidget(clear_btn)
        layout.addLayout(header)

        history_card = QFrame()
        history_card.setObjectName("Card")
        history_card_layout = QVBoxLayout(history_card)
        history_card_layout.setContentsMargins(12, 10, 12, 10)
        history_card_layout.setSpacing(8)

        self.library_scroll = QScrollArea()
        self.library_scroll.setWidgetResizable(True)
        self.library_scroll.setObjectName("GlassScroll")

        self.library_container = QWidget()
        self.library_layout = QVBoxLayout(self.library_container)
        self.library_layout.setSpacing(10)
        self.library_layout.setContentsMargins(0, 0, 0, 0)

        self.library_scroll.setWidget(self.library_container)
        history_card_layout.addWidget(self.library_scroll, 1)
        layout.addWidget(history_card, 1)
        self._apply_shadow(history_card, 22, 96, 0)
        return page

    def _build_options_page(self):
        page = QWidget()
        page.setObjectName("Page")
        layout = QVBoxLayout(page)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(12)

        title = QLabel("Preferences")
        title.setObjectName("SectionTitle")
        layout.addWidget(title)

        options_card = QFrame()
        options_card.setObjectName("OptionsCard")
        options_card_layout = QVBoxLayout(options_card)
        options_card_layout.setContentsMargins(12, 10, 12, 10)
        options_card_layout.setSpacing(8)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setObjectName("GlassScroll")
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)

        content = QWidget()
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(2, 2, 2, 2)
        content_layout.setSpacing(12)
        content_layout.addWidget(self._build_downloads_card())
        content_layout.addWidget(self._build_updates_card())
        content_layout.addWidget(self._build_appearance_card())
        content_layout.addStretch(1)

        scroll.setWidget(content)
        options_card_layout.addWidget(scroll, 1)
        layout.addWidget(options_card, 1)
        self._apply_shadow(options_card, 22, 96, 0)
        return page

    def _build_downloads_card(self):
        card = QFrame()
        card.setObjectName("Card")
        layout = QVBoxLayout(card)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(10)

        title = QLabel("Download settings")
        title.setObjectName("CardTitle")
        layout.addWidget(title)

        row = QHBoxLayout()
        row.addWidget(QLabel("Save to"))
        self.download_dir_input = QLineEdit()
        self.download_dir_input.setReadOnly(True)
        self.download_dir_input.setText(self.download_dir)
        row.addWidget(self.download_dir_input, 1)
        change_btn = QPushButton("Change Folder")
        change_btn.setObjectName("GhostButton")
        change_btn.clicked.connect(self.change_download_dir)
        row.addWidget(change_btn)
        layout.addLayout(row)

        limit_row = QHBoxLayout()
        limit_row.addWidget(QLabel("Max concurrent downloads"))
        self.concurrent_spin = QSpinBox()
        self.concurrent_spin.setRange(1, 10)
        self.concurrent_spin.setValue(self.max_concurrent_downloads)
        self.concurrent_spin.valueChanged.connect(self._on_max_concurrent_changed)
        limit_row.addWidget(self.concurrent_spin)
        limit_row.addSpacing(12)
        limit_row.addWidget(QLabel("Speed limit (KB/s)"))
        self.speed_limit_spin = QSpinBox()
        self.speed_limit_spin.setRange(0, 100000)
        self.speed_limit_spin.setSingleStep(250)
        self.speed_limit_spin.setValue(self.speed_limit_kbps)
        self.speed_limit_spin.setToolTip("0 = unlimited")
        self.speed_limit_spin.valueChanged.connect(self._on_speed_limit_changed)
        limit_row.addWidget(self.speed_limit_spin)
        limit_row.addStretch(1)
        layout.addLayout(limit_row)

        proxy_row = QHBoxLayout()
        proxy_row.addWidget(QLabel("Proxy URL (optional)"))
        self.proxy_input = QLineEdit()
        if hasattr(self, "proxy_display_url"):
            self.proxy_input.setText(self.proxy_display_url)
        elif hasattr(self, "proxy_url"):
            self.proxy_input.setText(self.proxy_url)
        self.proxy_input.setPlaceholderText("http://user:pass@127.0.0.1:1080")
        self.proxy_input.textChanged.connect(self._on_proxy_changed)
        proxy_row.addWidget(self.proxy_input, 1)
        layout.addLayout(proxy_row)

        install_btn = QPushButton("Install Essentials (ffmpeg)")
        install_btn.setObjectName("GhostButton")
        install_btn.clicked.connect(self._run_install_essentials)
        layout.addWidget(install_btn)

        return card

    def _build_updates_card(self):
        card = QFrame()
        card.setObjectName("Card")
        layout = QVBoxLayout(card)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(10)

        title = QLabel("Updates")
        title.setObjectName("CardTitle")
        layout.addWidget(title)

        self.check_updates_cb = QCheckBox("Check for updates on startup")
        self.check_updates_cb.setChecked(self.check_updates_on_startup)
        self.check_updates_cb.toggled.connect(self._on_update_check_toggle)
        layout.addWidget(self.check_updates_cb)

        self.auto_update_cb = QCheckBox("Auto-download updates when available")
        self.auto_update_cb.setChecked(self.auto_download_updates)
        self.auto_update_cb.toggled.connect(self._on_auto_update_toggle)
        layout.addWidget(self.auto_update_cb)

        layout.addWidget(QLabel("Update manifest URL"))
        row = QHBoxLayout()
        row.setSpacing(8)
        self.update_url_input = QLineEdit()
        self.update_url_input.setText(self.update_manifest_url)
        try:
            from updates.manager import custom_update_urls_enabled
            self.update_url_input.setReadOnly(not custom_update_urls_enabled())
        except Exception:
            self.update_url_input.setReadOnly(True)
        self.update_url_input.setCursorPosition(0)
        self.update_url_input.setMinimumWidth(0)
        self.update_url_input.textChanged.connect(self._on_update_url_changed)
        row.addWidget(self.update_url_input, 1)
        check_btn = QPushButton("Check Now")
        check_btn.setObjectName("GhostButton")
        check_btn.setMinimumWidth(92)
        check_btn.clicked.connect(lambda: self.start_update_check(manual=True))
        row.addWidget(check_btn)
        layout.addLayout(row)

        note = QLabel("This URL controls where the app checks for updates.")
        note.setWordWrap(True)
        layout.addWidget(note)

        return card

    def _build_appearance_card(self):
        card = QFrame()
        card.setObjectName("Card")
        layout = QVBoxLayout(card)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(10)

        title = QLabel("Appearance")
        title.setObjectName("CardTitle")
        layout.addWidget(title)

        self.dark_mode_cb = QCheckBox("Enable dark mode")
        self.dark_mode_cb.setChecked(self.dark_mode)
        self.dark_mode_cb.toggled.connect(self._on_dark_mode_toggle)
        layout.addWidget(self.dark_mode_cb)

        return card

    def _build_cookies_page(self):
        page = QWidget()
        page.setObjectName("Page")
        layout = QVBoxLayout(page)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(12)

        title = QLabel("Cookies")
        title.setObjectName("SectionTitle")
        layout.addWidget(title)

        card = QFrame()
        card.setObjectName("Card")
        outer_layout = QVBoxLayout(card)
        outer_layout.setContentsMargins(16, 16, 16, 16)
        outer_layout.setSpacing(12)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setObjectName("GlassScroll")
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)

        content = QWidget()
        card_layout = QVBoxLayout(content)
        card_layout.setContentsMargins(0, 0, 0, 0)
        card_layout.setSpacing(12)
        scroll.setWidget(content)
        outer_layout.addWidget(scroll, 1)

        card_layout.addLayout(self._make_cookie_status_row())

        mode_row = QHBoxLayout()
        self.restricted_mode_cb = QCheckBox("Restricted mode (use browser login)")
        self.restricted_mode_cb.setChecked(self.restricted_mode)
        self.restricted_mode_cb.toggled.connect(self._on_restricted_mode_toggle)
        mode_row.addWidget(self.restricted_mode_cb)
        mode_row.addStretch(1)
        card_layout.addLayout(mode_row)

        mode_note = QLabel(
            "Normal mode downloads public videos without cookies. Restricted mode "
            "lets you connect your local browser profile for account-required videos."
        )
        mode_note.setObjectName("MutedText")
        mode_note.setWordWrap(True)
        mode_note.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        mode_note.setMinimumWidth(0)
        card_layout.addWidget(mode_note)

        self.restricted_status_label = QLabel("")
        self.restricted_status_label.setObjectName("MutedText")
        self.restricted_status_label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        self.restricted_status_label.setMinimumWidth(0)
        card_layout.addWidget(self.restricted_status_label)

        self.diagnostics_label = QLabel("")
        self.diagnostics_label.setObjectName("MutedText")
        self.diagnostics_label.setWordWrap(True)
        self.diagnostics_label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        self.diagnostics_label.setMinimumWidth(0)
        card_layout.addWidget(self.diagnostics_label)

        auth_title = QLabel("Browser authentication")
        auth_title.setObjectName("CardTitle")
        card_layout.addWidget(auth_title)

        auth_row = QHBoxLayout()
        auth_row.addWidget(QLabel("Browser"))
        self.browser_auth_combo = QComboBox()
        combo_view = QListView()
        combo_view.setObjectName("ComboPopupView")
        self.browser_auth_combo.setView(combo_view)
        self.browser_auth_combo.addItem("Auto-detect installed browsers", "auto")
        self.browser_auth_combo.addItem("Chrome", "chrome")
        self.browser_auth_combo.addItem("Edge", "edge")
        self.browser_auth_combo.addItem("Firefox", "firefox")
        self.browser_auth_combo.addItem("Brave", "brave")
        self.browser_auth_combo.addItem("Opera", "opera")
        if hasattr(self, "_apply_combo_popup_theme"):
            self._apply_combo_popup_theme()
        if self.browser_auth_source:
            idx = self.browser_auth_combo.findData(self.browser_auth_source)
            if idx >= 0:
                self.browser_auth_combo.setCurrentIndex(idx)
        auth_row.addWidget(self.browser_auth_combo, 1)
        card_layout.addLayout(auth_row)

        profile_row = QHBoxLayout()
        profile_row.addWidget(QLabel("Profile (optional)"))
        self.browser_profile_input = QLineEdit()
        self.browser_profile_input.setPlaceholderText("Default, Profile 1, …")
        if self.browser_auth_profile:
            self.browser_profile_input.setText(self.browser_auth_profile)
        profile_row.addWidget(self.browser_profile_input, 1)
        card_layout.addLayout(profile_row)

        auth_btn_row = QHBoxLayout()
        self.browser_connect_btn = QPushButton("Connect Browser")
        self.browser_connect_btn.setObjectName("GhostButton")
        self.browser_connect_btn.clicked.connect(self._connect_browser_auth)
        self.browser_disconnect_btn = QPushButton("Disconnect")
        self.browser_disconnect_btn.setObjectName("GhostButton")
        self.browser_disconnect_btn.clicked.connect(self._disconnect_browser_auth)
        auth_btn_row.addWidget(self.browser_connect_btn)
        auth_btn_row.addWidget(self.browser_disconnect_btn)
        auth_btn_row.addStretch(1)
        card_layout.addLayout(auth_btn_row)

        import sys
        if sys.platform.startswith("linux"):
            linux_hint = QLabel("Tip: Firefox is the most reliable browser for cookie extraction on Linux.")
            linux_hint.setObjectName("MutedText")
            linux_hint.setWordWrap(True)
            card_layout.addWidget(linux_hint)

        warn = QLabel("Do not share your cookies file with anyone.")
        warn.setObjectName("MutedText")
        warn.setWordWrap(True)
        warn.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        warn.setMinimumWidth(0)
        card_layout.addWidget(warn)

        # ── System browser login section ──────────────────────────────────
        yt_login_title = QLabel("Login to YouTube")
        yt_login_title.setObjectName("CardTitle")
        yt_login_title.setContentsMargins(0, 10, 0, 0)
        card_layout.addWidget(yt_login_title)

        yt_login_hint = QLabel(
            "Open YouTube in your system browser, log in, then click "
            "\u2018I\u2019m Logged In\u2019. Cookies are extracted automatically."
        )
        yt_login_hint.setObjectName("MutedText")
        yt_login_hint.setWordWrap(True)
        card_layout.addWidget(yt_login_hint)

        # Status indicator
        self.yt_login_status_label = QLabel("Status: Not logged in")
        self.yt_login_status_label.setObjectName("MutedText")
        self.yt_login_status_label.setWordWrap(True)
        card_layout.addWidget(self.yt_login_status_label)

        yt_btn_row = QHBoxLayout()

        self.yt_open_login_btn = QPushButton("\U0001f310  Open YouTube Login")
        self.yt_open_login_btn.setObjectName("GhostButton")
        self.yt_open_login_btn.clicked.connect(self._yt_open_login)

        self.yt_confirm_login_btn = QPushButton("\u2713  I\u2019m Logged In")
        self.yt_confirm_login_btn.setObjectName("GhostButton")
        self.yt_confirm_login_btn.setEnabled(False)
        self.yt_confirm_login_btn.clicked.connect(self._yt_confirm_login)

        self.yt_logout_btn = QPushButton("Logout")
        self.yt_logout_btn.setObjectName("GhostButton")
        self.yt_logout_btn.clicked.connect(self._yt_logout)

        yt_btn_row.addWidget(self.yt_open_login_btn)
        yt_btn_row.addWidget(self.yt_confirm_login_btn)
        yt_btn_row.addWidget(self.yt_logout_btn)
        yt_btn_row.addStretch(1)
        card_layout.addLayout(yt_btn_row)
        # ─────────────────────────────────────────────────────────────────


        file_title = QLabel("Cookies file (optional)")
        file_title.setObjectName("CardTitle")
        file_title.setContentsMargins(0, 10, 0, 0)
        card_layout.addWidget(file_title)

        btn_row = QHBoxLayout()
        self.set_cookies_btn = QPushButton("Set Cookies File")
        self.set_cookies_btn.setObjectName("GhostButton")
        self.set_cookies_btn.clicked.connect(self.set_cookies_file)
        self.clear_cookies_btn = QPushButton("Clear Cookies File")
        self.clear_cookies_btn.setObjectName("GhostButton")
        self.clear_cookies_btn.clicked.connect(self.clear_cookies_file)
        btn_row.addWidget(self.set_cookies_btn)
        btn_row.addWidget(self.clear_cookies_btn)
        btn_row.addStretch(1)
        card_layout.addLayout(btn_row)

        help_btn = QPushButton("How To Add Cookies")
        help_btn.setObjectName("GhostButton")
        help_btn.clicked.connect(self.show_cookies_help)
        card_layout.addWidget(help_btn)

        layout.addWidget(card)
        self._apply_shadow(card, 22, 96, 0)
        layout.addStretch(1)
        return page

    def _build_about_page(self):
        page = QWidget()
        page.setObjectName("Page")
        layout = QVBoxLayout(page)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(12)

        title = QLabel("About")
        title.setObjectName("SectionTitle")
        layout.addWidget(title)

        card = QFrame()
        card.setObjectName("Card")
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(16, 16, 16, 16)
        card_layout.setSpacing(8)

        card_layout.addWidget(QLabel("Simple YouTube Downloader"))
        card_layout.addWidget(QLabel(f"Version: {self._version_text()}"))
        card_layout.addWidget(QLabel("Created by: Tahsan"))
        card_layout.addWidget(QLabel("A modern downloader built for speed and clarity."))
        card_layout.addWidget(QLabel("Keep building. Keep exploring."))

        terms_btn = QPushButton("View Terms & Privacy")
        terms_btn.setObjectName("GhostButton")
        terms_btn.clicked.connect(self.show_terms_dialog)
        card_layout.addWidget(terms_btn)

        layout.addWidget(card)
        self._apply_shadow(card, 22, 96, 0)
        layout.addStretch(1)
        return page
