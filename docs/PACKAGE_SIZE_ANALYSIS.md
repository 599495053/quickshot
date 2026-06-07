# QuickShot Package Size Analysis

This document records the current Windows one-file PyInstaller size baseline and the safest order for future package-size experiments.

## Baseline

Measured from the current local build artifacts:

| Artifact | Bytes | Size |
| --- | ---: | ---: |
| `dist\QuickShot.exe` | 110,809,410 | 105.68 MiB |
| `build\QuickShot\QuickShot.pkg` | 110,481,730 | 105.36 MiB |
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

## Archive Breakdown

`pyi-archive_viewer -l dist\QuickShot.exe` reports 276 archive entries with 110,465,434 compressed bytes and 268,658,738 uncompressed bytes.

Largest compressed groups:

| Group | Entries | Compressed | Uncompressed | Notes |
| --- | ---: | ---: | ---: | --- |
| `PyQt6` | 129 | 27.39 MiB | 72.25 MiB | Main GUI runtime. Core, Gui, Widgets, Svg, and `qwindows.dll` are required. |
| `cv2` | 12 | 25.26 MiB | 71.38 MiB | Used by blur annotations in `quickshot\overlay\_drawing.py`. |
| `rapidocr_onnxruntime` | 7 | 11.77 MiB | 13.08 MiB | OCR model files. Required for local OCR and privacy detection. |
| `onnxruntime` | 3 | 11.49 MiB | 32.67 MiB | OCR inference runtime. Required while OCR is bundled. |
| `PYZ.pyz` | 1 | 6.47 MiB | 6.47 MiB | Python module archive. |
| `numpy.libs` | 2 | 6.29 MiB | 20.02 MiB | Mainly OpenBLAS. Pulled by NumPy wheel. |
| `PIL` | 6 | 5.41 MiB | 10.68 MiB | Used by HDR tone-fix image conversion. |
| `python314.dll` | 1 | 2.60 MiB | 6.46 MiB | Python runtime. |
| `numpy` | 12 | 2.09 MiB | 5.79 MiB | OCR image conversion, HDR capture, and blur support. |
| `libcrypto-3.dll` | 1 | 1.77 MiB | 4.99 MiB | Needed by network/security dependencies. |
| `Shapely.libs` | 3 | 1.21 MiB | 3.41 MiB | Likely RapidOCR geometry dependency; investigate before excluding. |
| `winrt` | 9 | 0.50 MiB | 1.49 MiB | Used by Windows Graphics Capture support. |

Largest individual files:

| File | Compressed | Uncompressed | Initial judgment |
| --- | ---: | ---: | --- |
| `cv2\cv2.pyd` | 25.25 MiB | 71.35 MiB | Large but currently used. Requires a code replacement before removal. |
| `rapidocr_onnxruntime\models\ch_PP-OCRv3_rec_infer.onnx` | 9.15 MiB | 10.20 MiB | Core OCR recognition model. |
| `PyQt6\Qt6\bin\opengl32sw.dll` | 7.29 MiB | 19.68 MiB | Candidate exclusion, but test remote desktop/software-rendering cases. |
| `PYZ.pyz` | 6.47 MiB | 6.47 MiB | General Python code archive. |
| `numpy.libs\libscipy_openblas64_*.dll` | 6.11 MiB | 19.47 MiB | Hard to remove while NumPy is used. |
| `onnxruntime\capi\onnxruntime_pybind11_state.pyd` | 5.88 MiB | 16.65 MiB | OCR runtime. |
| `onnxruntime\capi\onnxruntime.dll` | 5.60 MiB | 16.01 MiB | OCR runtime. |
| `PIL\_avif.cp314-win_amd64.pyd` | 4.12 MiB | 7.53 MiB | Candidate exclusion if AVIF support is not needed. |
| `PyQt6\Qt6\bin\Qt6Gui.dll` | 4.06 MiB | 9.15 MiB | Required. |
| `PyQt6\Qt6\bin\Qt6Core.dll` | 3.53 MiB | 9.99 MiB | Required. |
| `PyQt6\Qt6\bin\Qt6Widgets.dll` | 2.84 MiB | 6.29 MiB | Required. |
| `PyQt6\Qt6\bin\Qt6Pdf.dll` | 2.35 MiB | 4.40 MiB | Candidate exclusion; no source reference to QtPdf was found. |

## Keep Bundled

Do not remove these without a feature change:

- PyQt6 Core, Gui, Widgets, Svg, and the Windows platform plugin. The app is a PyQt6 desktop app and `quickshot\overlay\icons.py` uses `PyQt6.QtSvg`.
- RapidOCR models and ONNX Runtime while local OCR/privacy detection remains a bundled feature.
- NumPy while OCR image conversion, HDR capture paths, WGC frame conversion, and blur annotations use NumPy arrays.
- `cv2\cv2.pyd` until blur annotations no longer call `cv2.GaussianBlur`.
- `email` from the standard library. `requests` and `urllib3` need `email.*` modules.
- `requests`, `keyring`, `libssl`, and `libcrypto` while upload, translation, and secret storage workflows remain bundled.
- `winrt` and `dxcam` while fast Windows capture and HDR capture paths are supported.

## Safe Experiments First

These are the best first trials because they are localized and measurable:

| Candidate | Potential saving | Why it may be safe | Validation focus |
| --- | ---: | --- | --- |
| Exclude `PIL\_avif*.pyd` | ~4.12 MiB | QuickShot imports `PIL.Image`, but no AVIF-specific source reference was found. | Save/open PNG, JPEG, BMP, and WebP if supported; verify HDR tone-fix path. |
| Exclude `PyQt6\Qt6\bin\Qt6Pdf.dll` | ~2.35 MiB | No direct `QtPdf`, `QPdf`, or PDF source reference was found. | Full packaged UI smoke, settings, capture, overlay, OCR dialogs. |
| Exclude `PyQt6\Qt6\bin\opengl32sw.dll` | ~7.29 MiB | The app does not intentionally depend on Qt software OpenGL rendering. | Test local GPU, remote desktop, VM, and older display-driver environments. |
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

1. `PIL\_avif*.pyd`
2. `Qt6Pdf.dll`
3. `opengl32sw.dll`
4. OpenCV blur replacement
5. Optional OCR packaging
