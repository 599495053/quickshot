# QuickShot Maintenance Plan

This document tracks the next maintenance cycle after the v5.3.0 release.

## Current Stable Release

- Version: `v5.3.0`
- Release URL: `https://github.com/599495053/quickshot/releases/tag/v5.3.0`
- Release status: published and verified
- Signing status: unsigned, because no code signing certificate is configured

## v5.3.1 Priorities

### Release Trust

- Connect a code signing certificate when available.
- Re-run the release script with `-Sign`.
- Verify both `dist\QuickShot.exe` and `installer_output\QuickShot-*-Setup.exe` return `Valid` from `Get-AuthenticodeSignature`.
- Update the release checklist with signed artifact hashes.

### Installer Regression Coverage

- Reuse `scripts\verify-release-installer.ps1` for GitHub Release installer verification.
- Cover fresh install and uninstall.
- Add future coverage for reinstall and upgrade-style install.
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
  -Tag v5.3.0 `
  -ExpectedSha256 D5834B52DC1FEC2D354695500258210B9BE562FCE7D9FE8F7F136AC9B1D69A90
```

If an existing QuickShot install is present and should be removed for a clean verification run, add `-RemoveExisting`.

### Package Size

- Review PyInstaller warnings and included modules.
- Check whether optional OCR, NumPy, or Qt assets can be trimmed safely.
- Compare artifact sizes before and after any exclusion changes.
- Keep `email` bundled because `requests` and `urllib3` need standard-library `email.*` modules.
- Use `docs\PACKAGE_SIZE_ANALYSIS.md` as the baseline and experiment order before changing package exclusions.
- Completed the first three binary trims by excluding Pillow's AVIF extension, `Qt6Pdf.dll`, and `opengl32sw.dll`.
- Replaced the OpenCV-backed blur implementation with Pillow blur and removed `opencv-python` from runtime dependencies.
- Retest the `opengl32sw.dll` exclusion on remote desktop, VM, older GPU, and software-rendering fallback environments before publishing the next release.
- The next meaningful size target is optional OCR packaging.

### User-Facing Polish

- Improve README screenshots or short usage visuals.
- Add clearer GitHub Release download instructions.
- Gather early user feedback from v5.3.0 before changing UI behavior.

### Quality Gates

- Keep CI green on every push.
- Keep the release script as the source of truth for local release validation.
- Run the GitHub Release installer verification before publishing any new release.

## Versioning Rule

Do not bump the project version at the start of the maintenance cycle.

When the next release is ready, run:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\set-version.ps1 -Version 5.3.1
```

Then run:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\release.ps1 -SkipInstall -Clean
```
