# QuickShot Maintenance Plan

This document tracks the next maintenance cycle after the v5.3.9 release.

## Current Stable Release

- Version: `v5.3.9`
- Release URL: `https://github.com/599495053/quickshot/releases/tag/v5.3.9`
- Release status: local artifacts verified; GitHub Release installer verification passed
- Release published: `2026-06-08T10:43:48Z`
- Signing status: unsigned, because no code signing certificate is configured

## Current Release Verification

These artifacts are the v5.3.9 release outputs from the current `master` branch.

- Build command: `powershell -ExecutionPolicy Bypass -File .\scripts\release.ps1 -SkipInstall -Clean`
- Packaged smoke/self-test command: `powershell -ExecutionPolicy Bypass -File .\scripts\release.ps1 -SkipBuild -SkipInstaller -SmokeTest`
- Installer verification: `powershell -ExecutionPolicy Bypass -File .\scripts\verify-local-installer.ps1 -RemoveExisting -PrivacySelfTest -OverlaySelfTest -CaptureSelfTest`
- GitHub Release verification: `powershell -ExecutionPolicy Bypass -File .\scripts\verify-release-installer.ps1 -Tag v5.3.9 -ExpectedSha256 EB68758488AE638AE8D84B835570BA21A67C10D6A85B371C278DF170E4B3D56F -RemoveExisting -PrivacySelfTest -OverlaySelfTest -CaptureSelfTest`
- Upgrade verification: local `v5.3.8` installer -> local `v5.3.9` installer, plus v5.3.9 same-version reinstall
- Desktop hotkey verification: `powershell -ExecutionPolicy Bypass -File .\scripts\verify-desktop-hotkeys.ps1 -ExePath .\dist\QuickShot.exe -StopExisting`
- GitHub Actions CI: `https://github.com/599495053/quickshot/actions/runs/27132246228`, result `success`
- Signature status: `NotSigned` for both `dist\QuickShot.exe` and `installer_output\QuickShot-5.3.9-Setup.exe`
- `dist\QuickShot.exe`: `31,657,093` bytes / `30.19 MiB`, SHA256 `2C1934DE601D1E29A804B65F830D32720B6F13E9ABD6BC6AFBD1DA53637DB4A9`
- `installer_output\QuickShot-5.3.9-Setup.exe`: `33,437,488` bytes / `31.89 MiB`, SHA256 `EB68758488AE638AE8D84B835570BA21A67C10D6A85B371C278DF170E4B3D56F`
- `installer_output\QuickShot-5.3.9-release.txt`: `488` bytes, SHA256 `9B2A836662BD3116423602B7BD6FCDBDBCA72734BC2F9AABEBB473A533AC98C3`
- Default package dependency check passed: no `numpy`, `numpy.libs`, `openblas`, `dxcam`, `winrt`, `rapidocr`, `onnxruntime`, `cv2`, `opencv`, `Qt6Pdf`, `opengl32sw`, or `_avif` entries in `pyi-archive_viewer`.

## Next Maintenance Priorities

### Release Trust

- Connect a code signing certificate when available.
- Re-run the release script with `-Sign`.
- Confirm the generated release manifest records `ExecutableSignatureStatus` and `InstallerSignatureStatus`.
- Before a signed release, run `scripts\verify-artifact-signature.ps1` with `-RequireSigned` against `dist\QuickShot.exe` and the installer.
- Update the release checklist with signed artifact hashes and Authenticode status.

Current unsigned release artifacts can be checked with:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\verify-artifact-signature.ps1 `
  .\dist\QuickShot.exe `
  .\installer_output\QuickShot-5.3.9-Setup.exe `
  -ExpectedStatus NotSigned
```

### Installer Regression Coverage

- Run `scripts\verify-local-installer.ps1` against locally built artifacts before uploading a release.
- Reuse `scripts\verify-release-installer.ps1` for GitHub Release installer verification.
- Use `scripts\verify-upgrade-installer.ps1` for same-version reinstall and previous-to-current upgrade coverage.
- Keep the packaged `privacy-ocr-fallback`, `overlay-edit-smoke`, and `capture-backend-smoke` self-tests in `release.ps1 -SmokeTest`; add `-PrivacySelfTest`, `-OverlaySelfTest`, and `-CaptureSelfTest` to installer verification runs for builds that include the hidden self-test entry point.
- Run `scripts\verify-desktop-hotkeys.ps1 -StopExisting` on a local Windows desktop before release when validating tray startup and real global hotkeys.
- Cover fresh install, same-version reinstall, previous-to-current upgrade, and uninstall.
- Verify default tasks remain unchecked:
  - no desktop shortcut
  - no Windows startup entry
- Verify uninstall cleanup:
  - install directory
  - uninstall registry key
  - startup registry value
  - optional shortcuts

Run the current release verification with:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\verify-release-installer.ps1 `
  -Tag v5.3.9 `
  -ExpectedSha256 EB68758488AE638AE8D84B835570BA21A67C10D6A85B371C278DF170E4B3D56F
```

If an existing QuickShot install is present and should be removed for a clean verification run, add `-RemoveExisting`.

Run upgrade/reinstall verification with a downloaded previous installer:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\verify-upgrade-installer.ps1 `
  -PreviousInstallerPath <downloaded-QuickShot-5.3.8-Setup.exe> `
  -PreviousVersion 5.3.8
```

### Package Size

- Review PyInstaller warnings and included modules.
- Check whether optional OCR, NumPy, or Qt assets can be trimmed safely.
- Compare artifact sizes before and after any exclusion changes.
- Keep `email` bundled because `requests` and `urllib3` need standard-library `email.*` modules.
- Use `docs\PACKAGE_SIZE_ANALYSIS.md` as the baseline and experiment order before changing package exclusions.
- Completed the first three binary trims by excluding Pillow's AVIF extension, `Qt6Pdf.dll`, and `opengl32sw.dll`.
- Replaced the OpenCV-backed blur implementation with Pillow blur and removed `opencv-python` from runtime dependencies.
- Made RapidOCR/ONNX Runtime optional so the default package stays light while Windows system OCR remains available.
- Smart privacy masking falls back to Windows system OCR line boxes when RapidOCR is unavailable.
- Made NumPy/OpenBLAS, dxcam, and WinRT HDR capture optional so the default package uses the lightweight `mss` capture backend.
- Excluded unused PyQt6 Qt translation files from PyInstaller binary and data entries.
- Retest the `opengl32sw.dll` exclusion on remote desktop, VM, older GPU, and software-rendering fallback environments before publishing the next release.
- Watch for user demand before adding a separate HDR/advanced-capture installer flavor.

### User-Facing Polish

- Release notes prepared in `docs\RELEASE_NOTES_v5.3.9.md`.
- Improve README screenshots or short usage visuals.
- Gather early user feedback from v5.3.9 before changing workflow presets or upload guidance further.

### Quality Gates

- Keep CI green on every push.
- Keep the release script as the source of truth for local release validation.
- Run local installer verification after each release build.
- Run the GitHub Release installer verification after publishing any new release.

## Versioning Rule

Do not bump the project version at the start of the maintenance cycle.

When the next release is ready, run:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\set-version.ps1 -Version <new-version>
```

Then run:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\release.ps1 -SkipInstall -Clean
```
