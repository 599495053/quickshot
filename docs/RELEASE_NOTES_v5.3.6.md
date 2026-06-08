# QuickShot v5.3.6 Release Notes

QuickShot v5.3.6 adds screenshot workflow presets so common post-capture flows can be switched with one setting instead of several separate toggles.

## Highlights

- Added workflow presets for quick copy, auto save, OCR, publish, and privacy-first screenshots.
- Added silent auto-save to the configured default screenshot directory.
- Privacy-first workflow starts smart masking review before copying any unmasked screenshot to the clipboard.
- Kept the default installer lightweight and unsigned, with optional OCR/HDR dependencies still excluded.

## Verification

Final v5.3.6 artifact and desktop verification results:

- `python -m pytest -q`: `517 passed, 37 subtests passed`
- `powershell -ExecutionPolicy Bypass -File .\scripts\release.ps1 -SkipInstall -Clean`
- `powershell -ExecutionPolicy Bypass -File .\scripts\release.ps1 -SkipBuild -SkipInstaller -SmokeTest`
- `powershell -ExecutionPolicy Bypass -File .\scripts\verify-artifact-signature.ps1 .\dist\QuickShot.exe .\installer_output\QuickShot-5.3.6-Setup.exe -ExpectedStatus NotSigned`
- `powershell -ExecutionPolicy Bypass -File .\scripts\verify-upgrade-installer.ps1 -PreviousInstallerPath .\installer_output\QuickShot-5.3.5-Setup.exe -PreviousVersion 5.3.5 -RemoveExisting -PrivacySelfTest -OverlaySelfTest -CaptureSelfTest`
- `powershell -ExecutionPolicy Bypass -File .\scripts\verify-local-installer.ps1 -RemoveExisting -PrivacySelfTest -OverlaySelfTest -CaptureSelfTest`
- `powershell -ExecutionPolicy Bypass -File .\scripts\verify-desktop-hotkeys.ps1 -ExePath .\dist\QuickShot.exe -StopExisting`
- `pyi-archive_viewer -l dist\QuickShot.exe`: no heavy optional OCR/HDR/runtime entries such as NumPy, OpenBLAS, dxcam, WinRT, RapidOCR, ONNX Runtime, or OpenCV.

## Artifacts

Generated from the final v5.3.6 release build:

| File | Size | SHA256 |
| --- | ---: | --- |
| `QuickShot.exe` | 31,651,170 bytes / 30.18 MiB | `6B23CA2A11B2DEC28929C9AF16093DA31F3CE9366CA5A6FACAE18E2AB1271295` |
| `QuickShot-5.3.6-Setup.exe` | 33,431,838 bytes / 31.88 MiB | `7D960B5111783F51A5AA2F073B8BED3188502168196D312E25303EDA01B866F1` |
| `QuickShot-5.3.6-release.txt` | 488 bytes | `6C4AA6BAD8362EC6D4C9864481158B91AEB3D0387A44EB56383FEDBE8DE932F5` |

Both executable and installer report `NotSigned` Authenticode status.
