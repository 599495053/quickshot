# QuickShot v5.3.1 Release Notes Draft

This is the working draft for the next GitHub Release. Do not publish it until the final artifacts are uploaded and the artifact table below is confirmed against those files.

## Title

QuickShot v5.3.1

## Summary

QuickShot v5.3.1 focuses on a much lighter Windows package and stronger release verification. The default installer keeps Windows system OCR available, while RapidOCR/ONNX Runtime becomes an optional add-on for source or custom builds.

## Highlights

- Reduced the Windows installer from the original v5.3.0 baseline by about 63 MiB through targeted dependency and binary trimming.
- Replaced OpenCV-backed blur annotations with Pillow Gaussian blur.
- Moved RapidOCR and ONNX Runtime out of the default package.
- Kept Windows system OCR available in the lightweight default build.
- Added and documented installer verification, package-size analysis, and packaged smoke-test cleanup.

## User-Facing Changes

- Default OCR now uses Windows system OCR.
- Smart privacy auto-detection requires the optional RapidOCR add-on. In lightweight builds, QuickShot shows a clear optional-component message instead of failing unexpectedly.
- Manual mosaic and blur tools remain available without RapidOCR.

## Optional RapidOCR Add-On

For source/custom builds that need local RapidOCR and smart privacy auto-detection:

```powershell
pip install -e .[ocr]
```

## Verification

Current v5.3.1 release-candidate artifact results:

- `python -m pyflakes quickshot launcher.py build_config.py`
- `python -m compileall -q quickshot launcher.py build_config.py`
- `python -m pytest -q`: `475 passed, 37 subtests passed`
- `python -m pip check`: `No broken requirements found.`
- `powershell -ExecutionPolicy Bypass -File .\scripts\release.ps1 -SkipInstall -Clean`
- `powershell -ExecutionPolicy Bypass -File .\scripts\release.ps1 -SkipBuild -SkipInstaller -SmokeTest`
- `powershell -ExecutionPolicy Bypass -File .\scripts\verify-local-installer.ps1`
- Local installer verification:
  - SHA256 matches release manifest.
  - Silent current-user install succeeds.
  - Default install creates no desktop shortcut.
  - Default install creates no Windows startup entry.
  - Installed app launch smoke passes.
  - Silent uninstall removes installed files and uninstall entry.
- OCR validation:
  - Lightweight build uses Windows system OCR.
  - Missing RapidOCR reports a clear optional-component message for smart privacy masking.
- Package archive scan:
  - No `rapidocr_onnxruntime`, `onnxruntime`, `.onnx`, `Shapely`, `pyclipper`, `cv2`, `opencv`, `opengl32sw.dll`, `Qt6Pdf.dll`, or `_avif` entries.

## Artifact Results

Generated from the current v5.3.1 release-candidate build:

| Artifact | Size | SHA256 |
| --- | ---: | --- |
| `QuickShot-5.3.1-Setup.exe` | 45,265,412 bytes / 43.17 MiB | `198D52BBF4E72EE1165B07D054AF4DC980461B1336E7733F29F51AC7F3430B93` |
| `QuickShot-5.3.1-release.txt` | 415 bytes | `4794726E10287DA1A458E26D03FB80F43AC59F08FD4DD3E34F5505E1233F4421` |

## Publish Checklist

Before publishing:

- Run `powershell -ExecutionPolicy Bypass -File .\scripts\set-version.ps1 -Version 5.3.1`.
- Run `powershell -ExecutionPolicy Bypass -File .\scripts\release.ps1 -SkipInstall -Clean`.
- Run packaged smoke test.
- Run `scripts\verify-local-installer.ps1` against the local build.
- Manually verify region screenshot drag selection and current-window screenshot once on the release desktop.
- Upload the final installer and release manifest.
- Run `scripts\verify-release-installer.ps1` against the GitHub Release asset.
- Confirm the artifact table above still matches the uploaded files.

## Known Notes

- The release is unsigned unless a code signing certificate is configured.
- The `opengl32sw.dll` exclusion should still be retested on remote desktop, VM, older GPU, and software-rendering fallback environments before wide distribution.
