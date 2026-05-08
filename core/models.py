from dataclasses import dataclass, field
from datetime import UTC, datetime


TASK_STATE_QUEUED = "queued"
TASK_STATE_STARTING = "starting"
TASK_STATE_ACTIVE = "active"
TASK_STATE_CANCELLING = "cancelling"
TASK_STATE_PAUSED = "paused"
TASK_STATE_FINALIZING = "finalizing"
TASK_STATE_COMPLETED = "completed"
TASK_STATE_FAILED = "failed"

TASK_STATES = frozenset({
    TASK_STATE_QUEUED,
    TASK_STATE_STARTING,
    TASK_STATE_ACTIVE,
    TASK_STATE_CANCELLING,
    TASK_STATE_PAUSED,
    TASK_STATE_FINALIZING,
    TASK_STATE_COMPLETED,
    TASK_STATE_FAILED,
})

TERMINAL_TASK_STATES = frozenset({
    TASK_STATE_COMPLETED,
    TASK_STATE_FAILED,
})


def normalize_task_state(value, default=TASK_STATE_QUEUED):
    state = (value or "").strip().lower()
    return state if state in TASK_STATES else default


@dataclass(frozen=True)
class DownloadOptions:
    url: str
    quality: str = "Auto"
    container: str = "mp4"
    download_dir: str = ""
    download_playlist: bool = False
    subtitles: bool = False
    proxy: str = ""
    extra: dict = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data):
        data = data or {}
        known = {
            "url",
            "quality",
            "container",
            "download_dir",
            "download_playlist",
            "subtitles",
            "proxy",
        }
        return cls(
            url=data.get("url") or "",
            quality=data.get("quality") or "Auto",
            container=data.get("container") or "mp4",
            download_dir=data.get("download_dir") or "",
            download_playlist=bool(data.get("download_playlist", False)),
            subtitles=bool(data.get("subtitles", False)),
            proxy=data.get("proxy") or "",
            extra={k: v for k, v in data.items() if k not in known},
        )

    def as_dict(self):
        data = {
            "url": self.url,
            "quality": self.quality,
            "container": self.container,
            "download_dir": self.download_dir,
            "download_playlist": self.download_playlist,
            "subtitles": self.subtitles,
            "proxy": self.proxy,
        }
        data.update(self.extra)
        return data


@dataclass(frozen=True)
class DownloadTask:
    id: str
    title: str
    payload: dict
    state: str = TASK_STATE_QUEUED

    @classmethod
    def from_dict(cls, data):
        data = data or {}
        payload = data.get("payload") or {}
        options = DownloadOptions.from_dict(payload)
        return cls(
            id=data.get("id") or "",
            title=data.get("title") or options.url or "Queued download",
            payload=dict(payload),
            state=normalize_task_state(data.get("state")),
        )

    def as_dict(self):
        return {
            "id": self.id,
            "title": self.title,
            "payload": self.payload,
            "state": self.state,
        }


@dataclass(frozen=True)
class DownloadResult:
    title: str
    url: str
    filepath: str
    thumb_path: str = ""
    added_at: str = field(default_factory=lambda: datetime.now(UTC).isoformat())

    def as_dict(self):
        return {
            "title": self.title or "Unknown",
            "url": self.url or "",
            "filepath": self.filepath or "",
            "thumb_path": self.thumb_path or "",
            "added_at": self.added_at,
        }
