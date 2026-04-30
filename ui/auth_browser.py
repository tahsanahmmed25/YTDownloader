"""
ui/auth_browser.py — Embedded YouTube Login Browser

Opens a QWebEngineView dialog so users can log in to Google/YouTube directly
inside the app. The session cookies are exported to embedded_cookies.txt and
used by yt-dlp for age-restricted / members-only downloads.

Key design decisions:
 - WebEngine is imported lazily (inside __init__) so the module can be
   imported safely even if QtWebEngine is not available.
 - The entire dialog init is wrapped in try/except — if Chromium crashes
   (e.g. missing QtWebEngineProcess in AppImage), the user sees a clear
   actionable error instead of the whole app crashing.
 - Browser init is deferred via QTimer so the dialog window appears first,
   making it clear the app is still alive while Chromium starts up.
 - The persistent profile is stored in app_data_dir() so sessions survive
   between logins (user doesn't need to re-login every time).
"""

import os
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QPushButton, QHBoxLayout,
    QMessageBox, QLabel, QSizePolicy,
)
from PySide6.QtCore import QUrl, Signal, Qt, QTimer
from PySide6.QtNetwork import QNetworkCookie

from app_config import app_data_dir

# Domains whose cookies matter for YouTube authentication
_YOUTUBE_DOMAINS = (
    ".youtube.com", "youtube.com",
    ".google.com",  "google.com",
    ".googleapis.com", ".ytimg.com",
    ".ggpht.com", ".googlevideo.com",
)


