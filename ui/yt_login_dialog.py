"""
ui/yt_login_dialog.py — YouTube Login Dialog

A polished modal popup that guides the user through browser-based cookie auth.

Flow
----
1. User selects which browser to read cookies from (auto by default).
2. Clicks "Open Login Page" → system browser opens to Google/YouTube sign-in.
3. User signs in, then returns to this dialog.
4. Clicks "I'm Signed In" → background cookie extraction runs.
5. Success  → dialog accepts; caller stores cookie_path.
   Failure  → error shown inline with a Retry option.
"""

import webbrowser

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QComboBox, QFrame, QProgressBar,
    QSizePolicy, QListView,
)
from PySide6.QtCore import Qt, QThread, Signal, QTimer

# Google / YouTube login URL (service=youtube keeps us on the YouTube flow)
_LOGIN_URL = (
    "https://accounts.google.com/ServiceLogin"
    "?service=youtube"
    "&continue=https://www.youtube.com/"
    "&hl=en"
)

_BROWSER_OPTIONS = [
    ("Auto-detect installed browsers", "auto"),
    ("Chrome",   "chrome"),
    ("Firefox",  "firefox"),
    ("Edge",     "edge"),
    ("Brave",    "brave"),
    ("Opera",    "opera"),
    ("Chromium", "chromium"),
]


# ---------------------------------------------------------------------------
class _ExtractionWorker(QThread):
    """Background thread: extracts cookies from the chosen browser."""

    success = Signal(str)   # path to saved cookies file
    failure = Signal(str)   # user-friendly error message

    def __init__(self, browser_name: str, parent=None):
        super().__init__(parent)
        self._browser_name = browser_name

    def run(self):
        try:
            from ui.session_manager import save_cookies_from_browser
            path = save_cookies_from_browser(self._browser_name)
            self.success.emit(path)
        except Exception as exc:
            self.failure.emit(str(exc))


