# Changelog

All notable changes to QuickShot are tracked here.

## Unreleased

### Added

- Added a packaged privacy OCR fallback self-test for release builds, with opt-in coverage for local installer, GitHub Release installer, and upgrade/reinstall verification.
- Added tests for the hidden packaged self-test entry point.

### Verified

- `python -m pytest -q`: `484 passed, 37 subtests passed`

## v5.3.2 - 2026-06-08

### Added

- Added installer upgrade and same-version reinstall regression verification.
- Added `docs/RELEASE_NOTES_v5.3.2.md` as the GitHub Release body.

### Changed

- Reduced Windows package size further by excluding unused PyQt6 Qt translation files.
- Updated release documentation and verification records for the v5.3.2 installer.

### Fixed

- Fixed smart privacy masking in lightweight builds by using Windows OCR line boxes when RapidOCR is unavailable.

### Verified

- `python -m pyflakes quickshot launcher.py build_config.py`
- `python -m compileall -q quickshot launcher.py build_config.py`
- `python -m pytest -q`: `478 passed, 37 subtests passed`
- `powershell -ExecutionPolicy Bypass -File .\scripts\release.ps1 -SkipInstall -Clean`
- `powershell -ExecutionPolicy Bypass -File .\scripts\release.ps1 -SkipBuild -SkipInstaller -SmokeTest`
- `powershell -ExecutionPolicy Bypass -File .\scripts\verify-local-installer.ps1 -RemoveExisting`
- `powershell -ExecutionPolicy Bypass -File .\scripts\verify-upgrade-installer.ps1 -PreviousInstallerPath .\installer_output\QuickShot-5.3.1-Setup.exe -PreviousVersion 5.3.1`

## v5.3.1 - 2026-06-08

### Added

- Added `scripts/verify-release-installer.ps1` for GitHub Release installer verification.
- Added `scripts/verify-local-installer.ps1` for local installer install, launch, and uninstall verification before publishing.
- Added `docs/PACKAGE_SIZE_ANALYSIS.md` with the current PyInstaller size baseline and optimization experiment plan.
- Added `docs/RELEASE_NOTES_v5.3.1.md` as the draft GitHub Release body and publishing checklist.

### Changed

- Reduced Windows package size by excluding Pillow's unused AVIF extension from the PyInstaller bundle.
- Reduced Windows package size further by excluding the unused Qt PDF runtime DLL from the PyInstaller bundle.
- Reduced Windows package size further by excluding the unused Qt software OpenGL fallback DLL from the PyInstaller bundle.
- Replaced OpenCV-backed blur annotations with Pillow Gaussian blur and removed `opencv-python` from runtime dependencies.
- Made RapidOCR/ONNX Runtime an optional OCR add-on; default text OCR keeps using Windows system OCR, while smart privacy auto-detection requires the optional add-on.
- Improved packaged smoke-test cleanup so PyInstaller child processes do not keep `dist\QuickShot.exe` locked.

### Planned

- Add code signing when a signing certificate is available.
- Improve release notes and public download instructions.
- Add more installer regression checks around upgrade and reinstall flows.
- Continue reducing packaged artifact size.
- Triage user feedback from the v5.3.0 release.

## v5.3.0 - 2026-06-08

### Added

- Added Inno Setup installer packaging with Simplified Chinese language support.
- Added release automation via `scripts/release.ps1`.
- Added version synchronization via `scripts/set-version.ps1`.
- Added GitHub Actions CI for Windows quality checks.
- Added optional code signing support to the release script.
- Added GitHub Release verification records to the release checklist.

### Changed

- Refreshed project documentation and release checklist.
- Improved capture, overlay editing, OCR, history, pin, and translation workflows.
- Improved overlay performance, selection snapping, picker support, and edit hotkeys.

### Fixed

- Fixed fallback hotkey modifier polling.
- Fixed startup toggle import wiring.
- Fixed post-capture clipboard notification threading.
- Fixed OCR result dialog stability.
- Fixed settings import sync for optional hotkeys.

### Verified

- `python -m pyflakes quickshot launcher.py build_config.py`
- `python -m compileall -q quickshot launcher.py build_config.py`
- `python -m pytest -q`: `471 passed, 37 subtests passed`
- PyInstaller build passed.
- Inno Setup build passed.
- Packaged smoke test passed.
- GitHub Release installer download, install, launch, and uninstall verification passed.
