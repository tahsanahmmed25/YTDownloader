import importlib


def test_history_storage_uses_sqlite_and_preserves_items(tmp_path):
    import storage.db as db
    import storage.history as history

    db.DB_FILE = str(tmp_path / "state.db")
    history.APPDATA_HISTORY_JSON = str(tmp_path / "missing-history.json")

    history.save_history({
        "title": "Example",
        "url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
        "filepath": str(tmp_path / "video.mp4"),
        "thumb_path": "",
    })

    rows = history.load_history()
    assert len(rows) == 1
    assert rows[0]["title"] == "Example"


def test_queue_storage_round_trips_payloads_transactionally(tmp_path):
    import storage.db as db
    import storage.queue as queue

    db.DB_FILE = str(tmp_path / "queue.db")

    queue.save_queue([
        {
            "id": "task-1",
            "title": "Queued",
            "payload": {"url": "https://youtu.be/dQw4w9WgXcQ", "quality": "720p"},
            "state": "queued",
        }
    ])

    rows = queue.load_queue()
    assert rows == [
        {
            "id": "task-1",
            "title": "Queued",
            "payload": {"quality": "720p", "url": "https://youtu.be/dQw4w9WgXcQ"},
            "state": "queued",
        }
    ]

    queue.clear_queue()
    assert queue.load_queue() == []


def test_storage_modules_import_cleanly():
    for name in ("storage.db", "storage.history", "storage.queue"):
        importlib.import_module(name)