# ---------------------------------------------------------------------------
class YouTubeLoginDialog(QDialog):
    """
    Modal YouTube-login dialog.

    After the dialog is accepted, `cookie_path` contains the path to the
    validated Netscape cookies file ready for yt-dlp.
    """

    def __init__(
        self,
        dark_mode: bool = False,
        initial_browser: str = "auto",
        parent=None,
    ):
        super().__init__(parent)
        self.cookie_path: str = ""
        self._dark = dark_mode
        self._initial_browser = initial_browser
        self._worker: _ExtractionWorker | None = None
        self._state = "idle"   # idle | waiting | extracting | done | failed

        self.setWindowTitle("Connect YouTube Account")
        self.setModal(True)
        self.setMinimumWidth(500)
        self.setMaximumWidth(580)
        self.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Preferred)
        self.setAttribute(Qt.WA_DeleteOnClose, True)

        self._build_ui()
        self._apply_style()
        self._set_state("idle")

    # ── UI ─────────────────────────────────────────────────────────────────

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(32, 32, 32, 28)
        root.setSpacing(0)

        # Header
        icon_lbl = QLabel("🎬")
        icon_lbl.setAlignment(Qt.AlignCenter)
        f = icon_lbl.font(); f.setPointSize(38); icon_lbl.setFont(f)
        root.addWidget(icon_lbl)
        root.addSpacing(8)

        title = QLabel("Connect YouTube Account")
        title.setObjectName("YTLoginTitle")
        title.setAlignment(Qt.AlignCenter)
        root.addWidget(title)
        root.addSpacing(6)

        sub = QLabel(
            "Sign in to access age-restricted, members-only,\n"
            "and private YouTube videos."
        )
        sub.setObjectName("YTLoginSub")
        sub.setAlignment(Qt.AlignCenter)
        sub.setWordWrap(True)
        root.addWidget(sub)
        root.addSpacing(22)

        # Card
        card = QFrame()
        card.setObjectName("YTLoginCard")
        card_lay = QVBoxLayout(card)
        card_lay.setContentsMargins(22, 20, 22, 20)
        card_lay.setSpacing(14)

        # Browser selector
        br_row = QHBoxLayout()
        br_row.setSpacing(10)
        br_lbl = QLabel("Browser:")
        br_lbl.setObjectName("YTLoginFieldLabel")
        br_lbl.setFixedWidth(62)
        self._browser_combo = QComboBox()
        lv = QListView(); lv.setObjectName("ComboPopupView")
        self._browser_combo.setView(lv)
        for label, data in _BROWSER_OPTIONS:
            self._browser_combo.addItem(label, data)
        for i in range(self._browser_combo.count()):
            if self._browser_combo.itemData(i) == self._initial_browser:
                self._browser_combo.setCurrentIndex(i)
                break
        br_row.addWidget(br_lbl)
        br_row.addWidget(self._browser_combo, 1)
        card_lay.addLayout(br_row)

        # Step indicators
        steps = QFrame()
        steps.setObjectName("YTLoginSteps")
        sl = QVBoxLayout(steps)
        sl.setContentsMargins(14, 12, 14, 12)
        sl.setSpacing(7)
        self._step1 = QLabel("① Open the login page in your browser")
        self._step1.setObjectName("YTLoginStep")
        self._step2 = QLabel("② Sign in to your Google / YouTube account")
        self._step2.setObjectName("YTLoginStep")
        self._step3 = QLabel("③ Return here and click  \"I'm Signed In\"")
        self._step3.setObjectName("YTLoginStep")
        sl.addWidget(self._step1)
        sl.addWidget(self._step2)
        sl.addWidget(self._step3)
        card_lay.addWidget(steps)

        # Status message
        self._status_lbl = QLabel("")
        self._status_lbl.setObjectName("YTLoginStatus")
        self._status_lbl.setWordWrap(True)
        self._status_lbl.setAlignment(Qt.AlignCenter)
        self._status_lbl.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        self._status_lbl.setMinimumHeight(38)
        card_lay.addWidget(self._status_lbl)

        # Indeterminate spinner
        self._spinner = QProgressBar()
        self._spinner.setObjectName("YTLoginSpinner")
        self._spinner.setRange(0, 0)
        self._spinner.setTextVisible(False)
        self._spinner.setFixedHeight(4)
        self._spinner.setVisible(False)
        card_lay.addWidget(self._spinner)

        root.addWidget(card)
        root.addSpacing(20)

        # Buttons
        btn_row = QHBoxLayout()
        btn_row.setSpacing(10)

        self._cancel_btn = QPushButton("Cancel")
        self._cancel_btn.setObjectName("YTLoginCancelBtn")
        self._cancel_btn.clicked.connect(self._on_cancel)

        self._open_btn = QPushButton("🌐  Open Login Page")
        self._open_btn.setObjectName("YTLoginOpenBtn")
        self._open_btn.clicked.connect(self._on_open_login)

        self._confirm_btn = QPushButton("✓  I'm Signed In")
        self._confirm_btn.setObjectName("YTLoginConfirmBtn")
        self._confirm_btn.setEnabled(False)
        self._confirm_btn.clicked.connect(self._on_confirm)

        btn_row.addWidget(self._cancel_btn)
        btn_row.addStretch(1)
        btn_row.addWidget(self._open_btn)
        btn_row.addWidget(self._confirm_btn)
        root.addLayout(btn_row)

    # ── State machine ──────────────────────────────────────────────────────

    def _set_state(self, state: str, message: str = ""):
        self._state = state

        msgs = {
            "idle":       "",
            "waiting":    "Browser opened — sign in to YouTube, then come back and click \"I'm Signed In\".",
            "extracting": "Reading cookies from your browser… please wait.",
            "done":       "✅  Signed in! Your session is saved securely.",
            "failed":     message or "Login failed. Please try again.",
        }
        self._status_lbl.setText(msgs.get(state, ""))

        # Spinner
        self._spinner.setVisible(state == "extracting")

        # Button / combo enable
        self._open_btn.setEnabled(state not in ("extracting", "done"))
        self._confirm_btn.setEnabled(state == "waiting")
        self._browser_combo.setEnabled(state not in ("extracting", "done"))

        # Step styles
        self._refresh_steps(state)

        # Colour status label
        if state == "failed":
            self._status_lbl.setStyleSheet("color:#f43f5e;font-weight:600;")
        elif state == "done":
            self._status_lbl.setStyleSheet("color:#10b981;font-weight:600;")
        else:
            self._status_lbl.setStyleSheet("")

        if state == "done":
            QTimer.singleShot(1500, self.accept)

    def _refresh_steps(self, state: str):
        accent_color = "#d4d4d4" if self._dark else "#3a3a3a"
        active  = f"font-weight:700; color:{accent_color};"
        done_c  = "font-weight:500; color:#10b981;"
        pending = "color:#9aa7b4;"

        if state == "idle":
            s1, s2, s3 = active, pending, pending
        elif state == "waiting":
            s1, s2, s3 = done_c, active, active
        elif state in ("extracting", "done"):
            s1, s2, s3 = done_c, done_c, done_c
        else:  # failed — retry at step 3
            s1, s2, s3 = done_c, done_c, active

        self._step1.setStyleSheet(s1)
        self._step2.setStyleSheet(s2)
        self._step3.setStyleSheet(s3)

    # ── Handlers ───────────────────────────────────────────────────────────

    def _on_open_login(self):
        browser_id = self._browser_combo.currentData()
        opened = False

        if browser_id and browser_id != "auto":
            # Map generic names to command-line executables (native, flatpak, snap)
            import shutil
            import subprocess
            import time
            
            candidates = []
            if browser_id == "firefox":
                candidates = ["firefox", "firefox-esr", "flatpak run org.mozilla.firefox", "snap run firefox"]
            elif browser_id == "chrome":
                candidates = ["google-chrome", "chrome", "chromium", "flatpak run com.google.Chrome", "google-chrome-stable"]
            elif browser_id == "edge":
                candidates = ["microsoft-edge", "microsoft-edge-stable", "flatpak run com.microsoft.Edge"]
            elif browser_id == "brave":
                candidates = ["brave-browser", "brave", "flatpak run com.brave.Browser", "snap run brave"]
            elif browser_id == "opera":
                candidates = ["opera", "snap run opera", "flatpak run com.opera.Client"]
            elif browser_id == "chromium":
                candidates = ["chromium-browser", "chromium", "snap run chromium", "flatpak run org.chromium.Chromium"]

            for cmd_str in candidates:
                parts = cmd_str.split()
                # If it's a direct command check if it exists in PATH
                if len(parts) == 1 and not shutil.which(parts[0]):
                    continue
                # For flatpak/snap, check if the runner exists
                if len(parts) > 1 and not shutil.which(parts[0]):
                    continue
                
                try:
                    p = subprocess.Popen(parts + [_LOGIN_URL], start_new_session=True)
                    # Verify if the process terminates immediately with an error (e.g. flatpak EPERM sandbox error)
                    try:
                        ret = p.wait(timeout=0.5)
                        if ret != 0:
                            continue  # exited with error, try next candidate
                    except subprocess.TimeoutExpired:
                        # still running, assume successful launch
                        pass
                    opened = True
                    break
                except Exception:
                    continue

        if not opened:
            # Fallback to system default
            try:
                webbrowser.open(_LOGIN_URL, new=2, autoraise=True)
            except Exception:
                pass

        self._set_state("waiting")

    def _on_confirm(self):
        if self._state != "waiting":
            return
        browser = self._browser_combo.currentData() or "auto"
        self._set_state("extracting")
        self._worker = _ExtractionWorker(browser, parent=self)
        self._worker.success.connect(self._on_success)
        self._worker.failure.connect(self._on_failure)
        self._worker.start()

    def _on_cancel(self):
        if self._worker and self._worker.isRunning():
            self._worker.quit()
            self._worker.wait(2000)
        self.reject()

    def _on_success(self, path: str):
        self._worker = None
        # Validate — reject tracking-only files
        try:
            from ui.session_manager import has_required_auth_cookies
            if not has_required_auth_cookies(path):
                self._on_failure(
                    "Cookies were found in your browser, but no complete "
                    "YouTube/Google sign-in session was detected.\n\n"
                    "Please make sure you are fully signed in to YouTube "
                    "in your browser, then click \"I'm Signed In\" again."
                )
                return
        except Exception:
            pass
        self.cookie_path = path
        self._set_state("done")

    def _on_failure(self, error: str):
        self._worker = None
        try:
            from errors import humanize_error
            msg = humanize_error(error)
        except Exception:
            msg = error
        self._set_state("failed", msg)
        # Re-enable confirm so the user can retry without reopening the dialog
        self._confirm_btn.setEnabled(True)

    # ── Styling ────────────────────────────────────────────────────────────

    def _apply_style(self):
        from ui_style import DARK, LIGHT
        t = DARK if self._dark else LIGHT
        
        bg        = t["bg_window"]
        card_bg   = t["bg_surface"]
        border    = t["border"]
        text      = t["text_primary"]
        muted     = t["text_secondary"]
        text_tert = t["text_tertiary"]
        steps_bg  = t["bg_hover"]
        cancel_bg = t["bg_card"]
        cancel_br = t["border"]
        open_bg   = t["bg_hover"]
        open_br   = t["border_focus"]
        cb_bg     = t["bg_input"]
        cb_br     = t["border"]
        sp_bg     = t["bg_active"]
        accent    = t["accent"]
        accent_h  = t["accent_hover"]
        text_acc  = t["text_on_accent"]

        self.setStyleSheet(f"""
            QDialog {{ background:{bg}; }}

            QLabel#YTLoginTitle {{
                font-size:19px; font-weight:700; color:{text};
            }}
            QLabel#YTLoginSub {{
                font-size:13px; color:{muted};
            }}
            QFrame#YTLoginCard {{
                background:{card_bg};
                border:1px solid {border};
                border-radius:14px;
            }}
            QLabel#YTLoginFieldLabel {{
                color:{text}; font-weight:600;
            }}
            QFrame#YTLoginSteps {{
                background:{steps_bg};
                border:1px solid {border};
                border-radius:10px;
            }}
            QLabel#YTLoginStep {{
                color:{muted}; font-size:13px; padding:1px 0px;
            }}
            QLabel#YTLoginStatus {{
                font-size:13px; color:{muted}; min-height:38px;
            }}
            QProgressBar#YTLoginSpinner {{
                background:{sp_bg}; border:none;
                height:4px; padding:0px; border-radius:2px;
            }}
            QProgressBar#YTLoginSpinner::chunk {{
                background:{accent};
                border-radius:2px;
            }}
            QComboBox {{
                background:{cb_bg}; border:1px solid {cb_br};
                border-radius:8px; padding:5px 10px; color:{text};
            }}
            QPushButton#YTLoginCancelBtn {{
                background:{cancel_bg}; border:1px solid {cancel_br};
                border-radius:10px; padding:8px 18px;
                color:{text}; font-size:13px;
            }}
            QPushButton#YTLoginCancelBtn:hover {{
                background:{steps_bg};
                border:1px solid {accent};
            }}
            QPushButton#YTLoginOpenBtn {{
                background:{open_bg}; border:1px solid {open_br};
                border-radius:10px; padding:8px 20px;
                color:{accent}; font-size:13px; font-weight:700;
            }}
            QPushButton#YTLoginOpenBtn:hover {{
                background:{steps_bg};
            }}
            QPushButton#YTLoginOpenBtn:disabled {{ opacity:0.5; }}
            QPushButton#YTLoginConfirmBtn {{
                background:{accent};
                border:none; border-radius:10px; padding:8px 22px;
                color:{text_acc}; font-size:13px; font-weight:700;
            }}
            QPushButton#YTLoginConfirmBtn:hover:!disabled {{
                background:{accent_h};
            }}
            QPushButton#YTLoginConfirmBtn:disabled {{
                background:{steps_bg};
                color:{text_tert};
            }}
        """)
