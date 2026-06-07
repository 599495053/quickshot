# QuickShot Release Checklist

Version: 5.3.1
Last verified: 2026-06-08

## Quality Gates

- [x] `python -m pytest -q`
  - Result: `475 passed, 37 subtests passed`
- [x] `python -m pyflakes quickshot launcher.py build_config.py`
- [x] `python -m compileall -q quickshot launcher.py build_config.py`
- [x] `python -m pip check`
  - Result: `No broken requirements found.`

## Build

- [x] Version references synchronized:
  - Check: `powershell -ExecutionPolicy Bypass -File .\scripts\set-version.ps1 -Version 5.3.1 -CheckOnly`
  - Update command for a new release: `powershell -ExecutionPolicy Bypass -File .\scripts\set-version.ps1 -Version <new-version>`
- [x] Automated release build:
  - Command: `powershell -ExecutionPolicy Bypass -File .\scripts\release.ps1 -SkipInstall -Clean`
  - Manifest: `installer_output\QuickShot-5.3.1-release.txt`
- [x] Build executable:
  - Command: `powershell -ExecutionPolicy Bypass -File .\scripts\release.ps1 -SkipInstall -Clean`
  - Output: `dist\QuickShot.exe`
  - Size: `43532731` bytes
  - SHA256: `97EDE745F2F425734CA12AA2081085B0605DF74ED626D386ED5DECF48F5AB8D8`
- [x] Build installer:
  - Command: `powershell -ExecutionPolicy Bypass -File .\scripts\release.ps1 -SkipInstall -Clean`
  - Output: `installer_output\QuickShot-5.3.1-Setup.exe`
  - Size: `45265412` bytes
  - SHA256: `198D52BBF4E72EE1165B07D054AF4DC980461B1336E7733F29F51AC7F3430B93`

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
- [x] RapidOCR is optional in the default package; Windows system OCR remains available.
- [x] Region hotkey `Ctrl+Shift+A` drag-selection capture manually verified on the release desktop.
  - Clipboard image observed after drag selection: `1382 x 806`.
- [x] Window hotkey `Ctrl+Shift+W` current-window capture manually verified on the release desktop.
  - Clipboard image observed after capturing Calculator: `484 x 801`.
- [x] Clipboard formats observed during core capture verification:
  - `application/x-qt-image`
  - `DeviceIndependentBitmap`
  - `image/png`
- [x] Capture history writes new PNG files.
- [x] Debug log has no new `CRASH`, `Traceback`, `error`, or `failed` entries during the tested launch windows.

## Local Installer Verification

- [x] Local installer verification passed:
  - Command: `powershell -ExecutionPolicy Bypass -File .\scripts\verify-local-installer.ps1`
- [x] Installer SHA256 matches the local release manifest.
- [x] Silent current-user install succeeds.
- [x] Default install does not create a desktop shortcut.
- [x] Default install does not create a Windows startup entry.
- [x] Installed app launch smoke passes.
- [x] Silent uninstall removes installed files and uninstall entry.

## GitHub Release Verification

- [ ] GitHub Release exists:
  - URL: `https://github.com/599495053/quickshot/releases/tag/v5.3.1`
- [ ] Downloaded `QuickShot-5.3.1-Setup.exe` from the GitHub Release.
- [ ] Downloaded `QuickShot-5.3.1-release.txt` from the GitHub Release.
- [ ] Installer SHA256 matches the expected release hash:
  - `198D52BBF4E72EE1165B07D054AF4DC980461B1336E7733F29F51AC7F3430B93`
- [ ] Release manifest contains the same installer SHA256.
- [ ] Silent install from the downloaded installer succeeds.
- [ ] Default silent install does not create a desktop shortcut.
- [ ] Default silent install does not create a Windows startup entry.
- [ ] Installed app launches successfully from the install directory.
- [ ] Launch smoke test writes no new `CRASH`, `Traceback`, or unhandled exception entries.
- [ ] Silent uninstall succeeds and removes the uninstall entry, installed executable, startup entry, and desktop shortcuts.

## Known Build Notes

- PyInstaller may report optional missing modules from third-party packages. Current relevant optional entries include `pycparser.lextab`, `pycparser.yacctab`, and `cffi._pycparser`.
- `email` must not be excluded from the PyInstaller build because `requests` and `urllib3` use standard-library `email.*` modules.
- `ISCC.exe` is installed at `C:\Users\59949\AppData\Local\Programs\Inno Setup 6\ISCC.exe`. It may not be visible in already-running terminals until PATH is refreshed.
- Code signing is optional. When a certificate is available, run `scripts\release.ps1` with `-Sign` and either `-CertificateThumbprint <thumbprint>` or `-CertificateFile <path>`.
- Keep `.pfx` and `.p12` certificate files out of Git. They are ignored by `.gitignore`.
- Current release artifacts are unsigned because no code signing certificate is configured.

## Before Publishing

- [x] Confirm the current Git diff contains only intended release changes.
- [x] Decide whether this release should be signed. Current release is unsigned; `Get-AuthenticodeSignature` returns `NotSigned` for both artifacts.
- [x] Decide whether to commit generated installer logs or keep them local only. Generated build output remains local and ignored.
- [x] Run one final local installer smoke test if the installer script changes again.
- [x] Manually verify region screenshot drag selection and current-window screenshot.
- [ ] Publish `installer_output\QuickShot-5.3.1-Setup.exe` and its SHA256.
- [ ] Run GitHub Release installer verification after publishing.
