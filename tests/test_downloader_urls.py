from downloader import _build_format_candidates, is_valid_youtube_url, normalize_youtube_url


def test_youtube_url_validation_accepts_supported_forms():
    assert is_valid_youtube_url("https://www.youtube.com/watch?v=dQw4w9WgXcQ")
    assert is_valid_youtube_url("https://youtu.be/dQw4w9WgXcQ")
    assert is_valid_youtube_url("https://youtube.com/shorts/dQw4w9WgXcQ")
    assert is_valid_youtube_url("https://music.youtube.com/watch?v=dQw4w9WgXcQ")


def test_youtube_url_validation_rejects_non_youtube_hosts():
    assert not is_valid_youtube_url("https://evil.example/watch?v=dQw4w9WgXcQ")
    assert not is_valid_youtube_url("file:///tmp/video")
    assert not is_valid_youtube_url("https://youtube.com/watch")


def test_normalize_youtube_url_strips_tracking_query_but_keeps_playlist_when_requested():
    assert normalize_youtube_url("https://youtu.be/dQw4w9WgXcQ?si=tracking") == (
        "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
    )
    assert normalize_youtube_url(
        "https://www.youtube.com/watch?v=dQw4w9WgXcQ&list=PL123&feature=share",
        keep_playlist=True,
    ) == "https://www.youtube.com/watch?v=dQw4w9WgXcQ&list=PL123"


def test_build_format_candidates_prefers_container_specific_formats():
    candidates = _build_format_candidates("1080p", "mp4")

    assert candidates[0] == ("bestvideo*[ext=mp4][height<=1080]+bestaudio[ext=m4a]", "mp4")
    assert ("best[ext=mp4][height<=1080]", None) in candidates
