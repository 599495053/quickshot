# QuickShot Maintenance Plan

This document tracks the next maintenance cycle after the v5.3.2 release.

## Current Stable Release

- Version: `v5.3.2`
- Release URL: `https://github.com/599495053/quickshot/releases/tag/v5.3.2`
- Release status: published and verified
- Signing status: unsigned, because no code signing certificate is configured

## Next Maintenance Priorities

### Release Trust

- Connect a code signing certificate when available.
- Re-run the release script with `-Sign`.
- Verify both `dist\QuickShot.exe` and `installer_output\QuickShot-*-Setup.exe` return `Valid` from `Get-AuthenticodeSignature`.
- Update the release checklist with signed artifact hashes.

### Installer Regression Coverage

- Run `scripts\verify-local-installer.ps1` against locally built artifacts before uploading a release.
- Reuse `scripts\verify-release-installer.ps1` for GitHub Release installer verification.
- Use `scripts\verify-upgrade-installer.ps1` for same-version reinstall and previous-to-current upgrade coverage.
- Keep the packaged `privacy-ocr-fallback`, `overlay-edit-smoke`, and `capture-backend-smoke` self-tests in `release.ps1 -SmokeTest`; add `-PrivacySelfTest`, `-OverlaySelfTest`, and `-CaptureSelfTest` to installer verification runs for builds that include the hidden self-test entry point.
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
  -Tag v5.3.2 `
  -ExpectedSha256 E0B9B948485783D9C031E1EB2100F9DE1476B19E73E0D0477A1582520CFE04FC
```

If an existing QuickShot install is present and should be removed for a clean verification run, add `-RemoveExisting`.

Run upgrade/reinstall verification with:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\verify-upgrade-installer.ps1 `
  -PreviousInstallerPath .\installer_output\QuickShot-5.3.1-Setup.exe `
  -PreviousVersion 5.3.1
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
- Excluded unused PyQt6 Qt translation files from PyInstaller binary and data entries.
- Retest the `opengl32sw.dll` exclusion on remote desktop, VM, older GPU, and software-rendering fallback environments before publishing the next release.
- The next meaningful size target is NumPy/OpenBLAS reduction, but only after replacing the remaining NumPy-dependent code paths.

### User-Facing Polish

- Release notes published in `docs\RELEASE_NOTES_v5.3.2.md`.
- Improve README screenshots or short usage visuals.
- Add clearer GitHub Release download instructions.
- Gather early user feedback from v5.3.2 before changing UI behavior.

### Quality Gates

- Keep CI green on every push.
- Keep the release script as the source of truth for local release validation.
- Run local installer verification after each release build.
- Run the GitHub Release installer verification before publishing any new release.

## Versioning Rule

Do not bump the project version at the start of the maintenance cycle.

When the next release is ready, run:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\set-version.ps1 -Version 5.3.3
```

Then run:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\release.ps1 -SkipInstall -Clean
```
