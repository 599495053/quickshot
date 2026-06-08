# Changelog

All notable changes to QuickShot are tracked here.

## Unreleased

### Added

- Added a settings-page workflow summary showing the current preset and Enter behavior.
- Added a settings-page action to restore the default workflow.
- Added a GitHub uploader status hint in settings so missing owner, repo, or token is visible before capture.

### Changed

- Workflow changes made from settings now refresh the tray tooltip and workflow menu.
- Upload workflow failures now include more actionable configuration, permission, token, and network guidance.

## v5.3.7 - 2026-06-08

### Added

- Added a tray menu workflow preset switcher for quick copy, auto save, OCR, publish, and privacy-first flows.
- Added `docs/RELEASE_NOTES_v5.3.7.md` as the GitHub Release body.

### Changed

- Screenshot selection messages now include the current workflow behavior so users can see what Enter will do.

### Verified

- `python -m pyflakes quickshot tests\test_workflow_presets.py tests\test_main.py tests\test_overlay_selection.py`
- `python -m compileall -q quickshot tests\test_workflow_presets.py tests\test_main.py tests\test_overlay_selection.py`
- `python -m pytest -q tests\test_workflow_presets.py tests\test_main.py tests\test_overlay_selection.py tests\test_settings.py`: `70 passed, 4 subtests passed`
- `python -m pytest -q`: `522 passed, 37 subtests passed`
- `powershell -ExecutionPolicy Bypass -File .\scripts\release.ps1 -SkipInstall -Clean`: v5.3.7 release build passed; generated unsigned `dist\QuickShot.exe` SHA256 `B4DB6F4C1B335CA5F4267752CF28F1AEED13764F05AB24458A5D173EF19A7B41` and unsigned `installer_output\QuickShot-5.3.7-Setup.exe` SHA256 `5BD5987E360832B90EA5BF1FD160B5CDC30CE954D96F2AD5B88CBB01494BB77B`.
- `powershell -ExecutionPolicy Bypass -File .\scripts\release.ps1 -SkipBuild -SkipInstaller -SmokeTest`: packaged smoke, privacy OCR fallback, overlay edit, and capture backend self-tests passed.
- `powershell -ExecutionPolicy Bypass -File .\scripts\verify-artifact-signature.ps1 .\dist\QuickShot.exe .\installer_output\QuickShot-5.3.7-Setup.exe -ExpectedStatus NotSigned`
- `powershell -ExecutionPolicy Bypass -File .\scripts\verify-upgrade-installer.ps1 -PreviousInstallerPath .\installer_output\QuickShot-5.3.6-Setup.exe -PreviousVersion 5.3.6 -RemoveExisting -PrivacySelfTest -OverlaySelfTest -CaptureSelfTest`: local v5.3.6 to v5.3.7 upgrade and v5.3.7 same-version reinstall passed.
- `powershell -ExecutionPolicy Bypass -File .\scripts\verify-local-installer.ps1 -RemoveExisting -PrivacySelfTest -OverlaySelfTest -CaptureSelfTest`: local installer install, launch, self-test, and uninstall passed.
- `powershell -ExecutionPolicy Bypass -File .\scripts\verify-desktop-hotkeys.ps1 -ExePath .\dist\QuickShot.exe -StopExisting`: region and current-window hotkey capture passed.
- `pyi-archive_viewer -l dist\QuickShot.exe`: no `numpy`, `numpy.libs`, `openblas`, `dxcam`, `winrt`, `rapidocr`, `onnxruntime`, `cv2`, `opencv`, `Qt6Pdf`, `opengl32sw`, or `_avif` entries.

### Package Size

- `dist\QuickShot.exe`: `31,654,804` bytes / `30.19 MiB`.
- `installer_output\QuickShot-5.3.7-Setup.exe`: `33,434,302` bytes / `31.89 MiB`.

## v5.3.6 - 2026-06-08

### Added

- Added screenshot workflow presets for quick copy, auto save, OCR, publish, and privacy-first capture flows.
- Added silent default-directory auto-save for post-capture workflows.
- Added `docs/RELEASE_NOTES_v5.3.6.md` as the GitHub Release body.

### Changed

- Privacy-first workflows now start smart masking review before copying any unmasked screenshot to the clipboard.

### Verified

