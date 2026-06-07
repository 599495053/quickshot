# QuickShot Commit Plan

Last reviewed: 2026-06-07

This plan groups the current working tree into reviewable commits. It does not stage or commit anything by itself.

## 0. Pre-commit Cleanup

Completed on 2026-06-07. The whitespace issues originally reported by:

```powershell
git diff --check
```

were cleaned up. The affected areas were:

- `quickshot/_manager_history.py`
- `quickshot/_manager_pin.py`
- `quickshot/config.py`
- `quickshot/history.py`
- `quickshot/hotkey.py`
- `quickshot/ocr.py`
- `quickshot/overlay/_drawing.py`
- `quickshot/overlay/_ocr.py`
- `quickshot/overlay/_paint.py`
- `quickshot/overlay/_selection.py`
- `quickshot/overlay/widget.py`
- `quickshot/uploader.py`

Follow-up verification:

- [x] `git diff --check`
- [x] `python -m pyflakes quickshot launcher.py build_config.py`
- [x] `python -m compileall -q quickshot launcher.py build_config.py`
- [x] `python -m pytest -q`

Remaining CRLF-to-LF warnings from Git are not test failures, but the line-ending normalization should be intentional before committing.

## 1. `fix: harden hotkeys, OCR, and post-capture workflows`

Purpose: stabilize the capture path and the specific regressions found during review.

Suggested files:

- `quickshot/hotkey_util.py`
- `quickshot/main.py`
- `quickshot/screenshot.py`
- `quickshot/pipeline.py`
- `quickshot/overlay/_export.py`
- `quickshot/overlay/_ocr.py`
- `quickshot/_settings_handlers.py`
- `tests/test_hotkey_util.py`
- `tests/test_main.py`
- `tests/test_overlay_events.py`
- `tests/test_settings.py`

Notes:

- Covers fallback hotkey modifier grouping.
- Covers GUI-thread-safe clipboard writes for post-capture Markdown.
- Covers non-modal OCR result dialog safety.
- Covers startup manager import and settings import synchronization.
- Covers `pyflakes`-friendly capture prewarm imports.

## 2. `feat: improve overlay editing, snapping, and paint performance`

Purpose: keep the larger overlay feature and rendering work together.

Suggested files:

- `quickshot/constants.py`
- `quickshot/window_enum.py`
- `quickshot/config.py`
- `quickshot/settings.py`
- `quickshot/overlay/_drawing.py`
- `quickshot/overlay/_events.py`
- `quickshot/overlay/_paint.py`
- `quickshot/overlay/_paint_style_panel.py`
- `quickshot/overlay/_paint_toolbar.py`
- `quickshot/overlay/_selection.py`
- `quickshot/overlay/_toolbar.py`
- `quickshot/overlay/annotation_painter.py`
- `quickshot/overlay/widget.py`
- `assets/toolbar/picker.svg`
- `tests/test_snap.py`
- `tests/test_overlay_perf.py`
- `tests/test_overlay_smoke.py`

Notes:

- Adds snap-to-window selection behavior and related settings.
- Adds configurable edit-mode tool hotkeys.
- Splits toolbar/style-panel paint code out of `_paint.py`.
- Adds cached `QImage` access to reduce repeated `QPixmap.toImage()` cost.
- Contains a lot of paint-path surface area, so keep this commit separate from installer work.

## 3. `feat: enhance history, pin, and translation tools`

Purpose: separate product workflow enhancements from capture-path fixes.

Suggested files:

- `quickshot/history.py`
- `quickshot/_manager_history.py`
- `quickshot/_manager_history_actions.py`
- `quickshot/pin.py`
- `quickshot/_manager_pin.py`
- `quickshot/translator.py`
- `quickshot/theme.py`
- `quickshot/ui.py`
- `quickshot/uploader.py`
- `quickshot/utils.py`
- `tests/test_secrets.py`
- `tests/test_translator.py`

Notes:

- Adds debounced history persistence and search helper extraction.
- Adds history and pin manager keyboard shortcuts.
- Adds pin-window annotation/edit mode.
- Adds translation fallback and timeout handling.
- Removes the custom-for-name branding from settings title via `quickshot/utils.py`.

## 4. `build: add installer packaging and release checklist`

Purpose: package/release infrastructure only.

Suggested files:

- `.gitignore`
- `build_config.py`
- `requirements.txt`
- `pyproject.toml`
- `QuickShot.iss`
- `installer/ChineseSimplified.isl`
- `RELEASE_CHECKLIST.md`
- `COMMIT_PLAN.md`

Notes:

- Keeps `email` in the PyInstaller bundle because `requests` and `urllib3` need standard-library `email.*` modules.
- Adds Inno Setup installer script.
- Adds Simplified Chinese installer language support.
- Defaults desktop shortcut and Windows startup tasks to unchecked.
- Sets uninstall display name to `QuickShot`.
- Records final build/test commands and artifact hashes in `RELEASE_CHECKLIST.md`.

## Generated Artifacts

Do not commit generated output unless there is a deliberate release-artifact policy:

- `build/`
- `dist/`
- `installer_output/`
- install/uninstall test logs

The installer to publish from the last verified build is:

- `installer_output/QuickShot-5.3.0-Setup.exe`

## Final Verification Before Commit

Run these after whitespace cleanup and before committing:

```powershell
python -m pytest -q
python -m pyflakes quickshot launcher.py build_config.py
python -m compileall -q quickshot launcher.py build_config.py
python -m pip check
powershell -ExecutionPolicy Bypass -File .\build.ps1 -SkipInstall -Clean
& 'C:\Users\59949\AppData\Local\Programs\Inno Setup 6\ISCC.exe' QuickShot.iss
git diff --check
```