class AuthBrowserDialog(QDialog):
    """Embedded browser dialog for YouTube / Google login.

    Emits ``cookies_extracted(path)`` when the user clicks Done and the
    cookies file has been written successfully.
    """
    cookies_extracted = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Log in to YouTube — YTDownloader")
        self.resize(960, 720)
        self.setWindowFlags(
            self.windowFlags()
            | Qt.WindowMaximizeButtonHint
            | Qt.WindowMinimizeButtonHint
        )

        self._cookies: dict = {}   # (domain, name) -> QNetworkCookie
        self._browser = None       # set after delayed init
        self._webengine_ok = False

        # --- Static layout built immediately (safe, no WebEngine yet) ---
        self._main_layout = QVBoxLayout(self)
        self._main_layout.setContentsMargins(8, 8, 8, 8)
        self._main_layout.setSpacing(6)

        self._info_label = QLabel(
            "Log in to your Google/YouTube account below. "
            "Once signed in, click <b>Done — Save Cookies</b> to authenticate YTDownloader."
        )
        self._info_label.setObjectName("MutedText")
        self._info_label.setWordWrap(True)
        self._main_layout.addWidget(self._info_label)

        # Placeholder shown while the browser is starting
        self._loading_label = QLabel("Starting built-in browser…")
        self._loading_label.setAlignment(Qt.AlignCenter)
        self._loading_label.setObjectName("MutedText")
        self._loading_label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self._main_layout.addWidget(self._loading_label, 1)

        # Buttons
        btn_row = QHBoxLayout()
        self._cancel_btn = QPushButton("Cancel")
        self._cancel_btn.clicked.connect(self.reject)

        self._done_btn = QPushButton("Done — Save Cookies")
        self._done_btn.setDefault(True)
        self._done_btn.setEnabled(False)   # enabled after browser loads
        self._done_btn.clicked.connect(self._save_cookies)

        btn_row.addWidget(self._cancel_btn)
        btn_row.addStretch()
        btn_row.addWidget(self._done_btn)
        self._main_layout.addLayout(btn_row)

        # Defer WebEngine init so the window is visible first
        QTimer.singleShot(200, self._init_webengine)

    # ------------------------------------------------------------------
    def _init_webengine(self):
        """Initialise QtWebEngine. Called 200ms after dialog is shown."""
        try:
            from PySide6.QtWebEngineWidgets import QWebEngineView
            from PySide6.QtWebEngineCore import QWebEngineProfile, QWebEnginePage
        except Exception as exc:
            self._show_webengine_unavailable(
                f"Could not load the built-in browser module:\n{exc}"
            )
            return

        try:
            # Persistent profile — user stays logged in across restarts
            profile_path = os.path.join(app_data_dir(), "embedded_browser_profile")
            os.makedirs(profile_path, exist_ok=True)

            self._profile = QWebEngineProfile("yt_auth_v1", self)
            self._profile.setPersistentStoragePath(profile_path)
            self._profile.setCachePath(os.path.join(profile_path, "cache"))

            # Spoof a desktop Chrome UA to avoid Google's "browser not secure" block
            self._profile.setHttpUserAgent(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0.0.0 Safari/537.36"
            )

            self._store = self._profile.cookieStore()
            self._store.cookieAdded.connect(self._on_cookie_added)
            self._store.loadAllCookies()   # restore saved session

            self._page = QWebEnginePage(self._profile, self)
            self._browser = QWebEngineView(self)
            self._browser.setPage(self._page)
            self._browser.loadFinished.connect(self._on_load_finished)
            self._browser.load(QUrl(
                "https://accounts.google.com/ServiceLogin?"
                "service=youtube&continue=https://www.youtube.com/"
            ))

            # Swap loading placeholder for the real browser widget
            self._main_layout.replaceWidget(self._loading_label, self._browser)
            self._loading_label.deleteLater()
            self._loading_label = None

            self._done_btn.setEnabled(True)
            self._webengine_ok = True

        except Exception as exc:
            self._show_webengine_unavailable(
                f"The built-in browser failed to start:\n{exc}"
            )

    # ------------------------------------------------------------------
    def _on_load_finished(self, ok: bool):
        """Enable Done button once the first page actually loads."""
        if ok and self._browser:
            self._done_btn.setEnabled(True)

    # ------------------------------------------------------------------
    def _on_cookie_added(self, cookie: QNetworkCookie):
        """Track every cookie, keyed by (domain, name) so later values win."""
        domain = cookie.domain()
        name = cookie.name().data().decode("utf-8", "replace")
        self._cookies[(domain, name)] = cookie

    # ------------------------------------------------------------------
    def _save_cookies(self):
        """Export captured YouTube/Google cookies to a Netscape cookies.txt."""
        if not self._webengine_ok:
            QMessageBox.warning(self, "Not Ready", "The built-in browser is not running.")
            return

        yt_cookies = {
            k: v for k, v in self._cookies.items()
            if any(k[0].endswith(d) for d in _YOUTUBE_DOMAINS)
        }

        if not yt_cookies:
            QMessageBox.warning(
                self, "Not Logged In",
                "No YouTube/Google cookies were found.\n\n"
                "Please complete the Google sign-in in the browser above before clicking Done.\n"
                "Make sure you see the YouTube homepage after logging in."
            )
            return

        out_path = os.path.join(app_data_dir(), "embedded_cookies.txt")
        try:
            with open(out_path, "w", encoding="utf-8") as f:
                f.write("# Netscape HTTP Cookie File\n")
                f.write("# Generated by YTDownloader Embedded Browser. Do not edit.\n\n")
                for (domain, name), cookie in yt_cookies.items():
                    include_subdomains = "TRUE" if domain.startswith(".") else "FALSE"
                    path_str = cookie.path() or "/"
                    secure = "TRUE" if cookie.isSecure() else "FALSE"
                    if cookie.isSessionCookie():
                        expiration = 0
                    else:
                        expiration = cookie.expirationDate().toSecsSinceEpoch()
                    value = cookie.value().data().decode("utf-8", "replace")
                    f.write(
                        f"{domain}\t{include_subdomains}\t{path_str}\t"
                        f"{secure}\t{expiration}\t{name}\t{value}\n"
                    )
            self.cookies_extracted.emit(out_path)
            self.accept()
        except Exception as exc:
            QMessageBox.critical(self, "Save Failed", f"Could not write cookies file:\n{exc}")

    # ------------------------------------------------------------------
    def _show_webengine_unavailable(self, detail: str):
        """Replace the loading placeholder with a clear fallback message."""
        msg = QLabel(
            "<b>The built-in browser could not start.</b><br><br>"
            "This can happen inside AppImage environments where the Chromium sandbox is restricted.<br><br>"
            "👉 <b>Use 'Set Cookies File' instead:</b><br>"
            "1. Install the <i>Get cookies.txt LOCALLY</i> extension in Chrome/Firefox.<br>"
            "2. Log in to YouTube in your regular browser.<br>"
            "3. Export cookies as <code>cookies.txt</code>.<br>"
            "4. In YTDownloader → Preferences → Cookies → click <b>Set Cookies File</b>.<br><br>"
            f"<small>Technical detail: {detail}</small>"
        )
        msg.setWordWrap(True)
        msg.setTextFormat(Qt.RichText)
        msg.setObjectName("MutedText")
        msg.setAlignment(Qt.AlignTop | Qt.AlignLeft)

        if self._loading_label:
            self._main_layout.replaceWidget(self._loading_label, msg)
            self._loading_label.deleteLater()
            self._loading_label = None
        else:
            self._main_layout.insertWidget(1, msg)

        self._done_btn.setEnabled(False)
        self._webengine_ok = False
