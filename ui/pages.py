import os
import app_config

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
from PySide6.QtCore import Qt, QSize, QCoreApplication, QObject, QThread, Signal, QTimer
from PySide6.QtGui import QFont, QColor, QPixmap, QIcon

QCoreApplication.setOrganizationName("Tahsan")
QCoreApplication.setApplicationName("YTDownloaderPro")

from ui.widgets import (
    FadingTextButton, PasteButton, BrandIcon, DownloadButton, GradientButton,
    DownloadProgressBar, ToggleSwitch, ToastFrame, NavButton, StatusBadge,
    SectionLabel, NavCounter, PrimaryButton, AnimatedComboBox, MarqueeLabel
)

class ThumbnailWorker(QThread):
    ready = Signal(str, bytes)

    def __init__(self, task_id: str, url: str, parent=None):
        super().__init__(parent)
        self.task_id = task_id
        self.url = url

    def run(self):
        if not self.url:
            return
        try:
            import urllib.request
            req = urllib.request.Request(
                self.url,
                headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
            )
            with urllib.request.urlopen(req, timeout=10) as response:
                data = response.read()
            if data:
                self.ready.emit(self.task_id, data)
        except Exception:
            pass


class AnalyzeWorker(QThread):
    result = Signal(dict)
    error  = Signal(str)

    def __init__(self, url: str, parent=None):
        super().__init__(parent)
        self.url = url
        self._process = None

    def run(self):
        try:
            import subprocess, json, shutil, os, sys

            # If the project has a ytdlp_exe_manager, get the path from it:
            try:
                from ytdlp_exe_manager import get_exe_path
                ytdlp_cmd = get_exe_path()
            except ImportError:
                try:
                    from ytdlp_exe_manager import get_ytdlp_path
                    ytdlp_cmd = get_ytdlp_path()
                except ImportError:
                    ytdlp_cmd = shutil.which('yt-dlp') or 'yt-dlp'

            cmd = [
                ytdlp_cmd,
                '--dump-json',
                '--no-playlist',
                '--quiet',
                '--no-warnings',
                '--socket-timeout', '15',
                '--extractor-args', 'youtube:player_client=android,ios,web',
            ]

            try:
                from ui.session_manager import load_session
                session_cookie = load_session()
                if session_cookie and os.path.isfile(session_cookie):
                    cmd.extend(['--cookies', session_cookie])
            except Exception:
                pass

            cmd.append(self.url)

            popen_kwargs = {
                "stdout": subprocess.PIPE,
                "stderr": subprocess.PIPE,
            }

            if sys.platform == "win32":
                popen_kwargs["creationflags"] = 0x08000000  # CREATE_NO_WINDOW
                startupinfo = subprocess.STARTUPINFO()
                startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
                startupinfo.wShowWindow = 0  # SW_HIDE
                popen_kwargs["startupinfo"] = startupinfo
            else:
                popen_kwargs["start_new_session"] = True

            self._process = subprocess.Popen(cmd, **popen_kwargs)

            stdout, stderr = self._process.communicate(timeout=25)

            if self._process.returncode != 0:
                err_msg = stderr.decode('utf-8', errors='replace').strip()
                # Get first meaningful line of error
                first_line = next(
                    (l for l in err_msg.splitlines() if l.strip()),
                    "Could not fetch video info"
                )
                self.error.emit(first_line)
                return

            raw = stdout.decode('utf-8', errors='replace').strip()
            if not raw:
                self.error.emit("No data returned from yt-dlp.")
                return

            info = json.loads(raw)

            # Extract only what the UI needs
            safe = {
                "title":           info.get("title", "Unknown"),
                "uploader":        info.get("uploader", ""),
                "duration":        info.get("duration", 0),
                "thumbnail":       info.get("thumbnail", ""),
                "filesize_approx": info.get("filesize_approx", 0),
                "webpage_url":     info.get("webpage_url", self.url),
                "formats": [
                    {
                        "format_id":   f.get("format_id", ""),
                        "ext":         f.get("ext", ""),
                        "height":      f.get("height"),
                        "fps":         f.get("fps"),
                        "vcodec":      f.get("vcodec", ""),
                        "acodec":      f.get("acodec", ""),
                        "filesize":    f.get("filesize"),
                        "format_note": f.get("format_note", ""),
                    }
                    for f in info.get("formats", [])
                    if isinstance(f, dict)
                ],
                "subtitles":          list(info.get("subtitles", {}).keys()),
                "automatic_captions": list(info.get("automatic_captions", {}).keys()),
            }
            self.result.emit(safe)

        except subprocess.TimeoutExpired:
            if self._process:
                self._process.kill()
            self.error.emit(
                "Analysis timed out after 25 seconds. "
                "Check your connection and try again."
            )
        except json.JSONDecodeError:
            self.error.emit("Could not parse video info. Try a different URL.")
        except FileNotFoundError:
            self.error.emit(
                "yt-dlp not found. Please ensure yt-dlp is installed."
            )
        except Exception as e:
            self.error.emit(str(e).split('\n')[0][:120])

    def cancel(self):
        if self._process and self._process.poll() is None:
            self._process.kill()
        self.quit()



