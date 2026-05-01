class AppError(Exception):
    def __init__(self, user_message, detail=None, code=None):
        super().__init__(user_message)
        self.user_message = user_message
        self.detail = detail
        self.code = code or "app_error"


class NetworkError(AppError):
    pass


class UserInputError(AppError):
    pass


class SystemError(AppError):
    pass


def humanize_error(raw_message, cookies_loaded=False):
    msg = (raw_message or "").strip()
    lowered = msg.lower()

    # ── Cookie / authentication failures ────────────────────────────────
    if "failed to decrypt cookie" in lowered or "cookie decryption failed" in lowered:
        return (
            "Failed to decrypt browser cookies.\n\n"
            "On Linux, Chrome/Edge cookies are locked by the system keyring. "
            "Options:\n"
            "• Use Firefox instead (most reliable on Linux)\n"
            "• Use 'Login to YouTube' (built-in browser) in the Cookies tab\n"
            "• Export a cookies.txt file manually via a browser extension"
        )
    if "secretstorage" in lowered or "jeepney" in lowered:
        return (
            "Browser cookie decryption libraries are missing on this system. "
            "Try Firefox, or use 'Login to YouTube' in the Cookies tab for a reliable alternative."
        )
    if "could not find" in lowered and "cookies database" in lowered:
        # e.g. "could not find opera cookies database in /home/.../.config/opera"
        # Extract browser name from message if possible
        import re as _re
        m = _re.search(r"could not find (\w+) cookies", lowered)
        browser = m.group(1).capitalize() if m else "That browser"
        return (
            f"{browser} is not installed or has no saved login.\n\n"
            "Options:\n"
            "• Switch to Firefox in the browser selector\n"
            "• Use 'Login to YouTube' in the Cookies tab\n"
            "• Or select a browser you are actually logged in to on YouTube"
        )
    if "dbus" in lowered or "secretservice" in lowered:
        return (
            "Could not access the system keyring to read browser cookies.\n\n"
            "Options:\n"
            "• Try Firefox (does not need the keyring)\n"
            "• Use 'Login to YouTube' in the Cookies tab\n"
            "• Export cookies.txt manually and load it via 'Set Cookies File'"
        )

    # ── yt-dlp setup ────────────────────────────────────────────────────
    if "yt-dlp is still setting up" in lowered or "still setting up" in lowered:
        return "yt-dlp is still setting up. Please wait a moment and try again."
    if "no module named" in lowered:
        return "A required component is missing. Please reinstall the app."
    if "no supported javascript runtime" in lowered or "js-runtimes" in lowered:
        # yt-dlp warning about missing deno/node — app falls back to ios client automatically
        return (
            "yt-dlp could not find a JavaScript runtime (deno/node). "
            "The app is automatically retrying with a compatible method — please wait."
        )

    # ── No downloadable formats ─────────────────────────────────────────
    if "no video formats" in lowered or "no formats available" in lowered:
        if not cookies_loaded:
            return (
                "No downloadable formats were found for this video.\n\n"
                "This can happen if the video is:\n"
                "\u2022 Private or geo-blocked in your region\n"
                "\u2022 Age-restricted (needs sign-in) \u2014 go to Cookies tab and connect your browser\n"
                "\u2022 A YouTube Short or live stream (try a different URL format)\n"
                "\u2022 Temporarily unavailable on YouTube's end"
            )
        return (
            "No downloadable formats were found. The video may be geo-blocked, private, "
            "or your login session may have expired. Try reconnecting in the Cookies tab."
        )

    # ── Format / quality ─────────────────────────────────────────────────
    if "requested format is not available" in lowered:
        if not cookies_loaded:
            return (
                "This video requires sign-in (age-restricted or members-only).\n\n"
                "Go to Preferences → Cookies and choose one of:\n"
                "• Connect Browser (select Firefox for best results on Linux)\n"
                "• Login to YouTube (built-in browser — most reliable)\n"
                "• Set Cookies File (manual export)"
            )
        return (
            "That video format is not available at the selected quality. "
            "Try Auto quality, or your browser auth may have expired — "
            "reconnect in the Cookies tab."
        )

    # ── HTTP / network ────────────────────────────────────────────────────
    if "http error 403" in lowered or "forbidden" in lowered:
        hint = ""
        if not cookies_loaded:
            hint = " Try Restricted Mode and connect your browser in the Cookies tab."
        return "Access denied by YouTube." + hint
    if "http error 429" in lowered or "too many requests" in lowered:
        return (
            "YouTube is rate-limiting your requests (too many downloads too fast). "
            "Wait a few minutes and try again."
        )
    if "sign in" in lowered or "login" in lowered or "age-restricted" in lowered:
        if cookies_loaded:
            return (
                "This video requires sign-in. Your current browser auth may be expired "
                "or missing YouTube permissions. Reconnect in the Cookies tab and try again."
            )
        return (
            "This video requires sign-in.\n\n"
            "Go to Preferences → Cookies and use 'Login to YouTube' or 'Connect Browser'."
        )

    # ── FFmpeg ─────────────────────────────────────────────────────────────
    if "ffmpeg" in lowered and ("not installed" in lowered or "required" in lowered):
        return (
            "FFmpeg is required to merge video and audio. "
            "Install it from Options."
        )

    # ── Misc ────────────────────────────────────────────────────────────────
    if "file is empty" in lowered or "downloaded file is empty" in lowered:
        return "Download failed. Try again or switch format/quality."
    if "page needs to be reloaded" in lowered:
        hint = ""
        if not cookies_loaded:
            hint = " Try Restricted Mode and connect your browser."
        return "YouTube asked to reload this video page." + hint
    if "watch video on youtube" in lowered or "error code: 152" in lowered:
        hint = ""
        if not cookies_loaded:
            hint = " Try Restricted Mode and connect your browser."
        return "This video can't be played in downloader mode. Try another link." + hint
    if "video is unavailable" in lowered or "this video is unavailable" in lowered:
        return "This video is unavailable. Try another link."
    if "network" in lowered or "timed out" in lowered or "timeout" in lowered:
        return "Network error. Check your internet connection and try again."
    if "invalid url" in lowered or "unsupported url" in lowered:
        return "Please enter a valid YouTube link."
    if "extract_failed" in lowered:
        return "Failed to analyze this video. Try again, or switch to Restricted mode if needed."

    if msg:
        return msg
    return "Something went wrong. Please try again."
