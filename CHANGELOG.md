# Changelog

All notable changes to QuickShot are tracked here.

## v5.3.1 - Unreleased

### Added

- Added `scripts/verify-release-installer.ps1` for GitHub Release installer verification.
- Added `docs/PACKAGE_SIZE_ANALYSIS.md` with the current PyInstaller size baseline and optimization experiment plan.
- Added `docs/RELEASE_NOTES_v5.3.1.md` as the draft GitHub Release body and publishing checklist.

### Changed

- Reduced Windows package size by excluding Pillow's unused AVIF extension from the PyInstaller bundle.
- Reduced Windows package size further by excluding the unused Qt PDF runtime DLL from the PyInstaller bundle.
- Reduced Windows package size further by excluding the unused Qt software OpenGL fallback DLL from the PyInstaller bundle.
- Replaced OpenCV-backed blur annotations with Pillow Gaussian blur and removed `opencv-python` from runtime dependencies.
- Made RapidOCR/ONNX Runtime an optional OCR add-on so the default Windows package uses the system OCR fallback and reports smart privacy masking as unavailable when the add-on is missing.
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
