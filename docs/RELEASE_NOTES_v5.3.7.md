# QuickShot v5.3.7 Release Notes

QuickShot v5.3.7 makes screenshot workflows easier to switch while working. You can now change the active workflow preset directly from the tray menu, and the screenshot selection prompt shows what pressing Enter will do for the current workflow.

## Highlights

- Added a tray menu workflow preset switcher for quick copy, auto save, OCR, publish, and privacy-first flows.
- Updated the tray tooltip and startup tray message to show the current workflow preset.
- Screenshot selection and edit prompts now include the current Enter behavior, such as copy, save, OCR, upload, or privacy review.
- Kept the default installer lightweight and unsigned, with optional OCR/HDR dependencies still excluded.

## Verification

Final v5.3.7 artifact and desktop verification results:

- `python -m pytest -q`: `522 passed, 37 subtests passed`
- `powershell -ExecutionPolicy Bypass -File .\scripts\release.ps1 -SkipInstall -Clean`
- `powershell -ExecutionPolicy Bypass -File .\scripts\release.ps1 -SkipBuild -SkipInstaller -SmokeTest`
- `powershell -ExecutionPolicy Bypass -File .\scripts\verify-artifact-signature.ps1 .\dist\QuickShot.exe .\installer_output\QuickShot-5.3.7-Setup.exe -ExpectedStatus NotSigned`
- `powershell -ExecutionPolicy Bypass -File .\scripts\verify-upgrade-installer.ps1 -PreviousInstallerPath .\installer_output\QuickShot-5.3.6-Setup.exe -PreviousVersion 5.3.6 -RemoveExisting -PrivacySelfTest -OverlaySelfTest -CaptureSelfTest`
- `powershell -ExecutionPolicy Bypass -File .\scripts\verify-local-installer.ps1 -RemoveExisting -PrivacySelfTest -OverlaySelfTest -CaptureSelfTest`
- `powershell -ExecutionPolicy Bypass -File .\scripts\verify-desktop-hotkeys.ps1 -ExePath .\dist\QuickShot.exe -StopExisting`
- `pyi-archive_viewer -l dist\QuickShot.exe`: no heavy optional OCR/HDR/runtime entries such as NumPy, OpenBLAS, dxcam, WinRT, RapidOCR, ONNX Runtime, or OpenCV.

## Artifacts

Generated from the final v5.3.7 release build:

| File | Size | SHA256 |
| --- | ---: | --- |
| `QuickShot.exe` | 31,654,804 bytes / 30.19 MiB | `B4DB6F4C1B335CA5F4267752CF28F1AEED13764F05AB24458A5D173EF19A7B41` |
| `QuickShot-5.3.7-Setup.exe` | 33,434,302 bytes / 31.89 MiB | `5BD5987E360832B90EA5BF1FD160B5CDC30CE954D96F2AD5B88CBB01494BB77B` |
| `QuickShot-5.3.7-release.txt` | 488 bytes | `317C0F72523EE03E84A383912B8C1C11D92C3E2C0D5D9D7896371C3D3591846B` |

Both executable and installer report `NotSigned` Authenticode status.
