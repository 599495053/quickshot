# QuickShot v5.3.5 Release Notes

QuickShot v5.3.5 focuses on making smart privacy masking safer and more controllable.

## Highlights

- Smart privacy masking now shows detected regions as editable preview boxes before applying mosaic.
- Preview boxes can be selected, dragged, resized, nudged with arrow keys, or deleted before confirmation.
- Press `Enter` to apply the previewed mosaic regions, `Delete`/`Backspace` to remove the selected candidate, and `Esc` to cancel the preview.
- Copy, save, pin, and finish actions are blocked while privacy preview is active, preventing accidental export of an unmasked image.
- The default installer remains lightweight and unsigned, with optional OCR/HDR dependencies still excluded.

## Verification

Final v5.3.5 artifact and desktop verification results:

- `python -m pytest -q`: `505 passed, 37 subtests passed`
- `powershell -ExecutionPolicy Bypass -File .\scripts\release.ps1 -SkipInstall -Clean`
- `powershell -ExecutionPolicy Bypass -File .\scripts\verify-artifact-signature.ps1 .\dist\QuickShot.exe .\installer_output\QuickShot-5.3.5-Setup.exe -ExpectedStatus NotSigned`
- `pyi-archive_viewer -l dist\QuickShot.exe`: no `numpy`, `numpy.libs`, `openblas`, `dxcam`, `winrt`, `rapidocr`, `onnxruntime`, `cv2`, `opencv`, `Qt6Pdf`, `opengl32sw`, or `_avif` entries
- `powershell -ExecutionPolicy Bypass -File .\scripts\release.ps1 -SkipBuild -SkipInstaller -SmokeTest`
- `powershell -ExecutionPolicy Bypass -File .\scripts\verify-local-installer.ps1 -RemoveExisting -PrivacySelfTest -OverlaySelfTest -CaptureSelfTest`
- `powershell -ExecutionPolicy Bypass -File .\scripts\verify-upgrade-installer.ps1 -PreviousInstallerPath <downloaded v5.3.4 installer> -PreviousVersion 5.3.4 -RemoveExisting -PrivacySelfTest -OverlaySelfTest -CaptureSelfTest`
- `powershell -ExecutionPolicy Bypass -File .\scripts\verify-desktop-hotkeys.ps1 -ExePath .\dist\QuickShot.exe -StopExisting`

## Artifact Hashes

Generated from the final v5.3.5 release build:

| File | Size | SHA256 |
| --- | ---: | --- |
| `QuickShot-5.3.5-Setup.exe` | 33,425,937 bytes / 31.88 MiB | `3F30E0CD67D14F689A29EB497F19273032606742C435B1127C5D7635D19F2BC7` |
| `QuickShot-5.3.5-release.txt` | 488 bytes | `7D6EE4FB4830283D5456DDA8DB12BF2F1A694D6477A473DCC78400DE38B32E8E` |

## Notes

- The release is unsigned because no code-signing certificate is configured.
- Windows may show a security warning for the unsigned installer. Verify the SHA256 hash above before installing.
- Default install does not create a desktop shortcut or Windows startup entry unless the user selects those tasks.
