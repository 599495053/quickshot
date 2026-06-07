# QuickShot Package Size Analysis

This document records the current Windows one-file PyInstaller size baseline and the safest order for future package-size experiments.

## Baseline

Measured from the current local build artifacts:

| Artifact | Bytes | Size |
| --- | ---: | ---: |
| `dist\QuickShot.exe` | 31,624,497 | 30.16 MiB |
| `installer_output\QuickShot-5.3.2-Setup.exe` | 33,405,382 | 31.86 MiB |
| `build\QuickShot\QuickShot.pkg` | 31,296,817 | 29.85 MiB |
| `build\QuickShot\PYZ-00.pyz` | 4,990,820 | 4.76 MiB |
| `build\QuickShot\base_library.zip` | 1,386,064 | 1.32 MiB |

Toolchain and major package versions:

| Package | Version |
| --- | --- |
| PyInstaller | 6.20.0 |
| PyQt6 | 6.11.0 |
| Pillow | 12.2.0 |
| requests | 2.34.2 |
| keyring | 25.7.0 |
| deep-translator | 1.11.4 |

The current `QuickShot.spec` uses `optimize=1`, `upx=True`, app asset data collection, and the shared exclusions in `build_config.py`. RapidOCR/ONNX Runtime and dxcam/NumPy/WinRT HDR capture support are optional add-ons and are not bundled in the default Windows package. Unused Qt translation files are excluded from both PyInstaller binary and data entries.

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

### OpenCV Blur Replacement

Blur annotations now use Pillow's `ImageFilter.GaussianBlur` instead of OpenCV. `opencv-python` is removed from runtime dependencies, and `cv2` is explicitly excluded from the PyInstaller module graph as a guard against optional transitive imports.

Result:

| Metric | Before | After | Saved |
| --- | ---: | ---: | ---: |
| `dist\QuickShot.exe` | 96,386,837 | 69,899,579 | 26,487,258 bytes / 25.26 MiB |
| `installer_output\QuickShot-5.3.0-Setup.exe` | 97,642,080 | 71,302,926 | 26,339,154 bytes / 25.12 MiB |
| Archive entries | 273 | 261 | 12 entries |

Verification:

- `python -m pyflakes quickshot launcher.py build_config.py`
- `python -m compileall -q quickshot launcher.py build_config.py`
- `python -m pytest -q`: `472 passed, 37 subtests passed`
- `python -m pytest tests\test_overlay_postprocess.py -q`: `12 passed`
- `powershell -ExecutionPolicy Bypass -File .\scripts\release.ps1 -SkipInstall -Clean`
- `powershell -ExecutionPolicy Bypass -File .\scripts\release.ps1 -SkipBuild -SkipInstaller -SmokeTest`
- `pyi-archive_viewer -l dist\QuickShot.exe` has no `cv2`, `opencv`, `opengl32sw.dll`, `Qt6Pdf.dll`, or `_avif` entries.

Cumulative result from the original baseline:

| Artifact | Original | Current | Saved |
| --- | ---: | ---: | ---: |
| `dist\QuickShot.exe` | 110,809,410 | 69,899,579 | 40,909,831 bytes / 39.01 MiB |
| `installer_output\QuickShot-5.3.0-Setup.exe` | 112,000,513 | 71,302,926 | 40,697,587 bytes / 38.81 MiB |

### Optional RapidOCR Packaging

RapidOCR and ONNX Runtime are now optional OCR add-ons instead of default runtime dependencies. The default package keeps Windows system OCR available, and v5.3.2 adds a Windows OCR line-box fallback for smart privacy masking when RapidOCR is unavailable. Local RapidOCR can still be enabled in source/custom builds with `pip install -e .[ocr]` for the in-process OCR path.

Result:

| Metric | Before | After | Saved |
| --- | ---: | ---: | ---: |
| `dist\QuickShot.exe` | 69,899,579 | 43,532,731 | 26,366,848 bytes / 25.15 MiB |
| `installer_output\QuickShot-5.3.1-Setup.exe` | 71,302,926 | 45,265,412 | 26,037,514 bytes / 24.83 MiB |
| Archive entries | 261 | 243 | 18 entries |

Verification:

- `python -m pyflakes quickshot launcher.py build_config.py`
- `python -m compileall -q quickshot launcher.py build_config.py`
- `python -m pytest tests\test_ocr_utils.py -q`: `50 passed`
- `python -m pytest -q`: `478 passed, 37 subtests passed`
- `python -m pip check`: `No broken requirements found.`
- `powershell -ExecutionPolicy Bypass -File .\scripts\release.ps1 -SkipInstall -Clean`
- `powershell -ExecutionPolicy Bypass -File .\scripts\release.ps1 -SkipBuild -SkipInstaller -SmokeTest`
- `pyi-archive_viewer -l dist\QuickShot.exe` has no `rapidocr_onnxruntime`, `onnxruntime`, `.onnx`, `Shapely`, `pyclipper`, `cv2`, `opencv`, `opengl32sw.dll`, `Qt6Pdf.dll`, or `_avif` entries.

