# QuickShot v5.3.3 Release Notes

QuickShot v5.3.3 focuses on a smaller default Windows installer and a clearer split between the lightweight capture path and optional advanced HDR capture support.

## Highlights

- Reduced the default installer by moving NumPy, OpenBLAS, dxcam, and WinRT HDR capture support out of the bundled runtime.
- Kept normal region and current-window screenshots on the lightweight `mss` backend.
- Added the optional `hdr` extra for source/custom builds that need the dxcam/WGC HDR capture path.
- Kept RapidOCR optional while preserving Windows system OCR and smart privacy masking fallback in the default package.
- The GitHub repository is now public.

## Optional HDR Add-On

The default installer no longer bundles the heavier HDR capture stack. Source/custom builds can enable it with:

```powershell
pip install -e .[hdr]
```

When the optional HDR dependencies are unavailable, QuickShot falls back to the normal `mss` capture backend.

## Verification

Final v5.3.3 artifact and desktop verification results:

- `python -m pytest -q`: `488 passed, 37 subtests passed`
- `powershell -ExecutionPolicy Bypass -File .\scripts\release.ps1 -SkipInstall -Clean`
- `pyi-archive_viewer -l dist\QuickShot.exe`: no `numpy`, `numpy.libs`, `openblas`, `dxcam`, `winrt`, `rapidocr`, `onnxruntime`, `cv2`, `opencv`, `Qt6Pdf`, `opengl32sw`, or `_avif` entries
- `powershell -ExecutionPolicy Bypass -File .\scripts\release.ps1 -SkipBuild -SkipInstaller -SmokeTest`
- `powershell -ExecutionPolicy Bypass -File .\scripts\verify-local-installer.ps1 -RemoveExisting -PrivacySelfTest -OverlaySelfTest -CaptureSelfTest`
- `powershell -ExecutionPolicy Bypass -File .\scripts\verify-upgrade-installer.ps1 -PreviousInstallerPath .\installer_output\QuickShot-5.3.2-Setup.exe -PreviousVersion 5.3.2 -RemoveExisting -PrivacySelfTest -OverlaySelfTest -CaptureSelfTest`
- `powershell -ExecutionPolicy Bypass -File .\scripts\verify-desktop-hotkeys.ps1 -ExePath .\dist\QuickShot.exe -StopExisting`

## Artifact Hashes

Generated from the final v5.3.3 release build:

| File | Size | SHA256 |
| --- | ---: | --- |
| `QuickShot-5.3.3-Setup.exe` | 33,405,239 bytes / 31.86 MiB | `738845DC1F9F086E3FDBFC0E70A5DEC9E9D8A12400937040464E998446196F8C` |
| `QuickShot-5.3.3-release.txt` | 415 bytes | `D2B898E7F39FB49E896F243112FC88E29B69465285DDC52813A7D2283C5CE86F` |

## Notes

- The release is unsigned because no code-signing certificate is configured.
- Windows may show a security warning for the unsigned installer. Verify the SHA256 hash above before installing.
