# QuickShot Release Checklist

Version: 5.3.0
Last verified: 2026-06-07

## Quality Gates

- [x] `python -m pytest -q`
  - Result: `471 passed, 37 subtests passed`
- [x] `python -m pyflakes quickshot launcher.py build_config.py`
- [x] `python -m compileall -q quickshot launcher.py build_config.py`
- [x] `python -m pip check`
  - Result: `No broken requirements found.`

## Build

- [x] Build executable:
  - Command: `powershell -ExecutionPolicy Bypass -File .\build.ps1 -SkipInstall -Clean`
  - Output: `dist\QuickShot.exe`
  - Size: `110809414` bytes
  - SHA256: `4DFDC269814FDF85A4FFAAC80D15EB77FE5F0935D7663BC5B4BEB61A83C50E3E`
- [x] Build installer:
  - Command: `& 'C:\Users\59949\AppData\Local\Programs\Inno Setup 6\ISCC.exe' QuickShot.iss`
  - Output: `installer_output\QuickShot-5.3.0-Setup.exe`
  - Size: `111998458` bytes
  - SHA256: `AC5A1DEC242EE2B917617F1A3BEED287B548BFE9296D66DD4F0C7DB0B5B4512A`

## Installer Behavior

- [x] Inno Setup compile completes with no warnings.
- [x] Simplified Chinese installer language is available via `/LANG=chinesesimp`.
- [x] Default install does not create a desktop shortcut.
- [x] Default install does not create a Windows startup entry.
- [x] Uninstall display name is `QuickShot`.
- [x] Uninstall removes install directory, Start Menu entries, desktop shortcut if selected, startup registry value, and uninstall registry key.
- [x] `[UninstallRun]` uses `RunOnceId` so the `taskkill` cleanup runs once on a clean install.

## Runtime Smoke Tests

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

## Before Publishing

- [ ] Confirm the current Git diff contains only intended release changes.
- [ ] Decide whether to commit generated installer logs or keep them local only.
- [ ] Run one final manual installer smoke test if the installer script changes again.
- [ ] Publish `installer_output\QuickShot-5.3.0-Setup.exe` and its SHA256.
