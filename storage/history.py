import hashlib
import json
import os
from datetime import UTC, datetime

from app_config import app_data_dir
from logging_utils import get_logger
from storage.db import connect, lock


_log = get_logger()
LEGACY_FILE = "history.json"
LEGACY_DB_FILE = "history.db"
APPDATA_HISTORY_JSON = os.path.join(app_data_dir(), "history.json")


def _hash_id(text):
    return hashlib.sha256(text.encode("utf-8", errors="ignore")).hexdigest()


def normalize_item(item):
    if isinstance(item, str):
        item = {"title": item, "url": item}
    if not isinstance(item, dict):
        item = {"title": "Unknown", "url": ""}
    title = item.get("title") or "Unknown"
    url = item.get("url") or ""
    filepath = item.get("filepath") or ""
    thumb_path = item.get("thumb_path") or ""
    added_at = item.get("added_at") or datetime.now(UTC).isoformat()
    item_id = item.get("id") or _hash_id(f"{url}|{filepath}|{title}|{added_at}")
    return {
        "id": item_id,
        "title": title,
        "url": url,
        "filepath": filepath,
        "thumb_path": thumb_path,
        "added_at": added_at,
    }


def _ensure_schema(conn):
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS history (
            id TEXT PRIMARY KEY,
            title TEXT NOT NULL,
            url TEXT NOT NULL,
            filepath TEXT NOT NULL,
            thumb_path TEXT NOT NULL,
            added_at TEXT NOT NULL
        )
        """
    )
    conn.execute("CREATE INDEX IF NOT EXISTS idx_history_added_at ON history(added_at DESC)")
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS meta (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL
        )
        """
    )


def _is_migration_done(conn, key):
    try:
        row = conn.execute("SELECT value FROM meta WHERE key = ?", (key,)).fetchone()
        return row is not None and row[0] == "1"
    except Exception:
        return False


def _mark_migration_done(conn, key):
    try:
        conn.execute("INSERT OR REPLACE INTO meta (key, value) VALUES (?, ?)", (key, "1"))
    except Exception:
        pass


def _count(conn):
    return conn.execute("SELECT COUNT(*) FROM history").fetchone()[0]


def _migrate_json(conn):
    """One-time import from legacy JSON. Guarded by a meta flag so it never repeats."""
    if _is_migration_done(conn, "json_migration"):
        return
    source = APPDATA_HISTORY_JSON if os.path.exists(APPDATA_HISTORY_JSON) else LEGACY_FILE
    if not os.path.exists(source):
        _mark_migration_done(conn, "json_migration")
        return
    try:
        with open(source, "r", encoding="utf-8") as f:
            raw = json.load(f)
    except Exception as exc:
        _log.warning("Could not migrate history JSON: %s", exc)
        _mark_migration_done(conn, "json_migration")
        return
    if not isinstance(raw, list):
        _mark_migration_done(conn, "json_migration")
        return
    for item in raw:
        save_history(item, _conn=conn)
    _mark_migration_done(conn, "json_migration")
    _log.info("Migrated %d items from legacy JSON history.", len(raw))


def _migrate_legacy_sqlite(conn):
    """One-time import from legacy history.db. Guarded by a meta flag."""
    if _is_migration_done(conn, "sqlite_migration"):
        return
    if not os.path.exists(LEGACY_DB_FILE):
        _mark_migration_done(conn, "sqlite_migration")
        return
    import sqlite3
    legacy_conn = None
    try:
        legacy_conn = sqlite3.connect(LEGACY_DB_FILE)
        rows = legacy_conn.execute("SELECT id, title, url, filepath, thumb_path, added_at FROM history").fetchall()
        for row in rows:
            conn.execute(
                "INSERT OR IGNORE INTO history (id, title, url, filepath, thumb_path, added_at) VALUES (?, ?, ?, ?, ?, ?)",
                row,
            )
        _mark_migration_done(conn, "sqlite_migration")
        _log.info("Migrated %d items from legacy SQLite history.", len(rows))
    except Exception as exc:
        _log.warning("Could not migrate legacy SQLite history: %s", exc)
    finally:
        if legacy_conn:
            legacy_conn.close()


def initialize(conn):
    _ensure_schema(conn)
    _migrate_legacy_sqlite(conn)
    _migrate_json(conn)


def load_history():
    with lock():
        with connect() as conn:
            initialize(conn)
            rows = conn.execute(
                "SELECT id, title, url, filepath, thumb_path, added_at FROM history ORDER BY added_at DESC"
            ).fetchall()
            return [dict(row) for row in rows]


def save_history(item, _conn=None):
    normalized = normalize_item(item)
    conn = _conn
    own_conn = conn is None
    with lock():
        try:
            if own_conn:
                conn = connect()
                _ensure_schema(conn)
            conn.execute(
                "INSERT OR IGNORE INTO history (id, title, url, filepath, thumb_path, added_at) VALUES (?, ?, ?, ?, ?, ?)",
                (
                    normalized["id"],
                    normalized["title"],
                    normalized["url"],
                    normalized["filepath"],
                    normalized["thumb_path"],
                    normalized["added_at"],
                ),
            )
        finally:
            if own_conn and conn:
                conn.close()


def remove_history(item_id):
    with lock():
        with connect() as conn:
            _ensure_schema(conn)
            conn.execute("DELETE FROM history WHERE id = ?", (item_id,))


def clear_history():
    with lock():
        with connect() as conn:
            _ensure_schema(conn)
            conn.execute("DELETE FROM history")

