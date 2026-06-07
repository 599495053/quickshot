# QuickShot Package Size Analysis

This document records the current Windows one-file PyInstaller size baseline and the safest order for future package-size experiments.

## Baseline

Measured from the current local build artifacts:

| Artifact | Bytes | Size |
| --- | ---: | ---: |
| `dist\QuickShot.exe` | 96,386,837 | 91.92 MiB |
| `installer_output\QuickShot-5.3.0-Setup.exe` | 97,642,080 | 93.12 MiB |
| `build\QuickShot\QuickShot.pkg` | 96,059,157 | 91.61 MiB |
| `build\QuickShot\PYZ-00.pyz` | 6,782,465 | 6.47 MiB |
| `build\QuickShot\base_library.zip` | 1,386,064 | 1.32 MiB |

Toolchain and major package versions:

| Package | Version |
| --- | --- |
| PyInstaller | 6.20.0 |
| PyQt6 | 6.11.0 |
| opencv-python | 4.13.0.92 |
| numpy | 2.4.6 |
| Pillow | 12.2.0 |
| rapidocr-onnxruntime | 1.2.3 |
| onnxruntime | 1.26.0 |
| dxcam | 0.3.0 |
| requests | 2.34.2 |
| keyring | 25.7.0 |
| deep-translator | 1.11.4 |

The current `QuickShot.spec` already uses `optimize=1`, `upx=True`, targeted RapidOCR model data collection, and the shared exclusions in `build_config.py`.

## Completed Experiments

### Pillow AVIF Extension

The `PIL\_avif*.pyd` extension is excluded from PyInstaller binaries because QuickShot imports `PIL.Image` but does not use AVIF-specific functionality.

Result:

| Metric | Before | After | Saved |
| --- | ---: | ---: | ---: |
| `dist\QuickShot.exe` | 110,809,410 | 106,488,532 | 4,320,878 bytes / 4.12 MiB |
| `installer_output\QuickShot-5.3.0-Setup.exe` | 112,000,513 | 107,685,743 | 4,314,770 bytes / 4.11 MiB |
| Archive entries | 276 | 275 | 1 entry |

Verification:

- `python -m pyflakes quickshot launcher.py build_config.py`
- `python -m compileall -q quickshot launcher.py build_config.py`
- `python -m pytest -q`: `471 passed, 37 subtests passed`
- `powershell -ExecutionPolicy Bypass -File .\scripts\release.ps1 -SkipInstall -Clean`
- `powershell -ExecutionPolicy Bypass -File .\scripts\release.ps1 -SkipBuild -SkipInstaller -SmokeTest`
- `pyi-archive_viewer -l dist\QuickShot.exe` has no `_avif`, `Avif`, or `AVIF` entries.

### Qt PDF Runtime DLL

The `PyQt6\Qt6\bin\Qt6Pdf.dll` runtime DLL is excluded from PyInstaller binaries because QuickShot does not import `QtPdf`, `QPdf`, or PDF-specific APIs. The small `PyQt6\Qt6\plugins\imageformats\qpdf.dll` image-format plugin remains bundled and is unrelated to this runtime DLL.

Result:

| Metric | Before | After | Saved |
| --- | ---: | ---: | ---: |
| `dist\QuickShot.exe` | 106,488,532 | 104,028,218 | 2,460,314 bytes / 2.35 MiB |
| `installer_output\QuickShot-5.3.0-Setup.exe` | 107,685,743 | 105,248,264 | 2,437,479 bytes / 2.32 MiB |
| Archive entries | 275 | 274 | 1 entry |

Verification:

- `python -m pyflakes quickshot launcher.py build_config.py`
- `python -m compileall -q quickshot launcher.py build_config.py`
- `python -m pytest -q`: `471 passed, 37 subtests passed`
- `powershell -ExecutionPolicy Bypass -File .\scripts\release.ps1 -SkipInstall -Clean`
- `powershell -ExecutionPolicy Bypass -File .\scripts\release.ps1 -SkipBuild -SkipInstaller -SmokeTest`
- `pyi-archive_viewer -l dist\QuickShot.exe` has no `Qt6Pdf.dll` entry.

Cumulative result after the first two experiments:

