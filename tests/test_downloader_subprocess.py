import stat

import pytest

import downloader


def _write_fake_ytdlp(tmp_path, body):
    path = tmp_path / "yt-dlp"
    path.write_text("#!/usr/bin/env python3\n" + body, encoding="utf-8")
    path.chmod(path.stat().st_mode | stat.S_IXUSR)
    return path


def test_fake_ytdlp_progress_events_are_parsed(tmp_path, monkeypatch):
    fake = _write_fake_ytdlp(
        tmp_path,
        """
import sys
print("DL:10:100:1024:100:10%", flush=True)
print("DL:100:100:0:100:100%", flush=True)
print("YTRESULT:abc123\\tFake title\\thttps://www.youtube.com/watch?v=abc123\\t\\t/tmp/fake.mp4", flush=True)
""",
    )
    monkeypatch.setattr(downloader, "_find_local_binary", lambda name: str(fake))
    progress = []
    download_dir = tmp_path / "downloads"
    download_dir.mkdir()

    result = downloader._download_with_exe(
        "https://www.youtube.com/watch?v=abc123",
        {"outtmpl": str(download_dir / "%(title)s.%(ext)s"), "_download_dir": str(download_dir)},
        progress_callback=lambda *args: progress.append(args),
    )

    assert result[0]["title"] == "Fake title"
    assert result[0]["filepath"] == "/tmp/fake.mp4"
    assert progress
    assert progress[-1][0] == 100.0


def test_fake_ytdlp_error_raises_runtime_error(tmp_path, monkeypatch):
    fake = _write_fake_ytdlp(
        tmp_path,
        """
import sys
print("ERROR: broken fake download", flush=True)
raise SystemExit(1)
""",
    )
    monkeypatch.setattr(downloader, "_find_local_binary", lambda name: str(fake))
    download_dir = tmp_path / "downloads"
    download_dir.mkdir()

    with pytest.raises(RuntimeError, match="broken fake download"):
        downloader._download_with_exe(
            "https://www.youtube.com/watch?v=abc123",
            {"outtmpl": str(download_dir / "%(title)s.%(ext)s"), "_download_dir": str(download_dir)},
        )


def test_fake_ytdlp_hang_can_be_cancelled(tmp_path, monkeypatch):
    fake = _write_fake_ytdlp(
        tmp_path,
        """
import time
while True:
    time.sleep(1)
""",
    )
    monkeypatch.setattr(downloader, "_find_local_binary", lambda name: str(fake))
    download_dir = tmp_path / "downloads"
    download_dir.mkdir()

    with pytest.raises(downloader.DownloadCancelled):
        downloader._download_with_exe(
            "https://www.youtube.com/watch?v=abc123",
            {"outtmpl": str(download_dir / "%(title)s.%(ext)s"), "_download_dir": str(download_dir)},
            cancel_check=lambda: True,
        )
