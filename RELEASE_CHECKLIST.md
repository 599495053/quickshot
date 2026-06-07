# QuickShot Release Checklist

Version: 5.3.0
Last verified: 2026-06-08

## Quality Gates

- [x] `python -m pytest -q`
  - Result: `471 passed, 37 subtests passed`
- [x] `python -m pyflakes quickshot launcher.py build_config.py`
- [x] `python -m compileall -q quickshot launcher.py build_config.py`
- [x] `python -m pip check`
  - Result: `No broken requirements found.`

## Build

- [x] Version references synchronized:
  - Check: `powershell -ExecutionPolicy Bypass -File .\scripts\set-version.ps1 -Version 5.3.0 -CheckOnly`
  - Update command for a new release: `powershell -ExecutionPolicy Bypass -File .\scripts\set-version.ps1 -Version <new-version>`
- [x] Automated release build:
  - Command: `powershell -ExecutionPolicy Bypass -File .\scripts\release.ps1 -SkipInstall -Clean`
  - Manifest: `installer_output\QuickShot-5.3.0-release.txt`
- [x] Build executable:
  - Command: `powershell -ExecutionPolicy Bypass -File .\build.ps1 -SkipInstall -Clean`
  - Output: `dist\QuickShot.exe`
  - Size: `110809410` bytes
  - SHA256: `DA467775690F52C1035856C1B2AB678CE5CE9FEF6D3378E41E16CCAA7462D1D7`
- [x] Build installer:
  - Command: `& 'C:\Users\59949\AppData\Local\Programs\Inno Setup 6\ISCC.exe' QuickShot.iss`
  - Output: `installer_output\QuickShot-5.3.0-Setup.exe`
  - Size: `112000513` bytes
  - SHA256: `D5834B52DC1FEC2D354695500258210B9BE562FCE7D9FE8F7F136AC9B1D69A90`

## Installer Behavior

- [x] Inno Setup compile completes with no warnings.
- [x] Simplified Chinese installer language is available via `/LANG=chinesesimp`.
- [x] Default install does not create a desktop shortcut.
- [x] Default install does not create a Windows startup entry.
- [x] Uninstall display name is `QuickShot`.
- [x] Uninstall removes install directory, Start Menu entries, desktop shortcut if selected, startup registry value, and uninstall registry key.
- [x] `[UninstallRun]` uses `RunOnceId` so the `taskkill` cleanup runs once on a clean install.

## Runtime Smoke Tests

- [x] Automated packaged smoke test:
  - Command: `powershell -ExecutionPolicy Bypass -File .\scripts\release.ps1 -SkipBuild -SkipInstaller -SmokeTest`
- [x] Packaged app starts from `dist\QuickShot.exe`.
- [x] Installed app starts from the install directory.
- [x] Tray initializes successfully.
- [x] Capture imports prewarm successfully.
- [x] RapidOCR prewarms successfully.
- [x] Region hotkey `Ctrl+Shift+A` captures and writes image clipboard formats.
- [x] Window hotkey `Ctrl+Shift+W` captures and writes image clipboard formats.
- [x] Clipboard formats observed:
  - `CF_BITMAP`
  - `CF_DIB`
  - `CF_DIBV5`
  - `image/png`
- [x] Capture history writes new PNG files.
- [x] Debug log has no new `CRASH`, `Traceback`, `error`, or `failed` entries during the tested launch windows.

## Known Build Notes

- PyInstaller may report optional missing modules from third-party packages. Current relevant optional entries include `pycparser.lextab`, `pycparser.yacctab`, and `cffi._pycparser`.
- `email` must not be excluded from the PyInstaller build because `requests` and `urllib3` use standard-library `email.*` modules.
- `ISCC.exe` is installed at `C:\Users\59949\AppData\Local\Programs\Inno Setup 6\ISCC.exe`. It may not be visible in already-running terminals until PATH is refreshed.
- Code signing is optional. When a certificate is available, run `scripts\release.ps1` with `-Sign` and either `-CertificateThumbprint <thumbprint>` or `-CertificateFile <path>`.
- Keep `.pfx` and `.p12` certificate files out of Git. They are ignored by `.gitignore`.
- Current release artifacts are unsigned because no code signing certificate is configured.

## Before Publishing

- [ ] Confirm the current Git diff contains only intended release changes.
- [x] Decide whether this release should be signed. Current release is unsigned; `Get-AuthenticodeSignature` returns `NotSigned` for both artifacts.
- [ ] Decide whether to commit generated installer logs or keep them local only.
- [ ] Run one final manual installer smoke test if the installer script changes again.
- [ ] Publish `installer_output\QuickShot-5.3.0-Setup.exe` and its SHA256.
