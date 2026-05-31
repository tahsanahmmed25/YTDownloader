import os
from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QGridLayout,
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
    QListView,
    QButtonGroup,
    QGraphicsOpacityEffect
)
from PySide6.QtCore import Qt, QSize, QCoreApplication
from PySide6.QtGui import QFont, QColor, QPixmap, QIcon

QCoreApplication.setOrganizationName("Tahsan")
QCoreApplication.setApplicationName("YTDownloader")

from ui.widgets import (
    FadingTextButton, PasteButton, BrandIcon, DownloadButton, GradientButton,
    DownloadProgressBar, ToggleSwitch, ToastFrame, NavButton, StatusBadge,
    SectionLabel, NavCounter, PrimaryButton, AnimatedComboBox
)



class PagesMixin:
    def _style_btn(self, btn):
        btn.setSizePolicy(QSizePolicy.Minimum, QSizePolicy.Fixed)
        btn.setMinimumWidth(0)
        btn.adjustSize()

    def _set_metadata_placeholder(self, is_placeholder):
        from ui_style import DARK, LIGHT
        dark = getattr(self, "dark_mode", False)
        t = DARK if dark else LIGHT
        
        if is_placeholder:
            self.thumbnail.clear()
            self.thumbnail.setStyleSheet(f"border-radius: 6px; background-color: {t['bg_surface']};")
            self.title.setText("No video selected")
            self.title.setStyleSheet(f"color: {t['text_tertiary']}; font-style: italic; font-size: 13px; font-weight: normal;")
            self.size.setText("—")
            self.size.setStyleSheet(f"color: {t['text_tertiary']}; font-size: 12px;")
            self.reset_btn.setEnabled(False)
        else:
            self.thumbnail.setStyleSheet("border-radius: 6px;")
            self.title.setStyleSheet("")
            self.size.setStyleSheet("")
            self.reset_btn.setEnabled(True)

    def _on_show_thumb_changed(self, checked: bool):
        self.settings.setValue("show_thumbnails", checked)
        self.settings.setValue("show_thumbnail", checked)
        self.show_thumbnail = checked
        if hasattr(self, "thumbnail") and self.thumbnail:
            self.thumbnail.setVisible(checked)
        if hasattr(self, "thumb_label") and self.thumb_label:
            self.thumb_label.setVisible(checked)
        win = self.window()
        for obj in (self, win):
            if obj:
                if hasattr(obj, 'home_page') and hasattr(obj.home_page, 'show_thumb_toggle'):
                    obj.home_page.show_thumb_toggle.blockSignals(True)
                    obj.home_page.show_thumb_toggle.setChecked(checked)
                    obj.home_page.show_thumb_toggle.blockSignals(False)
                if hasattr(obj, 'prefs_page') and hasattr(obj.prefs_page, 'show_thumb_toggle'):
                    obj.prefs_page.show_thumb_toggle.blockSignals(True)
                    obj.prefs_page.show_thumb_toggle.setChecked(checked)
                    obj.prefs_page.show_thumb_toggle.blockSignals(False)

    def _create_page_header(self, title, subtitle):
        header = QWidget()
        header.setObjectName("PageHeader")
        layout = QVBoxLayout(header)
        layout.setContentsMargins(0, 0, 0, 8)
        layout.setSpacing(2)
        
        t_label = QLabel(title)
        t_label.setObjectName("PageTitle")
        
        sub_label = QLabel(subtitle)
        sub_label.setObjectName("PageSubtitle")
        sub_label.setStyleSheet("font-size: 13px;")
        
        layout.addWidget(t_label)
        layout.addWidget(sub_label)
        return header


    def _create_config_cell(self, label_text, widget):
        cell = QFrame()
        cell.setObjectName("ConfigCell")
        layout = QVBoxLayout(cell)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(2)
        
        key_label = QLabel(label_text.upper())
        key_label.setObjectName("CellKey")
        
        combos = widget.findChildren(QComboBox) if not isinstance(widget, QComboBox) else [widget]
        for combo in combos:
            combo.setObjectName("CellValue")
            combo.setStyleSheet("background: transparent; border: none; padding: 0px; margin: 0px;")
            
        labels = widget.findChildren(QLabel) if not isinstance(widget, QLabel) else [widget]
        for label in labels:
            label.setObjectName("CellValue")
        
        layout.addWidget(key_label)
        layout.addWidget(widget)
        return cell



    def _create_toggle_row(self, label_text, toggle_switch):
        row = QHBoxLayout()
        row.setSpacing(10)
        row.setContentsMargins(0, 0, 0, 0)
        
        label = QLabel(label_text)
        label.setObjectName("ToggleLabel")
        
        row.addWidget(toggle_switch)
        row.addWidget(label)
        row.addStretch(1)
        return row

    def build_task_card(self, title):
        frame = QFrame()
        frame.setObjectName("Card")
        frame.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        frame.setFixedHeight(56)
        
        layout = QHBoxLayout(frame)
        layout.setContentsMargins(14, 14, 14, 14)
        layout.setSpacing(10)
        layout.setAlignment(Qt.AlignVCenter)

        # 1. Thumbnail QLabel — 50x28px, border-radius: 6px
        thumbnail = QLabel()
        thumbnail.setFixedSize(50, 28)
        thumbnail.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        thumbnail.setObjectName("TaskThumbnail")
        thumbnail.setAlignment(Qt.AlignCenter)

        # 2. Info column QVBoxLayout
        info_widget = QWidget()
        info_widget.setAttribute(Qt.WA_TransparentForMouseEvents)
        info_layout = QVBoxLayout(info_widget)
        info_layout.setContentsMargins(0, 0, 0, 0)
        info_layout.setSpacing(4)

        title_label = QLabel(title)
        title_label.setObjectName("TaskTitle")
        title_label.setStyleSheet("font-size: 12px; font-weight: 500;")
        
        # Elide title text
        metrics = title_label.fontMetrics()
        elided = metrics.elidedText(title, Qt.ElideRight, 350)
        title_label.setText(elided)

        progress = QProgressBar()
        progress.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        progress.setFixedHeight(4)
        progress.setValue(0)
        progress.setTextVisible(False)

        size_label = QLabel()
        size_label.setObjectName("MetaLabel")
        size_label.setVisible(False)

        speed_label = QLabel("0.0 KB/s")
        speed_label.setObjectName("MetaLabel")
        speed_label.setStyleSheet("font-size: 12px;")

        info_layout.addWidget(title_label)
        info_layout.addWidget(progress)
        info_layout.addWidget(size_label)
        info_layout.addWidget(speed_label)

        # 3. Right side percentage or badges
        percentage_label = QLabel("0%")
        percentage_label.setObjectName("PercentageLabel")
        percentage_label.setStyleSheet("font-size: 11px; font-weight: 500;")
        percentage_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        percentage_label.setFixedWidth(45)

        # Status badge
        status_label = StatusBadge("Downloading...")
        status_label.hide()
        status_label._item_pct = percentage_label
        status_label._item_prog = progress
        status_label._item_speed = speed_label

        # Hidden buttons to prevent crashes
        pause_btn = QPushButton("Pause")
        self._style_btn(pause_btn)
        pause_btn.hide()
        cancel_btn = QPushButton("Cancel")
        self._style_btn(cancel_btn)
        cancel_btn.hide()
        open_btn = QPushButton("Open")
        self._style_btn(open_btn)
        open_btn.hide()

        layout.addWidget(thumbnail)
        layout.addWidget(info_widget, 1)
        layout.addWidget(percentage_label)
        layout.addWidget(status_label)

        # Wire value changes
        progress.valueChanged.connect(lambda val: percentage_label.setText(f"{val}%"))

        item = {
            "frame": frame,
            "title": title_label,
            "status": status_label,
            "status_icon": QLabel(),
            "status_effect": QGraphicsOpacityEffect(),
            "progress": progress,
            "speed": speed_label,
            "size": size_label,
            "pause_btn": pause_btn,
            "cancel_btn": cancel_btn,
            "open_btn": open_btn,
            "percentage_label": percentage_label,
            "thumbnail": thumbnail
        }
        frame._download_item = item
        return item

    def _build_downloader_page(self):
        page = QWidget()
        page.setObjectName("Page")
        self.home_page = page
        layout = QVBoxLayout(page)
        layout.setContentsMargins(20, 8, 20, 20)
        layout.setSpacing(8)

        # Header
        header = self._create_page_header("Download media", "Paste a YouTube URL to get started")
        layout.addWidget(header)

        # Hidden widgets for compatibility
        self.playlist_toggle = QCheckBox()
        self.playlist_toggle.setObjectName("PlaylistToggle")
        self.playlist_toggle.toggled.connect(self._on_playlist_toggle)
        self.playlist_toggle.hide()
        layout.addWidget(self.playlist_toggle)

        self.paste_btn = PasteButton()
        self.paste_btn.clicked.connect(self._paste_from_clipboard)
        self.paste_btn.hide()
        layout.addWidget(self.paste_btn)

        self.subs_checkbox = QCheckBox()
        self.subs_checkbox.hide()
        layout.addWidget(self.subs_checkbox)

        self.embed_subs_checkbox = QCheckBox()
        self.embed_subs_checkbox.hide()
        layout.addWidget(self.embed_subs_checkbox)

        # URL Input Card
        url_card = QFrame()
        url_card.setObjectName("Card")
        url_card.setMinimumHeight(72)
        url_card.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        url_card_layout = QHBoxLayout(url_card)
        url_card_layout.setContentsMargins(14, 14, 14, 14)
        url_card_layout.setSpacing(8)

        self.url_input = QLineEdit()
        self.url_input.setObjectName("UrlInput")
        self.url_input.setPlaceholderText("https://youtube.com/watch?v=...")
        self.url_input.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        self.url_input.setTextMargins(6, 0, 6, 0)
        self.url_input.textChanged.connect(self._on_url_changed)

        _pal = self.url_input.palette()
        _pal.setColor(_pal.ColorRole.PlaceholderText, QColor("#a0a0a0" if self.dark_mode else "#6b6b6b"))
        self.url_input.setPalette(_pal)

        self.fetch_btn = PrimaryButton("Analyze")
        self.fetch_btn.setObjectName("PrimaryButton")
        self.fetch_btn.setFixedHeight(32)
        self.fetch_btn.setFixedWidth(110)

        self.fetch_spinner = QProgressBar()
        self.fetch_spinner.setObjectName("FetchBar")
        self.fetch_spinner.setRange(0, 0)
        self.fetch_spinner.setTextVisible(False)
        self.fetch_spinner.setFixedHeight(2)
        self.fetch_spinner.setVisible(False)

        url_input_col = QWidget()
        url_input_col_layout = QVBoxLayout(url_input_col)
        url_input_col_layout.setContentsMargins(0, 0, 0, 0)
        url_input_col_layout.setSpacing(4)
        url_input_col_layout.addWidget(self.url_input)
        url_input_col_layout.addWidget(self.fetch_spinner)

        # Fix 14 — visible Paste button
        self.paste_url_btn = QPushButton("Paste")
        self.paste_url_btn.setObjectName("PasteButton")
        self.paste_url_btn.setSizePolicy(QSizePolicy.Minimum, QSizePolicy.Fixed)
        self.paste_url_btn.setMinimumWidth(0)
        self.paste_url_btn.adjustSize()
        self.paste_url_btn.clicked.connect(self._paste_from_clipboard)

        url_card_layout.addWidget(self.paste_url_btn)
        url_card_layout.addWidget(url_input_col, 1)
        url_card_layout.addWidget(self.fetch_btn)
        layout.addWidget(url_card)

        # Video details container (always visible)
        self.details_container = QWidget()
        self.details_container.setVisible(True)
        details_layout = QVBoxLayout(self.details_container)
        details_layout.setContentsMargins(0, 0, 0, 0)
        details_layout.setSpacing(0)

        preview_card = QFrame()
        preview_card.setObjectName("Card")
        preview_layout = QHBoxLayout(preview_card)
        preview_layout.setContentsMargins(14, 14, 14, 14)
        preview_layout.setSpacing(14)
        preview_layout.setAlignment(Qt.AlignVCenter)

        self.thumbnail = QLabel()
        self.thumbnail.setObjectName("PreviewThumb")
        self.thumbnail.setFixedSize(80, 50)
        self.thumbnail.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        self.thumbnail.setScaledContents(True)
        self.thumbnail.setStyleSheet("")

        info_layout = QVBoxLayout()
        info_layout.setContentsMargins(0, 0, 0, 0)
        info_layout.setSpacing(4)

        self.title = QLabel("Title: -")
        self.title.setObjectName("InfoTitle")
        self.title.setWordWrap(True)
        self.title.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)

        self.size = QLabel("Estimated size: -")
        self.size.setObjectName("InfoSubtle")

        info_layout.addWidget(self.title)
        info_layout.addWidget(self.size)

        preview_action_layout = QHBoxLayout()
        preview_action_layout.setSpacing(12)

        self.show_thumb_toggle = QCheckBox("Show thumbnail")
        self.show_thumb_cb = self.show_thumb_toggle
        self.thumb_label = self.thumbnail
        page.show_thumb_toggle = self.show_thumb_toggle
        
        self.show_thumb_toggle.setChecked(self.settings.value("show_thumbnails", True, type=bool))
        self.thumbnail.setVisible(self.settings.value("show_thumbnails", True, type=bool))
        self.show_thumb_toggle.toggled.connect(self._on_show_thumb_changed)
        preview_action_layout.addWidget(self.show_thumb_toggle)

        self.reset_btn = QPushButton("Reset")
        self.reset_btn.setObjectName("PasteButton")
        self.reset_btn.setSizePolicy(QSizePolicy.Minimum, QSizePolicy.Fixed)
        self.reset_btn.setMinimumWidth(0)
        self.reset_btn.adjustSize()
        self.reset_btn.clicked.connect(self.clear_homepage_ui)
        preview_action_layout.addWidget(self.reset_btn)
        info_layout.addLayout(preview_action_layout)

        preview_layout.addWidget(self.thumbnail)
        preview_layout.addLayout(info_layout, 1)

        details_layout.addWidget(preview_card)
        layout.addWidget(self.details_container)

        # Configuration Card
        self.pill_group = QButtonGroup(page)
        self.pill_group.setExclusive(True)

        self.pill_video = QPushButton("Video")
        self.pill_video.setObjectName("PillButton")
        self.pill_video.setProperty("active", "true")
        self.pill_video.setCheckable(True)
        self.pill_video.setChecked(True)
        self._style_btn(self.pill_video)

        self.pill_audio = QPushButton("Audio")
        self.pill_audio.setObjectName("PillButton")
        self.pill_audio.setProperty("active", "false")
        self.pill_audio.setCheckable(True)
        self._style_btn(self.pill_audio)

        self.pill_playlist = QPushButton("Playlist")
        self.pill_playlist.setObjectName("PillButton")
        self.pill_playlist.setProperty("active", "false")
        self.pill_playlist.setCheckable(True)
        self._style_btn(self.pill_playlist)

        self.pill_group.addButton(self.pill_video)
        self.pill_group.addButton(self.pill_audio)
        self.pill_group.addButton(self.pill_playlist)

        def _update_pill_styles():
            for btn in [self.pill_video, self.pill_audio, self.pill_playlist]:
                is_active = btn.isChecked()
                btn.setProperty("active", "true" if is_active else "false")
                btn.style().unpolish(btn)
                btn.style().polish(btn)

        def on_pill_clicked(btn):
            # Only update visual state. Playlist mode flag is tracked internally
            # by _on_playlist_toggle but we do NOT propagate here to avoid UI
            # side-effects (placeholder changes, combo reset).
            self._active_is_playlist = (btn == self.pill_playlist)
            _update_pill_styles()
        self.pill_group.buttonClicked.connect(on_pill_clicked)

        def on_playlist_toggled(checked):
            if checked:
                self.pill_playlist.setChecked(True)
            else:
                if self.pill_playlist.isChecked():
                    self.pill_video.setChecked(True)
            _update_pill_styles()
        self.playlist_toggle.toggled.connect(on_playlist_toggled)

        self.subs_mode_combo = AnimatedComboBox()
        self.subs_mode_combo.blockSignals(True)
        self.subs_mode_combo.addItems(["None", "Download", "Embed"])
        self.subs_mode_combo.blockSignals(False)
        self.subs_mode_combo.setMaxVisibleItems(10)
        self.subs_mode_combo.view().setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)

        def on_subs_mode_changed(index):
            if index == 0:
                self.subs_checkbox.setChecked(False)
                self.embed_subs_checkbox.setChecked(False)
            elif index == 1:
                self.subs_checkbox.setChecked(True)
                self.embed_subs_checkbox.setChecked(False)
            elif index == 2:
                self.subs_checkbox.setChecked(True)
                self.embed_subs_checkbox.setChecked(True)
        self.subs_mode_combo.currentIndexChanged.connect(on_subs_mode_changed)

        def sync_subs_mode_from_checkboxes():
            self.subs_mode_combo.blockSignals(True)
            if not self.subs_checkbox.isChecked():
                self.subs_mode_combo.setCurrentIndex(0)
            elif not self.embed_subs_checkbox.isChecked():
                self.subs_mode_combo.setCurrentIndex(1)
            else:
                self.subs_mode_combo.setCurrentIndex(2)
            self.subs_mode_combo.blockSignals(False)

        self.subs_checkbox.toggled.connect(lambda _: sync_subs_mode_from_checkboxes())
        self.embed_subs_checkbox.toggled.connect(lambda _: sync_subs_mode_from_checkboxes())

        self.format_combo = AnimatedComboBox()
        self.format_combo.setMaxVisibleItems(10)
        self.format_combo.view().setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.quality = AnimatedComboBox()
        self.quality_combo = self.quality
        self.quality.setMaxVisibleItems(10)
        self.quality.view().setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.subs_lang = AnimatedComboBox()
        self.subs_lang.setMaxVisibleItems(10)
        self.subs_lang.view().setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)

        # Create audio_combo for Audio config cell
        self.audio_combo = AnimatedComboBox()
        self.audio_combo.setMaxVisibleItems(10)
        self.audio_combo.view().setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.audio_combo.addItems(["Best", "AAC", "MP3", "Opus", "FLAC", "Vorbis"])
        
        # Load from settings, default to Best
        default_audio_val = self.settings.value("default_audio", "Best", type=str)
        if default_audio_val == "Flac":
            default_audio_val = "FLAC"
        self.audio_combo.setCurrentText(default_audio_val)
        
        # Connect change signal to settings
        self.audio_combo.currentTextChanged.connect(
            lambda v: self.settings.setValue("default_audio", v)
        )

        # Create combined subtitles container for subtitles cell
        self.subs_container = QWidget()
        subs_container_layout = QHBoxLayout(self.subs_container)
        subs_container_layout.setContentsMargins(0, 0, 0, 0)
        subs_container_layout.setSpacing(6)
        subs_container_layout.addWidget(self.subs_mode_combo)
        subs_container_layout.addWidget(self.subs_lang)

        config_card = QFrame()
        config_card.setObjectName("Card")
        config_card_layout = QVBoxLayout(config_card)
        config_card_layout.setContentsMargins(14, 14, 14, 14)
        config_card_layout.setSpacing(10)

        header_row = QHBoxLayout()
        config_title = QLabel("Configuration")
        config_title.setStyleSheet("font-size: 13px; font-weight: 500;")

        tab_pills_layout = QHBoxLayout()
        tab_pills_layout.setSpacing(4)
        tab_pills_layout.setContentsMargins(0, 0, 0, 0)
        tab_pills_layout.addWidget(self.pill_video)
        tab_pills_layout.addWidget(self.pill_audio)
        tab_pills_layout.addWidget(self.pill_playlist)

        header_row.addWidget(config_title)
        header_row.addStretch(1)
        header_row.addLayout(tab_pills_layout)
        config_card_layout.addLayout(header_row)

        config_grid_layout = QGridLayout()
        config_grid_layout.setSpacing(6)
        config_grid_layout.setContentsMargins(0, 0, 0, 0)

        cell_quality = self._create_config_cell("Quality", self.quality)
        cell_format = self._create_config_cell("Video Format", self.format_combo)
        cell_audio = self._create_config_cell("Audio Format", self.audio_combo)
        self.subtitle_lang_cell = self._create_config_cell("Subtitles", self.subs_container)
        self.subtitle_lang_cell.setVisible(True)

        config_grid_layout.addWidget(cell_quality, 0, 0)
        config_grid_layout.addWidget(cell_format, 0, 1)
        config_grid_layout.addWidget(cell_audio, 0, 2)
        config_grid_layout.addWidget(self.subtitle_lang_cell, 0, 3)

        config_card_layout.addLayout(config_grid_layout)
        layout.addWidget(config_card)

        # Download Button
        self.download_btn = DownloadButton("Start Download")
        self.download_btn.setObjectName("DownloadButton")
        self.download_btn.setFixedHeight(40)
        self.download_btn.setEnabled(False)
        layout.addWidget(self.download_btn)

        self.progress = None

        self.fetch_btn.clicked.connect(self.fetch_info)
        self.download_btn.clicked.connect(self.start_download)
        
        self.config_cells = [cell_quality, cell_format, cell_audio, self.subtitle_lang_cell]
        self._set_metadata_placeholder(True)
        self._clear_format_quality()
        self._set_config_enabled(False)

        self.load_defaults_from_prefs()
        return page


    def _build_library_page(self):
        page = QWidget()
        page.setObjectName("Page")
        layout = QVBoxLayout(page)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(8)

        # Header Title + Subtitle
        self.library_header_title = QLabel("Downloads")
        self.library_header_title.setObjectName("PageTitle")

        self.library_header_subtitle = QLabel("No active downloads")

        self.library_header_subtitle.setObjectName("PageSubtitle")
        self.library_header_subtitle.setStyleSheet("font-size: 12px;")

        layout.addWidget(self.library_header_title)
        layout.addWidget(self.library_header_subtitle)

        # Scroll Area
        self.downloads_scroll = QScrollArea()
        self.downloads_scroll.setWidgetResizable(True)
        self.downloads_scroll.setFrameShape(QFrame.NoFrame)
        self.downloads_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.downloads_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        # Fix 6 — ensure scroll viewport is transparent so theme bg shows through
        self.downloads_scroll.viewport().setStyleSheet("background: transparent;")

        self.downloads_container = QWidget()
        self.downloads_container.setStyleSheet("background: transparent;")
        self.downloads_list_layout = QVBoxLayout(self.downloads_container)
        self.downloads_list_layout.setContentsMargins(0, 0, 0, 0)
        self.downloads_list_layout.setSpacing(8)
        self.downloads_list_layout.setAlignment(Qt.AlignTop)

        # Empty Label
        self.library_empty_label = QLabel("No active downloads")
        self.library_empty_label.setObjectName("PageSubtitle")
        self.library_empty_label.setAlignment(Qt.AlignCenter)
        self.library_empty_label.setStyleSheet("")
        self.downloads_list_layout.addWidget(self.library_empty_label)

        # Child layouts for active & completed tasks
        self.active_downloads_layout = QVBoxLayout()
        self.active_downloads_layout.setSpacing(8)
        self.active_downloads_layout.setAlignment(Qt.AlignTop)
        self.downloads_list_layout.addLayout(self.active_downloads_layout)

        self.completed_downloads_layout = QVBoxLayout()
        self.completed_downloads_layout.setSpacing(8)
        self.completed_downloads_layout.setAlignment(Qt.AlignTop)
        self.downloads_list_layout.addLayout(self.completed_downloads_layout)

        self.downloads_scroll.setWidget(self.downloads_container)
        layout.addWidget(self.downloads_scroll, 1)

        # Dummy variables to maintain backward compatibility with self references in main_window.py
        self.downloads_panel = QFrame(page)
        self.downloads_panel.hide()
        self.downloads_header = QLabel(page)
        self.downloads_header.hide()
        self.reset_btn_downloads = QPushButton(page)
        self._style_btn(self.reset_btn_downloads)
        self.reset_btn_downloads.hide()

        return page

    def _build_history_page(self):
        page = QWidget()
        page.setObjectName("Page")
        layout = QVBoxLayout(page)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(8)

        # Header
        header = self._create_page_header("History", "Recently downloaded files")
        layout.addWidget(header)

        controls_row = QHBoxLayout()
        controls_row.setSpacing(7)
        controls_row.setContentsMargins(0, 0, 0, 0)

        self.library_search = QLineEdit()
        self.library_search.setPlaceholderText("Search history...")
        self.library_search.textChanged.connect(self._on_library_search_changed)
        controls_row.addWidget(self.library_search, 1)

        clear_btn = QPushButton("Clear History")
        clear_btn.setObjectName("GhostButton")
        self._style_btn(clear_btn)
        clear_btn.clicked.connect(self.clear_library)
        controls_row.addWidget(clear_btn)
        layout.addLayout(controls_row)

        history_card = QFrame()
        history_card.setObjectName("Card")
        history_card_layout = QVBoxLayout(history_card)
        history_card_layout.setContentsMargins(14, 14, 14, 14)
        history_card_layout.setSpacing(10)

        self.library_scroll = QScrollArea()
        self.library_scroll.setWidgetResizable(True)
        self.library_scroll.setFrameShape(QFrame.NoFrame)
        self.library_scroll.setObjectName("GlassScroll")
        self.library_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        # Fix 7 — ensure history scroll viewport is transparent
        self.library_scroll.viewport().setStyleSheet("background: transparent;")

        self.library_container = QWidget()
        self.library_layout = QVBoxLayout(self.library_container)
        self.library_layout.setSpacing(8)
        self.library_layout.setContentsMargins(0, 0, 0, 0)

        self.library_scroll.setWidget(self.library_container)
        history_card_layout.addWidget(self.library_scroll, 1)
        layout.addWidget(history_card, 1)
        return page

    def _build_options_page(self):
        page = QWidget()
        page.setObjectName("Page")
        self.prefs_page = page
        layout = QVBoxLayout(page)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(8)

        # Header
        header = self._create_page_header("Preferences", "Configure your download settings")
        layout.addWidget(header)

        # Settings Card (QFrame, objectName="Card")
        settings_card = QFrame()
        settings_card.setObjectName("Card")
        card_layout = QVBoxLayout(settings_card)
        card_layout.setContentsMargins(14, 14, 14, 14)
        card_layout.setSpacing(0)

        def create_setting_row(label_text, sublabel_text, control_widget, is_last=False):
            row_frame = QFrame()
            row_frame.setObjectName("PrefRow")
            row_layout = QHBoxLayout(row_frame)
            row_layout.setContentsMargins(0, 12, 0, 12)
            row_layout.setSpacing(12)

            label_block = QWidget()
            label_block_layout = QVBoxLayout(label_block)
            label_block_layout.setContentsMargins(0, 0, 0, 0)
            label_block_layout.setSpacing(2)

            main_label = QLabel(label_text)
            main_label.setObjectName("SettingLabel")
            label_block_layout.addWidget(main_label)

            if sublabel_text:
                sub_label = QLabel(sublabel_text)
                sub_label.setObjectName("SettingSubLabel")
                sub_label.setStyleSheet("font-size: 11px;")
                label_block_layout.addWidget(sub_label)

            row_layout.addWidget(label_block, 1)
            row_layout.addWidget(control_widget)

            if is_last:
                row_frame.setStyleSheet("border-bottom: none;")

            return row_frame


        # 1. Save Folder Row
        self.download_dir_input = QLabel(self.download_dir)
        self.download_dir_input.setObjectName("SettingSubLabel")
        self.download_dir_input.setStyleSheet("font-size: 11px;")
        self.change_btn = QPushButton("Change")
        self.change_btn.setObjectName("PasteButton")
        self.change_btn.setSizePolicy(QSizePolicy.Minimum, QSizePolicy.Fixed)
        self.change_btn.setMinimumWidth(0)
        self.change_btn.adjustSize()
        self.change_btn.clicked.connect(self.change_download_dir)

        # 3. Show Thumbnails Row
        self.show_thumbnails_pref_cb = ToggleSwitch(self.dark_mode, self)
        self.show_thumb_toggle = self.show_thumbnails_pref_cb
        page.show_thumb_toggle = self.show_thumb_toggle
        
        self.show_thumb_toggle.setChecked(self.settings.value("show_thumbnails", True, type=bool))
        self.show_thumb_toggle.toggled.connect(self._on_show_thumb_changed)

        # 4. Restricted Mode — widget now lives on the Restricted Mode (Cookies) page.
        #    A hidden dummy is created in the dummy block below to prevent any
        #    early attribute access errors in backend code.

        # 5. Speed Limit Row
        self.speed_limit_spin = QSpinBox()
        self.speed_limit_spin.setRange(0, 100000)
        self.speed_limit_spin.setSingleStep(250)
        self.speed_limit_spin.setValue(self.speed_limit_kbps)
        self.speed_limit_spin.setSizePolicy(QSizePolicy.Minimum, QSizePolicy.Fixed)
        self.speed_limit_spin.adjustSize()
        self.speed_limit_spin.valueChanged.connect(self._on_speed_limit_changed)

        # 6. Default Quality Row — Fix 11: full quality list
        self.pref_quality_combo = AnimatedComboBox()
        self.default_quality_combo = self.pref_quality_combo
        self.pref_quality_combo.setSizePolicy(QSizePolicy.Minimum, QSizePolicy.Fixed)
        self.pref_quality_combo.setMinimumContentsLength(6)
        self.pref_quality_combo.adjustSize()
        self.pref_quality_combo.blockSignals(True)
        self.pref_quality_combo.addItems([
            "Best", "4320p (8K)", "2160p (4K)", "1440p (2K)",
            "1080p", "720p", "480p", "360p", "240p", "144p", "Worst"
        ])
        self.pref_quality_combo.blockSignals(False)
        self.pref_quality_combo.setCurrentText(
            self.settings.value("default_quality", "1080p", type=str)
        )
        self.pref_quality_combo.setMaxVisibleItems(12)
        self.pref_quality_combo.view().setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)

        # 7. Default Format Row — Fix 10
        self.pref_format_combo = AnimatedComboBox()
        self.default_format_combo = self.pref_format_combo
        self.pref_format_combo.setSizePolicy(QSizePolicy.Minimum, QSizePolicy.Fixed)
        self.pref_format_combo.setMinimumContentsLength(6)
        self.pref_format_combo.adjustSize()
        self.pref_format_combo.blockSignals(True)
        self.pref_format_combo.addItems(["MP4", "MKV", "WebM", "MP3", "M4A"])
        self.pref_format_combo.blockSignals(False)
        self.pref_format_combo.setCurrentText(
            self.settings.value("default_format", "MP4", type=str)
        )
        self.pref_format_combo.setMaxVisibleItems(10)
        self.pref_format_combo.view().setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)

        # 8. Default Audio Codec Row — Fix 10
        self.pref_audio_combo = AnimatedComboBox()
        self.default_audio_combo = self.pref_audio_combo
        self.pref_audio_combo.setSizePolicy(QSizePolicy.Minimum, QSizePolicy.Fixed)
        self.pref_audio_combo.setMinimumContentsLength(6)
        self.pref_audio_combo.adjustSize()
        self.pref_audio_combo.blockSignals(True)
        self.pref_audio_combo.addItems(["AAC", "MP3", "Opus", "Flac", "Best"])
        self.pref_audio_combo.blockSignals(False)
        self.pref_audio_combo.setCurrentText(
            self.settings.value("default_audio", "AAC", type=str)
        )
        self.pref_audio_combo.setMaxVisibleItems(10)
        self.pref_audio_combo.view().setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)


        self.default_quality_combo.currentTextChanged.connect(
            lambda v: self.settings.setValue("default_quality", v)
        )
        self.default_format_combo.currentTextChanged.connect(
            lambda v: self.settings.setValue("default_format", v)
        )
        self.default_audio_combo.currentTextChanged.connect(
            lambda v: self.settings.setValue("default_audio", v)
        )

        # Build rows
        card_layout.addWidget(create_setting_row("Save folder", self.download_dir, self.change_btn))
        card_layout.addWidget(create_setting_row("Show thumbnails", "", self.show_thumbnails_pref_cb))
        card_layout.addWidget(create_setting_row("Speed limit", "", self.speed_limit_spin))
        card_layout.addWidget(create_setting_row("Default quality", "", self.pref_quality_combo))
        card_layout.addWidget(create_setting_row("Default format", "", self.pref_format_combo))
        card_layout.addWidget(create_setting_row("Default audio codec", "", self.pref_audio_combo, is_last=True))

        layout.addWidget(settings_card)
        layout.addStretch(1)

        # Dummy hidden widgets for option settings referenced by backend to prevent crashes
        self.concurrent_spin = QSpinBox()
        self.concurrent_spin.hide()
        self.proxy_input = QLineEdit()
        self.proxy_input.hide()
        
        self.essentials_status_label = QLabel()
        self.essentials_status_label.hide()
        self.essentials_progress = QProgressBar()
        self.essentials_progress.hide()
        
        self.install_essentials_btn = QPushButton()
        self._style_btn(self.install_essentials_btn)
        self.install_essentials_btn.hide()
        self.reinstall_essentials_btn = QPushButton()
        self._style_btn(self.reinstall_essentials_btn)
        self.reinstall_essentials_btn.hide()
        self.update_essentials_btn = QPushButton()
        self._style_btn(self.update_essentials_btn)
        self.update_essentials_btn.hide()

        self.check_updates_cb = QCheckBox()
        self.check_updates_cb.hide()
        self.auto_update_cb = QCheckBox()
        self.auto_update_cb.hide()
        self.update_url_input = QLineEdit()
        self.update_url_input.hide()

        return page

    def _build_cookies_page(self):
        page = QWidget()
        page.setObjectName("Page")
        layout = QVBoxLayout(page)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(8)

        # Page Header
        header = self._create_page_header("Restricted Mode", "Manage authentication and access settings")
        layout.addWidget(header)

        # ── Restricted Mode Toggle Card ──────────────────────────────────────
        rm_card = QFrame()
        rm_card.setObjectName("Card")
        rm_card_layout = QVBoxLayout(rm_card)
        rm_card_layout.setContentsMargins(14, 14, 14, 14)
        rm_card_layout.setSpacing(0)

        rm_row_widget = QWidget()
        rm_row_layout = QHBoxLayout(rm_row_widget)
        rm_row_layout.setContentsMargins(0, 4, 0, 4)
        rm_row_layout.setSpacing(12)

        rm_label_block = QWidget()
        rm_label_block_layout = QVBoxLayout(rm_label_block)
        rm_label_block_layout.setContentsMargins(0, 0, 0, 0)
        rm_label_block_layout.setSpacing(2)

        rm_main_label = QLabel("Restricted mode")
        rm_main_label.setObjectName("SettingLabel")
        rm_label_block_layout.addWidget(rm_main_label)

        rm_sub_label = QLabel("Force cookie auth on downloads")
        rm_sub_label.setObjectName("SettingSubLabel")
        rm_sub_label.setStyleSheet("font-size: 11px;")
        rm_label_block_layout.addWidget(rm_sub_label)

        rm_label_block.setLayout(rm_label_block_layout)
        rm_row_layout.addWidget(rm_label_block, 1)

        self.restricted_mode_cb = ToggleSwitch(self.dark_mode, self)
        self.restricted_mode_cb.setChecked(self.restricted_mode)
        self.restricted_mode_cb.toggled.connect(self._on_restricted_mode_toggle)
        rm_row_layout.addWidget(self.restricted_mode_cb)

        rm_card_layout.addWidget(rm_row_widget)
        layout.addWidget(rm_card)

        card = QFrame()
        card.setObjectName("Card")
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(14, 14, 14, 14)
        card_layout.setSpacing(10)

        # Setup YouTube login section
        yt_login_title = QLabel("Login to YouTube")
        yt_login_title.setObjectName("SettingLabel")
        card_layout.addWidget(yt_login_title)

        yt_login_hint = QLabel(
            "Connect your Google account to access age-restricted and members-only videos. "
            "Cookies are read from your installed browser and stored securely on this device."
        )
        yt_login_hint.setObjectName("SettingSubLabel")
        yt_login_hint.setStyleSheet("font-size: 11px;")
        yt_login_hint.setWordWrap(True)
        card_layout.addWidget(yt_login_hint)

        self.yt_login_status_label = QLabel("Status: Not connected")
        self.yt_login_status_label.setObjectName("SettingSubLabel")
        self.yt_login_status_label.setStyleSheet("font-size: 11px;")
        self.yt_login_status_label.setWordWrap(True)
        card_layout.addWidget(self.yt_login_status_label)

        yt_btn_row = QHBoxLayout()
        self.yt_login_btn = QPushButton("🔑  Login to YouTube")
        self.yt_login_btn.setObjectName("GhostButton")
        self._style_btn(self.yt_login_btn)
        self.yt_login_btn.clicked.connect(self._yt_open_login_dialog)

        self.yt_logout_btn = QPushButton("Disconnect")
        self.yt_logout_btn.setObjectName("GhostButton")
        self._style_btn(self.yt_logout_btn)
        self.yt_logout_btn.clicked.connect(self._yt_logout)

        yt_btn_row.addWidget(self.yt_login_btn)
        yt_btn_row.addWidget(self.yt_logout_btn)
        yt_btn_row.addStretch(1)
        card_layout.addLayout(yt_btn_row)

        # Cookies file row section
        file_title = QLabel("Cookies file (optional)")
        file_title.setObjectName("SettingLabel")
        card_layout.addWidget(file_title)

        btn_row = QHBoxLayout()
        self.set_cookies_btn = QPushButton("Set Cookies File")
        self.set_cookies_btn.setObjectName("PasteButton")
        self.set_cookies_btn.setSizePolicy(QSizePolicy.Minimum, QSizePolicy.Fixed)
        self.set_cookies_btn.setMinimumWidth(0)
        self.set_cookies_btn.adjustSize()
        self.set_cookies_btn.clicked.connect(self.set_cookies_file)
        self.clear_cookies_btn = QPushButton("Clear Cookies File")
        self.clear_cookies_btn.setObjectName("GhostButton")
        self._style_btn(self.clear_cookies_btn)
        self.clear_cookies_btn.clicked.connect(self.clear_cookies_file)
        btn_row.addWidget(self.set_cookies_btn)
        btn_row.addWidget(self.clear_cookies_btn)
        btn_row.addStretch(1)
        card_layout.addLayout(btn_row)

        self.help_btn = QPushButton("How To Add Cookies")
        self.help_btn.setObjectName("GhostButton")
        self._style_btn(self.help_btn)
        self.help_btn.clicked.connect(self.show_cookies_help)
        card_layout.addWidget(self.help_btn)

        layout.addWidget(card)
        layout.addStretch(1)

        # Hidden elements for cookies page compatibility
        self.restricted_status_label = QLabel()
        self.restricted_status_label.hide()
        self.diagnostics_label = QLabel()
        self.diagnostics_label.hide()
        self.browser_auth_combo = QComboBox()
        self.browser_auth_combo.hide()
        self.browser_profile_input = QLineEdit()
        self.browser_profile_input.hide()
        self.browser_connect_btn = QPushButton()
        self._style_btn(self.browser_connect_btn)
        self.browser_connect_btn.hide()
        self.browser_disconnect_btn = QPushButton()
        self._style_btn(self.browser_disconnect_btn)
        self.browser_disconnect_btn.hide()

        return page

    def _build_about_page(self):
        page = QWidget()
        page.setObjectName("Page")
        layout = QVBoxLayout(page)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(8)

        # Page Header
        header = self._create_page_header("About", "Application information and terms")
        layout.addWidget(header)

        card = QFrame()
        card.setObjectName("Card")
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(14, 14, 14, 14)
        card_layout.setSpacing(8)

        title = QLabel("YT Downloader Pro")
        title.setObjectName("SettingLabel")
        card_layout.addWidget(title)
        
        card_layout.addWidget(QLabel(f"Version: {self._version_text()}"))
        card_layout.addWidget(QLabel("Created by: Tahsan"))
        card_layout.addWidget(QLabel("A modern downloader built for speed and clarity."))
        card_layout.addWidget(QLabel("License: GNU GPLv3"))
        
        repo_link = QLabel('<a href="https://github.com/tahsanahmmed25/YTDownloader" style="color: inherit; text-decoration: none;">github.com/tahsanahmmed25/YTDownloader</a>')
        repo_link.setObjectName("SettingSubLabel")
        repo_link.setOpenExternalLinks(True)
        card_layout.addWidget(repo_link)
        
        notice_label = QLabel(
            "Security Notice: To protect your system, discourage fake/rebranded copies, and ensure "
            "you receive official updates, always download from the official source link above."
        )
        notice_label.setWordWrap(True)
        notice_label.setObjectName("SettingSubLabel")
        notice_label.setStyleSheet("font-size: 11px;")
        self.terms_btn = QPushButton("View Terms && Privacy")
        self.terms_btn.setObjectName("GhostButton")
        self.terms_btn.clicked.connect(self.show_terms_dialog)
        card_layout.addWidget(self.terms_btn)

        layout.addWidget(card)
        layout.addStretch(1)
        return page

    def load_defaults_from_prefs(self):
        quality = self.settings.value("default_quality", "1080p")
        fmt     = self.settings.value("default_format",  "MP4")
        audio   = self.settings.value("default_audio",   "MP3")
        
        # Populate combos with default options if empty on startup
        if self.quality.count() == 0:
            self.quality.addItems(["Auto (Best)", "720p", "1080p", "2K", "4K"])
        if self.format_combo.count() == 0:
            self.format_combo.addItems(["Auto", "MP4", "MKV", "WEBM"])
        if self.audio_combo.count() == 0:
            self.audio_combo.addItems(["Best", "AAC", "MP3", "Opus", "FLAC", "Vorbis"])
        if self.subs_lang.count() == 0:
            self.subs_lang.addItem("None")

        # Set the combobox/config cell to match saved defaults
        idx = self.quality.findText(quality)
        if idx >= 0:
            self.quality.setCurrentIndex(idx)
        else:
            self.quality.addItem(quality)
            self.quality.setCurrentText(quality)
        
        idx = self.format_combo.findText(fmt)
        if idx >= 0:
            self.format_combo.setCurrentIndex(idx)
        else:
            self.format_combo.addItem(fmt)
            self.format_combo.setCurrentText(fmt)
        
        idx = self.audio_combo.findText(audio)
        if idx >= 0:
            self.audio_combo.setCurrentIndex(idx)
        else:
            self.audio_combo.addItem(audio)
            self.audio_combo.setCurrentText(audio)

        self.subs_mode_combo.setCurrentText("None")
        self.subs_lang.setCurrentText("None")


