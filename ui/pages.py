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
    QSpinBox
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
        self.thumbnail.setFixedSize(250, 140)
        self.thumbnail.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        self.thumbnail.setScaledContents(False)
        self.thumbnail.setAlignment(Qt.AlignCenter)
        self.thumbnail.setStyleSheet("border-radius: 12px; background: #dfe7f2;")
        self.thumbnail.setPixmap(self._placeholder_pixmap(self.thumbnail.size()))
        self.thumbnail.setVisible(self.show_thumbnail)
        preview_layout.addWidget(self.thumbnail)
        preview_layout.setAlignment(self.thumbnail, Qt.AlignLeft | Qt.AlignVCenter)

        info_layout = QVBoxLayout()
        self.title = QLabel("Title: -")
        self.title.setObjectName("InfoTitle")
        self.title.setWordWrap(True)
        self.title.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.size = QLabel("Estimated size: -")
        info_layout.addWidget(self.title)
        info_layout.addWidget(self.size)

        self.show_thumb_cb = QCheckBox("Show thumbnail")
        self.show_thumb_cb.setChecked(self.show_thumbnail)
        self.show_thumb_cb.toggled.connect(self._on_show_thumbnail_toggle)
        info_layout.addWidget(self.show_thumb_cb)
        info_layout.addStretch(1)

        self.reset_btn = QPushButton("Reset")
        self.reset_btn.setObjectName("GhostButton")
        self.reset_btn.setMinimumHeight(36)
        self.reset_btn.setMinimumWidth(104)
        reset_font = self.reset_btn.font()
        reset_font.setWeight(QFont.Medium)
        self.reset_btn.setFont(reset_font)
        self.reset_btn.clicked.connect(self.reset_ui)
        info_layout.addLayout(self._make_cookie_status_row(self.reset_btn))
        preview_layout.addLayout(info_layout, 1)
        preview_layout.setStretch(0, 0)
        preview_layout.setStretch(1, 1)

        preview_wrap = QWidget()
        preview_wrap_layout = QVBoxLayout(preview_wrap)
        preview_wrap_layout.setContentsMargins(18, 10, 18, 10)
        preview_wrap_layout.addWidget(preview_card)
        details_layout.addWidget(preview_wrap)
        self._apply_shadow(preview_card, 26, 110, 2)

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
        config_wrap_layout.setContentsMargins(18, 10, 18, 10)
        config_wrap_layout.addWidget(config_card)
        details_layout.addWidget(config_wrap)
        self._apply_shadow(config_card, 26, 110, 2)

        layout.addWidget(self.details_container)

        actions_col = QVBoxLayout()
        self.download_btn = FadingTextButton("Start Download")
        self.download_btn.setObjectName("PrimaryButton")
        self.download_btn.setMinimumHeight(36)
        self.download_btn.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.download_btn.setEnabled(False)
        actions_col.addWidget(self.download_btn)
        self.progress = QProgressBar(page)
        self.progress.setVisible(False)
        layout.addLayout(actions_col)
        layout.addSpacing(6)

        self.fetch_btn.clicked.connect(self.fetch_info)
        self.download_btn.clicked.connect(self.start_download)
        self._clear_format_quality()
        self._set_config_enabled(False)

        return page

    def _build_downloads_panel(self):
        self.downloads_panel = QFrame()
        self.downloads_panel.setObjectName("Card")
        downloads_layout = QVBoxLayout(self.downloads_panel)
        downloads_layout.setContentsMargins(16, 16, 16, 16)
        downloads_layout.setSpacing(10)

        downloads_header_row = QHBoxLayout()
        downloads_header = QLabel("Downloads (0)")
        downloads_header.setObjectName("CardTitle")
        self.downloads_header = downloads_header
        downloads_header_row.addWidget(downloads_header)
        downloads_header_row.addStretch(1)
        self.reset_btn_downloads = QPushButton("Reset")
        self.reset_btn_downloads.setObjectName("GhostButton")
        self.reset_btn_downloads.setMinimumHeight(32)
        self.reset_btn_downloads.setMinimumWidth(96)
        self.reset_btn_downloads.clicked.connect(self.reset_ui)
        downloads_header_row.addWidget(self.reset_btn_downloads)
        downloads_layout.addLayout(downloads_header_row)

        self.downloads_scroll = QScrollArea()
        self.downloads_scroll.setWidgetResizable(True)
        self.downloads_scroll.setObjectName("GlassScroll")
        self.downloads_scroll.setMinimumHeight(160)
        self.downloads_container = QWidget()
        self.downloads_list_layout = QVBoxLayout(self.downloads_container)
        self.downloads_list_layout.setSpacing(10)
        self.downloads_list_layout.setContentsMargins(0, 0, 0, 0)

        self.active_downloads_layout = QVBoxLayout()
        self.downloads_list_layout.addLayout(self.active_downloads_layout)
        self.downloads_list_layout.addSpacing(6)
        self.completed_downloads_layout = QVBoxLayout()
        self.downloads_list_layout.addLayout(self.completed_downloads_layout)
        self.downloads_list_layout.addStretch(1)

        self.downloads_scroll.setWidget(self.downloads_container)
        downloads_layout.addWidget(self.downloads_scroll)
        self.downloads_panel.hide()
        self._apply_shadow(self.downloads_panel, 26, 110, 2)
        return self.downloads_panel

    def _build_library_page(self):
        page = QWidget()
        page.setObjectName("Page")
        layout = QVBoxLayout(page)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(12)

        header = QHBoxLayout()
        title = QLabel("Library")
        title.setObjectName("SectionTitle")
        header.addWidget(title)
        self.library_search = QLineEdit()
        self.library_search.setPlaceholderText("Search library...")
        self.library_search.textChanged.connect(self._on_library_search_changed)
        header.addWidget(self.library_search, 1)
        header.addStretch(1)

        clear_btn = QPushButton("Clear Library")
        clear_btn.setObjectName("GhostButton")
        clear_btn.clicked.connect(self.clear_library)
        header.addWidget(clear_btn)
        layout.addLayout(header)

        layout.addWidget(self._build_downloads_panel())

        self.library_scroll = QScrollArea()
        self.library_scroll.setWidgetResizable(True)
        self.library_scroll.setObjectName("GlassScroll")

        self.library_container = QWidget()
        self.library_layout = QVBoxLayout(self.library_container)
        self.library_layout.setSpacing(12)
        self.library_layout.setContentsMargins(0, 0, 0, 0)

        self.library_scroll.setWidget(self.library_container)
        layout.addWidget(self.library_scroll)
        return page

    def _build_options_page(self):
        page = QWidget()
        page.setObjectName("Page")
        layout = QVBoxLayout(page)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(12)

        title = QLabel("Options")
        title.setObjectName("SectionTitle")
        layout.addWidget(title)

        layout.addWidget(self._build_downloads_card())
        layout.addWidget(self._build_updates_card())
        layout.addWidget(self._build_appearance_card())
        layout.addStretch(1)
        return page

    def _build_downloads_card(self):
        card = QFrame()
        card.setObjectName("Card")
        layout = QVBoxLayout(card)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(10)

        title = QLabel("Downloads")
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
        self.concurrent_spin.setRange(1, 5)
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

        install_btn = QPushButton("Install Essentials (ffmpeg)")
        install_btn.setObjectName("GhostButton")
        install_btn.clicked.connect(self._run_install_essentials)
        layout.addWidget(install_btn)

        self._apply_shadow(card, 36, 160, 8)
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

        row = QHBoxLayout()
        row.addWidget(QLabel("Update manifest URL"))
        self.update_url_input = QLineEdit()
        self.update_url_input.setText(self.update_manifest_url)
        self.update_url_input.textChanged.connect(self._on_update_url_changed)
        row.addWidget(self.update_url_input, 1)
        check_btn = QPushButton("Check Now")
        check_btn.setObjectName("GhostButton")
        check_btn.clicked.connect(lambda: self.start_update_check(manual=True))
        row.addWidget(check_btn)
        layout.addLayout(row)

        note = QLabel(
            "This URL tells the app where to check for updates (GitHub Releases by default). "
            "Leave it unless you move releases. Required updates may block usage until updated. "
            "Optional updates can be skipped. For GitHub releases, add "
            "`min_required_version: x.y.z` and `installer_sha256: <64-hex>` to the release notes."
        )
        note.setObjectName("MutedText")
        note.setWordWrap(True)
        layout.addWidget(note)

        self._apply_shadow(card, 36, 160, 8)
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

        self._apply_shadow(card, 36, 160, 8)
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
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(16, 16, 16, 16)
        card_layout.setSpacing(12)

        card_layout.addLayout(self._make_cookie_status_row())

        warn = QLabel("Do not share your cookies file with anyone.")
        warn.setObjectName("MutedText")
        warn.setWordWrap(True)
        card_layout.addWidget(warn)

        btn_row = QHBoxLayout()
        set_btn = QPushButton("Set Cookies File")
        set_btn.setObjectName("PrimaryButton")
        set_btn.clicked.connect(self.set_cookies_file)
        clear_btn = QPushButton("Clear Cookies File")
        clear_btn.setObjectName("GhostButton")
        clear_btn.clicked.connect(self.clear_cookies_file)
        btn_row.addWidget(set_btn)
        btn_row.addWidget(clear_btn)
        btn_row.addStretch(1)
        card_layout.addLayout(btn_row)

        help_btn = QPushButton("How To Add Cookies")
        help_btn.setObjectName("GhostButton")
        help_btn.clicked.connect(self.show_cookies_help)
        card_layout.addWidget(help_btn)

        layout.addWidget(card)
        self._apply_shadow(card, 36, 160, 8)
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
        self._apply_shadow(card, 36, 160, 8)
        layout.addStretch(1)
        return page
