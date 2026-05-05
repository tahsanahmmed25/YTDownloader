# Security Policy

## Supported Versions

Only the latest tagged release is expected to receive security fixes.

## Reporting a Vulnerability

Open a private security advisory on GitHub if available, or contact the maintainer privately before publishing details. Include affected version, operating system, reproduction steps, and whether cookies, proxy credentials, update manifests, or downloaded binaries are involved.

## Security Design Notes

- Cookies never leave the local machine.
- Managed YouTube session cookies are stored in the OS keyring when available and materialized to a private file only because yt-dlp requires a cookies file path.
- Proxy passwords are stripped from QSettings and stored in keyring when available.
- Logs redact cookie values, proxy credentials, bearer tokens, and sensitive cookie-file arguments.
- In-app installer updates require HTTPS, trusted update hosts by default, platform asset matching, and a valid SHA256.
- Custom update URLs are disabled unless `YTDL_ALLOW_CUSTOM_UPDATE_URL=true` is set.
- Browser force-closing is intentional app behavior, but it must remain explicitly confirmed by the user.

## Known Security Gaps

- Release artifacts are not code-signed yet.
- Update manifests are checksum-gated but not cryptographically signed.
- Some FFmpeg mirror downloads still rely on HTTPS unless pinned SHA256 environment variables are configured.
- Direct dependencies are pinned, but a fully hash-locked transitive dependency workflow is still recommended.
