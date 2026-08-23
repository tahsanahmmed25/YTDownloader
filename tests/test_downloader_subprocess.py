import stat
import sys
import pytest

import downloader


def _write_fake_ytdlp(tmp_path, body):
    if sys.platform == "win32":
        py_script = tmp_path / "fake_ytdlp.py"
        py_script.write_text(body, encoding="utf-8")
        path = tmp_path / "yt-dlp.bat"
        path.write_text(f'@"{sys.executable}" "{py_script}" %*\n', encoding="utf-8")
        return path
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


def test_quality_attempts_order(monkeypatch):
    recorded_attempts = []
    
    def fake_download_with_exe(url, opts, **kwargs):
        recorded_attempts.append(opts.get("format"))
        raise RuntimeError("Requested format not available")

    monkeypatch.setattr(downloader, "_download_with_exe", fake_download_with_exe)
    monkeypatch.setattr(downloader, "_find_local_binary", lambda name: "/fake/bin")
    monkeypatch.setattr(downloader, "_client_fallbacks", lambda authenticated: ["android"])
    monkeypatch.setattr(downloader, "_cookiefile_path", lambda path, require_auth: "/fake/cookies.txt" if path else None)

    with pytest.raises(RuntimeError, match="Requested format not available"):
        downloader.download_video(
            url="https://www.youtube.com/watch?v=abc123",
            quality="1080p",
            progress_callback=lambda *a: None,
            cookiefile="/fake/cookies.txt",
            download_dir="/fake/downloads"
        )

    # Ensure 1080p-split is tried across all auth sets before falling back to 1080p-progressive
    assert len(recorded_attempts) >= 4
    # Attempt 1: 1080p-split (normal mode)
    assert "bestvideo[height<=1080]" in recorded_attempts[0]
    # Attempt 2: 1080p-split (restricted/cookies mode)
    assert "bestvideo[height<=1080]" in recorded_attempts[1]
    # Attempt 3: 1080p-progressive (normal mode)
    assert "best[height<=1080]" in recorded_attempts[2]
    # Attempt 4: 1080p-progressive (restricted/cookies mode)
    assert "best[height<=1080]" in recorded_attempts[3]