class ThemeCard(QFrame):
    def __init__(self, theme_name, display_name, description, accent_color, is_selected, parent_page):
        super().__init__()
        self.theme_name = theme_name
        self.parent_page = parent_page
        self.setObjectName("Card")
        self.setFixedHeight(88)
        self.setCursor(Qt.PointingHandCursor)

        layout = QHBoxLayout(self)
        layout.setSpacing(12)
        layout.setContentsMargins(12, 12, 12, 12)

        # Left: accent dot
        self.dot = QLabel()
        self.dot.setFixedSize(36, 36)
        self.dot.setStyleSheet(f"border-radius: 18px; background-color: {accent_color};")
        layout.addWidget(self.dot)

        # Center: text layout
        text_layout = QVBoxLayout()
        text_layout.setSpacing(2)
        text_layout.setContentsMargins(0, 0, 0, 0)

        self.name_label = QLabel(display_name)
        self.name_label.setObjectName("BrandName")
        self.name_label.setStyleSheet("font-size: 13px; font-weight: 500; background: transparent;")

        self.desc_label = QLabel(description)
        self.desc_label.setObjectName("SettingSubLabel")
        self.desc_label.setStyleSheet("font-size: 11px; background: transparent;")

        text_layout.addWidget(self.name_label)
        text_layout.addWidget(self.desc_label)
        layout.addLayout(text_layout)
        layout.addStretch(1)

        # Right: selected indicator
        self.indicator = QLabel()
        self.indicator.setFixedSize(18, 18)
        self.indicator.setAlignment(Qt.AlignCenter)
        self.update_selection(is_selected, accent_color)
        layout.addWidget(self.indicator)

    def update_selection(self, is_selected, accent_color):
        if is_selected:
            self.indicator.setText("✓")
            self.indicator.setStyleSheet(
                f"border-radius: 9px; background-color: {accent_color}; color: #ffffff; font-size: 10px; font-weight: bold; border: none;"
            )
        else:
            self.indicator.setText("")
            self.indicator.setStyleSheet(
                "border-radius: 9px; background: transparent; border: 1px solid #888888;"
            )

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.parent_page.select_theme(self.theme_name)
        super().mousePressEvent(event)


