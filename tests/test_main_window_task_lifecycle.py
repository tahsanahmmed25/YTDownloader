import os
import importlib.util
from types import MethodType

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
_pyside_spec = importlib.util.find_spec("PySide6")
if _pyside_spec and _pyside_spec.origin:
    _plugin_path = os.path.join(os.path.dirname(_pyside_spec.origin), "Qt", "plugins", "platforms")
    if os.path.isdir(_plugin_path):
        os.environ.setdefault("QT_QPA_PLATFORM_PLUGIN_PATH", _plugin_path)

import pytest
from PySide6.QtCore import QTimer
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import QApplication, QCheckBox, QLabel, QLineEdit, QProgressBar, QPushButton

import ui.main_window as main_window
from core.models import TASK_STATE_CANCELLING, TASK_STATE_QUEUED


class WindowHarness:
    pass


@pytest.fixture(scope="session")
def qapp():
    app = QApplication.instance() or QApplication([])
    return app


class DummyThread:
    def __init__(self, running=True, wait_result=True):
        self.running = running
        self.wait_result = wait_result
        self.quit_called = False
        self.terminate_called = False

    def isRunning(self):
        return self.running

    def quit(self):
        self.quit_called = True

    def terminate(self):
        self.terminate_called = True
        self.running = False

    def wait(self, _timeout=None):
        if self.wait_result:
            self.running = False
            return True
        return False

    def deleteLater(self):
        pass


class DummyWorker:
    def __init__(self):
        self.cancel_count = 0

    def request_cancel(self):
        self.cancel_count += 1


class FakeEvent:
    def __init__(self):
        self.accepted = False
        self.ignored = False

    def accept(self):
        self.accepted = True

    def ignore(self):
        self.ignored = True


class FakeSettings:
    def __init__(self):
        self.values = {}

    def setValue(self, key, value):
        self.values[key] = value


def _make_item():
    return {
        "frame": QLabel("row"),
        "status": QLabel(""),
        "pause_btn": QPushButton("Pause"),
        "cancel_btn": QPushButton("Cancel"),
        "progress": QProgressBar(),
        "size": QLabel(""),
        "speed": QLabel(""),
        "status_icon": QLabel(""),
    }


def _make_window(monkeypatch):
    monkeypatch.setattr(main_window.queue_manager, "clear_queue", lambda: None)
    monkeypatch.setattr(main_window.queue_manager, "save_queue", lambda _tasks: None)

    window = WindowHarness()
    for name in (
        "_thread_is_running",
        "_has_running_download_threads",
        "_is_cancel_cleanup_blocking",
        "_release_cancel_gate_if_safe",
        "_request_cancel_all_downloads",
        "_clear_task_activity",
        "_clear_non_active_downloads",
        "_reset_download_ui",
        "_sync_download_button_text",
        "_start_next_downloads",
        "_on_task_cancel_clicked",
        "reset_ui",
        "closeEvent",
        "_on_update_error",
        "update_progress",
        "_touch_task_activity",
    ):

        setattr(window, name, MethodType(getattr(main_window.Downloader, name), window))
    window._ui_generation = 0
    window._active_tasks = {}
    window._pending_tasks = []
    window._paused_tasks = {}
    window._download_threads = {}
    window._download_workers = {}
    window._playlist_sessions = {}
    window._task_last_activity = {}
    window._cancel_cleanup_pending = False
    window._reset_requested = False
    window._CANCEL_GRACE_MS = getattr(main_window.Downloader, "_CANCEL_GRACE_MS", 7000)
    window._cancel_grace_timer = QTimer()
    window._download_reset_timer = QTimer()
    window._task_watchdog = QTimer()
    window._library_nav_pulse_timer = QTimer()
    window._fetch_thread = None
    window._fetch_worker = None
    window._update_thread = None
    window._update_worker = None
    window._update_download_thread = None
    window._update_download_worker = None
    window._tray = None
    window._force_quit = True
    window._info_ready = False
    window._active_url = ""
    window._active_is_playlist = False
    window._estimated_size_mb = None
    window._last_downloaded_bytes = None
    window._last_total_bytes = None
    window._last_progress_value = 0
    window._download_item_pool = []
    window.max_concurrent_downloads = 2
    window.download_dir = os.getcwd()

    window.fetch_btn = QPushButton("Analyze")
    window.download_btn = QPushButton("Start Download")
    window.url_input = QLineEdit()
    window.title = QLabel("Title: -")
    window.size = QLabel("Estimated size: -")
    window.thumbnail = QLabel()
    window.progress = QProgressBar()
    window.subs_checkbox = QCheckBox()
    window.embed_subs_checkbox = QCheckBox()
    window.playlist_toggle = QCheckBox()
    window.nav_library_btn = QPushButton("Downloads")

    window._animate_button_text = lambda button, text: button.setText(text)
    window._set_config_enabled = lambda *_args, **_kwargs: None
    window._clear_format_quality = lambda *_args, **_kwargs: None
    window._apply_subtitle_options = lambda *_args, **_kwargs: None
    window._placeholder_pixmap = lambda _size: QPixmap(1, 1)
    window._show_toast = lambda *_args, **_kwargs: None
    window._show_error_dialog = lambda *_args, **_kwargs: None
    window._show_message_dialog = lambda *_args, **_kwargs: None
    window._show_downloads_panel = lambda *_args, **_kwargs: None
    window._expand_details = lambda *_args, **_kwargs: None
    window._collapse_details = lambda *_args, **_kwargs: None
    window._clear_downloads_list = lambda *_args, **_kwargs: None
    window._update_downloads_header = lambda *_args, **_kwargs: None
    window._update_library_nav_state = lambda *_args, **_kwargs: None
    window._update_global_progress = lambda *_args, **_kwargs: window._sync_download_button_text()
    window._persist_queue = lambda *_args, **_kwargs: None
    window._maybe_finalize_reset = lambda *_args, **_kwargs: None
    return window


