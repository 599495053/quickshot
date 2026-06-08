# QuickShot v5.3.8 Release Notes

QuickShot v5.3.8 focuses on making workflow automation easier to understand and safer to recover from. The settings page now explains the active workflow behavior, and upload failures give clearer next steps when GitHub configuration, token, permissions, repository settings, or network connectivity are the problem.

## Highlights

- Added a settings-page workflow summary showing the current preset and what pressing Enter will do.
- Added a settings-page action to restore the default workflow: copy image after capture, with save/OCR/upload/privacy automation turned off.
- Workflow changes made from settings now refresh the tray tooltip and workflow preset menu.
- Added a GitHub uploader status hint in settings so missing owner, repo, or Personal Access Token is visible before capture.
- Upload workflow failures now include more actionable guidance for missing configuration, expired tokens, insufficient permissions, repository or branch issues, and network/proxy failures.
- Kept the default installer lightweight and unsigned, with optional OCR/HDR dependencies still excluded.

## Verification

Final v5.3.8 artifact and desktop verification results:

- `python -m pytest -q`: `530 passed, 37 subtests passed`
- `powershell -ExecutionPolicy Bypass -File .\scripts\release.ps1 -SkipInstall -Clean`
- `powershell -ExecutionPolicy Bypass -File .\scripts\release.ps1 -SkipBuild -SkipInstaller -SmokeTest`
- `powershell -ExecutionPolicy Bypass -File .\scripts\verify-artifact-signature.ps1 .\dist\QuickShot.exe .\installer_output\QuickShot-5.3.8-Setup.exe -ExpectedStatus NotSigned`
- `powershell -ExecutionPolicy Bypass -File .\scripts\verify-upgrade-installer.ps1 -PreviousInstallerPath .\installer_output\QuickShot-5.3.7-Setup.exe -PreviousVersion 5.3.7 -RemoveExisting -PrivacySelfTest -OverlaySelfTest -CaptureSelfTest`
- `powershell -ExecutionPolicy Bypass -File .\scripts\verify-local-installer.ps1 -RemoveExisting -PrivacySelfTest -OverlaySelfTest -CaptureSelfTest`
- `powershell -ExecutionPolicy Bypass -File .\scripts\verify-desktop-hotkeys.ps1 -ExePath .\dist\QuickShot.exe -StopExisting`
- `pyi-archive_viewer -l dist\QuickShot.exe`: no heavy optional OCR/HDR/runtime entries such as NumPy, OpenBLAS, dxcam, WinRT, RapidOCR, ONNX Runtime, or OpenCV.

## Artifacts

Generated from the final v5.3.8 release build:

| File | Size | SHA256 |
| --- | ---: | --- |
| `QuickShot.exe` | 31,657,788 bytes / 30.19 MiB | `B23857233A2929F6A32722ABB40803086A3F629348F3C7D265FF154EBE35DA5A` |
| `QuickShot-5.3.8-Setup.exe` | 33,438,608 bytes / 31.89 MiB | `5269AD772B55FA6029CD90B3BC83AEE676A4782DC38AD56059D2095EC9CDDFF4` |
| `QuickShot-5.3.8-release.txt` | 488 bytes | `CC9869AF547718786542EFFB7E05061DA452538B6131C7E882E1112ABD1682AF` |

Both executable and installer report `NotSigned` Authenticode status.
