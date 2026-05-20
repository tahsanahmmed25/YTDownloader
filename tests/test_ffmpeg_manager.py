import ffmpeg_manager

def test_is_ffmpeg_latest_returns_true_for_system_version(monkeypatch):
    # Mock local version to be "system"
    monkeypatch.setattr(ffmpeg_manager, "_get_local_version", lambda: "system")
    
    # Verify that it returns True immediately without making network calls
    assert ffmpeg_manager.is_ffmpeg_latest() is True
