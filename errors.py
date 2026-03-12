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

    if "no module named" in lowered:
        return "A required component is missing. Please reinstall the app."
    if "ffmpeg" in lowered and ("not installed" in lowered or "required" in lowered):
        return (
            "FFmpeg is required to merge video and audio. "
            "Install essentials from Options."
        )
    if "requested format is not available" in lowered:
        return "That format/quality isn't available. Try Auto or a different quality."
    if "http error 403" in lowered or "forbidden" in lowered:
        hint = ""
        if not cookies_loaded:
            hint = " Add cookies in the Cookies tab and try again."
        return "Access denied by YouTube." + hint
    if "sign in" in lowered or "login" in lowered or "age-restricted" in lowered:
        hint = ""
        if not cookies_loaded:
            hint = " Add cookies in the Cookies tab and try again."
        return "This video requires sign-in." + hint
    if "file is empty" in lowered or "downloaded file is empty" in lowered:
        return "Download failed. Try again or switch format/quality."
    if "video is unavailable" in lowered or "this video is unavailable" in lowered:
        return "This video is unavailable. Try another link."
    if "network" in lowered or "timed out" in lowered or "timeout" in lowered:
        return "Network error. Check your internet connection and try again."
    if "invalid url" in lowered or "unsupported url" in lowered:
        return "Please enter a valid YouTube link."

    if msg:
        return msg
    return "Something went wrong. Please try again."
