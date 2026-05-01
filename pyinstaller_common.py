import os
import sys

from PyInstaller.utils.hooks import collect_all

_IS_WINDOWS = sys.platform == "win32"


COMMON_HIDDEN_IMPORTS = [
    "getpass",
    "optparse",
    "xml",
    "xml.etree",
    "xml.etree.ElementTree",
    "html",
    "html.parser",
    "uuid",
    "fileinput",
    "lzma",
    "json",
    "subprocess",
    "ssl",
    "hashlib",
    "ctypes",
    # Windows-only — omitted on Linux builds
    *(["ctypes.wintypes"] if _IS_WINDOWS else []),
    "PySide6",
    "PySide6.QtCore",
    "PySide6.QtGui",
    "PySide6.QtWidgets",
    "PySide6.QtNetwork",
    "PySide6.QtSvg",
    "PySide6.QtWebChannel",
    "shiboken6",
    "urllib3",
    "urllib3.util",
    "urllib3.contrib",
    "urllib3.packages",
    "charset_normalizer",
    "certifi",
    "idna",
    "keyring",
    "keyring.backends",
    # Windows-only keyring backend — omitted on Linux builds
    *(["keyring.backends.Windows"] if _IS_WINDOWS else [
        "keyring.backends.SecretService",
        "keyring.backends.Gnome",
        "secretstorage",
        "secretstorage.collection",
        "secretstorage.exceptions",
        "secretstorage.item",
        "jeepney",
        "jeepney.bus_obj",
        "jeepney.io",
        "jeepney.io.blocking",
        "jeepney.routing",
        "jeepney.wrappers",
    ]),
    "keyring.backends.chainer",
    "keyring.credentials",
    "keyring.errors",
    "keyring.util",
    "keyring.util.platform_",
    "keyring.backends.fail",
    "zipfile",
    "zlib",
    "zipimport",
    "ytdlp_exe_manager",
    "ffmpeg_manager",
    "downloader",
    "workers",
    "history_manager",
    "queue_manager",
    "app_config",
    "errors",
    "logging_utils",
    "net_utils",
    "ui.main_window",
    "ui.pages",
    "ui.widgets",
    "ui.dialogs",
    "ui.auth_controller",
    "ui.session_manager",
    "ui_style",
]

COMMON_EXCLUDES = [
    "tkinter",
    "matplotlib",
    "numpy",
    "scipy",
    "PIL",
    "cv2",
    "test",
]


def _dedupe(items):
    seen = set()
    ordered = []
    for item in items:
        if item in seen:
            continue
        seen.add(item)
        ordered.append(item)
    return ordered


def make_spec_config(spec_dir, entry_script, pathex):
    yt_dlp_datas, yt_dlp_binaries, yt_dlp_hidden = collect_all("yt_dlp")
    bc3_datas, bc3_binaries, bc3_hidden = collect_all("browser_cookie3")

    normalized_pathex = []
    for path in pathex:
        normalized_pathex.append(path if os.path.isabs(path) else os.path.join(spec_dir, path))

    entry_path = entry_script
    if not os.path.isabs(entry_path):
        entry_path = os.path.join(spec_dir, entry_path)

    icon_dir = os.path.join(spec_dir, "icons")
    all_datas = yt_dlp_datas + bc3_datas + [(icon_dir, "icons")]
    all_binaries = yt_dlp_binaries + bc3_binaries
    all_hidden = _dedupe(list(yt_dlp_hidden) + list(bc3_hidden) + COMMON_HIDDEN_IMPORTS)

    return {
        "analysis": {
            "scripts": [entry_path],
            "pathex": normalized_pathex,
            "binaries": all_binaries,
            "datas": all_datas,
            "hiddenimports": all_hidden,
            "hookspath": [],
            "hooksconfig": {},
            "runtime_hooks": [],
            "excludes": COMMON_EXCLUDES,
            "noarchive": False,
            "optimize": 0,
        },
        "exe": {
            "exclude_binaries": True,
            "name": "YTDownloader",
            "debug": False,
            "bootloader_ignore_signals": False,
            "strip": False,
            "upx": False,
            "console": False,
            "disable_windowed_traceback": False,
            "argv_emulation": False,
            "target_arch": None,
            "codesign_identity": None,
            "entitlements_file": None,
            # Use .ico on Windows, .png on Linux
            "icon": os.path.join(icon_dir, "download.ico" if _IS_WINDOWS else "download.png"),
        },
        "collect": {
            "strip": False,
            "upx": False,
            "upx_exclude": [],
            "name": "YTDownloader",
        },
    }
