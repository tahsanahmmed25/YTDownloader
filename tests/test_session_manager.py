from ui.session_manager import get_auth_cookie_names_in_file, has_required_auth_cookies


def _write_cookie(path, domain, name, value="value"):
    with open(path, "a", encoding="utf-8") as f:
        f.write(f"{domain}\tTRUE\t/\tTRUE\t0\t{name}\t{value}\n")


def test_required_auth_cookies_need_youtube_and_google_domains(tmp_path):
    cookies = tmp_path / "cookies.txt"
    cookies.write_text("# Netscape HTTP Cookie File\n", encoding="utf-8")
    _write_cookie(cookies, ".youtube.com", "SID")
    _write_cookie(cookies, ".youtube.com", "SAPISID")

    assert not has_required_auth_cookies(str(cookies))

    _write_cookie(cookies, ".google.com", "__Secure-1PSID")

    assert has_required_auth_cookies(str(cookies))
    assert {"SID", "SAPISID", "__Secure-1PSID"} <= get_auth_cookie_names_in_file(str(cookies))
