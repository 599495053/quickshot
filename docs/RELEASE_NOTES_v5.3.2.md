# QuickShot v5.3.2 Release Notes

## Summary

QuickShot v5.3.2 fixes smart privacy masking in the lightweight Windows package. RapidOCR/ONNX Runtime remains optional, and the default installer now falls back to Windows system OCR line boxes when RapidOCR is unavailable.

## Highlights

- Fixed smart privacy masking in the default lightweight build.
- Kept RapidOCR/ONNX Runtime optional instead of rebundling the heavy local OCR runtime.
- Trimmed unused PyQt6 Qt translation files from the Windows bundle.
- Added installer upgrade and same-version reinstall regression verification.

## User-Facing Changes

- Smart privacy masking works in the default installer without installing RapidOCR.
- Manual mosaic and blur tools remain available without optional OCR add-ons.
- Windows system OCR remains the default OCR path in the lightweight build.

## Optional RapidOCR Add-On

For source/custom builds that need the local RapidOCR engine:

```powershell
pip install -e .[ocr]
```

## Verification

Final v5.3.2 artifact and desktop verification results:

- `python -m pyflakes quickshot launcher.py build_config.py`
- `python -m compileall -q quickshot launcher.py build_config.py`
- `python -m pytest -q`: `478 passed, 37 subtests passed`
- `powershell -ExecutionPolicy Bypass -File .\scripts\release.ps1 -SkipInstall -Clean`
- `powershell -ExecutionPolicy Bypass -File .\scripts\release.ps1 -SkipBuild -SkipInstaller -SmokeTest`
- `powershell -ExecutionPolicy Bypass -File .\scripts\verify-local-installer.ps1 -RemoveExisting`
- `powershell -ExecutionPolicy Bypass -File .\scripts\verify-upgrade-installer.ps1 -PreviousInstallerPath .\installer_output\QuickShot-5.3.1-Setup.exe -PreviousVersion 5.3.1`
- Local Windows OCR fallback smoke: generated phone-number image returned a smart privacy rectangle without RapidOCR.
- Package archive scan:
  - No `PyQt6\Qt6\translations`, `.qm`, `rapidocr_onnxruntime`, `onnxruntime`, `.onnx`, `Shapely`, `pyclipper`, `cv2`, `opencv`, `opengl32sw.dll`, `Qt6Pdf.dll`, or `_avif` entries.

## Artifact Results

Generated from the final v5.3.2 release build:

| Artifact | Size | SHA256 |
| --- | ---: | --- |
| `QuickShot-5.3.2-Setup.exe` | 43,339,059 bytes / 41.33 MiB | `E0B9B948485783D9C031E1EB2100F9DE1476B19E73E0D0477A1582520CFE04FC` |
| `QuickShot-5.3.2-release.txt` | 415 bytes | `A4AB7C53FA5815718FFE9F599B9566F2FCC8B34DD808783232C8EFC6D550680C` |

## Known Notes

- The release is unsigned unless a code signing certificate is configured.
- The `opengl32sw.dll` exclusion should still be retested on remote desktop, VM, older GPU, and software-rendering fallback environments before wide distribution.
