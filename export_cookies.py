import os
import browser_cookie3
from http.cookiejar import MozillaCookieJar


def try_export(getter, name):
    try:
        jar = getter(domain_name="youtube.com")
        if not jar or len(jar) == 0:
            return False, f"{name}: no cookies"
        out_path = os.path.join(os.getcwd(), "cookies.txt")
        out = MozillaCookieJar(out_path)
        for c in jar:
            out.set_cookie(c)
        out.save(ignore_discard=True, ignore_expires=True)
        return True, f"{name}: saved to {out_path}"
    except Exception as e:
        return False, f"{name}: {e}"


def main():
    chrome_user_data = os.path.join(
        os.getenv("LOCALAPPDATA") or os.path.expandvars(r"%LOCALAPPDATA%"),
        "Google",
        "Chrome",
        "User Data",
    )
    local_state = os.path.join(chrome_user_data, "Local State")
    chrome_profiles = ["Profile 1", "Profile 2", "Default"]

    for profile in chrome_profiles:
        cookie_file = os.path.join(chrome_user_data, profile, "Network", "Cookies")
        if os.path.exists(cookie_file) and os.path.exists(local_state):
            ok, msg = try_export(
                lambda domain_name="": browser_cookie3.chrome(
                    cookie_file=cookie_file,
                    key_file=local_state,
                    domain_name=domain_name,
                ),
                f"chrome:{profile}",
            )
            print(msg)
            if ok:
                return

    sources = ["chrome", "edge", "firefox"]
    getters = {
        "chrome": browser_cookie3.chrome,
        "edge": browser_cookie3.edge,
        "firefox": browser_cookie3.firefox,
    }

    for name in sources:
        ok, msg = try_export(getters[name], name)
        print(msg)
        if ok:
            return


if __name__ == "__main__":
    main()
