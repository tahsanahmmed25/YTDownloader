import argparse
import importlib
import sys


RUNTIME_DEPENDENCIES = (
    ("PySide6", "PySide6"),
    ("requests", "requests"),
    ("browser-cookie3", "browser_cookie3"),
    ("yt-dlp", "yt_dlp"),
)


def _check_runtime_dependencies():
    missing = []
    for package_name, module_name in RUNTIME_DEPENDENCIES:
        try:
            importlib.import_module(module_name)
        except Exception as exc:
            missing.append((package_name, module_name, exc))
    return missing


def run_preflight():
    print(f"Using Python interpreter: {sys.executable}")
    print(f"Python version: {sys.version.split()[0]}")

    missing = _check_runtime_dependencies()
    if not missing:
        print("Runtime dependency preflight passed.")
        return 0

    print("Missing runtime dependencies in the selected interpreter:")
    for package_name, module_name, exc in missing:
        print(f"  - {package_name} ({module_name}): {exc}")

    print("Install them into this interpreter before building:")
    print(f'  "{sys.executable}" -m pip install -r requirements-dev.lock')
    return 1


def main(argv=None):
    parser = argparse.ArgumentParser(description="Release build helper checks.")
    parser.add_argument("command", choices=("preflight",))
    args = parser.parse_args(argv)

    if args.command == "preflight":
        return run_preflight()
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
