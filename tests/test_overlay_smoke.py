"""Overlay 烟雾测试：确保各标注工具的 select_tool + paint 链路不抛异常。

历史上曾出现 ``QPainterPath`` 漏导入导致点击箭头按钮闪退的事故，本测试
覆盖所有绘制工具，在 paintEvent 路径上跑一遍，提早暴露未定义符号、
NameError、类型不匹配等低级错误。
"""

from __future__ import annotations

import os
import sys
import unittest
from pathlib import Path

# 让测试既能在仓库根目录运行，也能在 tests/ 目录运行
ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtCore import QPoint, QRect  # noqa: E402
from PyQt6.QtGui import QColor, QImage, QPainter, QPixmap  # noqa: E402
from PyQt6.QtWidgets import QApplication  # noqa: E402

from quickshot.config import Config  # noqa: E402
from quickshot.history import CaptureHistoryStore  # noqa: E402
from quickshot.overlay.widget import FloatingSnipOverlay  # noqa: E402


_app: QApplication | None = None


def _ensure_app() -> QApplication:
    global _app
    if _app is None:
        _app = QApplication.instance() or QApplication(sys.argv)
    return _app


def _make_overlay() -> FloatingSnipOverlay:
    _ensure_app()
    cfg = Config()
    store = CaptureHistoryStore(cfg)
    raw = QPixmap(800, 600)
    raw.fill(QColor(60, 60, 60))
    disp = QPixmap(800, 600)
    disp.fill(QColor(60, 60, 60))
    overlay = FloatingSnipOverlay(
        raw, disp, QRect(0, 0, 800, 600), 1.0, 1.0, 0, 0, cfg, store
    )
    overlay.selection_rect = QRect(100, 100, 400, 300)
    overlay.selection_physical_rect = QRect(100, 100, 400, 300)
    overlay.base_edit_pixmap = raw.copy(QRect(100, 100, 400, 300))
    overlay.edit_pixmap = overlay.base_edit_pixmap.copy()
    overlay.mode = "edit"
    overlay.resize(800, 600)
    return overlay


def _make_select_overlay_with_horizontal_desktop_lines() -> FloatingSnipOverlay:
    _ensure_app()
    cfg = Config()
    cfg.snap_to_windows = False
    raw = QPixmap(800, 600)
    painter = QPainter(raw)
    try:
        painter.fillRect(QRect(0, 0, 800, 600), QColor(60, 60, 60))
        painter.fillRect(QRect(0, 100, 800, 1), QColor(245, 245, 245))
        painter.fillRect(QRect(0, 108, 800, 1), QColor(245, 245, 245))
        painter.fillRect(QRect(0, 391, 800, 1), QColor(245, 245, 245))
        painter.fillRect(QRect(0, 399, 800, 1), QColor(245, 245, 245))
    finally:
        painter.end()
    display = raw.copy()
    overlay = FloatingSnipOverlay(
        raw, display, QRect(0, 0, 800, 600), 1.0, 1.0, 0, 0, cfg, None
    )
    overlay.mode = "select"
    overlay.selecting = True
    overlay.start = QPoint(240, 100)
    overlay.end = QPoint(639, 399)
    overlay.resize(800, 600)
    return overlay


def _paint_once(overlay: FloatingSnipOverlay) -> None:
    canvas = QPixmap(overlay.width(), overlay.height())
    canvas.fill(QColor(0, 0, 0))
    painter = QPainter(canvas)
    try:
        overlay.paint_edit_mode(painter)
    finally:
        painter.end()


