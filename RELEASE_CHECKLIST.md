# QuickShot Release Checklist

Version: 5.3.9
Last verified: 2026-06-09

## Current Verified Baseline

- Test suite: `631 passed, 111 subtests passed`
- Executable SHA256: `D6BDCB151171DE3FE363636C9011049386DA40997F8AC66A0EF41BEEC1F343C2`
- Installer SHA256: `556CC426B74D4A18815917FB73A677017E9295094AFB3D4A7F8AF45BE4BD8149`
- Executable signature status: `NotSigned`
- Installer signature status: `NotSigned`

## 1. Version Sync

- [ ] Update all version references for a new release:
  - `powershell -ExecutionPolicy Bypass -File .\scripts\set-version.ps1 -Version <new-version>`
- [ ] Verify version references are synchronized:
  - `powershell -ExecutionPolicy Bypass -File .\scripts\set-version.ps1 -Version 5.3.9 -CheckOnly`

## 2. Full Local Release Build

- [ ] Run the one-command release gate:
  - `powershell -ExecutionPolicy Bypass -File .\scripts\full-release.ps1 -Clean -DesktopWorkflowTest`
- [ ] Confirm the release script completed these gates:
  - version metadata consistency
  - `python -m pyflakes quickshot launcher.py build_config.py`
  - `python -m compileall -q quickshot launcher.py build_config.py`
  - `python -m pytest -q`
  - PyInstaller build
  - Inno Setup build
  - packaged smoke tests
  - desktop overlay workflow test
- [ ] Build executable:
  - Output: `dist\QuickShot.exe`
  - Expected SHA256 after the latest verification: `D6BDCB151171DE3FE363636C9011049386DA40997F8AC66A0EF41BEEC1F343C2`
- [ ] Build installer:
  - Output: `installer_output\QuickShot-5.3.9-Setup.exe`
  - Expected SHA256 after the latest verification: `556CC426B74D4A18815917FB73A677017E9295094AFB3D4A7F8AF45BE4BD8149`
- [ ] Release manifest:
  - Manifest: `installer_output\QuickShot-5.3.9-release.txt`
  - Confirm `ExecutableSHA256` matches `dist\QuickShot.exe`.
  - Confirm `InstallerSHA256` matches `installer_output\QuickShot-5.3.9-Setup.exe`.

## 3. Optional Install Verification

- [ ] Install the freshly built release and verify the installed EXE hash:
  - `powershell -ExecutionPolicy Bypass -File .\scripts\full-release.ps1 -SkipBuild -SkipInstaller -Install`
- [ ] Verify the installed desktop overlay workflow:
  - `powershell -ExecutionPolicy Bypass -File .\scripts\verify-desktop-overlay-workflow.ps1 -ExePath "$env:LOCALAPPDATA\Programs\QuickShot\QuickShot.exe" -StopExisting`
- [ ] Confirm the installed app starts normally and no new crash text appears in `%APPDATA%\QuickShot\debug.log`.

## 4. Local Installer Verification

- [ ] Run the local installer verification:
  - `powershell -ExecutionPolicy Bypass -File .\scripts\verify-local-installer.ps1 -RemoveExisting -PrivacySelfTest -OverlaySelfTest -CaptureSelfTest`
- [ ] Confirm:
  - installer SHA256 matches the local release manifest
  - silent current-user install succeeds
  - default install creates no desktop shortcut
  - default install creates no Windows startup entry
  - installed app launch smoke passes
  - silent uninstall removes installed files and uninstall entry

## 5. Upgrade And Reinstall Verification

- [ ] Run upgrade/reinstall verification when a previous installer is available:
  - `powershell -ExecutionPolicy Bypass -File .\scripts\verify-upgrade-installer.ps1 -PreviousInstallerPath .\installer_output\QuickShot-<previous-version>-Setup.exe -PreviousVersion <previous-version> -RemoveExisting -PrivacySelfTest -OverlaySelfTest -CaptureSelfTest`
- [ ] Confirm:
  - previous-to-current upgrade succeeds
  - same-version reinstall succeeds
  - exactly one uninstall entry exists after install
  - app configuration is preserved
  - default upgrade/reinstall creates no desktop shortcut
  - default upgrade/reinstall changes no Windows startup entry
  - silent uninstall removes installed files and uninstall entry

## 6. Publishing

- [ ] Confirm the current Git diff contains only intended release changes.
- [ ] Decide whether the release should be signed.
- [ ] Verify artifact signature state:
  - Unsigned release: `powershell -ExecutionPolicy Bypass -File .\scripts\verify-artifact-signature.ps1 .\dist\QuickShot.exe .\installer_output\QuickShot-5.3.9-Setup.exe -ExpectedStatus NotSigned`
  - Signed release: `powershell -ExecutionPolicy Bypass -File .\scripts\verify-artifact-signature.ps1 .\dist\QuickShot.exe .\installer_output\QuickShot-5.3.9-Setup.exe -RequireSigned`
- [ ] Publish `installer_output\QuickShot-5.3.9-Setup.exe` as release asset.
- [ ] Publish `installer_output\QuickShot-5.3.9-release.txt` as release asset.

## 7. GitHub Release Verification

- [ ] Downloaded `QuickShot-5.3.9-Setup.exe` from the GitHub Release.
- [ ] Downloaded `QuickShot-5.3.9-release.txt` from the GitHub Release.
- [ ] Verify the downloaded installer:
  - `powershell -ExecutionPolicy Bypass -File .\scripts\verify-release-installer.ps1 -Tag v5.3.9 -ExpectedSha256 556CC426B74D4A18815917FB73A677017E9295094AFB3D4A7F8AF45BE4BD8149 -RemoveExisting -PrivacySelfTest -OverlaySelfTest -CaptureSelfTest`
- [ ] Confirm:
  - release assets are present
  - downloaded installer SHA256 matches the expected release hash
  - downloaded release manifest contains the same installer SHA256
  - silent install from the downloaded installer succeeds
  - default silent install creates no desktop shortcut
  - default silent install creates no Windows startup entry
  - installed app launches successfully from the install directory
  - packaged privacy OCR fallback self-test passes
  - packaged overlay edit smoke self-test passes
  - packaged capture backend smoke self-test passes
  - launch smoke test writes no new crash text
  - silent uninstall removes installed files, uninstall entry, startup entry, and desktop shortcuts

## Known Build Notes

- Inno Setup 6 is expected at `C:\Users\59949\AppData\Local\Programs\Inno Setup 6\ISCC.exe`, or can be passed with `-InnoSetupCompiler`.
- PyInstaller may report optional missing modules from third-party packages. Current relevant optional entries include `pycparser.lextab`, `pycparser.yacctab`, and `cffi._pycparser`.
- `email` must not be excluded from the PyInstaller build because `requests` and `urllib3` use standard-library `email.*` modules.
- RapidOCR, NumPy/OpenBLAS, dxcam, and WinRT HDR capture modules are optional in the default package.
- Code signing is optional. When a certificate is available, run `scripts\full-release.ps1` with `-Sign` and either `-CertificateThumbprint <thumbprint>` or `-CertificateFile <path>`.
- Keep `.pfx` and `.p12` certificate files out of Git. They are ignored by `.gitignore`.
