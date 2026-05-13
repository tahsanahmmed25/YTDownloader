from ui.session_manager import get_auth_cookie_names_in_file, has_required_auth_cookies


def _write_cookie(path, domain, name, value="value"):
    with open(path, "a", encoding="utf-8") as f:
        f.write(f"{domain}\tTRUE\t/\tTRUE\t0\t{name}\t{value}\n")


def test_required_auth_cookies_need_youtube_and_google_domains(tmp_path):
    """YouTube-only sessions with strong tokens (SAPISID) are now accepted.
    Google-domain cookies are still preferred but no longer mandatory."""
    cookies = tmp_path / "cookies.txt"
    cookies.write_text("# Netscape HTTP Cookie File\n", encoding="utf-8")
    # Single weak YouTube cookie should NOT pass
    _write_cookie(cookies, ".youtube.com", "SID")
    assert not has_required_auth_cookies(str(cookies))

    # Two YouTube cookies including a strong one (SAPISID) should pass
    _write_cookie(cookies, ".youtube.com", "SAPISID")
    assert has_required_auth_cookies(str(cookies))

    # Adding Google cookies continues to work (strict mode)
    _write_cookie(cookies, ".google.com", "__Secure-1PSID")
    assert has_required_auth_cookies(str(cookies))
    assert {"SID", "SAPISID", "__Secure-1PSID"} <= get_auth_cookie_names_in_file(str(cookies))
