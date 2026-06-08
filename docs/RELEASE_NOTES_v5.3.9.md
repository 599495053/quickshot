# QuickShot v5.3.9 Release Notes

QuickShot v5.3.9 is a small polish release for the new automation settings experience. It fixes the GitHub uploader missing-configuration hint so the status text reads naturally when GitHub is selected but owner, repo, or token details are missing.

## Highlights

- Fixed the GitHub uploader status text in settings: missing items are now introduced with `缺少：...`.
- Added a regression assertion for the corrected GitHub uploader wording.
- Kept the default installer lightweight and unsigned, with optional OCR/HDR dependencies still excluded.

## Verification

Final v5.3.9 artifact and desktop verification results:

- Real settings-window UI smoke: automation page rendered correctly; publish preset, restore defaults, and GitHub uploader missing-configuration hint updated as expected.
- `python -m pytest -q`: `530 passed, 37 subtests passed`
- `powershell -ExecutionPolicy Bypass -File .\scripts\release.ps1 -SkipInstall -Clean`
- `powershell -ExecutionPolicy Bypass -File .\scripts\release.ps1 -SkipBuild -SkipInstaller -SmokeTest`
- `powershell -ExecutionPolicy Bypass -File .\scripts\verify-artifact-signature.ps1 .\dist\QuickShot.exe .\installer_output\QuickShot-5.3.9-Setup.exe -ExpectedStatus NotSigned`
- `powershell -ExecutionPolicy Bypass -File .\scripts\verify-local-installer.ps1 -RemoveExisting -PrivacySelfTest -OverlaySelfTest -CaptureSelfTest`
- `powershell -ExecutionPolicy Bypass -File .\scripts\verify-upgrade-installer.ps1 -PreviousInstallerPath .\installer_output\QuickShot-5.3.8-Setup.exe -PreviousVersion 5.3.8 -RemoveExisting -PrivacySelfTest -OverlaySelfTest -CaptureSelfTest`
- `powershell -ExecutionPolicy Bypass -File .\scripts\verify-desktop-hotkeys.ps1 -ExePath .\dist\QuickShot.exe -StopExisting`
- `pyi-archive_viewer -l dist\QuickShot.exe`: no heavy optional OCR/HDR/runtime entries such as NumPy, OpenBLAS, dxcam, WinRT, RapidOCR, ONNX Runtime, or OpenCV.

## Artifacts

Generated from the final v5.3.9 release build:

| File | Size | SHA256 |
| --- | ---: | --- |
| `QuickShot.exe` | 31,657,093 bytes / 30.19 MiB | `2C1934DE601D1E29A804B65F830D32720B6F13E9ABD6BC6AFBD1DA53637DB4A9` |
| `QuickShot-5.3.9-Setup.exe` | 33,437,488 bytes / 31.89 MiB | `EB68758488AE638AE8D84B835570BA21A67C10D6A85B371C278DF170E4B3D56F` |
| `QuickShot-5.3.9-release.txt` | 488 bytes | `9B2A836662BD3116423602B7BD6FCDBDBCA72734BC2F9AABEBB473A533AC98C3` |

Both executable and installer report `NotSigned` Authenticode status.