class CombinedMetaLabel(QLabel):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._size_text = ""
        self._speed_text = ""

    def set_size_text(self, text):
        self._size_text = text
        self._update_display()

    def set_speed_text(self, text):
        self._speed_text = text
        self._update_display()

    def _update_display(self):
        parts = []
        if self._size_text:
            parts.append(self._size_text)
        if self._speed_text:
            spd = self._speed_text
            if spd.startswith("Speed: "):
                spd = spd[len("Speed: "):]
            parts.append(spd)
        
        combined = "  •  ".join(parts)
        self.setText(combined)


class SizeProxy(QObject):
    def __init__(self, label):
        super().__init__()
        self.label = label

    def setText(self, text):
        self.label.set_size_text(text)

    def setVisible(self, visible):
        pass

    def isVisible(self):
        return True


class SpeedProxy(QObject):
    def __init__(self, label):
        super().__init__()
        self.label = label

    def setText(self, text):
        self.label.set_speed_text(text)

    def setVisible(self, visible):
        pass

    def isVisible(self):
        return True


class InvisiblePlaceholderButton(QPushButton):
    def __init__(self, text="", parent=None):
        super().__init__(text, parent)
        self.setFixedSize(0, 0)
        self.hide()

    def setVisible(self, visible):
        pass

    def show(self):
        pass


