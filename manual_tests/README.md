# Manual Diagnostics

These scripts intentionally touch real YouTube URLs, local browsers, and local account/session state. They are not part of automated pytest runs.

Run them only when debugging a specific local environment:

```bash
python manual_tests/age_restricted_manual.py
python manual_tests/cookies_debug_manual.py
```

Do not paste cookies, account identifiers, or private video URLs into issue reports.
