import os
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QPushButton, QHBoxLayout, QMessageBox, QLabel
)
from PySide6.QtCore import QUrl, Signal, Qt
from PySide6.QtNetwork import QNetworkCookie

from app_config import app_data_dir


YOUTUBE_DOMAINS = (".youtube.com", "youtube.com", ".google.com", "google.com", ".googleapis.com", ".ytimg.com")


class AuthBrowserDialog(QDialog):
    """Embedded web browser dialog for YouTube authentication.
    
    Opens a QtWebEngine window to the Google login page. The user logs in
    normally, then clicks Done. All YouTube/Google cookies are exported to
    embedded_cookies.txt in the app data directory and used by yt-dlp.
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

        try:
            from PySide6.QtWebEngineWidgets import QWebEngineView
            from PySide6.QtWebEngineCore import QWebEngineProfile, QWebEnginePage
        except ImportError:
            QMessageBox.critical(
                self, "Missing Component",
                "The embedded browser component (PySide6-WebEngine) is not installed.\n"
                "Please use 'Connect Browser' or 'Set Cookies File' instead."
            )
            self.reject()
            return

        self._cookies: dict = {}  # (domain, name) -> QNetworkCookie

        # --- Layout ---
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(8, 8, 8, 8)
        main_layout.setSpacing(6)

        info_label = QLabel(
            "Log in to your Google/YouTube account below. "
            "Once signed in, click <b>Done — Save Cookies</b> to authenticate YTDownloader."
        )
        info_label.setObjectName("MutedText")
        info_label.setWordWrap(True)
        main_layout.addWidget(info_label)

        # --- WebEngine ---
        # Use a persistent named profile so the user doesn't need to
        # re-login every single time (profile is re-used across restarts).
        profile_path = os.path.join(app_data_dir(), "embedded_browser_profile")
        os.makedirs(profile_path, exist_ok=True)

        self._profile = QWebEngineProfile("yt_auth_v1", self)
        self._profile.setPersistentStoragePath(profile_path)
        self._profile.setCachePath(os.path.join(profile_path, "cache"))

        # Spoof a real Chrome User-Agent to avoid Google's 'browser not secure' block.
        self._profile.setHttpUserAgent(
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/124.0.0.0 Safari/537.36"
        )

        self._store = self._profile.cookieStore()
        self._store.cookieAdded.connect(self._on_cookie_added)
        # Load all existing cookies from the profile
        self._store.loadAllCookies()

        self._page = QWebEnginePage(self._profile, self)
        self._browser = QWebEngineView(self)
        self._browser.setPage(self._page)
        self._browser.load(QUrl(
            "https://accounts.google.com/ServiceLogin?"
            "service=youtube&continue=https://www.youtube.com/"
        ))
        main_layout.addWidget(self._browser, 1)

        # --- Buttons ---
        btn_row = QHBoxLayout()
        self._cancel_btn = QPushButton("Cancel")
        self._cancel_btn.clicked.connect(self.reject)

        self._done_btn = QPushButton("Done — Save Cookies")
        self._done_btn.setDefault(True)
        self._done_btn.clicked.connect(self._save_cookies)

        btn_row.addWidget(self._cancel_btn)
        btn_row.addStretch()
        btn_row.addWidget(self._done_btn)
        main_layout.addLayout(btn_row)

    # ------------------------------------------------------------------
    def _on_cookie_added(self, cookie: QNetworkCookie):
        """Store every cookie keyed by (domain, name) so later ones win."""
        domain = cookie.domain()
        name = cookie.name().data().decode("utf-8", "replace")
        self._cookies[(domain, name)] = cookie

    # ------------------------------------------------------------------
    def _save_cookies(self):
        """Export captured YouTube/Google cookies to a Netscape cookies.txt file."""
        yt_cookies = {
            k: v for k, v in self._cookies.items()
            if any(k[0].endswith(d) for d in YOUTUBE_DOMAINS)
        }

        if not yt_cookies:
            QMessageBox.warning(
                self, "Not Logged In",
                "No YouTube/Google cookies were found. "
                "Please complete the Google sign-in before clicking Done."
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
                    f.write(f"{domain}\t{include_subdomains}\t{path_str}\t{secure}\t{expiration}\t{name}\t{value}\n")

            self.cookies_extracted.emit(out_path)
            self.accept()
        except Exception as exc:
            QMessageBox.critical(self, "Save Failed", f"Could not write cookies file:\n{exc}")
