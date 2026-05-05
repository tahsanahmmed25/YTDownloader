import importlib


def test_non_ui_modules_import_without_network():
    for name in (
        "app_config",
        "core.models",
        "core.security",
        "auth.session_store",
        "updates.manager",
        "storage.db",
        "history_manager",
        "queue_manager",
        "downloader",
        "ffmpeg_manager",
        "ytdlp_exe_manager",
    ):
        importlib.import_module(name)
