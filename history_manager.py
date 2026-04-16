import json
import os
import hashlib
import sqlite3
from datetime import datetime, UTC

from logging_utils import get_logger

_log = get_logger()

FILE = "history.json"
DB_FILE = "history.db"


def _use_sqlite():
    flag = os.environ.get("YTDL_USE_SQLITE", "").strip().lower()
    if flag in ("1", "true", "yes"):
        return True
    return os.path.exists(DB_FILE)


def _ensure_db():
    conn = sqlite3.connect(DB_FILE)
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS history (
            id TEXT PRIMARY KEY,
            title TEXT,
            url TEXT,
            filepath TEXT,
            thumb_path TEXT,
            added_at TEXT
        )
        """
    )
    conn.execute("CREATE INDEX IF NOT EXISTS idx_history_added_at ON history(added_at DESC)")
    conn.commit()
    return conn


def _migrate_json_if_needed(conn):
    try:
        cur = conn.execute("SELECT COUNT(*) FROM history")
        count = cur.fetchone()[0]
    except Exception:
        count = 0
    if count or not os.path.exists(FILE):
        return
    try:
        with open(FILE, "r", encoding="utf-8") as f:
            raw = json.load(f)
    except Exception:
        return
    if not isinstance(raw, list):
        return
    for item in raw:
        normalized = _normalize_item(item)
        conn.execute(
            "INSERT OR IGNORE INTO history (id, title, url, filepath, thumb_path, added_at) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (
                normalized["id"],
                normalized["title"],
                normalized["url"],
                normalized["filepath"],
                normalized["thumb_path"],
                normalized["added_at"]
            )
        )
    conn.commit()


def _hash_id(text):
    return hashlib.md5(text.encode("utf-8", errors="ignore")).hexdigest()


def _normalize_item(item):
    if isinstance(item, str):
        item = {
            "title": item,
            "url": item
        }
    if not isinstance(item, dict):
        item = {"title": "Unknown", "url": ""}

    title = item.get("title") or "Unknown"
    url = item.get("url") or ""
    filepath = item.get("filepath") or ""
    thumb_path = item.get("thumb_path") or ""
    raw_added_at = item.get("added_at")
    added_at = raw_added_at or ""

    item_id = item.get("id")
    if not item_id:
        seed = f"{url}|{filepath}|{title}|{added_at}"
        item_id = _hash_id(seed)
    if not raw_added_at:
        added_at = datetime.now(UTC).isoformat()

    return {
        "id": item_id,
        "title": title,
        "url": url,
        "filepath": filepath,
        "thumb_path": thumb_path,
        "added_at": added_at
    }


def _load_raw():
    if os.path.exists(FILE):
        try:
            with open(FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as exc:
            _log.warning("Failed to load history: %s", exc)
            return []
    return []


def load_history():
    if _use_sqlite():
        conn = None
        try:
            conn = _ensure_db()
            _migrate_json_if_needed(conn)
            cur = conn.execute(
                "SELECT id, title, url, filepath, thumb_path, added_at "
                "FROM history ORDER BY added_at DESC"
            )
            rows = cur.fetchall()
            return [
                {
                    "id": r[0],
                    "title": r[1],
                    "url": r[2],
                    "filepath": r[3],
                    "thumb_path": r[4],
                    "added_at": r[5]
                }
                for r in rows
            ]
        except Exception as exc:
            _log.warning("Failed to load history (sqlite): %s", exc)
            return []
        finally:
            if conn:
                conn.close()
    raw = _load_raw()
    data = []
    if isinstance(raw, list):
        for item in raw:
            data.append(_normalize_item(item))
    return data


def save_history(item):
    normalized = _normalize_item(item)
    if _use_sqlite():
        conn = None
        try:
            conn = _ensure_db()
            _migrate_json_if_needed(conn)
            conn.execute(
                "INSERT OR IGNORE INTO history (id, title, url, filepath, thumb_path, added_at) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (
                    normalized["id"],
                    normalized["title"],
                    normalized["url"],
                    normalized["filepath"],
                    normalized["thumb_path"],
                    normalized["added_at"]
                )
            )
            conn.commit()
            return
        except Exception as exc:
            _log.warning("Failed to save history (sqlite): %s", exc)
            return
        finally:
            if conn:
                conn.close()

    data = load_history()
    if any(x.get("id") == normalized["id"] for x in data):
        return
    data.insert(0, normalized)
    try:
        with open(FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=4)
    except Exception as exc:
        _log.warning("Failed to save history: %s", exc)


def remove_history(item_id):
    if _use_sqlite():
        conn = None
        try:
            conn = _ensure_db()
            conn.execute("DELETE FROM history WHERE id = ?", (item_id,))
            conn.commit()
            return
        except Exception as exc:
            _log.warning("Failed to remove history (sqlite): %s", exc)
            return
        finally:
            if conn:
                conn.close()
    data = load_history()
    data = [x for x in data if x.get("id") != item_id]
    try:
        with open(FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=4)
    except Exception as exc:
        _log.warning("Failed to remove history: %s", exc)


def clear_history():
    if _use_sqlite():
        conn = None
        try:
            conn = _ensure_db()
            conn.execute("DELETE FROM history")
            conn.commit()
            return
        except Exception as exc:
            _log.warning("Failed to clear history (sqlite): %s", exc)
            return
        finally:
            if conn:
                conn.close()
    try:
        with open(FILE, "w", encoding="utf-8") as f:
            json.dump([], f, indent=4)
    except Exception as exc:
        _log.warning("Failed to clear history: %s", exc)
