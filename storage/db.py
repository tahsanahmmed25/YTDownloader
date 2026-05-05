import os
import sqlite3
import threading

from app_config import app_data_dir
from core.security import ensure_private_dir, set_private_file_permissions


DB_FILE = os.path.join(app_data_dir(), "app_state.db")
_LOCK = threading.RLock()


def connect():
    ensure_private_dir(app_data_dir())
    conn = sqlite3.connect(DB_FILE, timeout=30, isolation_level=None)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=30000")
    conn.execute("PRAGMA foreign_keys=ON")
    set_private_file_permissions(DB_FILE)
    return conn


def lock():
    return _LOCK

