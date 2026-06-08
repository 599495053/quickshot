# QuickShot Release Checklist

Version: 5.3.8
Last verified: 2026-06-08

## Quality Gates

- [x] `python -m pytest -q`
  - Result: `530 passed, 37 subtests passed`
- [x] `python -m pyflakes quickshot launcher.py build_config.py`
- [x] `python -m compileall -q quickshot launcher.py build_config.py`
- [x] `python -m pip check`
  - Result: `No broken requirements found.`
- [x] GitHub Actions CI for the release commit passed:
  - Run: `https://github.com/599495053/quickshot/actions/runs/27129930818`
  - Commit: `7d7fad8c2f0401010728524e6f1f05ad9e934dd0`
  - Result: `success`

## Build

- [x] Version references synchronized:
  - Check: `powershell -ExecutionPolicy Bypass -File .\scripts\set-version.ps1 -Version 5.3.8 -CheckOnly`
  - Update command for a new release: `powershell -ExecutionPolicy Bypass -File .\scripts\set-version.ps1 -Version <new-version>`
- [x] Automated release build:
  - Command: `powershell -ExecutionPolicy Bypass -File .\scripts\release.ps1 -SkipInstall -Clean`
  - Manifest: `installer_output\QuickShot-5.3.8-release.txt`
  - Current release script records executable and installer Authenticode signature status for newly generated manifests.
- [x] Build executable:
  - Command: `powershell -ExecutionPolicy Bypass -File .\scripts\release.ps1 -SkipInstall -Clean`
  - Output: `dist\QuickShot.exe`
  - Size: `31657788` bytes
  - SHA256: `B23857233A2929F6A32722ABB40803086A3F629348F3C7D265FF154EBE35DA5A`
- [x] Build installer:
  - Command: `powershell -ExecutionPolicy Bypass -File .\scripts\release.ps1 -SkipInstall -Clean`
  - Output: `installer_output\QuickShot-5.3.8-Setup.exe`
  - Size: `33438608` bytes
  - SHA256: `5269AD772B55FA6029CD90B3BC83AEE676A4782DC38AD56059D2095EC9CDDFF4`

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
  - Previous installer source: local v5.3.7 release artifact.
  - Command: `powershell -ExecutionPolicy Bypass -File .\scripts\verify-upgrade-installer.ps1 -PreviousInstallerPath .\installer_output\QuickShot-5.3.7-Setup.exe -PreviousVersion 5.3.7 -RemoveExisting -PrivacySelfTest -OverlaySelfTest -CaptureSelfTest`
- [x] Previous-to-current upgrade succeeds: `5.3.7` -> `5.3.8`.
- [x] Same-version reinstall succeeds: `5.3.8` -> `5.3.8`.
- [x] Upgrade/reinstall keeps exactly one uninstall entry.
- [x] Upgrade/reinstall preserves app configuration in the test AppData root.
- [x] Default upgrade/reinstall creates no desktop shortcut and changes no Windows startup entry.
- [x] Installed app launch smoke passes after upgrade/reinstall.
- [x] Silent uninstall after upgrade/reinstall removes installed files and uninstall entry.

## GitHub Release Verification

- [x] GitHub Release exists:
  - URL: `https://github.com/599495053/quickshot/releases/tag/v5.3.8`
  - Published: `2026-06-08T09:57:44Z`
  - Draft: `false`
  - Prerelease: `false`
- [x] Uploaded release assets are present:
  - `QuickShot-5.3.8-Setup.exe`: `33438608` bytes, digest `sha256:5269ad772b55fa6029cd90b3bc83aee676a4782dc38ad56059d2095ec9cddff4`
  - `QuickShot-5.3.8-release.txt`: `488` bytes, digest `sha256:cc9869af547718786542effb7e05061da452538b6131c7e882e1112abd1682af`
- [x] Downloaded `QuickShot-5.3.8-Setup.exe` from the GitHub Release.
- [x] Downloaded `QuickShot-5.3.8-release.txt` from the GitHub Release.
- [x] Installer SHA256 matches the expected release hash:
  - `5269AD772B55FA6029CD90B3BC83AEE676A4782DC38AD56059D2095EC9CDDFF4`
- [x] Release manifest contains the same installer SHA256.
- [x] Silent install from the downloaded installer succeeds.
- [x] Default silent install does not create a desktop shortcut.
- [x] Default silent install does not create a Windows startup entry.
- [x] Installed app launches successfully from the install directory.
- [x] Packaged privacy OCR fallback self-test passes.
- [x] Packaged overlay edit smoke self-test passes.
- [x] Packaged capture backend smoke self-test passes.
- [x] Launch smoke test writes no new `CRASH`, `Traceback`, or unhandled exception entries.
- [x] Silent uninstall succeeds and removes the uninstall entry, installed executable, startup entry, and desktop shortcuts.
- [x] GitHub Release installer verification passed:
  - Command: `powershell -ExecutionPolicy Bypass -File .\scripts\verify-release-installer.ps1 -Tag v5.3.8 -ExpectedSha256 5269AD772B55FA6029CD90B3BC83AEE676A4782DC38AD56059D2095EC9CDDFF4 -RemoveExisting -PrivacySelfTest -OverlaySelfTest -CaptureSelfTest`

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
  - Command: `powershell -ExecutionPolicy Bypass -File .\scripts\verify-artifact-signature.ps1 .\dist\QuickShot.exe .\installer_output\QuickShot-5.3.8-Setup.exe -ExpectedStatus NotSigned`
- [x] Decide whether to commit generated installer logs or keep them local only. Generated build output remains local and ignored.
- [x] Run one final local installer smoke test if the installer script changes again.
- [x] Verify region screenshot and current-window screenshot with `scripts\verify-desktop-hotkeys.ps1`.
- [x] Publish `installer_output\QuickShot-5.3.8-Setup.exe` and its SHA256.
- [x] Run GitHub Release installer verification after publishing.
