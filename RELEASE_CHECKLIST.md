# QuickShot Release Checklist

Version: 5.3.7
Last verified: 2026-06-08

## Quality Gates

- [x] `python -m pytest -q`
  - Result: `522 passed, 37 subtests passed`
- [x] `python -m pyflakes quickshot launcher.py build_config.py`
- [x] `python -m compileall -q quickshot launcher.py build_config.py`
- [x] `python -m pip check`
  - Result: `No broken requirements found.`

## Build

- [x] Version references synchronized:
  - Check: `powershell -ExecutionPolicy Bypass -File .\scripts\set-version.ps1 -Version 5.3.7 -CheckOnly`
  - Update command for a new release: `powershell -ExecutionPolicy Bypass -File .\scripts\set-version.ps1 -Version <new-version>`
- [x] Automated release build:
  - Command: `powershell -ExecutionPolicy Bypass -File .\scripts\release.ps1 -SkipInstall -Clean`
  - Manifest: `installer_output\QuickShot-5.3.7-release.txt`
  - Current release script records executable and installer Authenticode signature status for newly generated manifests.
- [x] Build executable:
  - Command: `powershell -ExecutionPolicy Bypass -File .\scripts\release.ps1 -SkipInstall -Clean`
  - Output: `dist\QuickShot.exe`
  - Size: `31654804` bytes
  - SHA256: `B4DB6F4C1B335CA5F4267752CF28F1AEED13764F05AB24458A5D173EF19A7B41`
- [x] Build installer:
  - Command: `powershell -ExecutionPolicy Bypass -File .\scripts\release.ps1 -SkipInstall -Clean`
  - Output: `installer_output\QuickShot-5.3.7-Setup.exe`
  - Size: `33434302` bytes
  - SHA256: `5BD5987E360832B90EA5BF1FD160B5CDC30CE954D96F2AD5B88CBB01494BB77B`

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
- [x] NumPy/OpenBLAS, dxcam, and WinRT HDR capture modules are optional and absent from the default package.
- [x] Region hotkey capture verified by `scripts\verify-desktop-hotkeys.ps1`.
- [x] Window hotkey capture verified by `scripts\verify-desktop-hotkeys.ps1`.
- [x] Clipboard formats observed during core capture verification:
  - `application/x-qt-image`
  - `DeviceIndependentBitmap`
  - `image/png`
- [x] Capture history writes new PNG files.
- [x] Debug log has no new `CRASH`, `Traceback`, `error`, or `failed` entries during the tested launch windows.

## Local Installer Verification

- [x] Local installer verification passed:
  - Command: `powershell -ExecutionPolicy Bypass -File .\scripts\verify-local-installer.ps1 -RemoveExisting -PrivacySelfTest -OverlaySelfTest -CaptureSelfTest`
- [x] Installer SHA256 matches the local release manifest.
- [x] Silent current-user install succeeds.
- [x] Default install does not create a desktop shortcut.
- [x] Default install does not create a Windows startup entry.
- [x] Installed app launch smoke passes.
- [x] Silent uninstall removes installed files and uninstall entry.

## Upgrade/Reinstall Verification

- [x] Upgrade/reinstall verification passed:
  - Previous installer source: local v5.3.6 release artifact.
  - Command: `powershell -ExecutionPolicy Bypass -File .\scripts\verify-upgrade-installer.ps1 -PreviousInstallerPath .\installer_output\QuickShot-5.3.6-Setup.exe -PreviousVersion 5.3.6 -RemoveExisting -PrivacySelfTest -OverlaySelfTest -CaptureSelfTest`
- [x] Previous-to-current upgrade succeeds: `5.3.6` -> `5.3.7`.
- [x] Same-version reinstall succeeds: `5.3.7` -> `5.3.7`.
- [x] Upgrade/reinstall keeps exactly one uninstall entry.
- [x] Upgrade/reinstall preserves app configuration in the test AppData root.
- [x] Default upgrade/reinstall creates no desktop shortcut and changes no Windows startup entry.
- [x] Installed app launch smoke passes after upgrade/reinstall.
- [x] Silent uninstall after upgrade/reinstall removes installed files and uninstall entry.

## GitHub Release Verification

- [ ] GitHub Release exists:
  - URL: `https://github.com/599495053/quickshot/releases/tag/v5.3.7`
- [ ] Downloaded `QuickShot-5.3.7-Setup.exe` from the GitHub Release.
- [ ] Downloaded `QuickShot-5.3.7-release.txt` from the GitHub Release.
- [ ] Installer SHA256 matches the expected release hash:
  - `5BD5987E360832B90EA5BF1FD160B5CDC30CE954D96F2AD5B88CBB01494BB77B`
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
- Use `scripts\verify-artifact-signature.ps1` to confirm `NotSigned` for unsigned artifacts or `-RequireSigned` for signed artifacts.
- Keep `.pfx` and `.p12` certificate files out of Git. They are ignored by `.gitignore`.
- Current release artifacts are unsigned because no code signing certificate is configured.

## Before Publishing

- [x] Confirm the current Git diff contains only intended release changes.
- [x] Decide whether this release should be signed. Current release is unsigned; `Get-AuthenticodeSignature` returns `NotSigned` for both artifacts.
- [x] Verify artifact signature state:
  - Command: `powershell -ExecutionPolicy Bypass -File .\scripts\verify-artifact-signature.ps1 .\dist\QuickShot.exe .\installer_output\QuickShot-5.3.7-Setup.exe -ExpectedStatus NotSigned`
- [x] Decide whether to commit generated installer logs or keep them local only. Generated build output remains local and ignored.
- [x] Run one final local installer smoke test if the installer script changes again.
- [x] Verify region screenshot and current-window screenshot with `scripts\verify-desktop-hotkeys.ps1`.
- [ ] Publish `installer_output\QuickShot-5.3.7-Setup.exe` and its SHA256.
- [ ] Run GitHub Release installer verification after publishing.
