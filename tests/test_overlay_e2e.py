"""End-to-end overlay capture workflows."""

from __future__ import annotations

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
) -> tuple[FloatingSnipOverlay, CaptureHistoryStore, Config]:
    cfg = _make_config(tmp_path, monkeypatch)
    store = CaptureHistoryStore(cfg)
    raw = _make_pixmap(raw_size, QColor(60, 60, 60))
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
