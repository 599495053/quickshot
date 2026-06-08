"""End-to-end overlay capture workflows."""

from __future__ import annotations

import json
import time
from pathlib import Path
from unittest.mock import patch

import pytest
from PyQt6.QtCore import QPoint, QPointF, QRect, Qt
from PyQt6.QtGui import QColor, QImage, QPainter, QPixmap

from quickshot.config import Config
from quickshot.history import CaptureHistoryStore
from quickshot.overlay.widget import FloatingSnipOverlay


class _MouseEvent:
    def __init__(self, pos: QPoint, button=Qt.MouseButton.LeftButton) -> None:
        self._pos = QPoint(pos)
        self._button = button

    def button(self):
        return self._button

    def position(self):
        return QPointF(self._pos)


class _KeyEvent:
    def __init__(
        self,
        key,
        modifiers=Qt.KeyboardModifier.NoModifier,
    ) -> None:
        self._key = key
        self._modifiers = modifiers

    def key(self):
        return self._key

    def modifiers(self):
        return self._modifiers


def _make_pixmap(size: tuple[int, int], color: QColor) -> QPixmap:
    pixmap = QPixmap(size[0], size[1])
    pixmap.fill(color)
    painter = QPainter(pixmap)
    painter.fillRect(0, 0, size[0] // 2, size[1], QColor(80, 120, 180))
    painter.fillRect(size[0] // 2, 0, size[0] // 2, size[1], QColor(180, 120, 80))
    painter.end()
    return pixmap


def _indexed_color(x: int, y: int) -> QColor:
    return QColor(
        (x * 17 + y * 7) % 256,
        (x * 5 + y * 19) % 256,
        (x * 11 + y * 3) % 256,
    )


def _make_indexed_pixmap(size: tuple[int, int]) -> QPixmap:
    image = QImage(size[0], size[1], QImage.Format.Format_RGB32)
    for y in range(size[1]):
        for x in range(size[0]):
            image.setPixelColor(x, y, _indexed_color(x, y))
    return QPixmap.fromImage(image)


def _make_config(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Config:
    monkeypatch.setenv("APPDATA", str(tmp_path / "appdata"))
    cfg = Config()
    save_dir = tmp_path / "screenshots"
    history_dir = tmp_path / "history"
    cfg.save_dir = str(save_dir)
    cfg.save_dir_mode = "flat"
    cfg.save_format = "png"
    cfg.auto_copy = False
    cfg.auto_history = True
    cfg.show_notifications = False
    cfg.workflow_auto_save = False
    cfg.workflow_auto_ocr = False
    cfg.workflow_auto_upload = False
    cfg.workflow_copy_markdown = False
    cfg.history_dir = lambda: history_dir  # type: ignore[method-assign]
    cfg.history_index_path = lambda: history_dir / "index.json"  # type: ignore[method-assign]
    cfg.ensure_history_dir = (  # type: ignore[method-assign]
        lambda: history_dir.mkdir(parents=True, exist_ok=True) or history_dir
    )
    return cfg


def _make_overlay(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    *,
    raw_size: tuple[int, int] = (320, 240),
    logical_size: tuple[int, int] = (320, 240),
    scale: float = 1.0,
    raw_pixmap: QPixmap | None = None,
) -> tuple[FloatingSnipOverlay, CaptureHistoryStore, Config]:
    cfg = _make_config(tmp_path, monkeypatch)
    store = CaptureHistoryStore(cfg)
    raw = raw_pixmap if raw_pixmap is not None else _make_pixmap(raw_size, QColor(60, 60, 60))
    display = raw.scaled(logical_size[0], logical_size[1])
    overlay = FloatingSnipOverlay(
        raw,
        display,
        QRect(0, 0, logical_size[0], logical_size[1]),
        scale,
        scale,
        0,
        0,
        cfg,
        store,
    )
    overlay.resize(logical_size[0], logical_size[1])
    return overlay, store, cfg


def _drag_select(overlay: FloatingSnipOverlay, start: QPoint, end: QPoint) -> QRect:
    overlay.mousePressEvent(_MouseEvent(start))
    overlay.mouseMoveEvent(_MouseEvent(end))
    overlay.mouseReleaseEvent(_MouseEvent(end))
    return QRect(start, end).normalized().intersected(overlay.rect())


def _flush_history(store: CaptureHistoryStore) -> list[dict]:
    store.flush()
    return store.load_items()


def _assert_pixmap_matches_raw_region(
    pixmap: QPixmap,
    raw: QPixmap,
    physical_rect: QRect,
) -> None:
    actual = pixmap.toImage()
    source = raw.toImage()
    assert actual.width() == physical_rect.width()
    assert actual.height() == physical_rect.height()
    width = actual.width()
    height = actual.height()

    for x in range(width):
        assert actual.pixelColor(x, 0) == source.pixelColor(physical_rect.left() + x, physical_rect.top())
        assert actual.pixelColor(x, height - 1) == source.pixelColor(
            physical_rect.left() + x,
            physical_rect.top() + height - 1,
        )
    for y in range(height):
        assert actual.pixelColor(0, y) == source.pixelColor(physical_rect.left(), physical_rect.top() + y)
        assert actual.pixelColor(width - 1, y) == source.pixelColor(
            physical_rect.left() + width - 1,
            physical_rect.top() + y,
        )
    for x in range(0, width, max(1, width // 7)):
        for y in range(0, height, max(1, height // 7)):
            assert actual.pixelColor(x, y) == source.pixelColor(
                physical_rect.left() + x,
                physical_rect.top() + y,
            )


def _changed_pixels(before: QImage, after: QImage) -> int:
    assert before.size() == after.size()
    changed = 0
    for y in range(after.height()):
        for x in range(after.width()):
            if before.pixelColor(x, y) != after.pixelColor(x, y):
                changed += 1
    return changed


def _drag_tool(overlay: FloatingSnipOverlay, tool: str, start: QPoint, end: QPoint) -> None:
    overlay.select_tool(tool)
    overlay.mousePressEvent(_MouseEvent(start))
    overlay.mouseMoveEvent(_MouseEvent(end))
    overlay.mouseReleaseEvent(_MouseEvent(end))


@pytest.mark.parametrize("scale", [1.0, 1.5, 2.0])
def test_region_capture_pixel_edges_match_raw_source(
    qapp,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    scale: float,
) -> None:
    logical_size = (180, 120)
    raw_size = (int(logical_size[0] * scale), int(logical_size[1] * scale))
    raw = _make_indexed_pixmap(raw_size)
    overlay, _store, _cfg = _make_overlay(
        tmp_path,
        monkeypatch,
        raw_size=raw_size,
        logical_size=logical_size,
        scale=scale,
        raw_pixmap=raw,
    )

    _drag_select(overlay, QPoint(17, 13), QPoint(118, 91))

    _assert_pixmap_matches_raw_region(overlay.edit_pixmap, raw, overlay.selection_physical_rect)


@pytest.mark.parametrize("scale", [1.0, 1.5, 2.0])
def test_window_capture_pixel_edges_match_raw_source(
    qapp,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    scale: float,
) -> None:
    logical_size = (180, 120)
    raw_size = (int(logical_size[0] * scale), int(logical_size[1] * scale))
    raw = _make_indexed_pixmap(raw_size)
    overlay, _store, _cfg = _make_overlay(
        tmp_path,
        monkeypatch,
        raw_size=raw_size,
        logical_size=logical_size,
        scale=scale,
        raw_pixmap=raw,
    )
    physical_rect = QRect(
        int(13 * scale),
        int(11 * scale),
        int(83 * scale),
        int(59 * scale),
    )

    overlay.set_initial_capture_from_physical_abs(
        (
            physical_rect.x(),
            physical_rect.y(),
            physical_rect.width(),
            physical_rect.height(),
        )
    )

    assert overlay.selection_physical_rect == physical_rect
    _assert_pixmap_matches_raw_region(overlay.edit_pixmap, raw, physical_rect)


def test_r_reuse_preserves_pixel_edges_after_dpi_change(
    qapp,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    FloatingSnipOverlay._last_selection_rect = None
    FloatingSnipOverlay._last_selection_physical_rect = None
    first, _store, _cfg = _make_overlay(tmp_path / "first", monkeypatch)
    logical = _drag_select(first, QPoint(19, 17), QPoint(119, 88))
    raw = _make_indexed_pixmap((360, 240))
    second, _store2, _cfg2 = _make_overlay(
        tmp_path / "second",
        monkeypatch,
        raw_size=(360, 240),
        logical_size=(180, 120),
        scale=2.0,
        raw_pixmap=raw,
    )

    second.keyPressEvent(_KeyEvent(Qt.Key.Key_R))

    assert second.selection_rect == logical
    _assert_pixmap_matches_raw_region(second.edit_pixmap, raw, second.selection_physical_rect)


def test_all_toolbar_buttons_hit_expected_commands(
    qapp,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    overlay, _store, _cfg = _make_overlay(tmp_path, monkeypatch, logical_size=(420, 420))
    _drag_select(overlay, QPoint(60, 40), QPoint(330, 180))
    calls = []

    overlay.select_tool = lambda tool: calls.append(("tool", tool))  # type: ignore[method-assign]
    overlay.copy_current = lambda: calls.append(("copy_current", ""))  # type: ignore[method-assign]
    overlay.save_current = lambda: calls.append(("save_current", ""))  # type: ignore[method-assign]
    overlay.pin_current = lambda: calls.append(("pin_current", ""))  # type: ignore[method-assign]
    overlay.recognize_current_text = lambda: calls.append(("recognize_current_text", ""))  # type: ignore[method-assign]
    overlay.undo = lambda: calls.append(("undo", ""))  # type: ignore[method-assign]
    overlay.redo = lambda: calls.append(("redo", ""))  # type: ignore[method-assign]
    overlay.clear_annotations = lambda: calls.append(("clear_annotations", ""))  # type: ignore[method-assign]
    overlay.finish = lambda: calls.append(("finish", ""))  # type: ignore[method-assign]
    overlay.close = lambda: calls.append(("close", ""))  # type: ignore[method-assign]
    overlay.apply_shadow = lambda: calls.append(("apply_shadow", ""))  # type: ignore[method-assign]
    overlay.apply_border = lambda: calls.append(("apply_border", ""))  # type: ignore[method-assign]
    overlay.apply_watermark = lambda: calls.append(("apply_watermark", ""))  # type: ignore[method-assign]
    overlay.toggle_style_panel = lambda kind: calls.append(("toggle_style_panel", kind))  # type: ignore[method-assign]
    overlay.cycle_fill_mode = lambda: calls.append(("cycle_fill_mode", ""))  # type: ignore[method-assign]
    overlay.toggle_grid = lambda: calls.append(("toggle_grid", ""))  # type: ignore[method-assign]
    overlay.apply_mosaic_to_selection = lambda: calls.append(("apply_mosaic_to_selection", ""))  # type: ignore[method-assign]

    expected_keys = [key for key, _label, _icon, _tip in overlay.toolbar_items() if key != "sep"]
    assert set(expected_keys) == set(overlay.toolbar_buttons)
    for key in expected_keys:
        overlay._toolbar_layout_geometry = None
        overlay.update_toolbar_layout()
        pos = overlay.toolbar_buttons[key].center()
        assert overlay.button_at(pos) == key
        before = len(calls)
        overlay.mousePressEvent(_MouseEvent(pos))
        assert len(calls) == before + 1, key

    called_tools = {value for name, value in calls if name == "tool"}
    for key in (
        "arrow",
        "rect",
        "ellipse",
        "dashed_rect",
        "pen",
        "highlight",
        "text",
        "number",
        "mosaic",
        "blur",
        "picker",
    ):
        assert key in called_tools


def test_annotation_tools_change_saved_pixels_and_history(
    qapp,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    raw = _make_indexed_pixmap((320, 240))
    overlay, store, _cfg = _make_overlay(tmp_path, monkeypatch, raw_pixmap=raw)
    _drag_select(overlay, QPoint(40, 40), QPoint(250, 180))
    before = overlay.edit_pixmap.toImage()

    _drag_tool(overlay, "arrow", QPoint(60, 60), QPoint(140, 90))
    _drag_tool(overlay, "rect", QPoint(80, 100), QPoint(170, 150))
    overlay.push_history()
    overlay.apply_mosaic(QRect(145, 24, 45, 48))
    _drag_tool(overlay, "blur", QPoint(185, 122), QPoint(230, 168))
    overlay.annotations.append({
        "type": "text",
        "x": 20,
        "y": 24,
        "text": "QuickShot",
        "size": 28,
        "color": "#ffffff",
    })
    overlay.rebuild_edit_pixmap()

    after = overlay.edit_pixmap.toImage()
    assert _changed_pixels(before, after) > 250
    assert {"arrow", "rect", "mosaic", "blur", "text"}.issubset(
        {str(item.get("type")) for item in overlay.annotations}
    )

    target = tmp_path / "annotated.png"
    with patch(
        "PyQt6.QtWidgets.QFileDialog.getSaveFileName",
        return_value=(str(target), ""),
    ):
        overlay.save_current()

    saved = QImage(str(target))
    assert saved.size() == after.size()
    assert _changed_pixels(before, saved) > 250
    items = _flush_history(store)
    assert len(items) == 1
    assert items[0]["source"] == "save"


def test_overlay_test_event_log_records_automation_milestones(
    qapp,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    event_log = tmp_path / "events.jsonl"
    monkeypatch.setenv("QUICKSHOT_TEST_EVENTS_LOG", str(event_log))
    overlay, _store, _cfg = _make_overlay(tmp_path, monkeypatch)
    _drag_select(overlay, QPoint(30, 30), QPoint(160, 110))
    with patch("quickshot.overlay._export.copy_pixmap_to_clipboard"):
        overlay.copy_current()
    target = tmp_path / "debug-save.png"
    overlay._save_current_to_path(str(target), "PNG", "PNG")

    events = [json.loads(line) for line in event_log.read_text(encoding="utf-8").splitlines()]
    names = [event["event"] for event in events]
    assert names == [
        "overlay_enter_edit",
        "overlay_copy_current",
        "overlay_save_current",
    ]
    assert events[0]["logical_w"] == overlay.selection_rect.width()
    assert events[1]["history_item_id"]
    assert events[2]["filepath"] == str(target)


def test_overlay_hot_path_performance_budget(
    qapp,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    overlay, _store, _cfg = _make_overlay(
        tmp_path,
        monkeypatch,
        raw_size=(1920, 1080),
        logical_size=(1280, 720),
        scale=1.5,
    )
    _drag_select(overlay, QPoint(140, 90), QPoint(980, 590))
    overlay.annotations = [
        {
            "type": "rect",
            "x": 10 + (i % 20) * 18,
            "y": 10 + (i // 20) * 18,
            "w": 44,
            "h": 28,
            "color": "#ff4646",
            "width": 3,
        }
        for i in range(80)
    ]

    start = time.perf_counter()
    overlay.rebuild_edit_pixmap()
    rebuild_elapsed = time.perf_counter() - start

    start = time.perf_counter()
    for _ in range(250):
        overlay._toolbar_layout_geometry = None
        overlay.update_toolbar_layout()
    toolbar_elapsed = time.perf_counter() - start

    assert rebuild_elapsed < 1.5
    assert toolbar_elapsed < 0.75


def test_drag_region_then_copy_records_history(
    qapp,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    FloatingSnipOverlay._last_selection_rect = None
    FloatingSnipOverlay._last_selection_physical_rect = None
    overlay, store, _cfg = _make_overlay(tmp_path, monkeypatch)
    expected = _drag_select(overlay, QPoint(32, 40), QPoint(172, 134))

    assert overlay.mode == "edit"
    assert overlay.selection_rect == expected
    assert overlay.selection_physical_rect == expected
    assert overlay.edit_pixmap.width() == expected.width()
    assert overlay.edit_pixmap.height() == expected.height()

    emitted = []
    overlay.history_updated.connect(lambda: emitted.append(True))
    with patch("quickshot.overlay._export.copy_pixmap_to_clipboard") as copy_clipboard:
        overlay.copy_current()

    copy_clipboard.assert_called_once()
    items = _flush_history(store)
    assert emitted == [True]
    assert len(items) == 1
    assert items[0]["source"] == "copy"
    assert items[0]["width"] == expected.width()
    assert items[0]["height"] == expected.height()
    assert store.image_path(items[0]).exists()
    assert overlay.history_item_id == items[0]["id"]


def test_drag_region_then_save_writes_file_and_history(
    qapp,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    overlay, store, _cfg = _make_overlay(tmp_path, monkeypatch)
    expected = _drag_select(overlay, QPoint(20, 24), QPoint(140, 118))
    target = tmp_path / "manual-save.png"

    with patch(
        "PyQt6.QtWidgets.QFileDialog.getSaveFileName",
        return_value=(str(target), ""),
    ):
        overlay.save_current()

    assert target.exists()
    saved = QImage(str(target))
    assert saved.width() == expected.width()
    assert saved.height() == expected.height()
    items = _flush_history(store)
    assert len(items) == 1
    assert items[0]["source"] == "save"
    assert items[0]["width"] == expected.width()
    assert items[0]["height"] == expected.height()


def test_finish_auto_save_writes_default_file_updates_history_and_closes(
    qapp,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    overlay, store, cfg = _make_overlay(tmp_path, monkeypatch)
    expected = _drag_select(overlay, QPoint(50, 50), QPoint(200, 150))
    cfg.workflow_auto_save = True
    closed = []
    overlay.close = lambda: closed.append(True)  # type: ignore[method-assign]

    overlay.finish()

    files = list((tmp_path / "screenshots").glob("screenshot_*.png"))
    assert len(files) == 1
    saved = QImage(str(files[0]))
    assert saved.width() == expected.width()
    assert saved.height() == expected.height()
    assert closed == [True]
    items = _flush_history(store)
    assert len(items) == 1
    assert items[0]["source"] == "save"
    assert items[0]["width"] == expected.width()
    assert items[0]["height"] == expected.height()


def test_window_capture_rect_then_toolbar_copy_records_history(
    qapp,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    overlay, store, _cfg = _make_overlay(
        tmp_path,
        monkeypatch,
        raw_size=(640, 480),
        logical_size=(320, 240),
        scale=2.0,
    )
    overlay.set_initial_capture_from_physical_abs((40, 50, 200, 120))

    assert overlay.mode == "edit"
    assert overlay.selection_rect == QRect(20, 25, 100, 60)
    assert overlay.selection_physical_rect == QRect(40, 50, 200, 120)
    assert overlay.edit_pixmap.width() == 200
    assert overlay.edit_pixmap.height() == 120

    copy_button = overlay.toolbar_buttons["copy"].center()
    with patch("quickshot.overlay._export.copy_pixmap_to_clipboard") as copy_clipboard:
        overlay.mousePressEvent(_MouseEvent(copy_button))

    copy_clipboard.assert_called_once()
    items = _flush_history(store)
    assert len(items) == 1
    assert items[0]["source"] == "copy"
    assert items[0]["width"] == 200
    assert items[0]["height"] == 120


def test_r_reuses_last_selection_and_recomputes_physical_rect(
    qapp,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    FloatingSnipOverlay._last_selection_rect = None
    FloatingSnipOverlay._last_selection_physical_rect = None
    first, _store, _cfg = _make_overlay(tmp_path / "first", monkeypatch)
    logical = _drag_select(first, QPoint(24, 30), QPoint(150, 112))
    assert first.selection_rect == logical

    second, _store2, _cfg2 = _make_overlay(
        tmp_path / "second",
        monkeypatch,
        raw_size=(640, 480),
        logical_size=(320, 240),
        scale=2.0,
    )
    second.keyPressEvent(_KeyEvent(Qt.Key.Key_R))

    expected_physical = second.logical_to_physical_rect(logical)
    assert second.mode == "edit"
    assert second.selection_rect == logical
    assert second.selection_physical_rect == expected_physical
    assert second.edit_pixmap.width() == expected_physical.width()
    assert second.edit_pixmap.height() == expected_physical.height()