Cumulative result from the original baseline:

| Artifact | Original | Current | Saved |
| --- | ---: | ---: | ---: |
| `dist\QuickShot.exe` | 110,809,410 | 43,532,731 | 67,276,679 bytes / 64.16 MiB |
| `installer_output\QuickShot-5.3.1-Setup.exe` | 112,000,513 | 45,265,412 | 66,735,101 bytes / 63.64 MiB |

### Qt Translation Files

PyInstaller's PyQt6 hooks collect many `PyQt6\Qt6\translations\*.qm` files. QuickShot does not install a `QTranslator`, and the installer language files are handled separately by Inno Setup, so these Qt runtime translation files are excluded from both `a.binaries` and `a.datas`.

Result:

| Metric | Before | After | Saved |
| --- | ---: | ---: | ---: |
| `dist\QuickShot.exe` | 43,532,731 | 41,601,767 | 1,930,964 bytes / 1.84 MiB |
| `installer_output\QuickShot-5.3.2-Setup.exe` | 45,265,412 | 43,339,059 | 1,926,353 bytes / 1.84 MiB |
| Archive entries | 243 | 147 | 96 entries |

Verification:

- `python -m pytest tests\test_build_config.py -q`: `2 passed`
- `python -m pyflakes quickshot launcher.py build_config.py tests\test_build_config.py`
- `python -m compileall -q quickshot launcher.py build_config.py tests\test_build_config.py`
- `python -m pytest -q`: `478 passed, 37 subtests passed`
- `powershell -ExecutionPolicy Bypass -File .\scripts\release.ps1 -SkipInstall -Clean`
- `powershell -ExecutionPolicy Bypass -File .\scripts\release.ps1 -SkipBuild -SkipInstaller -SmokeTest`
- `powershell -ExecutionPolicy Bypass -File .\scripts\verify-local-installer.ps1 -RemoveExisting`
- `powershell -ExecutionPolicy Bypass -File .\scripts\verify-upgrade-installer.ps1 -PreviousInstallerPath .\installer_output\QuickShot-5.3.1-Setup.exe -PreviousVersion 5.3.1`
- `pyi-archive_viewer -l dist\QuickShot.exe` has no `PyQt6\Qt6\translations` or `.qm` entries.

Cumulative result from the original baseline:

| Artifact | Original | Current | Saved |
| --- | ---: | ---: | ---: |
| `dist\QuickShot.exe` | 110,809,410 | 41,601,767 | 69,207,643 bytes / 66.00 MiB |
| `installer_output\QuickShot-5.3.2-Setup.exe` | 112,000,513 | 43,339,059 | 68,661,454 bytes / 65.48 MiB |

### Optional HDR/NumPy Packaging

The default packaged app now uses the `mss` capture backend and keeps dxcam, NumPy, OpenBLAS, and WinRT HDR capture support as the optional `hdr` source/custom-build extra. The HDR-accurate capture setting still fails closed: when optional dependencies are unavailable, QuickShot logs the missing path and falls back to the normal `mss` capture path.

Result:

| Metric | Before | After | Saved |
| --- | ---: | ---: | ---: |
| `dist\QuickShot.exe` | 41,601,767 | 31,624,497 | 9,977,270 bytes / 9.52 MiB |
| `installer_output\QuickShot-5.3.2-Setup.exe` | 43,339,059 | 33,405,382 | 9,933,677 bytes / 9.47 MiB |
| Archive entries | 147 | 124 | 23 entries |

Verification:

- `python -m pytest tests\test_build_config.py -q`: `4 passed`
- `python -m pyflakes quickshot launcher.py build_config.py tests\test_build_config.py tests\test_selftest.py`
- `python -m compileall -q quickshot launcher.py build_config.py tests\test_build_config.py tests\test_selftest.py`
- `python -m pytest -q`: `488 passed, 37 subtests passed`
- `powershell -ExecutionPolicy Bypass -File .\scripts\release.ps1 -SkipInstall -Clean`
- `pyi-archive_viewer -l dist\QuickShot.exe` has no `numpy`, `numpy.libs`, `openblas`, `dxcam`, `winrt`, `rapidocr`, `onnxruntime`, `cv2`, `opencv`, `Qt6Pdf`, `opengl32sw`, or `_avif` entries.
- `powershell -ExecutionPolicy Bypass -File .\scripts\release.ps1 -SkipBuild -SkipInstaller -SmokeTest`
- `powershell -ExecutionPolicy Bypass -File .\scripts\verify-desktop-hotkeys.ps1 -ExePath .\dist\QuickShot.exe -StopExisting`