| Artifact | Original | Current | Saved |
| --- | ---: | ---: | ---: |
| `dist\QuickShot.exe` | 110,809,410 | 104,028,218 | 6,781,192 bytes / 6.47 MiB |
| `installer_output\QuickShot-5.3.0-Setup.exe` | 112,000,513 | 105,248,264 | 6,752,249 bytes / 6.44 MiB |

### Qt Software OpenGL Fallback DLL

The `PyQt6\Qt6\bin\opengl32sw.dll` fallback DLL is excluded from PyInstaller binaries because QuickShot does not import OpenGL, QtOpenGL, QtQuick, or QML APIs.

Result:

| Metric | Before | After | Saved |
| --- | ---: | ---: | ---: |
| `dist\QuickShot.exe` | 104,028,218 | 96,386,837 | 7,641,381 bytes / 7.29 MiB |
| `installer_output\QuickShot-5.3.0-Setup.exe` | 105,248,264 | 97,642,080 | 7,606,184 bytes / 7.25 MiB |
| Archive entries | 274 | 273 | 1 entry |

Verification:

- `python -m pyflakes quickshot launcher.py build_config.py`
- `python -m compileall -q quickshot launcher.py build_config.py`
- `python -m pytest -q`: `471 passed, 37 subtests passed`
- `powershell -ExecutionPolicy Bypass -File .\scripts\release.ps1 -SkipInstall -Clean`
- `powershell -ExecutionPolicy Bypass -File .\scripts\release.ps1 -SkipBuild -SkipInstaller -SmokeTest`
- Extra packaged launch smoke with `QT_OPENGL=software`
- `pyi-archive_viewer -l dist\QuickShot.exe` has no `opengl32sw.dll`, `Qt6Pdf.dll`, or `_avif` entries.

Risk note:

- This is validated on the local Windows environment only.
- Before publishing a release with this exclusion, retest on remote desktop, VM, older GPU, and software-rendering fallback environments.

Cumulative result from the original baseline:

| Artifact | Original | Current | Saved |
| --- | ---: | ---: | ---: |
| `dist\QuickShot.exe` | 110,809,410 | 96,386,837 | 14,422,573 bytes / 13.75 MiB |
| `installer_output\QuickShot-5.3.0-Setup.exe` | 112,000,513 | 97,642,080 | 14,358,433 bytes / 13.69 MiB |

## Archive Breakdown

`pyi-archive_viewer -l dist\QuickShot.exe` reports 273 archive entries with 96,043,005 compressed bytes and 235,514,474 uncompressed bytes.

Largest compressed groups:

| Group | Entries | Compressed | Uncompressed | Notes |
| --- | ---: | ---: | ---: | --- |
| `cv2` | 12 | 25.26 MiB | 71.38 MiB | Used by blur annotations in `quickshot\overlay\_drawing.py`. |
| `PyQt6` | 127 | 17.75 MiB | 48.17 MiB | Main GUI runtime. Core, Gui, Widgets, Svg, and `qwindows.dll` are required. |
| `rapidocr_onnxruntime` | 7 | 11.77 MiB | 13.08 MiB | OCR model files. Required for local OCR and privacy detection. |
| `onnxruntime` | 3 | 11.49 MiB | 32.67 MiB | OCR inference runtime. Required while OCR is bundled. |
| `PYZ.pyz` | 1 | 6.47 MiB | 6.47 MiB | Python module archive. |
| `numpy.libs` | 2 | 6.29 MiB | 20.02 MiB | Mainly OpenBLAS. Pulled by NumPy wheel. |
| Python DLLs | 2 | 2.63 MiB | 6.53 MiB | Python runtime. |
| `numpy` | 12 | 2.09 MiB | 5.79 MiB | OCR image conversion, HDR capture, and blur support. |
| `libcrypto-3.dll` | 1 | 1.77 MiB | 4.99 MiB | Needed by network/security dependencies. |
| `PIL` | 5 | 1.29 MiB | 3.15 MiB | Used by HDR tone-fix image conversion; AVIF extension is excluded. |
| `Shapely.libs` | 3 | 1.21 MiB | 3.41 MiB | Likely RapidOCR geometry dependency; investigate before excluding. |
| `winrt` | 9 | 0.50 MiB | 1.49 MiB | Used by Windows Graphics Capture support. |

Largest individual files:

