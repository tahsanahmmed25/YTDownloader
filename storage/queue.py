import json
import time

from core.models import DownloadTask
from logging_utils import get_logger
from storage.db import connect, lock


_log = get_logger()


def _ensure_schema(conn):
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS download_queue (
            id TEXT PRIMARY KEY,
            sort_order INTEGER NOT NULL,
            title TEXT NOT NULL,
            payload_json TEXT NOT NULL,
            state TEXT NOT NULL,
            updated_at REAL NOT NULL
        )
        """
    )
    conn.execute("CREATE INDEX IF NOT EXISTS idx_download_queue_sort ON download_queue(sort_order)")


def load_queue():
    with lock():
        with connect() as conn:
            _ensure_schema(conn)
            rows = conn.execute(
                "SELECT id, title, payload_json, state FROM download_queue ORDER BY sort_order ASC"
            ).fetchall()
            items = []
            for row in rows:
                try:
                    payload = json.loads(row["payload_json"])
                except Exception as exc:
                    _log.warning("Skipping corrupt queue payload for %s: %s", row["id"], exc)
                    continue
                items.append(DownloadTask(
                    id=row["id"],
                    title=row["title"],
                    payload=payload,
                    state=row["state"],
                ).as_dict())
            return items


def save_queue(items):
    items = items or []
    now = time.time()
    with lock():
        with connect() as conn:
            _ensure_schema(conn)
            conn.execute("BEGIN IMMEDIATE")
            try:
                conn.execute("DELETE FROM download_queue")
                for idx, item in enumerate(items):
                    if not isinstance(item, dict):
                        continue
                    task = DownloadTask.from_dict(item)
                    task_id = task.id
                    payload = task.payload
                    if not task_id or not isinstance(payload, dict):
                        continue
                    conn.execute(
                        "INSERT INTO download_queue (id, sort_order, title, payload_json, state, updated_at) VALUES (?, ?, ?, ?, ?, ?)",
                        (
                            task_id,
                            idx,
                            task.title or payload.get("url") or "Queued download",
                            json.dumps(payload, ensure_ascii=False, sort_keys=True),
                            task.state or "queued",
                            now,
                        ),
                    )
                conn.execute("COMMIT")
            except Exception:
                conn.execute("ROLLBACK")
                raise


def add_task(task):
    data = load_queue()
    data.append(task)
    save_queue(data)


def remove_task(task_id):
    data = [t for t in load_queue() if t.get("id") != task_id]
    save_queue(data)


def clear_queue():
    save_queue([])