Cumulative result from the original baseline:

| Artifact | Original | Current | Saved |
| --- | ---: | ---: | ---: |
| `dist\QuickShot.exe` | 110,809,410 | 31,624,497 | 79,184,913 bytes / 75.52 MiB |
| `installer_output\QuickShot-5.3.2-Setup.exe` | 112,000,513 | 33,405,382 | 78,595,131 bytes / 74.95 MiB |

## Archive Breakdown

`pyi-archive_viewer -l dist\QuickShot.exe` reports 124 archive entries with 31,290,425 compressed bytes and 72,700,073 uncompressed bytes.

Largest compressed groups:

| Group | Entries | Compressed | Uncompressed | Notes |
| --- | ---: | ---: | ---: | --- |
| `PyQt6` | 31 | 15.92 MiB | 41.78 MiB | Main GUI runtime. Core, Gui, Widgets, Svg, and `qwindows.dll` are required; Qt translations are excluded. |
| Python/runtime DLLs | 30 | 6.27 MiB | 15.78 MiB | Python runtime plus common SSL/standard-library extension DLLs. |
| `PYZ.pyz` | 1 | 4.76 MiB | 4.76 MiB | Python module archive. |
| `PIL` | 6 | 2.24 MiB | 5.21 MiB | Used by blur annotation and image conversion; AVIF extension is excluded. |
| Root modules/hooks | 56 | 0.65 MiB | 1.80 MiB | Launcher, PyInstaller runtime hooks, and root-level modules. |

Largest individual files:

| File | Compressed | Uncompressed | Initial judgment |
| --- | ---: | ---: | --- |
| `PYZ.pyz` | 4.76 MiB | 4.76 MiB | General Python code archive. |
| `PyQt6\Qt6\bin\Qt6Gui.dll` | 4.06 MiB | 9.15 MiB | Required. |
| `PyQt6\Qt6\bin\Qt6Core.dll` | 3.53 MiB | 9.99 MiB | Required. |
| `PyQt6\Qt6\bin\Qt6Widgets.dll` | 2.84 MiB | 6.29 MiB | Required. |
| `python314.dll` | 2.60 MiB | 6.46 MiB | Required Python runtime. |
| `libcrypto-3.dll` | 1.77 MiB | 4.99 MiB | Needed by network/security dependencies. |
| `PyQt6\QtWidgets.pyd` | 1.20 MiB | 4.84 MiB | Required PyQt6 bindings. |
| `PIL\_imaging.cp314-win_amd64.pyd` | 0.96 MiB | 2.46 MiB | Required by Pillow image operations. |

## Keep Bundled

Do not remove these without a feature change:

- PyQt6 Core, Gui, Widgets, Svg, and the Windows platform plugin. The app is a PyQt6 desktop app and `quickshot\overlay\icons.py` uses `PyQt6.QtSvg`.
- Windows OCR support assets. The default package still provides OCR through the Windows system OCR path.
- Pillow while blur annotations and HDR tone-fix image conversion use Pillow image processing.
- `email` from the standard library. `requests` and `urllib3` need `email.*` modules.
- `requests`, `keyring`, `libssl`, and `libcrypto` while upload, translation, and secret storage workflows remain bundled.

## Optional Add-Ons

Keep these outside the default installer unless user demand makes a separate flavor worthwhile:

- `rapidocr_onnxruntime`, ONNX Runtime, and NumPy for in-process RapidOCR.
- dxcam, NumPy/OpenBLAS, and WinRT HDR capture modules for the optional `hdr` extra.

## Remaining Experiments

The low-risk packaging-only exclusions have been applied. Remaining package-size work requires feature-level code changes or a deliberate packaging split.

## Larger Projects

These can save more space, but require code changes:

- Consider a separate RapidOCR-enabled installer flavor only if users need smart privacy auto-detection out of the box. Keep the default installer light unless that feature becomes core.
- Consider a separate HDR/advanced-capture installer flavor only if users need the dxcam/WGC HDR path out of the box. Keep the default installer on `mss` unless that feature becomes core.

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
5. Manually smoke-test region capture, window capture, overlay editing, blur annotation, Windows OCR, optional RapidOCR/privacy detection when the add-on is installed, pin window, export, and GitHub upload if credentials are configured.
6. For a published release, run `scripts\verify-release-installer.ps1` against the GitHub Release asset before marking the release verified.

Recommended trial order:

1. Optional RapidOCR-enabled installer flavor, only if needed
2. Optional HDR/advanced-capture installer flavor, only if needed