def _add_active_task(window, task_id="task-1", running=True, wait_result=True):
    worker = DummyWorker()
    thread = DummyThread(running=running, wait_result=wait_result)
    task = {
        "id": task_id,
        "generation": window._ui_generation,
        "payload": {"url": "https://www.youtube.com/watch?v=abc123"},
        "title": "Fake download",
        "state": "active",
        "item": _make_item(),
    }
    window._active_tasks[task_id] = task
    window._download_workers[task_id] = worker
    window._download_threads[task_id] = thread
    return task, worker, thread


def test_reset_during_active_download_blocks_new_starts_until_cleanup(qapp, monkeypatch):
    window = _make_window(monkeypatch)
    _task, worker, thread = _add_active_task(window)

    window.reset_ui()

    assert worker.cancel_count == 1
    assert window._cancel_cleanup_pending is True

    started = []
    window._pending_tasks.append({"id": "next", "payload": {}, "state": TASK_STATE_QUEUED})
    window._start_task = lambda task: started.append(task)
    window._start_next_downloads()
    assert started == []

    thread.running = False
    window._release_cancel_gate_if_safe(start_pending=False)
    assert window._cancel_cleanup_pending is False


def test_reset_spam_is_idempotent_while_thread_is_still_running(qapp, monkeypatch):
    window = _make_window(monkeypatch)
    _task, worker, _thread = _add_active_task(window)

    for _ in range(3):
        window.reset_ui()

    assert worker.cancel_count == 3
    assert window._cancel_cleanup_pending is True


def test_cancel_then_new_download_waits_for_old_thread_cleanup(qapp, monkeypatch):
    window = _make_window(monkeypatch)
    task, worker, _thread = _add_active_task(window)

    window._on_task_cancel_clicked(task["id"])

    assert worker.cancel_count == 1
    assert task["state"] == TASK_STATE_CANCELLING

    started = []
    window._pending_tasks.append({"id": "next", "payload": {}, "state": TASK_STATE_QUEUED})
    window._start_task = lambda task: started.append(task)
    window._start_next_downloads()

    assert started == []


def test_app_close_requests_active_download_cancellation(qapp, monkeypatch):
    window = _make_window(monkeypatch)
    _task, worker, thread = _add_active_task(window, wait_result=False)
    event = FakeEvent()

    window.closeEvent(event)

    assert worker.cancel_count == 1
    assert thread.quit_called is True
    assert thread.terminate_called is True
    assert event.accepted is True
    assert event.ignored is False


def test_multiple_downloads_respect_concurrency_limit(qapp, monkeypatch):
    window = _make_window(monkeypatch)
    window.max_concurrent_downloads = 2
    window._pending_tasks = [
        {"id": "one", "payload": {}, "state": TASK_STATE_QUEUED},
        {"id": "two", "payload": {}, "state": TASK_STATE_QUEUED},
        {"id": "three", "payload": {}, "state": TASK_STATE_QUEUED},
    ]
    started = []

    def fake_start(task):
        started.append(task["id"])
        window._active_tasks[task["id"]] = task

    window._start_task = fake_start
    window._start_next_downloads()

    assert started == ["one", "two"]
    assert [task["id"] for task in window._pending_tasks] == ["three"]


def test_private_update_404_quietly_pauses_startup_checks(qapp, monkeypatch):
    window = _make_window(monkeypatch)
    window.settings = FakeSettings()
    window.update_manifest_url = "https://api.github.com/repos/private/repo/releases/latest"
    window.check_updates_on_startup = True
    window.update_url_404_disabled = False
    window.update_url_404_value = ""
    window._update_manual = False
    window.check_updates_cb = QCheckBox()
    messages = []
    toasts = []
    window._show_message_dialog = lambda *args, **kwargs: messages.append((args, kwargs))
    window._show_toast = lambda *args, **kwargs: toasts.append((args, kwargs))

    window._on_update_error("404 Client Error: Not Found")

    assert window.update_url_404_disabled is True
    assert window.check_updates_on_startup is False
    assert window.settings.values["update_url_404_disabled"] is True
    assert messages == []
    assert toasts == []


def test_update_progress_ranges(qapp, monkeypatch):
    window = _make_window(monkeypatch)
    task, worker, thread = _add_active_task(window)
    item = task["item"]
    prog_bar = item["progress"]

    # Initially range is 0-100
    assert prog_bar.maximum() == 100
    prog_bar.setValue(0)
    assert prog_bar.value() == 0

    # Progress start -> normal progress updates range to 0-100 and value to 25
    window.update_progress(task["id"], 25.0)
    assert prog_bar.maximum() == 100
    assert prog_bar.value() == 25
    assert window._progress_started.get(task["id"]) is True

    # Audio merge phase -> progress emits 0
    window.update_progress(task["id"], 0.0)
    assert prog_bar.maximum() == 0  # Indeterminate mode

    # Switch back to normal progress (e.g. download restarts or next item in playlist starts)
    window.update_progress(task["id"], 50.0)
    assert prog_bar.maximum() == 100
    assert prog_bar.value() == 50