- `python -m pyflakes quickshot launcher.py build_config.py`
- `python -m compileall -q quickshot launcher.py build_config.py`
- `python -m pyflakes quickshot tests\test_workflow_presets.py tests\test_config.py tests\test_settings.py tests\test_overlay_export.py tests\test_overlay_selection.py tests\test_pipeline.py`
- `python -m compileall -q quickshot tests\test_workflow_presets.py tests\test_config.py tests\test_settings.py tests\test_overlay_export.py tests\test_overlay_selection.py tests\test_pipeline.py`
- `python -m pytest -q tests\test_workflow_presets.py tests\test_config.py tests\test_settings.py tests\test_settings_extended.py tests\test_overlay_export.py tests\test_overlay_selection.py tests\test_pipeline.py`: `125 passed, 4 subtests passed`
- `python -m pytest -q`: `517 passed, 37 subtests passed`
- `powershell -ExecutionPolicy Bypass -File .\scripts\release.ps1 -SkipInstall -Clean`: v5.3.6 release build passed; generated unsigned `dist\QuickShot.exe` SHA256 `6B23CA2A11B2DEC28929C9AF16093DA31F3CE9366CA5A6FACAE18E2AB1271295` and unsigned `installer_output\QuickShot-5.3.6-Setup.exe` SHA256 `7D960B5111783F51A5AA2F073B8BED3188502168196D312E25303EDA01B866F1`.
- `powershell -ExecutionPolicy Bypass -File .\scripts\release.ps1 -SkipBuild -SkipInstaller -SmokeTest`: packaged smoke, privacy OCR fallback, overlay edit, and capture backend self-tests passed.
- `powershell -ExecutionPolicy Bypass -File .\scripts\verify-artifact-signature.ps1 .\dist\QuickShot.exe .\installer_output\QuickShot-5.3.6-Setup.exe -ExpectedStatus NotSigned`
- `powershell -ExecutionPolicy Bypass -File .\scripts\verify-upgrade-installer.ps1 -PreviousInstallerPath .\installer_output\QuickShot-5.3.5-Setup.exe -PreviousVersion 5.3.5 -RemoveExisting -PrivacySelfTest -OverlaySelfTest -CaptureSelfTest`: local v5.3.5 to v5.3.6 upgrade and v5.3.6 same-version reinstall passed.
- `powershell -ExecutionPolicy Bypass -File .\scripts\verify-local-installer.ps1 -RemoveExisting -PrivacySelfTest -OverlaySelfTest -CaptureSelfTest`: local installer install, launch, self-test, and uninstall passed.
- `powershell -ExecutionPolicy Bypass -File .\scripts\verify-desktop-hotkeys.ps1 -ExePath .\dist\QuickShot.exe -StopExisting`: region and current-window hotkey capture passed.
- `pyi-archive_viewer -l dist\QuickShot.exe`: no `numpy`, `numpy.libs`, `openblas`, `dxcam`, `winrt`, `rapidocr`, `onnxruntime`, `cv2`, `opencv`, `Qt6Pdf`, `opengl32sw`, or `_avif` entries.

### Package Size

- `dist\QuickShot.exe`: `31,651,170` bytes / `30.18 MiB`.
- `installer_output\QuickShot-5.3.6-Setup.exe`: `33,431,838` bytes / `31.88 MiB`.

## v5.3.5 - 2026-06-08

### Added

- Added a smart privacy masking review step: detected privacy regions are shown as editable preview boxes and are only mosaicked after confirmation.
- Added `docs/RELEASE_NOTES_v5.3.5.md` as the GitHub Release body.

### Changed

- Screenshot export actions now block while smart privacy masking preview is active, preventing accidental copy/save/pin of an unmasked image.

### Verified

