"""Packaged-app self-tests used by release verification."""

from __future__ import annotations

import sys
import tempfile
from contextlib import contextmanager
from os import environ
from pathlib import Path
from typing import Iterator

from PIL import Image, ImageDraw, ImageFont
from PyQt6.QtGui import QImage

from . import ocr


SELF_TEST_ARG = "--quickshot-self-test"
PRIVACY_OCR_FALLBACK_TEST = "privacy-ocr-fallback"
OVERLAY_EDIT_SMOKE_TEST = "overlay-edit-smoke"
CAPTURE_BACKEND_SMOKE_TEST = "capture-backend-smoke"


def _write_line(stream_name: str, text: str) -> None:
    stream = getattr(sys, stream_name, None)
    if stream is None:
        return
    try:
        stream.write(text + "\n")
        stream.flush()
    except Exception:
        pass


def _load_sample_font(size: int) -> ImageFont.FreeTypeFont:
    candidates = [
        Path("C:/Windows/Fonts/arial.ttf"),
        Path("C:/Windows/Fonts/segoeui.ttf"),
        Path("C:/Windows/Fonts/calibri.ttf"),
    ]
    for candidate in candidates:
        if candidate.exists():
            return ImageFont.truetype(str(candidate), size)
    try:
        return ImageFont.truetype("arial.ttf", size)
    except OSError as exc:
        raise RuntimeError("No usable TrueType font found for privacy OCR self-test.") from exc


def _make_privacy_sample_qimage() -> QImage:
    image = Image.new("RGB", (1600, 420), "white")
    draw = ImageDraw.Draw(image)
    font = _load_sample_font(96)
    draw.text((80, 50), "Phone 13812345678", fill="black", font=font)
    draw.text((80, 220), "test@example.com", fill="black", font=font)

    temp_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(prefix="quickshot_privacy_selftest_", suffix=".png", delete=False) as handle:
            temp_path = Path(handle.name)
        image.save(temp_path)
        qimage = QImage(str(temp_path))
    finally:
        if temp_path is not None:
            try:
                temp_path.unlink()
            except OSError:
                pass

    if qimage.isNull():
        raise RuntimeError("Failed to create privacy OCR self-test image.")
    return qimage


@contextmanager
def _temporary_appdata() -> Iterator[Path]:
    previous = environ.get("APPDATA")
    with tempfile.TemporaryDirectory(prefix="quickshot_selftest_appdata_") as temp_dir:
        environ["APPDATA"] = temp_dir
        try:
            yield Path(temp_dir)
        finally:
            if previous is None:
                environ.pop("APPDATA", None)
            else:
                environ["APPDATA"] = previous


def run_privacy_ocr_fallback_self_test() -> None:
    if ocr.is_rapidocr_available():
        raise RuntimeError("RapidOCR is available; lightweight fallback path was not exercised.")

    rects = ocr.detect_privacy_info(_make_privacy_sample_qimage())
    if not rects:
        raise RuntimeError("Windows OCR fallback did not detect privacy text.")

    if not any(width > 0 and height > 0 for _x, _y, width, height in rects):
        raise RuntimeError(f"Windows OCR fallback returned invalid privacy rectangles: {rects!r}")


def _ensure_qapplication():
    from PyQt6.QtWidgets import QApplication

    return QApplication.instance() or QApplication(["QuickShotSelfTest"])


def _paint_overlay_once(overlay) -> None:
    from PyQt6.QtGui import QColor, QPainter, QPixmap

    canvas = QPixmap(overlay.width(), overlay.height())
    canvas.fill(QColor(0, 0, 0))
    painter = QPainter(canvas)
    try:
        overlay.paint_edit_mode(painter)
    finally:
        painter.end()

    if canvas.isNull():
        raise RuntimeError("Overlay edit smoke produced a null paint canvas.")


