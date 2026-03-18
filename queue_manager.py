import json
import os

from app_config import app_data_dir
from logging_utils import get_logger

_log = get_logger()
QUEUE_FILE = os.path.join(app_data_dir(), "queue.json")


def load_queue():
    if not os.path.exists(QUEUE_FILE):
        return []
    try:
        with open(QUEUE_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, list):
            return data
    except Exception as exc:
        _log.warning("Failed to load queue: %s", exc)
    return []


def save_queue(items):
    try:
        with open(QUEUE_FILE, "w", encoding="utf-8") as f:
            json.dump(items or [], f, indent=4)
    except Exception as exc:
        _log.warning("Failed to save queue: %s", exc)


def add_task(task):
    data = load_queue()
    data.append(task)
    save_queue(data)


def remove_task(task_id):
    data = load_queue()
    data = [t for t in data if t.get("id") != task_id]
    save_queue(data)


def clear_queue():
    save_queue([])