- `python -m pyflakes quickshot launcher.py build_config.py tests\test_overlay_events.py tests\test_selftest.py`
- `python -m compileall -q quickshot launcher.py build_config.py tests\test_overlay_events.py`
- `python -m pytest -q`: `505 passed, 37 subtests passed`
- `powershell -ExecutionPolicy Bypass -File .\scripts\verify-artifact-signature.ps1 .\dist\QuickShot.exe .\installer_output\QuickShot-5.3.5-Setup.exe -ExpectedStatus NotSigned`
- `powershell -ExecutionPolicy Bypass -File .\scripts\release.ps1 -SkipInstall -Clean`: v5.3.5 release build passed; generated unsigned `dist\QuickShot.exe` SHA256 `1FAE3BB843F542E47FE7CD338FD8BE91EA03526A2B22214FB9BBBAA44D43CB7E` and unsigned `installer_output\QuickShot-5.3.5-Setup.exe` SHA256 `3F30E0CD67D14F689A29EB497F19273032606742C435B1127C5D7635D19F2BC7`.
- `powershell -ExecutionPolicy Bypass -File .\scripts\release.ps1 -SkipBuild -SkipInstaller -SmokeTest`: packaged smoke, privacy OCR fallback, overlay edit, and capture backend self-tests passed.
- `powershell -ExecutionPolicy Bypass -File .\scripts\verify-local-installer.ps1 -RemoveExisting -PrivacySelfTest -OverlaySelfTest -CaptureSelfTest`: local installer install, launch, self-test, and uninstall passed.
- `powershell -ExecutionPolicy Bypass -File .\scripts\verify-upgrade-installer.ps1 -PreviousInstallerPath <downloaded v5.3.4 installer> -PreviousVersion 5.3.4 -RemoveExisting -PrivacySelfTest -OverlaySelfTest -CaptureSelfTest`: published v5.3.4 to v5.3.5 upgrade and v5.3.5 same-version reinstall passed.
- `powershell -ExecutionPolicy Bypass -File .\scripts\verify-desktop-hotkeys.ps1 -ExePath .\dist\QuickShot.exe -StopExisting`: region and current-window hotkey capture passed.
- `pyi-archive_viewer -l dist\QuickShot.exe`: no `numpy`, `numpy.libs`, `openblas`, `dxcam`, `winrt`, `rapidocr`, `onnxruntime`, `cv2`, `opencv`, `Qt6Pdf`, `opengl32sw`, or `_avif` entries.
- `powershell -ExecutionPolicy Bypass -File .\scripts\set-version.ps1 -Version 5.3.5 -CheckOnly`

### Package Size

- `dist\QuickShot.exe`: `31,644,753` bytes / `30.18 MiB`.
- `installer_output\QuickShot-5.3.5-Setup.exe`: `33,425,937` bytes / `31.88 MiB`.

## v5.3.4 - 2026-06-08

### Added

- Added public repository badges, installer verification guidance, feedback links, MIT license text, security policy, and GitHub issue templates.
- Added `scripts/verify-artifact-signature.ps1` for explicit Authenticode status checks on release artifacts.
- Added an in-app "copy diagnostic info" action for tray and settings feedback flows.
- Added shared user-facing error feedback helpers with diagnostic-copy guidance.
- Added `docs/RELEASE_NOTES_v5.3.4.md` as the GitHub Release body.

### Changed

- Release manifests generated by `scripts/release.ps1` now include executable and installer Authenticode signature status.
- Bug reports now include a dedicated diagnostic info field.
- Screenshot, OCR, smart privacy masking, save, pin, and post-capture workflow failures now show clearer next-step guidance.
- Refreshed the README workflow preview image and public download instructions for v5.3.4.
- Updated CI to `actions/checkout@v6`, `actions/setup-python@v6`, and the pinned `windows-2025-vs2026` runner.

### Verified

