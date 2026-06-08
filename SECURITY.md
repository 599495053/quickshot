# Security Policy

## Supported Versions

Only the latest published QuickShot release is actively verified for security and installer behavior.

| Version | Supported |
| --- | --- |
| 5.3.3 | Yes |
| Older releases | No |

## Installer Trust

Current QuickShot releases are unsigned because no code-signing certificate is configured. Windows may show a security warning for the installer.

Before installing, download from the official GitHub Release page and verify the SHA256 hash:

```powershell
Get-FileHash .\QuickShot-5.3.3-Setup.exe -Algorithm SHA256
```

Expected SHA256 for v5.3.3:

```text
738845DC1F9F086E3FDBFC0E70A5DEC9E9D8A12400937040464E998446196F8C
```

The release manifest is published next to the installer:

<https://github.com/599495053/quickshot/releases/latest>

## Reporting a Vulnerability

Please do not post sensitive vulnerability details, private screenshots, tokens, or personal data in a public issue.

Preferred reporting flow:

1. Use GitHub private vulnerability reporting if it is enabled for this repository.
2. If private reporting is unavailable, open a public issue with a minimal description and write that details can be shared privately.

Helpful information to include:

- QuickShot version.
- Windows version.
- Whether the issue affects the installer, screenshot capture, OCR, upload, history, or credential storage.
- Whether the issue requires local access or can be triggered remotely.
- A redacted proof of concept or reproduction outline.

Security fixes will be prioritized for the latest release branch.