| File | Compressed | Uncompressed | Initial judgment |
| --- | ---: | ---: | --- |
| `cv2\cv2.pyd` | 25.25 MiB | 71.35 MiB | Large but currently used. Requires a code replacement before removal. |
| `rapidocr_onnxruntime\models\ch_PP-OCRv3_rec_infer.onnx` | 9.15 MiB | 10.20 MiB | Core OCR recognition model. |
| `PYZ.pyz` | 6.47 MiB | 6.47 MiB | General Python code archive. |
| `numpy.libs\libscipy_openblas64_*.dll` | 6.11 MiB | 19.47 MiB | Hard to remove while NumPy is used. |
| `onnxruntime\capi\onnxruntime_pybind11_state.pyd` | 5.88 MiB | 16.65 MiB | OCR runtime. |
| `onnxruntime\capi\onnxruntime.dll` | 5.60 MiB | 16.01 MiB | OCR runtime. |
| `PyQt6\Qt6\bin\Qt6Gui.dll` | 4.06 MiB | 9.15 MiB | Required. |
| `PyQt6\Qt6\bin\Qt6Core.dll` | 3.53 MiB | 9.99 MiB | Required. |
| `PyQt6\Qt6\bin\Qt6Widgets.dll` | 2.84 MiB | 6.29 MiB | Required. |

## Keep Bundled

Do not remove these without a feature change:

- PyQt6 Core, Gui, Widgets, Svg, and the Windows platform plugin. The app is a PyQt6 desktop app and `quickshot\overlay\icons.py` uses `PyQt6.QtSvg`.
- RapidOCR models and ONNX Runtime while local OCR/privacy detection remains a bundled feature.
- NumPy while OCR image conversion, HDR capture paths, WGC frame conversion, and blur annotations use NumPy arrays.
- `cv2\cv2.pyd` until blur annotations no longer call `cv2.GaussianBlur`.
- `email` from the standard library. `requests` and `urllib3` need `email.*` modules.
- `requests`, `keyring`, `libssl`, and `libcrypto` while upload, translation, and secret storage workflows remain bundled.
- `winrt` and `dxcam` while fast Windows capture and HDR capture paths are supported.

## Remaining Experiments

The low-risk binary exclusions have been applied. Remaining work is either small or requires code changes:

| Candidate | Potential saving | Why it may be safe | Validation focus |
| --- | ---: | --- | --- |
| Trim unused Qt translations | likely small | Many translation files are bundled, but each is small. | Installer language and app startup. Low priority. |

Do these as separate commits or feature branches so each size delta and regression risk is easy to isolate.

## Larger Projects

These can save more space, but require code changes:

- Replace the OpenCV blur implementation in `quickshot\overlay\_drawing.py` with a Qt/Pillow/NumPy implementation or make blur optional. This is the largest single opportunity, with about 25 MiB compressed tied to `cv2\cv2.pyd`.
- Make OCR an optional add-on or lazy external download. This can remove RapidOCR models plus ONNX Runtime from the default installer, roughly 23 MiB compressed, but it changes the out-of-box feature set.
- Reduce NumPy/OpenBLAS only after replacing the NumPy-dependent OCR, HDR, WGC, and blur paths. This is broad and should not be attempted as a packaging-only exclusion.
- Investigate why `Shapely.libs` is included. It is probably a RapidOCR dependency, and the current potential saving is small enough to treat as lower priority.

## Experiment Procedure

For each candidate exclusion:

1. Record the baseline `dist\QuickShot.exe` size.
2. Change only one exclusion at a time in `build_config.py` or `QuickShot.spec`.
3. Run:

```powershell
python -m pyflakes quickshot launcher.py build_config.py
python -m compileall -q quickshot launcher.py build_config.py
python -m pytest -q
powershell -ExecutionPolicy Bypass -File .\scripts\release.ps1 -SkipInstall -Clean
powershell -ExecutionPolicy Bypass -File .\scripts\release.ps1 -SkipBuild -SkipInstaller -SmokeTest
```

4. Compare `dist\QuickShot.exe`, `build\QuickShot\QuickShot.pkg`, and installer size.
5. Manually smoke-test region capture, window capture, overlay editing, blur annotation, OCR, privacy detection, pin window, export, and GitHub upload if credentials are configured.
6. For a published release, run `scripts\verify-release-installer.ps1` against the GitHub Release asset before marking the release verified.

Recommended trial order:

1. OpenCV blur replacement
2. Optional OCR packaging
3. NumPy/OpenBLAS reduction only after replacing NumPy-dependent code paths
