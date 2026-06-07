# Changelog

All notable changes to QuickShot are tracked here.

## v5.3.1 - Unreleased

### Added

- Added `scripts/verify-release-installer.ps1` for GitHub Release installer verification.

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