class ThemesPage(QWidget):
    def __init__(self, main_window):
        super().__init__()
        self.main_window = main_window
        self.setObjectName("ThemesPage")

        layout = QVBoxLayout(self)
        layout.setSpacing(8)
        layout.setContentsMargins(20, 20, 20, 20)

        # Header
        header = QWidget()
        header.setObjectName("PageHeader")
        header_layout = QVBoxLayout(header)
        header_layout.setContentsMargins(0, 0, 0, 8)
        header_layout.setSpacing(2)

        title_label = QLabel("Themes")
        title_label.setObjectName("PageTitle")

        subtitle_label = QLabel("Choose an accent color style for the app")

        subtitle_label.setObjectName("PageSubtitle")
        subtitle_label.setStyleSheet("font-size: 13px;")

        header_layout.addWidget(title_label)
        header_layout.addWidget(subtitle_label)
        layout.addWidget(header)

        # Dark mode card
        dark_card = QFrame()
        dark_card.setObjectName("Card")
        row = QHBoxLayout(dark_card)
        row.setContentsMargins(14, 12, 14, 12)
        row.setSpacing(12)

        # Left side — label block
        label_col = QVBoxLayout()
        label_col.setSpacing(2)
        title_lbl = QLabel("Dark mode")
        title_lbl.setObjectName("SettingLabel")
        sub_lbl = QLabel("Switch between light and dark interface")
        sub_lbl.setObjectName("SettingSubLabel")
        label_col.addWidget(title_lbl)
        label_col.addWidget(sub_lbl)

        row.addLayout(label_col)
        row.addStretch()

        # Right side — toggle switch
        self.dark_toggle = ToggleSwitch()
        win = self.main_window if self.main_window else self.window()
        self.dark_toggle.setChecked(getattr(win, 'dark_mode', False))
        self.dark_toggle.toggled.connect(self._on_dark_toggled)
        row.addWidget(self.dark_toggle)

        layout.addWidget(dark_card)

        # Theme Grid
        self.grid_layout = QGridLayout()
        self.grid_layout.setSpacing(10)
        layout.addLayout(self.grid_layout)
        layout.addStretch(1)

        self.cards = {}
        self.populate_themes()

    def showEvent(self, event):
        super().showEvent(event)
        if hasattr(self, 'dark_toggle'):
            win = self.main_window if self.main_window else self.window()
            self.dark_toggle.blockSignals(True)
            self.dark_toggle.setChecked(getattr(win, 'dark_mode', False))
            self.dark_toggle.blockSignals(False)

    def _on_dark_toggled(self, checked: bool):
        win = self.main_window if self.main_window else self.window()
        if hasattr(win, 'dark_mode'):
            win.dark_mode = checked
            win._apply_theme()
            self.dark_toggle.blockSignals(True)
            self.dark_toggle.setChecked(checked)
            self.dark_toggle.blockSignals(False)

    def populate_themes(self):
        from ui.themes import THEMES, all_theme_names
        current_theme = getattr(self.main_window, 'current_theme_name', 'Teal Clarity')

        # Remove old cards if any
        for card in list(self.cards.values()):
            self.grid_layout.removeWidget(card)
            card.deleteLater()
        self.cards.clear()

        names = all_theme_names()
        for idx, name in enumerate(names):
            theme = THEMES[name]
            is_selected = (name == current_theme)
            card = ThemeCard(
                theme_name=name,
                display_name=theme["display_name"],
                description=theme["description"],
                accent_color=theme["accent_light"],
                is_selected=is_selected,
                parent_page=self
            )
            self.cards[name] = card
            row = idx // 2
            col = idx % 2
            self.grid_layout.addWidget(card, row, col)

    def select_theme(self, theme_name):
        self.main_window.apply_theme(theme_name)

    def update_card_selection(self):
        from ui.themes import THEMES
        current_theme = getattr(self.main_window, 'current_theme_name', 'Teal Clarity')
        for name, card in self.cards.items():
            is_selected = (name == current_theme)
            theme = THEMES[name]
            card.update_selection(is_selected, theme["accent_light"])