def _exercise_overlay_edit_path(
    raw,
    display,
    logical_geometry,
    scale_x: float,
    scale_y: float,
    physical_left: int,
    physical_top: int,
    cfg,
    store,
    temp_dir: str,
) -> None:
    from PyQt6.QtCore import QPoint, QRect

    from .overlay.widget import FloatingSnipOverlay

    if raw.isNull() or display.isNull():
        raise RuntimeError("Overlay edit smoke received a null pixmap.")
    if logical_geometry.width() < 16 or logical_geometry.height() < 16:
        raise RuntimeError(f"Overlay edit smoke received invalid geometry: {logical_geometry}.")
    if scale_x <= 0 or scale_y <= 0:
        raise RuntimeError(f"Overlay edit smoke received invalid scale: {scale_x}, {scale_y}.")

    overlay = FloatingSnipOverlay(
        raw,
        display,
        logical_geometry,
        scale_x,
        scale_y,
        physical_left,
        physical_top,
        cfg,
        store,
    )
    try:
        widget_rect = overlay.rect()
        selection_w = max(16, min(520, widget_rect.width() - 20))
        selection_h = max(16, min(360, widget_rect.height() - 20))
        selection_x = widget_rect.left() + max(0, (widget_rect.width() - selection_w) // 2)
        selection_y = widget_rect.top() + max(0, (widget_rect.height() - selection_h) // 2)
        selection = QRect(selection_x, selection_y, selection_w, selection_h).intersected(widget_rect)
        physical = overlay.logical_to_physical_rect(selection)
        if physical.width() < 8 or physical.height() < 8:
            raise RuntimeError(f"Overlay edit smoke produced invalid physical selection: {physical}.")

        overlay.selection_rect = selection
        overlay.selection_physical_rect = physical
        overlay.base_edit_pixmap = raw.copy(physical)
        overlay.base_edit_pixmap.setDevicePixelRatio(1.0)
        overlay.edit_pixmap = overlay.base_edit_pixmap.copy()
        overlay.edit_pixmap.setDevicePixelRatio(1.0)
        overlay.mode = "edit"
        overlay.resize(logical_geometry.size())
        overlay.update_toolbar_layout()
        if not overlay.toolbar_buttons:
            raise RuntimeError("Overlay toolbar did not build any buttons.")

        for tool in ("arrow", "rect", "pen", "highlight", "mosaic", "text"):
            overlay.select_tool(tool)
            _paint_overlay_once(overlay)

        draw_end_x = min(max(60, overlay.edit_pixmap.width() - 20), 240)
        draw_end_y = min(max(60, overlay.edit_pixmap.height() - 20), 160)
        for tool in ("arrow", "rect", "pen", "highlight", "mosaic"):
            overlay.select_tool(tool)
            overlay.drag_start = QPoint(20, 20)
            overlay.drag_end = QPoint(draw_end_x, draw_end_y)
            overlay.dragging_annotation = True
            if tool in ("pen", "highlight"):
                overlay.drag_path = [
                    QPoint(20, 20),
                    QPoint(max(30, draw_end_x // 2), max(30, draw_end_y // 2)),
                    QPoint(draw_end_x, draw_end_y),
                ]
            _paint_overlay_once(overlay)
            overlay.dragging_annotation = False
            overlay.drag_path = []

        overlay.select_tool("arrow")
        overlay.push_history()
        overlay.draw_arrow_on_pixmap(QPoint(24, 24), QPoint(draw_end_x, draw_end_y))
        if not overlay.annotations or overlay.annotations[-1].get("type") != "arrow":
            raise RuntimeError("Overlay arrow annotation was not recorded.")

        overlay.select_tool("number")
        overlay.push_history()
        overlay.draw_number_on_pixmap(QPoint(max(30, draw_end_x // 2), max(30, draw_end_y // 2)))
        if overlay.annotations[-1].get("type") != "number":
            raise RuntimeError("Overlay number annotation was not recorded.")

        overlay.select_tool("arrow")
        if overlay.style_panel_kind != "style":
            raise RuntimeError("Overlay style panel did not open.")
        _paint_overlay_once(overlay)

        export_path = Path(temp_dir) / "overlay-selftest.png"
        if not overlay.edit_pixmap.save(str(export_path), "PNG") or not export_path.exists():
            raise RuntimeError("Overlay edit pixmap export failed.")
    finally:
        overlay.close()


def run_overlay_edit_smoke_self_test() -> None:
    from PyQt6.QtCore import QRect
    from PyQt6.QtGui import QColor, QPainter, QPixmap

    from .config import Config
    from .history import CaptureHistoryStore

    app = _ensure_qapplication()

    with _temporary_appdata(), tempfile.TemporaryDirectory(prefix="quickshot_overlay_selftest_") as temp_dir:
        cfg = Config()
        cfg.auto_copy = False
        cfg.auto_history = False
        cfg.show_notifications = False
        cfg.save_dir = temp_dir
        store = CaptureHistoryStore(cfg)

        raw = QPixmap(900, 620)
        raw.fill(QColor(48, 52, 60))
        painter = QPainter(raw)
        try:
            painter.fillRect(QRect(80, 70, 300, 120), QColor(92, 125, 230))
            painter.fillRect(QRect(430, 180, 320, 180), QColor(37, 162, 127))
            painter.fillRect(QRect(180, 410, 520, 90), QColor(245, 159, 0))
        finally:
            painter.end()

        _exercise_overlay_edit_path(raw, raw.copy(), QRect(0, 0, 900, 620), 1.0, 1.0, 0, 0, cfg, store, temp_dir)
        store.flush()
        app.processEvents()


def run_capture_backend_smoke_self_test() -> None:
    from .config import Config
    from .history import CaptureHistoryStore
    from .screenshot import grab_virtual_screen

    app = _ensure_qapplication()

    with _temporary_appdata(), tempfile.TemporaryDirectory(prefix="quickshot_capture_selftest_") as temp_dir:
        cfg = Config()
        cfg.auto_copy = False
        cfg.auto_history = False
        cfg.show_notifications = False
        cfg.hdr_color_accurate = False
        cfg.save_dir = temp_dir
        store = CaptureHistoryStore(cfg)

        raw, display, logical_geometry, scale_x, scale_y, physical_left, physical_top = grab_virtual_screen(False)
        if raw.isNull() or display.isNull():
            raise RuntimeError("Screen capture backend returned a null pixmap.")
        if raw.width() < 16 or raw.height() < 16:
            raise RuntimeError(f"Screen capture backend returned an implausible size: {raw.width()}x{raw.height()}.")
        if logical_geometry.width() < 16 or logical_geometry.height() < 16:
            raise RuntimeError(f"Screen capture backend returned invalid logical geometry: {logical_geometry}.")
        if scale_x <= 0 or scale_y <= 0:
            raise RuntimeError(f"Screen capture backend returned invalid scale: {scale_x}, {scale_y}.")

        _exercise_overlay_edit_path(
            raw,
            display,
            logical_geometry,
            scale_x,
            scale_y,
            physical_left,
            physical_top,
            cfg,
            store,
            temp_dir,
        )
        store.flush()
        app.processEvents()


def run_self_test(name: str) -> int:
    try:
        if name == PRIVACY_OCR_FALLBACK_TEST:
            run_privacy_ocr_fallback_self_test()
        elif name == OVERLAY_EDIT_SMOKE_TEST:
            run_overlay_edit_smoke_self_test()
        elif name == CAPTURE_BACKEND_SMOKE_TEST:
            run_capture_backend_smoke_self_test()
        else:
            raise RuntimeError(f"Unknown self-test: {name}")
    except Exception as exc:
        _write_line("stderr", f"QuickShot self-test failed ({name}): {exc}")
        return 1

    _write_line("stdout", f"QuickShot self-test passed: {name}")
    return 0