class PagesMixin:
    def _on_analyze_clicked(self):
        # Fully clean up any previous worker before starting
        if hasattr(self, '_analyze_worker') and self._analyze_worker is not None:
            try:
                self._analyze_worker.result.disconnect()
                self._analyze_worker.error.disconnect()
            except Exception:
                pass
            if self._analyze_worker.isRunning():
                try:
                    self._analyze_worker.cancel()
                except Exception:
                    self._analyze_worker.quit()
                self._analyze_worker.wait(500)
            self._analyze_worker = None

        if hasattr(self, '_fetch_thread') and self._fetch_thread is not None:
            try:
                self._fetch_worker.info_ready.disconnect()
                self._fetch_worker.error.disconnect()
            except Exception:
                pass
            if self._fetch_thread.isRunning():
                self._fetch_thread.quit()
                self._fetch_thread.wait(500)
            self._fetch_thread = None
            self._fetch_worker = None

        # Clear any previous error
        if hasattr(self, 'error_label') and self.error_label:
            self.error_label.setVisible(False)

        url = self.url_input.text().strip()
        if not url:
            return
        from downloader import is_valid_youtube_url
        if not is_valid_youtube_url(url):
            self._show_error_dialog("Error", "Please enter a valid YouTube link.")
            return

        self._info_ready = False
        self._active_url = url
        self.download_btn.setEnabled(False)
        self._set_config_enabled(False)
        self._set_analyzing_state(True)
        try:
            self.url_input.setCursorPosition(0)
            self.url_input.deselect()
        except Exception:
            pass
        self._set_metadata_placeholder(True)
        self._clear_format_quality()

        # Dynamic override of slots
        self._on_analyze_result = self._custom_on_analyze_result
        self._on_analyze_error = self._custom_on_analyze_error

        # Start AnalyzeWorker QThread
        self._analyze_worker = AnalyzeWorker(url, parent=self)
        self._analyze_worker.result.connect(self._on_analyze_result)
        self._analyze_worker.error.connect(self._on_analyze_error)
        self._analyze_worker.start()

    def _custom_on_analyze_result(self, safe):
        self._set_analyzing_state(False)   # ← must be first line
        
        # 1. Title
        title = safe.get("title", "Unknown")
        self.title.setText(title)
        if hasattr(self, "title_label") and self.title_label:
            self.title_label.setText(title)
            
        # 2. Size
        size_approx = safe.get("filesize_approx", 0)
        size_mb = f"{size_approx / (1024*1024):.1f}" if size_approx else "Unknown"
        self.size.setText(f"Estimated size: ~{size_mb} MB" if size_mb != "Unknown" else "Estimated size: Unknown")
        try:
            self._estimated_size_mb = float(size_mb) if size_mb != "Unknown" else None
        except Exception:
            self._estimated_size_mb = None
            
        # 3. Thumbnail (Fetch using ThumbnailWorker if not empty)
        thumbnail = safe.get("thumbnail", "")
        if thumbnail:
            worker = ThumbnailWorker("preview", thumbnail, parent=self)
            def on_preview_thumb_ready(task_id, data):
                if data:
                    from PySide6.QtGui import QPixmap
                    pix = QPixmap()
                    pix.loadFromData(data)
                    self._set_preview_thumbnail(pix)
            worker.ready.connect(on_preview_thumb_ready)
            self._thumb_worker = worker
            worker.start()
        else:
            self.thumbnail.clear()
            
        # 4. Formats & Qualities
        from downloader import _available_format_quality
        available_formats, available_qualities = _available_format_quality(safe)
        
        self._apply_format_options(available_formats)
        self._apply_quality_options(available_qualities)
        
        # 5. Subtitles
        subs = safe.get("subtitles", [])
        self._apply_subtitle_options(subs)
        
        self._info_ready = True
        self.download_btn.setEnabled(True)
        self._set_config_enabled(True)
        self._sync_download_button_text()
        self._expand_details()
        self._set_metadata_placeholder(False)
        self._apply_defaults_after_populate()   # ← add this line last

    def _custom_on_analyze_error(self, msg):
        self._set_analyzing_state(False)   # ← must be first line
        self._show_error_dialog("Error", msg)
        self._info_ready = False
        self._estimated_size_mb = None
        self.download_btn.setEnabled(False)
        self._set_config_enabled(False)
        self._set_metadata_placeholder(True)
        self._sync_download_button_text()
        if hasattr(self, "error_label") and self.error_label:
            self.error_label.setText(f"⚠ {msg}")
            self.error_label.setVisible(True)

    def _apply_defaults_after_populate(self):
        from PySide6.QtCore import QSettings, Qt
        s = QSettings()
        quality_pref = s.value("default_quality", "1080p")
        format_pref  = s.value("default_format",  "MP4")
        audio_pref   = s.value("default_audio",   "MP3")

        for combo, pref in [
            (self.quality_combo, quality_pref),
            (self.format_combo,  format_pref),
            (self.audio_combo,   audio_pref),
        ]:
            if not combo:
                continue
            # Try exact match first
            idx = combo.findText(pref, Qt.MatchFlag.MatchFixedString)
            if idx < 0:
                # Try case-insensitive partial match (e.g. "1080p" in "1080p (HD)")
                idx = combo.findText(pref, Qt.MatchFlag.MatchContains)
            if idx >= 0:
                combo.blockSignals(True)
                combo.setCurrentIndex(idx)
                combo.blockSignals(False)

    def _on_task_card_thumbnail_ready(self, task_id: str, data: bytes):
        if not data:
            return
        from PySide6.QtGui import QPixmap
        pixmap = QPixmap()
        pixmap.loadFromData(data)
        if pixmap.isNull():
            return

        if not hasattr(self, "_task_cards") or not self._task_cards:
            return
        card = self._task_cards.get(task_id)
        if card is None:
            return
        if hasattr(card, 'thumb_label') and card.thumb_label:
            card.thumb_label.setPixmap(
                pixmap.scaled(80, 46, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            )
            card.thumb_label.setText("")
            card.thumb_label.setStyleSheet("""
                background: #e5e5e5;
                border-radius: 6px;
                border: 1px solid #d0d0d0;
            """)
        
        # Cache the pixmap
        task = None
        for t in getattr(self, "_pending_tasks", []):
            if t.get("id") == task_id:
                task = t
                break
        if not task:
            for t in getattr(self, "_active_tasks", {}).values():
                if t.get("id") == task_id:
                    task = t
                    break
        if not task:
            for t in getattr(self, "_paused_tasks", {}).values():
                if t.get("id") == task_id:
                    task = t
                    break
        if task:
            payload = task.get("payload") or {}
            url = payload.get("url")
            if url:
                if not hasattr(self, "_thumb_cache"):
                    self._thumb_cache = {}
                self._thumb_cache[url] = pixmap

    def _on_paste_clicked(self):
        from PySide6.QtWidgets import QApplication
        clipboard = QApplication.clipboard()
        text = clipboard.text().strip()
        if text:
            self.url_input.setText(text)


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

    def build_task_card(self, task_id, title):
        frame = QFrame()
        frame.setObjectName("Card")
        frame.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        frame.setFixedHeight(72)

        if not hasattr(self, "_task_cards"):
            self._task_cards = {}
        self._task_cards[task_id] = frame
        
        layout = QHBoxLayout(frame)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(12)
        layout.setAlignment(Qt.AlignVCenter)

        # 1. Thumbnail QLabel — 80x46px (16:9 ratio)
        thumb_label = QLabel()
        thumb_label.setObjectName("TaskThumbnail")
        thumb_label.setFixedSize(80, 46)
        thumb_label.setScaledContents(False)
        thumb_label.setAlignment(Qt.AlignCenter)
        dark = getattr(self.window(), 'dark_mode', False)
        thumb_bg   = "#242424" if dark else "#efefef"
        thumb_border = "#333333" if dark else "#e0e0e0"
        thumb_label.setStyleSheet(f"""
            background: {thumb_bg};
            border-radius: 6px;
            border: 1px solid {thumb_border};
            color: {'#555555' if dark else '#b0b0b0'};
            font-size: 16px;
        """)
        thumb_label.setText("▶")

        frame.thumb_label = thumb_label
        frame.task_id = None

        # 2. Info column QVBoxLayout
        info_widget = QWidget()
        info_widget.setAttribute(Qt.WA_TransparentForMouseEvents)
        info_layout = QVBoxLayout(info_widget)
        info_layout.setContentsMargins(0, 2, 0, 2)
        info_layout.setSpacing(6)

        # Row 1 — title (marquee)
        title_label = MarqueeLabel(title)
        title_label.setObjectName("TaskTitle")
        title_label.setStyleSheet("font-size: 12px; font-weight: 500;")
        title_label.setFixedHeight(20)

        # Row 2 — progress bar
        progress = QProgressBar()
        progress.setMinimum(0)
        progress.setMaximum(100)
        progress.setValue(0)
        progress.setTextVisible(False)
        progress.setFixedHeight(5)
        progress.setMinimumWidth(100)
        progress.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        progress.setContentsMargins(0, 0, 0, 0)

        # Row 3 — size and speed on same line
        meta_label = CombinedMetaLabel()
        meta_label.setObjectName("MetaLabel")
        meta_label.setStyleSheet("font-size: 10px;")
        meta_label.setFixedHeight(16)
        meta_label.set_speed_text("0.0 KB/s")

        info_layout.addWidget(title_label)
        info_layout.addWidget(progress)
        info_layout.addWidget(meta_label)

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
        status_label._item_speed = meta_label

        orig_set_text = status_label.setText
        def custom_set_text(text):
            txt = (text or "").lower()
            if "starting" in txt:
                status_label.show()
                status_label.setObjectName("BadgeNeutral")
                QLabel.setText(status_label, "Starting...")
                if status_label._item_pct: status_label._item_pct.hide()
                if status_label._item_prog: status_label._item_prog.hide()
                if status_label._item_speed: status_label._item_speed.hide()
            elif "finalizing" in txt:
                status_label.show()
                status_label.setObjectName("BadgeNeutral")
                QLabel.setText(status_label, "Finalizing...")
                if status_label._item_pct: status_label._item_pct.hide()
                if status_label._item_prog: status_label._item_prog.hide()
                if status_label._item_speed: status_label._item_speed.hide()
            elif "cancelling" in txt:
                status_label.show()
                status_label.setObjectName("BadgeWarning")
                QLabel.setText(status_label, "Cancelling...")
                if status_label._item_pct: status_label._item_pct.hide()
                if status_label._item_prog: status_label._item_prog.hide()
                if status_label._item_speed: status_label._item_speed.hide()
            else:
                orig_set_text(text)
        status_label.setText = custom_set_text

        # Functional active download controls
        btn_group = QWidget(frame)
        btn_group.setObjectName("ButtonGroup")
        btn_group_layout = QHBoxLayout(btn_group)
        btn_group_layout.setContentsMargins(0, 0, 0, 0)
        btn_group_layout.setSpacing(6)
        btn_group_layout.setAlignment(Qt.AlignCenter)

        pause_btn = QPushButton("⏸")
        pause_btn.setObjectName("CardIconButton")
        pause_btn.setFixedSize(28, 28)
        pause_btn.setCursor(Qt.PointingHandCursor)

        resume_btn = QPushButton("▶")
        resume_btn.setObjectName("CardIconButton")
        resume_btn.setFixedSize(28, 28)
        resume_btn.setCursor(Qt.PointingHandCursor)
        resume_btn.setVisible(False)

        cancel_btn = QPushButton("✕")
        cancel_btn.setObjectName("CardIconButton")
        cancel_btn.setProperty("action", "cancel")
        cancel_btn.setFixedSize(28, 28)
        cancel_btn.setCursor(Qt.PointingHandCursor)

        btn_group_layout.addWidget(pause_btn)
        btn_group_layout.addWidget(resume_btn)
        btn_group_layout.addWidget(cancel_btn)

        open_btn = InvisiblePlaceholderButton("Open", frame)

        layout.addWidget(thumb_label)
        layout.addWidget(info_widget, 1)
        layout.addWidget(percentage_label)
        layout.addWidget(status_label)
        layout.addWidget(btn_group)

        # Wire value changes
        progress.valueChanged.connect(lambda val: percentage_label.setText(f"{val}%"))

        item = {
            "frame": frame,
            "title": title_label,
            "status": status_label,
            "status_icon": QLabel(),
            "status_effect": QGraphicsOpacityEffect(),
            "progress": progress,
            "speed": SpeedProxy(meta_label),
            "size": SizeProxy(meta_label),
            "pause_btn": pause_btn,
            "resume_btn": resume_btn,
            "cancel_btn": cancel_btn,
            "open_btn": open_btn,
            "percentage_label": percentage_label,
            "thumbnail": thumb_label
        }
        frame._download_item = item
        QTimer.singleShot(300, title_label._check_and_start)
        return item

    def _update_task_card(self, task_id, percent, speed=None, downloaded=None, total=None):
        if not hasattr(self, "_task_cards"):
            self._task_cards = {}
        card = self._task_cards.get(task_id)
        if card is None:
            return
        self.update_progress(task_id, percent, speed, downloaded, total)

    def _build_downloader_page(self):
        # Helper to register task card mappings cleanly
        def register_task_card(task_id, item):
            if not task_id or not item:
                return
            if not hasattr(self, "_task_cards"):
                self._task_cards = {}
            frame = item.get("frame")
            if frame:
                self._task_cards[task_id] = frame
                frame.task_id = task_id
            item["task_id"] = task_id

        # Dynamically wrap on_info_ready to update thumbnails on task cards
        if hasattr(self, "on_info_ready"):
            orig_on_info_ready = self.on_info_ready
            def wrapped_on_info_ready(title, size, thumb_bytes, *args, **kwargs):
                orig_on_info_ready(title, size, thumb_bytes, *args, **kwargs)
                if hasattr(self, "title_label") and self.title_label:
                    self.title_label.setText(title or "Unknown")
                if thumb_bytes:
                    from PySide6.QtGui import QPixmap
                    pix = QPixmap()
                    pix.loadFromData(thumb_bytes)
                    if not pix.isNull():
                        # Cache the pixmap under the active url
                        if not hasattr(self, "_thumb_cache"):
                            self._thumb_cache = {}
                        url = getattr(self, "_active_url", "")
                        if url:
                            self._thumb_cache[url] = pix

                        # Find matching cards and update their thumbnails
                        active = getattr(self, "_active_tasks", {})
                        pending = getattr(self, "_pending_tasks", [])
                        paused = getattr(self, "_paused_tasks", {})
                        for task in list(active.values()) + list(pending) + list(paused.values()):
                            payload = task.get("payload") or {}
                            if task.get("title") == title or payload.get("url") == url:
                                item = task.get("item")
                                if item:
                                    card = item.get("frame")
                                    if card and hasattr(card, "thumb_label") and card.thumb_label:
                                        card.thumb_label.setPixmap(
                                            pix.scaled(80, 46, Qt.KeepAspectRatio, Qt.SmoothTransformation)
                                        )
                                        card.thumb_label.setText("")
                                        card.thumb_label.setStyleSheet("""
                                            background: #e5e5e5;
                                            border-radius: 6px;
                                            border: 1px solid #d0d0d0;
                                        """)
            self.on_info_ready = wrapped_on_info_ready

        # Dynamically wrap _create_download_item to set the correct thumbnail on creation/reuse!
        if hasattr(self, "_create_download_item"):
            orig_create_download_item = self._create_download_item
            def wrapped_create_download_item(task_id, title):
                item = orig_create_download_item(task_id, title)
                if item:
                    # Clear thumbnail to placeholder
                    thumb_label = item.get("thumbnail")
                    if thumb_label:
                        thumb_label.setPixmap(QPixmap())
                        thumb_label.setText("▶")
                        thumb_label.setStyleSheet("""
                            background: #efefef;
                            border-radius: 6px;
                            border: 1px solid #e0e0e0;
                            color: #b0b0b0;
                            font-size: 16px;
                        """)
                    if item.get("frame"):
                        item["frame"].task_id = None
                    
                    # Match preview thumbnail if title matches the current preview
                    if hasattr(self, "thumbnail") and self.thumbnail:
                        px = self.thumbnail.pixmap()
                        if px and not px.isNull():
                            current_title = ""
                            if hasattr(self, "title") and self.title:
                                current_title = self.title.text().replace("Title: ", "").strip()
                            if current_title == title:
                                if thumb_label:
                                    thumb_label.setPixmap(
                                        px.scaled(80, 46, Qt.KeepAspectRatio, Qt.SmoothTransformation)
                                    )
                                    thumb_label.setText("")
                                    thumb_label.setStyleSheet("""
                                        background: #e5e5e5;
                                        border-radius: 6px;
                                        border: 1px solid #d0d0d0;
                                    """)
                return item
            self._create_download_item = wrapped_create_download_item

        # Dynamically wrap _queue_download to set/fetch thumbnail of the queued task card
        if hasattr(self, "_queue_download"):
            orig_queue_download = self._queue_download
            def wrapped_queue_download(payload, title_text, announce=True, autostart=True):
                res = orig_queue_download(payload, title_text, announce, autostart)
                for task in getattr(self, "_pending_tasks", []):
                    register_task_card(task.get("id"), task.get("item"))
                for tid, task in getattr(self, "_active_tasks", {}).items():
                    register_task_card(tid, task.get("item"))
                for tid, task in getattr(self, "_paused_tasks", {}).items():
                    register_task_card(tid, task.get("item"))

                # Find the task we just queued
                task = None
                for t in getattr(self, "_pending_tasks", []):
                    if t.get("payload") is payload or (t.get("title") == title_text and t.get("payload", {}).get("url") == payload.get("url")):
                        task = t
                        break
                if not task:
                    for t in getattr(self, "_active_tasks", {}).values():
                        if t.get("payload") is payload or (t.get("title") == title_text and t.get("payload", {}).get("url") == payload.get("url")):
                            task = t
                            break
                
                if task:
                    tid = task.get("id")
                    item = task.get("item")
                    if tid and item:
                        url = payload.get("url")
                        thumb_label = item.get("thumbnail")
                        
                        # 1. Try cache first
                        cached_px = getattr(self, "_thumb_cache", {}).get(url)
                        if cached_px and not cached_px.isNull():
                            if thumb_label:
                                thumb_label.setPixmap(
                                    cached_px.scaled(80, 46, Qt.KeepAspectRatio, Qt.SmoothTransformation)
                                )
                                thumb_label.setText("")
                                thumb_label.setStyleSheet("""
                                    background: #e5e5e5;
                                    border-radius: 6px;
                                    border: 1px solid #d0d0d0;
                                """)
                        else:
                            # 2. Try playlist session entries next
                            thumbnail_url = None
                            session_id = payload.get("playlist_session_id")
                            if session_id and session_id in getattr(self, "_playlist_sessions", {}):
                                session = self._playlist_sessions[session_id]
                                entries = session.get("entries") or []
                                idx = payload.get("playlist_item_index", 0) - 1
                                if 0 <= idx < len(entries):
                                    entry = entries[idx]
                                    thumbnail_url = entry.get("thumbnail")
                            
                            # 3. If we have a thumbnail URL, fetch asynchronously
                            if thumbnail_url:
                                worker = ThumbnailWorker(task_id=tid, url=thumbnail_url, parent=self)
                                worker.ready.connect(self._on_task_card_thumbnail_ready)
                                if not hasattr(self, "_thumbnail_workers"):
                                    self._thumbnail_workers = {}
                                self._thumbnail_workers[tid] = worker
                                worker.finished.connect(lambda t_id=tid: self._thumbnail_workers.pop(t_id, None))
                                worker.start()
                return res
            self._queue_download = wrapped_queue_download

        # Dynamically wrap _restore_queued_task to map task_id to item/card
        if hasattr(self, "_restore_queued_task"):
            orig_restore_queued_task = self._restore_queued_task
            def wrapped_restore_queued_task(saved):
                res = orig_restore_queued_task(saved)
                if res:
                    for task in getattr(self, "_pending_tasks", []):
                        register_task_card(task.get("id"), task.get("item"))
                    for tid, task in getattr(self, "_paused_tasks", {}).items():
                        register_task_card(tid, task.get("item"))
                return res
            self._restore_queued_task = wrapped_restore_queued_task

        # Dynamically wrap _start_task to register task card mapping
        if hasattr(self, "_start_task"):
            orig_start_task = self._start_task
            def wrapped_start_task(task):
                orig_start_task(task)
                if task:
                    register_task_card(task.get("id"), task.get("item"))
            self._start_task = wrapped_start_task

        # Dynamically wrap update_progress to safeguard status label transitions
        if hasattr(self, "update_progress"):
            orig_update_progress = self.update_progress
            def wrapped_update_progress(task_id, percent, speed=None, downloaded=None, total=None):
                orig_update_progress(task_id, percent, speed, downloaded, total)
                task = getattr(self, "_active_tasks", {}).get(task_id)
                if task:
                    item = task.get("item")
                    if item and item.get("status"):
                        status_lbl = item["status"]
                        if status_lbl.text() in ("Queued", "Starting..."):
                            status_lbl.setText("Downloading...")
            self.update_progress = wrapped_update_progress


        # Dynamically wrap _recycle_task_frame and _remove_active_item_with_fade to clean up references and workers
        if hasattr(self, "_recycle_task_frame"):
            orig_recycle_task_frame = self._recycle_task_frame
            def wrapped_recycle_task_frame(task):
                if task:
                    tid = task.get("id")
                    if tid:
                        if hasattr(self, "_task_cards"):
                            self._task_cards.pop(tid, None)
                        worker = getattr(self, "_thumbnail_workers", {}).get(tid)
                        if worker:
                            try:
                                worker.disconnect()
                                worker.terminate()
                            except Exception:
                                pass
                            self._thumbnail_workers.pop(tid, None)
                        if hasattr(self, "_progress_started"):
                            self._progress_started.pop(tid, None)
                return orig_recycle_task_frame(task)
            self._recycle_task_frame = wrapped_recycle_task_frame

        if hasattr(self, "_remove_active_item_with_fade"):
            orig_remove_active_item_with_fade = self._remove_active_item_with_fade
            def wrapped_remove_active_item_with_fade(task):
                if task:
                    tid = task.get("id")
                    if tid:
                        if hasattr(self, "_task_cards"):
                            self._task_cards.pop(tid, None)
                        worker = getattr(self, "_thumbnail_workers", {}).get(tid)
                        if worker:
                            try:
                                worker.disconnect()
                                worker.terminate()
                            except Exception:
                                pass
                            self._thumbnail_workers.pop(tid, None)
                        if hasattr(self, "_progress_started"):
                            self._progress_started.pop(tid, None)
                return orig_remove_active_item_with_fade(task)
            self._remove_active_item_with_fade = wrapped_remove_active_item_with_fade

        page = QWidget()
        page.setObjectName("Page")
        self.home_page = page

        # Wrap _apply_theme to update the thumbnail placeholder stylesheet after setting theme stylesheet
        if hasattr(self, '_apply_theme'):
            orig_apply_theme = self._apply_theme
            def wrapped_apply_theme(*args, **kwargs):
                orig_apply_theme(*args, **kwargs)
                if hasattr(self, 'home_page') and self.home_page and hasattr(self.home_page, 'thumb_label') and self.home_page.thumb_label:
                    if getattr(self, 'dark_mode', False):
                        self.home_page.thumb_label.setStyleSheet("""
                            background: #242424;
                            border-radius: 6px;
                            border: 1px solid #333333;
                        """)
                    else:
                        self.home_page.thumb_label.setStyleSheet("""
                            background: #efefef;
                            border-radius: 6px;
                            border: 1px solid #e0e0e0;
                        """)
            self._apply_theme = wrapped_apply_theme
        layout = QVBoxLayout(page)
        layout.setContentsMargins(20, 20, 20, 20)
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
        self.paste_btn.clicked.connect(self._on_paste_clicked)
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
        self.paste_url_btn.clicked.connect(self._on_paste_clicked)

        url_card_layout.addWidget(self.paste_url_btn)
        url_card_layout.addWidget(url_input_col, 1)
        url_card_layout.addWidget(self.fetch_btn)
        layout.addWidget(url_card)

        self.error_label = QLabel()
        self.error_label.setObjectName("BadgeError")
        self.error_label.setWordWrap(True)
        self.error_label.setVisible(False)
        layout.addWidget(self.error_label)

        # Video details container (always visible)
        self.details_container = QWidget()
        self.details_container.setVisible(True)
        details_layout = QVBoxLayout(self.details_container)
        details_layout.setContentsMargins(0, 0, 0, 0)
        details_layout.setSpacing(0)

        preview_card = QFrame()
        preview_card.setObjectName("Card")
        self.result_card = preview_card
        preview_layout = QVBoxLayout(preview_card)
        preview_layout.setContentsMargins(14, 14, 14, 14)
        preview_layout.setSpacing(12)

        row1_layout = QHBoxLayout()
        row1_layout.setContentsMargins(0, 0, 0, 0)
        row1_layout.setSpacing(14)
        row1_layout.setAlignment(Qt.AlignVCenter)

        self.thumbnail = QLabel()
        self.thumbnail.setObjectName("PreviewThumb")
        self.thumbnail.setFixedSize(80, 46)
        self.thumbnail.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        self.thumbnail.setScaledContents(True)
        self.thumbnail.setStyleSheet("""
            background: #e5e5e5;
            border-radius: 6px;
            border: 1px solid #d0d0d0;
        """)

        title_size_layout = QVBoxLayout()
        title_size_layout.setContentsMargins(0, 0, 0, 0)
        title_size_layout.setSpacing(4)

        self.title = QLabel("Title: -")
        self.title.setObjectName("TaskTitle")
        self.title.setWordWrap(True)
        self.title.setMaximumHeight(44)
        self.title.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)

        self.size = QLabel("Estimated size: -")
        self.size.setObjectName("InfoSubtle")

        title_size_layout.addWidget(self.title)
        title_size_layout.addWidget(self.size)
        self.title_label = self.title
        self.size_label = self.size

        row2_layout = QHBoxLayout()
        row2_layout.setContentsMargins(0, 0, 0, 0)
        row2_layout.setSpacing(12)

        self.show_thumb_toggle = QCheckBox("Show thumbnail")
        self.show_thumb_cb = self.show_thumb_toggle
        self.thumb_label = self.thumbnail
        self.home_page.thumb_label = self.thumbnail
        page.show_thumb_toggle = self.show_thumb_toggle
        
        self.show_thumb_toggle.setChecked(self.settings.value("show_thumbnails", True, type=bool))
        self.thumbnail.setVisible(self.settings.value("show_thumbnails", True, type=bool))
        self.show_thumb_toggle.toggled.connect(self._on_show_thumb_changed)

        self.reset_btn = QPushButton("Reset")
        self.reset_btn.setObjectName("PasteButton")
        self.reset_btn.setSizePolicy(QSizePolicy.Minimum, QSizePolicy.Fixed)
        self.reset_btn.setMinimumWidth(0)
        self.reset_btn.adjustSize()
        self.reset_btn.clicked.connect(self.clear_homepage_ui)

        row2_layout.addWidget(self.show_thumb_toggle)
        row2_layout.addStretch()
        row2_layout.addWidget(self.reset_btn)

        row1_layout.addWidget(self.thumbnail)
        row1_layout.addLayout(title_size_layout, 1)

        preview_layout.addLayout(row1_layout)
        preview_layout.addLayout(row2_layout)

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

        self.fetch_btn.clicked.connect(self._on_analyze_clicked)
        self.download_btn.clicked.connect(self.start_download)
        
        self.config_cells = [cell_quality, cell_format, cell_audio, self.subtitle_lang_cell]
        self._set_metadata_placeholder(True)
        self._clear_format_quality()
        self._set_config_enabled(False)

        QTimer.singleShot(0, self.load_defaults_from_prefs)


        return page


    def _build_library_page(self):
        page = QWidget()
        page.setObjectName("Page")
        layout = QVBoxLayout(page)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(8)

        # Header Title + Subtitle wrapped in PageHeader
        header = self._create_page_header("Downloads", "Manage your downloads")
        self.library_header_title = header.findChild(QLabel, "PageTitle")
        self.library_header_subtitle = header.findChild(QLabel, "PageSubtitle")
        layout.addWidget(header)

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
        self.library_empty_label = QLabel("")
        self.library_empty_label.setObjectName("PageSubtitle")
        self.library_empty_label.setAlignment(Qt.AlignCenter)
        self.library_empty_label.setStyleSheet("")
        self.library_empty_label.setVisible(False)
        self.library_empty_label.setFixedHeight(0)
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
            lambda v: QSettings().setValue("default_quality", v))
        self.default_format_combo.currentTextChanged.connect(
            lambda v: QSettings().setValue("default_format", v))
        self.default_audio_combo.currentTextChanged.connect(
            lambda v: QSettings().setValue("default_audio", v))

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

        icon_path = app_config.get_icon_path()
        if icon_path and os.path.exists(icon_path):
            logo_label = QLabel()
            logo_pix = QPixmap(icon_path)
            if not logo_pix.isNull():
                logo_label.setPixmap(logo_pix.scaled(56, 56, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation))
                logo_label.setFixedSize(56, 56)
                card_layout.addWidget(logo_label)

        title = QLabel("YT Downloader Pro")
        title.setObjectName("SettingLabel")
        card_layout.addWidget(title)
        
        card_layout.addWidget(QLabel(f"Version: {self._version_text()}"))
        card_layout.addWidget(QLabel("Created by: Tahsan Ahmmed"))
        card_layout.addWidget(QLabel("A modern downloader built for speed and clarity."))
        card_layout.addWidget(QLabel("License: Custom License — Personal use only. See LICENSE file."))
        
        repo_link = QLabel('<a href="https://github.com/tahsanahmmed25/YTDownloaderPro" style="color: inherit; text-decoration: none;">github.com/tahsanahmmed25/YTDownloaderPro</a>')
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
        from PySide6.QtCore import QSettings
        s = QSettings()
        quality = s.value("default_quality", "1080p")
        fmt     = s.value("default_format",  "MP4")
        audio   = s.value("default_audio",   "MP3")
        
        # Ensure combos have items so findText can succeed
        if self.quality_combo.count() == 0:
            self.quality_combo.addItems(["Auto (Best)", "720p", "1080p", "2K", "4K"])
        if self.format_combo.count() == 0:
            self.format_combo.addItems(["Auto", "MP4", "MKV", "WEBM"])
        if self.audio_combo.count() == 0:
            self.audio_combo.addItems(["Best", "AAC", "MP3", "Opus", "FLAC", "Vorbis"])
        if self.subs_lang.count() == 0:
            self.subs_lang.addItem("None")

        for combo, value in [
            (self.quality_combo, quality),
            (self.format_combo, fmt),
            (self.audio_combo, audio),
        ]:
            idx = combo.findText(value)
            if idx < 0:
                # Case-insensitive lookup helper
                for i in range(combo.count()):
                    if combo.itemText(i).lower() == str(value).lower():
                        idx = i
                        break
            if idx >= 0:
                combo.blockSignals(True)
                combo.setCurrentIndex(idx)
                combo.blockSignals(False)
            else:
                combo.blockSignals(True)
                combo.addItem(value)
                combo.setCurrentText(value)
                combo.blockSignals(False)

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

