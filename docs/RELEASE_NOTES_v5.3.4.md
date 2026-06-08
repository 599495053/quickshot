# QuickShot v5.3.4 Release Notes

QuickShot v5.3.4 focuses on public release trust, clearer diagnostics, and better failure guidance while keeping the default Windows installer lightweight.

## Highlights

- Added public repository polish: README badges, direct download guidance, MIT license text, security policy, and issue templates.
- Added release artifact signature status to the generated manifest, with `scripts/verify-artifact-signature.ps1` for explicit Authenticode checks.
- Added "copy diagnostic info" from the tray menu and settings feedback flow so bug reports can include useful environment details.
- Improved user-facing error guidance for screenshot, OCR, smart privacy masking, save, pin, and post-capture workflow failures.
- Kept RapidOCR, ONNX Runtime, NumPy/OpenBLAS, dxcam, and WinRT HDR capture support out of the default package.

## Diagnostics

When screenshot, OCR, smart privacy masking, save, pin, or upload workflows fail, QuickShot now points users toward diagnostic info instead of leaving a generic failure message. Diagnostic info can also be copied from the tray menu or settings page and pasted into the bug report template after checking that it does not contain private information.

## Verification

Final v5.3.4 artifact and desktop verification results:

- `python -m pytest -q`: `497 passed, 37 subtests passed`
- `powershell -ExecutionPolicy Bypass -File .\scripts\release.ps1 -SkipInstall -Clean`
- `powershell -ExecutionPolicy Bypass -File .\scripts\verify-artifact-signature.ps1 .\dist\QuickShot.exe .\installer_output\QuickShot-5.3.4-Setup.exe -ExpectedStatus NotSigned`
- `pyi-archive_viewer -l dist\QuickShot.exe`: no `numpy`, `numpy.libs`, `openblas`, `dxcam`, `winrt`, `rapidocr`, `onnxruntime`, `cv2`, `opencv`, `Qt6Pdf`, `opengl32sw`, or `_avif` entries
- `powershell -ExecutionPolicy Bypass -File .\scripts\release.ps1 -SkipBuild -SkipInstaller -SmokeTest`
- `powershell -ExecutionPolicy Bypass -File .\scripts\verify-local-installer.ps1 -RemoveExisting -PrivacySelfTest -OverlaySelfTest -CaptureSelfTest`
- `powershell -ExecutionPolicy Bypass -File .\scripts\verify-upgrade-installer.ps1 -PreviousInstallerPath <downloaded v5.3.3 installer> -PreviousVersion 5.3.3 -RemoveExisting -PrivacySelfTest -OverlaySelfTest -CaptureSelfTest`
- `powershell -ExecutionPolicy Bypass -File .\scripts\verify-desktop-hotkeys.ps1 -ExePath .\dist\QuickShot.exe -StopExisting`

## Artifact Hashes

Generated from the final v5.3.4 release build:

| File | Size | SHA256 |
| --- | ---: | --- |
| `QuickShot-5.3.4-Setup.exe` | 33,414,015 bytes / 31.87 MiB | `65693568E293608FD39096241362A95A6DB1722B74CE282BDC4C7CCCA3FA4685` |
| `QuickShot-5.3.4-release.txt` | 488 bytes | `57808CA6E2A18D930357ED9AE854A69C1ED8245E80D5FFC882FDF9DB3AB0D30F` |

## Notes

- The release is unsigned because no code-signing certificate is configured.
- Windows may show a security warning for the unsigned installer. Verify the SHA256 hash above before installing.
- Default install does not create a desktop shortcut or Windows startup entry unless the user selects those tasks.