- Workflow YAML parse check.
- GitHub issue template YAML parse check.
- PowerShell parser check for build and release scripts.
- Markdown local link and image reference check.
- `powershell -ExecutionPolicy Bypass -File .\scripts\verify-artifact-signature.ps1 .\dist\QuickShot.exe .\installer_output\QuickShot-5.3.4-Setup.exe -ExpectedStatus NotSigned`
- `powershell -ExecutionPolicy Bypass -File .\scripts\release.ps1 -SkipBuild -SkipInstaller -SmokeTest`: `497 passed, 37 subtests passed`; packaged smoke, privacy OCR fallback, overlay edit, and capture backend self-tests passed.
- `powershell -ExecutionPolicy Bypass -File .\scripts\release.ps1 -SkipInstall -Clean`: v5.3.4 release build passed; generated unsigned `dist\QuickShot.exe` SHA256 `1BFA72CA4DA2F91961190F78DF05C509C2404D2314E0B5D56275AC8BC7766663` and unsigned `installer_output\QuickShot-5.3.4-Setup.exe` SHA256 `65693568E293608FD39096241362A95A6DB1722B74CE282BDC4C7CCCA3FA4685`.
- `powershell -ExecutionPolicy Bypass -File .\scripts\verify-local-installer.ps1 -RemoveExisting -PrivacySelfTest -OverlaySelfTest -CaptureSelfTest`: post-release local installer install, launch, self-test, and uninstall passed.
- `powershell -ExecutionPolicy Bypass -File .\scripts\verify-upgrade-installer.ps1 -PreviousInstallerPath <downloaded v5.3.3 installer> -PreviousVersion 5.3.3 -RemoveExisting -PrivacySelfTest -OverlaySelfTest -CaptureSelfTest`: published v5.3.3 to v5.3.4 upgrade and v5.3.4 same-version reinstall passed.
- `powershell -ExecutionPolicy Bypass -File .\scripts\verify-desktop-hotkeys.ps1 -ExePath .\dist\QuickShot.exe -StopExisting`: region and current-window hotkey capture passed.
- `pyi-archive_viewer -l dist\QuickShot.exe`: no `numpy`, `numpy.libs`, `openblas`, `dxcam`, `winrt`, `rapidocr`, `onnxruntime`, `cv2`, `opencv`, `Qt6Pdf`, `opengl32sw`, or `_avif` entries.
- `powershell -ExecutionPolicy Bypass -File .\scripts\set-version.ps1 -Version 5.3.4 -CheckOnly`
- `python -m pyflakes quickshot launcher.py build_config.py tests\test_build_config.py tests\test_selftest.py`
- `python -m compileall -q quickshot launcher.py build_config.py tests\test_build_config.py tests\test_selftest.py`
- `python -m pytest -q tests\test_feedback.py tests\test_overlay_events.py tests\test_overlay_export.py`: `51 passed`
- `python -m pytest -q`: `497 passed, 37 subtests passed`

### Package Size

- `dist\QuickShot.exe`: `31,633,183` bytes / `30.17 MiB`.
- `installer_output\QuickShot-5.3.4-Setup.exe`: `33,414,015` bytes / `31.87 MiB`.

## v5.3.3 - 2026-06-08

### Added

- Added packaged privacy OCR fallback, overlay edit smoke, and capture backend smoke self-tests for release builds, with opt-in coverage for local installer, GitHub Release installer, and upgrade/reinstall verification.
- Added tests for the hidden packaged self-test entry point.
- Added local desktop verification for tray startup and real global hotkey capture flows.
- Added optional `hdr` extra for dxcam/NumPy/WinRT HDR capture support in source and custom builds.

### Changed

- Removed NumPy, OpenBLAS, dxcam, and WinRT capture dependencies from the default runtime package.
- Default packaged builds now rely on the lightweight `mss` capture backend and fall back cleanly when optional HDR capture dependencies are unavailable.

### Verified

- `powershell` parser check for build and verification scripts.
- `python -m pyflakes quickshot launcher.py build_config.py tests\test_build_config.py tests\test_selftest.py`
- `python -m compileall -q quickshot launcher.py build_config.py tests\test_build_config.py tests\test_selftest.py`
- `python -m pytest -q`: `488 passed, 37 subtests passed`
- `powershell -ExecutionPolicy Bypass -File .\scripts\release.ps1 -SkipInstall -Clean`
- `pyi-archive_viewer -l dist\QuickShot.exe`: no `numpy`, `numpy.libs`, `openblas`, `dxcam`, `winrt`, `rapidocr`, `onnxruntime`, `cv2`, `opencv`, `Qt6Pdf`, `opengl32sw`, or `_avif` entries.
- `powershell -ExecutionPolicy Bypass -File .\scripts\release.ps1 -SkipBuild -SkipInstaller -SmokeTest`
- `powershell -ExecutionPolicy Bypass -File .\scripts\verify-local-installer.ps1 -RemoveExisting -PrivacySelfTest -OverlaySelfTest -CaptureSelfTest`
- `powershell -ExecutionPolicy Bypass -File .\scripts\verify-upgrade-installer.ps1 -PreviousInstallerPath .\installer_output\QuickShot-5.3.2-Setup.exe -PreviousVersion 5.3.2 -RemoveExisting -PrivacySelfTest -OverlaySelfTest -CaptureSelfTest`
- `powershell -ExecutionPolicy Bypass -File .\scripts\verify-desktop-hotkeys.ps1 -ExePath .\dist\QuickShot.exe -StopExisting`

### Package Size

- `dist\QuickShot.exe`: `31,624,375` bytes / `30.16 MiB`.
- `installer_output\QuickShot-5.3.3-Setup.exe`: `33,405,239` bytes / `31.86 MiB`.
- Saved `9.52 MiB` from the previous executable baseline and `9.47 MiB` from the previous installer baseline.

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