class OverlayToolSmokeTest(unittest.TestCase):
    """每种工具走一遍 select_tool + paint + 模拟拖拽 paint。"""

    DRAW_TOOLS = ("arrow", "rect", "pen", "highlight", "mosaic")
    # 仅这些工具会激活 stroke 颜色/线宽样式面板（mosaic/blur 无 stroke 配置）
    STYLE_TOOLS = ("arrow", "rect", "pen", "highlight")
    ALL_TOOLS = DRAW_TOOLS + ("text",)

    def test_select_each_tool_and_paint(self) -> None:
        for tool in self.ALL_TOOLS:
            with self.subTest(tool=tool):
                overlay = _make_overlay()
                overlay.select_tool(tool)
                _paint_once(overlay)

    def test_drag_preview_for_draw_tools(self) -> None:
        for tool in self.DRAW_TOOLS:
            with self.subTest(tool=tool):
                overlay = _make_overlay()
                overlay.select_tool(tool)
                overlay.drag_start = QPoint(50, 50)
                overlay.drag_end = QPoint(200, 150)
                overlay.dragging_annotation = True
                if tool in ("pen", "highlight"):
                    overlay.drag_path = [QPoint(50, 50), QPoint(120, 100), QPoint(200, 150)]
                _paint_once(overlay)

    def test_commit_arrow_annotation(self) -> None:
        overlay = _make_overlay()
        overlay.select_tool("arrow")
        overlay.push_history()
        overlay.draw_arrow_on_pixmap(QPoint(50, 50), QPoint(200, 150))
        self.assertEqual(overlay.annotations[-1]["type"], "arrow")

    def test_commit_number_annotation_accepts_click_point(self) -> None:
        overlay = _make_overlay()
        overlay.select_tool("number")
        overlay.push_history()
        overlay.draw_number_on_pixmap(QPoint(120, 90))
        self.assertEqual(overlay.annotations[-1]["type"], "number")
        _paint_once(overlay)

    def test_style_panel_renders_for_all_draw_tools(self) -> None:
        # 直接覆盖之前 QPainterPath 漏导入触发的崩溃路径
        for tool in self.STYLE_TOOLS:
            with self.subTest(tool=tool):
                overlay = _make_overlay()
                overlay.select_tool(tool)
                self.assertEqual(overlay.style_panel_kind, "style")
                _paint_once(overlay)

    def test_ocr_region_preview_paints(self) -> None:
        # 覆盖 OCR 局部框选预览路径，避免 QRectF 这类只在交互分支出现的漏导入。
        overlay = _make_overlay()
        overlay.ocr_region_mode = True
        overlay.active_tool = "none"
        overlay.dragging_annotation = True
        overlay.drag_start = QPoint(40, 40)
        overlay.drag_end = QPoint(220, 140)
        _paint_once(overlay)

    def test_adjusting_selection_skips_toolbar_and_style_panel(self) -> None:
        overlay = _make_overlay()
        overlay.select_tool("arrow")
        overlay.adjusting_selection = True
        calls = []
        orig_toolbar = overlay.draw_toolbar
        orig_style = overlay.draw_style_panel
        try:
            overlay.draw_toolbar = lambda _painter: calls.append("toolbar")
            overlay.draw_style_panel = lambda _painter: calls.append("style")
            _paint_once(overlay)
        finally:
            overlay.draw_toolbar = orig_toolbar
            overlay.draw_style_panel = orig_style
        self.assertEqual(calls, [])

    def test_select_and_edit_mode_use_same_dim_rect(self) -> None:
        overlay = _make_overlay()
        overlay.mode = "select"
        overlay.start = QPoint(100, 100)
        overlay.end = QPoint(499, 399)
        rect = overlay.current_select_rect()
        calls = []
        original = overlay.draw_dim_outside
        try:
            overlay.draw_dim_outside = lambda _painter, clear_rect: calls.append(QRect(clear_rect))
            canvas = QPixmap(overlay.width(), overlay.height())
            painter = QPainter(canvas)
            try:
                overlay.paint_select_mode(painter)
            finally:
                painter.end()
        finally:
            overlay.draw_dim_outside = original
        self.assertEqual(calls, [rect])

    def test_select_mode_edges_do_not_have_white_handle_stripes(self) -> None:
        overlay = _make_overlay()
        overlay.mode = "select"
        overlay.selecting = True
        overlay.start = QPoint(100, 100)
        overlay.end = QPoint(499, 399)
        rect = overlay.current_select_rect()

        canvas = QImage(overlay.width(), overlay.height(), QImage.Format.Format_ARGB32)
        canvas.fill(QColor(0, 0, 0))
        painter = QPainter(canvas)
        try:
            overlay.paint_select_mode(painter)
        finally:
            painter.end()

        white_pixels = 0
        probes = (
            (range(rect.left() - 3, rect.left() + 4), range(rect.center().y() - 10, rect.center().y() + 11)),
            (range(rect.right() - 3, rect.right() + 4), range(rect.center().y() - 10, rect.center().y() + 11)),
            (range(rect.center().x() - 10, rect.center().x() + 11), range(rect.top() - 3, rect.top() + 4)),
            (range(rect.center().x() - 10, rect.center().x() + 11), range(rect.bottom() - 3, rect.bottom() + 4)),
        )
        for xs, ys in probes:
            for x in xs:
                for y in ys:
                    color = canvas.pixelColor(x, y)
                    if color.red() > 220 and color.green() > 220 and color.blue() > 220:
                        white_pixels += 1

        self.assertEqual(white_pixels, 0)

    def test_select_frame_uses_corner_marks_without_full_width_horizontal_edges(self) -> None:
        overlay = _make_overlay()
        overlay.mode = "select"
        overlay.selecting = True
        overlay.start = QPoint(240, 100)
        overlay.end = QPoint(639, 399)
        rect = overlay.current_select_rect()

        canvas = QImage(overlay.width(), overlay.height(), QImage.Format.Format_ARGB32)
        canvas.fill(QColor(0, 0, 0))
        painter = QPainter(canvas)
        try:
            overlay.clear_canvas(painter)
            overlay.draw_frozen_desktop(painter)
            overlay.paint_select_mode(painter)
        finally:
            painter.end()

        top_mid = canvas.pixelColor(rect.center().x(), rect.top()).getRgb()[:3]
        bottom_mid = canvas.pixelColor(rect.center().x(), rect.bottom()).getRgb()[:3]
        left_mid = canvas.pixelColor(rect.left(), rect.center().y()).getRgb()[:3]
        right_mid = canvas.pixelColor(rect.right(), rect.center().y()).getRgb()[:3]
        self.assertEqual(top_mid, (60, 60, 60))
        self.assertEqual(bottom_mid, (60, 60, 60))
        self.assertEqual(left_mid, (60, 60, 60))
        self.assertEqual(right_mid, (60, 60, 60))
        self.assertNotEqual(canvas.pixelColor(rect.left() - 10, rect.top()).getRgb()[:3], top_mid)
        self.assertNotEqual(canvas.pixelColor(rect.right() + 10, rect.bottom()).getRgb()[:3], bottom_mid)

        corner_points = (
            (rect.left() + 8, rect.top()),
            (rect.right() - 8, rect.top()),
            (rect.left() + 8, rect.bottom()),
            (rect.right() - 8, rect.bottom()),
        )
        for point in corner_points:
            with self.subTest(point=point):
                color = canvas.pixelColor(*point)
                self.assertLess(color.red(), 120)
                self.assertLess(color.green(), 120)
                self.assertGreater(color.blue(), 180)

    def test_select_mode_preserves_desktop_lines_without_edge_cleanup_bands(self) -> None:
        overlay = _make_select_overlay_with_horizontal_desktop_lines()
        rect = overlay.current_select_rect()

        canvas = QImage(overlay.width(), overlay.height(), QImage.Format.Format_ARGB32)
        canvas.fill(QColor(0, 0, 0))
        painter = QPainter(canvas)
        try:
            overlay.clear_canvas(painter)
            overlay.draw_frozen_desktop(painter)
            overlay.paint_select_mode(painter)
        finally:
            painter.end()

        outside_xs = (40, rect.left() - 10, rect.right() + 10, overlay.width() - 40)
        line_rows = (rect.top(), rect.top() + 8, rect.bottom() - 8, rect.bottom())
        for y in line_rows:
            with self.subTest(outside_y=y):
                for x in outside_xs:
                    color = canvas.pixelColor(x, y)
                    self.assertGreater(color.red(), 120)
                    self.assertGreater(color.green(), 120)
                    self.assertGreater(color.blue(), 120)
                    self.assertLess(color.red(), 245)
                    self.assertLess(color.green(), 245)
                    self.assertLess(color.blue(), 245)

        for y in line_rows:
            with self.subTest(interior_content_y=y):
                color = canvas.pixelColor(rect.center().x(), y)
                self.assertEqual(color.getRgb()[:3], (245, 245, 245))

        for y in (rect.top() - 2, rect.top() - 1, rect.bottom() + 1, rect.bottom() + 2):
            with self.subTest(adjacent_y=y):
                for x in outside_xs:
                    color = canvas.pixelColor(x, y)
                    self.assertNotEqual((color.red(), color.green(), color.blue()), (245, 245, 245))

    def test_select_mode_light_dim_keeps_outside_sharp(self) -> None:
        _ensure_app()
        cfg = Config()
        cfg.snap_to_windows = False
        raw = QPixmap(800, 600)
        raw.fill(QColor(60, 60, 60))
        raw_painter = QPainter(raw)
        try:
            raw_painter.fillRect(QRect(0, 250, 800, 1), QColor(245, 245, 245))
        finally:
            raw_painter.end()
        display = raw.copy()
        overlay = FloatingSnipOverlay(
            raw, display, QRect(0, 0, 800, 600), 1.0, 1.0, 0, 0, cfg, None
        )
        overlay.mode = "select"
        overlay.selecting = True
        overlay.start = QPoint(240, 100)
        overlay.end = QPoint(639, 399)
        overlay.resize(800, 600)
        rect = overlay.current_select_rect()

        canvas = QImage(overlay.width(), overlay.height(), QImage.Format.Format_ARGB32)
        canvas.fill(QColor(0, 0, 0))
        painter = QPainter(canvas)
        try:
            overlay.clear_canvas(painter)
            overlay.draw_frozen_desktop(painter)
            overlay.paint_select_mode(painter)
        finally:
            painter.end()

        for x in (40, rect.left() - 10, rect.right() + 10, overlay.width() - 40):
            with self.subTest(outside_x=x):
                color = canvas.pixelColor(x, 250)
                self.assertGreater(color.red(), 160)
                for adjacent_y in (249, 251):
                    adjacent = canvas.pixelColor(x, adjacent_y)
                    self.assertLess(adjacent.red(), 70)
        self.assertEqual(canvas.pixelColor(rect.center().x(), 250).getRgb()[:3], (245, 245, 245))

    def test_edit_mode_light_dim_keeps_outside_sharp(self) -> None:
        _ensure_app()
        cfg = Config()
        cfg.snap_to_windows = False
        raw = QPixmap(800, 600)
        raw.fill(QColor(60, 60, 60))
        raw_painter = QPainter(raw)
        try:
            raw_painter.fillRect(QRect(0, 250, 800, 1), QColor(245, 245, 245))
        finally:
            raw_painter.end()
        display = raw.copy()
        overlay = FloatingSnipOverlay(
            raw, display, QRect(0, 0, 800, 600), 1.0, 1.0, 0, 0, cfg, None
        )
        overlay.mode = "edit"
        overlay.selection_rect = QRect(240, 100, 400, 300)
        overlay.selection_physical_rect = QRect(240, 100, 400, 300)
        overlay.base_edit_pixmap = raw.copy(overlay.selection_physical_rect)
        overlay.edit_pixmap = overlay.base_edit_pixmap.copy()
        overlay.resize(800, 600)
        rect = overlay.selection_rect

        canvas = QImage(overlay.width(), overlay.height(), QImage.Format.Format_ARGB32)
        canvas.fill(QColor(0, 0, 0))
        painter = QPainter(canvas)
        try:
            overlay.clear_canvas(painter)
            overlay.draw_frozen_desktop(painter)
            overlay.paint_edit_mode(painter)
        finally:
            painter.end()

        for x in (40, rect.left() - 10, rect.right() + 10, overlay.width() - 40):
            with self.subTest(outside_x=x):
                color = canvas.pixelColor(x, 250)
                self.assertGreater(color.red(), 160)
                for adjacent_y in (249, 251):
                    adjacent = canvas.pixelColor(x, adjacent_y)
                    self.assertLess(adjacent.red(), 70)
        self.assertEqual(canvas.pixelColor(rect.center().x(), 250).getRgb()[:3], (245, 245, 245))

    def test_dim_style_controls_outside_brightness(self) -> None:
        _ensure_app()
        raw = QPixmap(800, 600)
        raw.fill(QColor(80, 80, 80))
        raw_painter = QPainter(raw)
        try:
            raw_painter.fillRect(QRect(0, 250, 800, 1), QColor(245, 245, 245))
        finally:
            raw_painter.end()

        def render(style: str) -> tuple[int, tuple[int, int, int]]:
            cfg = Config()
            cfg.snap_to_windows = False
            cfg.screenshot_dim_style = style
            overlay = FloatingSnipOverlay(
                raw, raw.copy(), QRect(0, 0, 800, 600), 1.0, 1.0, 0, 0, cfg, None
            )
            overlay.mode = "select"
            overlay.selecting = True
            overlay.start = QPoint(240, 100)
            overlay.end = QPoint(639, 399)
            overlay.resize(800, 600)
            rect = overlay.current_select_rect()
            canvas = QImage(overlay.width(), overlay.height(), QImage.Format.Format_ARGB32)
            canvas.fill(QColor(0, 0, 0))
            painter = QPainter(canvas)
            try:
                overlay.clear_canvas(painter)
                overlay.draw_frozen_desktop(painter)
                overlay.paint_select_mode(painter)
            finally:
                painter.end()
            return (
                canvas.pixelColor(40, 250).red(),
                canvas.pixelColor(rect.center().x(), 250).getRgb()[:3],
            )

        clear_outside, clear_inside = render("clear")
        system_outside, system_inside = render("system")
        deep_outside, deep_inside = render("deep")
        self.assertGreater(clear_outside, deep_outside)
        self.assertGreater(system_outside, deep_outside)
        self.assertGreater(clear_outside, system_outside)
        self.assertEqual(clear_inside, (245, 245, 245))
        self.assertEqual(system_inside, (245, 245, 245))
        self.assertEqual(deep_inside, (245, 245, 245))

    def test_default_dim_shade_is_snipaste_light(self) -> None:
        overlay = _make_overlay()
        overlay.mode = "select"
        overlay.selecting = True

        self.assertEqual(overlay.dim_shade().alpha(), 56)

    def test_select_mode_masks_edge_scanlines_on_fractional_scale(self) -> None:
        _ensure_app()
        scale = 1.5
        logical_w, logical_h = 800, 600
        raw_w, raw_h = int(logical_w * scale), int(logical_h * scale)
        cfg = Config()
        cfg.snap_to_windows = False
        raw = QPixmap(raw_w, raw_h)
        raw.fill(QColor(60, 60, 60))
        start = QPoint(240, 100)
        end = QPoint(639, 399)
        top_physical = int(round(start.y() * scale))
        bottom_physical = int(round(end.y() * scale))
        inside_top_physical = top_physical + 9
        inside_bottom_physical = bottom_physical - 12
        outside_only_physical = bottom_physical - 6
        raw_painter = QPainter(raw)
        try:
            for physical_y in (
                top_physical,
                inside_top_physical,
                inside_bottom_physical,
                outside_only_physical,
                bottom_physical - 3,
                bottom_physical - 1,
                bottom_physical,
            ):
                raw_painter.fillRect(QRect(0, physical_y, raw_w, 1), QColor(245, 245, 245))
        finally:
            raw_painter.end()
        display = raw.copy()
        display.setDevicePixelRatio(scale)
        overlay = FloatingSnipOverlay(
            raw, display, QRect(0, 0, logical_w, logical_h), scale, scale, 0, 0, cfg, None
        )
        overlay.mode = "select"
        overlay.selecting = True
        overlay.start = start
        overlay.end = end
        overlay.resize(logical_w, logical_h)
        rect = overlay.current_select_rect()

        canvas = QImage(raw_w, raw_h, QImage.Format.Format_ARGB32)
        canvas.setDevicePixelRatio(scale)
        canvas.fill(QColor(0, 0, 0))
        painter = QPainter(canvas)
        try:
            overlay.clear_canvas(painter)
            overlay.draw_frozen_desktop(painter)
            overlay.paint_select_mode(painter)
        finally:
            painter.end()

        for physical_y in (
            top_physical,
            inside_top_physical,
            inside_bottom_physical,
            outside_only_physical,
            bottom_physical - 3,
            bottom_physical - 1,
            bottom_physical,
        ):
            with self.subTest(physical_y=physical_y):
                for logical_x in (rect.left() - 10, rect.right() + 10):
                    physical_x = int(round(logical_x * scale))
                    color = canvas.pixelColor(physical_x, physical_y)
                    self.assertGreater(color.red(), 120)
                    self.assertGreater(color.green(), 120)
                    self.assertGreater(color.blue(), 120)
                    self.assertLess(color.red(), 245)
                    self.assertLess(color.green(), 245)
                    self.assertLess(color.blue(), 245)

        for physical_y in (
            top_physical,
            inside_top_physical,
            inside_bottom_physical,
            outside_only_physical,
            bottom_physical - 3,
            bottom_physical - 1,
            bottom_physical,
        ):
            with self.subTest(interior_physical_y=physical_y):
                logical_x = rect.center().x()
                physical_x = int(round(logical_x * scale))
                color = canvas.pixelColor(physical_x, physical_y)
                self.assertEqual(color.getRgb()[:3], (245, 245, 245))

    def test_select_mode_dim_uses_four_non_overlapping_bands(self) -> None:
        _ensure_app()
        cfg = Config()
        cfg.snap_to_windows = False
        raw = QPixmap(800, 600)
        raw.fill(QColor(60, 60, 60))
        display = raw.copy()
        overlay = FloatingSnipOverlay(
            raw, display, QRect(0, 0, 800, 600), 1.0, 1.0, 0, 0, cfg, None
        )
        overlay.mode = "select"
        overlay.selecting = True
        overlay.start = QPoint(240, 100)
        overlay.end = QPoint(639, 399)
        overlay.resize(800, 600)
        rect = overlay.current_select_rect()

        bands = overlay.outside_dim_rects(rect)

        self.assertEqual(
            bands,
            (
                QRect(0, 0, 800, 100),
                QRect(0, 400, 800, 200),
                QRect(0, 100, 240, 300),
                QRect(640, 100, 160, 300),
            ),
        )
        for band in bands:
            with self.subTest(band=band):
                self.assertTrue(band.intersected(rect).isNull())

    def test_select_mode_dim_does_not_touch_selection_edge_rows(self) -> None:
        _ensure_app()
        cfg = Config()
        cfg.snap_to_windows = False
        raw = QPixmap(800, 600)
        painter = QPainter(raw)
        try:
            painter.fillRect(QRect(0, 0, 800, 600), QColor(60, 60, 60))
            painter.fillRect(QRect(0, 100, 800, 1), QColor(245, 245, 245))
            painter.fillRect(QRect(0, 399, 800, 1), QColor(245, 245, 245))
        finally:
            painter.end()
        display = raw.copy()
        overlay = FloatingSnipOverlay(
            raw, display, QRect(0, 0, 800, 600), 1.0, 1.0, 0, 0, cfg, None
        )
        overlay.mode = "select"
        overlay.selecting = True
        overlay.start = QPoint(240, 100)
        overlay.end = QPoint(639, 399)
        overlay.resize(800, 600)
        rect = overlay.current_select_rect()

        canvas = QImage(overlay.width(), overlay.height(), QImage.Format.Format_ARGB32)
        canvas.fill(QColor(0, 0, 0))
        canvas_painter = QPainter(canvas)
        try:
            overlay.clear_canvas(canvas_painter)
            overlay.draw_frozen_desktop(canvas_painter)
            overlay.paint_select_mode(canvas_painter)
        finally:
            canvas_painter.end()

        for y in (rect.top(), rect.bottom()):
            with self.subTest(selection_edge_y=y):
                self.assertEqual(canvas.pixelColor(rect.center().x(), y).getRgb()[:3], (245, 245, 245))
                self.assertNotEqual(canvas.pixelColor(rect.left() - 1, y).getRgb()[:3], (245, 245, 245))
                self.assertNotEqual(canvas.pixelColor(rect.right() + 1, y).getRgb()[:3], (245, 245, 245))

    def test_snap_guides_are_hidden_by_default(self) -> None:
        overlay = _make_overlay()
        overlay.mode = "select"
        overlay.start = QPoint(240, 100)
        overlay.end = QPoint(639, 399)
        overlay._snap_edges = [
            ("top", QRect(0, 100, 800, 300)),
            ("bottom", QRect(0, 100, 800, 300)),
        ]

        canvas = QImage(overlay.width(), overlay.height(), QImage.Format.Format_ARGB32)
        canvas.fill(QColor(0, 0, 0, 0))
        painter = QPainter(canvas)
        try:
            overlay.draw_snap_guides(painter)
        finally:
            painter.end()

        for y in (100, 399):
            with self.subTest(y=y):
                for x in (40, overlay.width() // 2, overlay.width() - 40):
                    self.assertEqual(canvas.pixelColor(x, y).alpha(), 0)

    def test_edit_mode_skips_selection_snapshot_by_default(self) -> None:
        overlay = _make_overlay()
        calls = []
        original = overlay.draw_selection_snapshot
        try:
            overlay.draw_selection_snapshot = lambda _painter: calls.append(True)
            _paint_once(overlay)
        finally:
            overlay.draw_selection_snapshot = original
        self.assertEqual(calls, [])

    def test_edit_mode_draws_selection_snapshot_when_required(self) -> None:
        overlay = _make_overlay()
        overlay.selection_snapshot_required = True
        overlay.update_selection_display_cache()
        calls = []
        original = overlay.draw_selection_snapshot
        try:
            overlay.draw_selection_snapshot = lambda _painter: calls.append(True)
            _paint_once(overlay)
        finally:
            overlay.draw_selection_snapshot = original
        self.assertEqual(calls, [True])


if __name__ == "__main__":
    unittest.main()
