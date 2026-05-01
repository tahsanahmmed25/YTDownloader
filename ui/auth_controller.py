"""
ui/auth_controller.py — YouTube Login Flow Controller

Orchestrates the system-browser login flow:

  1. User clicks "Open YouTube Login" → open system browser to youtube.com login page
  2. User logs in in their normal browser (no embedded Chromium, no crashes)
  3. User clicks "I'm Logged In" → AuthController runs cookie extraction in a QThread
  4. On success, emits login_success(path); on failure, emits login_failed(error)

Design guarantees:
  - The Qt main/UI thread is NEVER blocked
  - All cookie I/O happens inside _ExtractionWorker (a QThread)
  - QTimer implements the login timeout — no threading.Timer or asyncio
  - Proper cleanup on cancel / timeout / success / failure
"""

import webbrowser
from PySide6.QtCore import QObject, QThread, Signal, QTimer

from ui.session_manager import save_cookies_from_browser

# URL the user is sent to in their system browser
_LOGIN_URL = (
    "https://accounts.google.com/ServiceLogin"
    "?service=youtube"
    "&continue=https://www.youtube.com/"
    "&hl=en"
)

# How long to wait before auto-cancelling (seconds)
_TIMEOUT_SECONDS = 300   # 5 minutes


# ---------------------------------------------------------------------------
class _ExtractionWorker(QThread):
    """Runs browser cookie extraction on a background thread."""

    success = Signal(str)   # path to cookies.txt
    failure = Signal(str)   # human-readable error

    def __init__(self, browser_name: str, parent=None):
        super().__init__(parent)
        self._browser_name = browser_name

    def run(self):
        try:
            path = save_cookies_from_browser(self._browser_name)
            self.success.emit(path)
        except Exception as exc:
            self.failure.emit(str(exc))


# ---------------------------------------------------------------------------
class AuthController(QObject):
    """
    Signals
    -------
    login_started()
        Emitted when the system browser has been opened.
    login_success(path: str)
        Emitted when cookies have been extracted and written to *path*.
    login_failed(error: str)
        Emitted when extraction failed or timed out.
    login_timeout()
        Emitted when the user did not confirm login within the timeout window.
    state_changed(state: str)
        Emitted on every state transition. *state* is one of:
        "idle", "waiting", "extracting", "done", "failed"
    """

    login_started  = Signal()
    login_success  = Signal(str)
    login_failed   = Signal(str)
    login_timeout  = Signal()
    state_changed  = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._worker: _ExtractionWorker | None = None
        self._timeout_timer = QTimer(self)
        self._timeout_timer.setSingleShot(True)
        self._timeout_timer.timeout.connect(self._on_timeout)
        self._state = "idle"

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    @property
    def state(self) -> str:
        return self._state

    def start_login(self, browser_name: str = "auto") -> None:
        """
        Step 1 — open the system browser to the Google/YouTube login page.

        :param browser_name: which browser to extract cookies from after the
            user confirms login. 'auto' tries all installed browsers.
        """
        if self._state not in ("idle", "done", "failed"):
            return   # already in progress

        self._browser_name = browser_name
        self._set_state("waiting")

        try:
            webbrowser.open(_LOGIN_URL, new=2, autoraise=True)
        except Exception as exc:
            self._set_state("failed")
            self.login_failed.emit(
                f"Could not open your system browser: {exc}\n"
                "Please open youtube.com manually and log in."
            )
            return

        self.login_started.emit()
        self._timeout_timer.start(_TIMEOUT_SECONDS * 1000)

    def confirm_logged_in(self) -> None:
        """
        Step 2 — user has confirmed they logged in; extract cookies now.
        Called from the UI when the user clicks "I'm Logged In ✓".
        """
        if self._state != "waiting":
            return

        self._timeout_timer.stop()
        self._set_state("extracting")
        self._start_worker()

    def cancel(self) -> None:
        """Cancel any in-progress login or extraction."""
        self._timeout_timer.stop()
        if self._worker and self._worker.isRunning():
            self._worker.quit()
            self._worker.wait(3000)
        self._worker = None
        self._set_state("idle")

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _set_state(self, state: str) -> None:
        self._state = state
        self.state_changed.emit(state)

    def _start_worker(self) -> None:
        self._worker = _ExtractionWorker(self._browser_name, parent=self)
        self._worker.success.connect(self._on_extraction_success)
        self._worker.failure.connect(self._on_extraction_failure)
        self._worker.start()

    def _on_extraction_success(self, path: str) -> None:
        self._set_state("done")
        self.login_success.emit(path)
        self._worker = None

    def _on_extraction_failure(self, error: str) -> None:
        self._set_state("failed")
        self.login_failed.emit(error)
        self._worker = None

    def _on_timeout(self) -> None:
        if self._state == "waiting":
            self.cancel()
            self._set_state("failed")
            self.login_timeout.emit()
            self.login_failed.emit(
                "Login timed out. Please try again — click 'Open YouTube Login', "
                "log in to YouTube in your browser, then click 'I'm Logged In ✓' "
                "within 5 minutes."
            )
