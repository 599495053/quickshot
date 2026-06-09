"""SelectionMixin + DrawingMixin 测试：选区管理、标注绘制。"""

from __future__ import annotations

import os
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtCore import QPoint, QRect, Qt  # noqa: E402
from PyQt6.QtGui import QColor, QPixmap  # noqa: E402
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


# ═══════════════════════════════════════════════════════════════════
#  SelectionMixin 测试
# ═══════════════════════════════════════════════════════════════════

class SelectionHandleAtTest(unittest.TestCase):
    """选区把手碰撞检测。"""

    def test_corner_tl(self):
        ov = _make_overlay()
        r = ov.selection_rect
        handle = ov.selection_handle_at(QPoint(r.left(), r.top()))
        self.assertEqual(handle, "tl")

    def test_corner_br(self):
        ov = _make_overlay()
        r = ov.selection_rect
        handle = ov.selection_handle_at(QPoint(r.right(), r.bottom()))
        self.assertEqual(handle, "br")

    def test_edge_left(self):
        ov = _make_overlay()
        r = ov.selection_rect
        mid_y = (r.top() + r.bottom()) // 2
        handle = ov.selection_handle_at(QPoint(r.left(), mid_y))
        self.assertEqual(handle, "l")

    def test_edge_right(self):
        ov = _make_overlay()
        r = ov.selection_rect
        mid_y = (r.top() + r.bottom()) // 2
        handle = ov.selection_handle_at(QPoint(r.right(), mid_y))
        self.assertEqual(handle, "r")

    def test_edge_top(self):
        ov = _make_overlay()
        r = ov.selection_rect
        mid_x = (r.left() + r.right()) // 2
        handle = ov.selection_handle_at(QPoint(mid_x, r.top()))
        self.assertEqual(handle, "t")

    def test_edge_bottom(self):
        ov = _make_overlay()
        r = ov.selection_rect
        mid_x = (r.left() + r.right()) // 2
        handle = ov.selection_handle_at(QPoint(mid_x, r.bottom()))
        self.assertEqual(handle, "b")

    def test_move_inside(self):
        ov = _make_overlay()
        r = ov.selection_rect
        center = r.center()
        handle = ov.selection_handle_at(center)
        self.assertEqual(handle, "move")

    def test_empty_outside(self):
        ov = _make_overlay()
        handle = ov.selection_handle_at(QPoint(5, 5))
        self.assertEqual(handle, "")


class CursorForHandleTest(unittest.TestCase):
    """把手 -> 光标映射。"""

    def test_tl_cursor(self):
        self.assertEqual(
            FloatingSnipOverlay.cursor_for_handle("tl"),
            Qt.CursorShape.SizeFDiagCursor,
        )

    def test_tr_cursor(self):
        self.assertEqual(
            FloatingSnipOverlay.cursor_for_handle("tr"),
            Qt.CursorShape.SizeBDiagCursor,
        )

    def test_left_right_cursor(self):
        for h in ("l", "r"):
            with self.subTest(handle=h):
                self.assertEqual(
                    FloatingSnipOverlay.cursor_for_handle(h),
                    Qt.CursorShape.SizeHorCursor,
                )

    def test_top_bottom_cursor(self):
        for h in ("t", "b"):
            with self.subTest(handle=h):
                self.assertEqual(
                    FloatingSnipOverlay.cursor_for_handle(h),
                    Qt.CursorShape.SizeVerCursor,
                )

    def test_move_cursor(self):
        self.assertEqual(
            FloatingSnipOverlay.cursor_for_handle("move"),
            Qt.CursorShape.SizeAllCursor,
        )

    def test_empty_cursor(self):
        self.assertEqual(
            FloatingSnipOverlay.cursor_for_handle(""),
            Qt.CursorShape.ArrowCursor,
        )


class MoveRectWithinScreenTest(unittest.TestCase):
    """选区移动边界约束。"""

    def test_no_change_when_inside(self):
        ov = _make_overlay()
        rect = QRect(200, 200, 100, 100)
        moved = ov.move_rect_within_screen(rect)
        self.assertEqual(moved, rect)

    def test_clamp_left_top(self):
        ov = _make_overlay()
        rect = QRect(-50, -30, 100, 100)
        moved = ov.move_rect_within_screen(rect)
        self.assertGreaterEqual(moved.left(), 0)
        self.assertGreaterEqual(moved.top(), 0)

    def test_clamp_right_bottom(self):
        ov = _make_overlay()
        rect = QRect(750, 550, 100, 100)
        moved = ov.move_rect_within_screen(rect)
        self.assertLessEqual(moved.right(), ov.width() - 1)
        self.assertLessEqual(moved.bottom(), ov.height() - 1)


class ResizedRectFromHandleTest(unittest.TestCase):
    """选区缩放逻辑。"""

    def test_resize_right_edge(self):
        ov = _make_overlay()
        ov.adjust_origin_rect = QRect(100, 100, 400, 300)
        new_rect = ov.resized_rect_from_handle("r", QPoint(600, 250))
        self.assertGreater(new_rect.right(), 499)

    def test_resize_minimum_width(self):
        ov = _make_overlay()
        ov.adjust_origin_rect = QRect(100, 100, 400, 300)
        new_rect = ov.resized_rect_from_handle("r", QPoint(105, 250))
        self.assertGreaterEqual(new_rect.width(), 28)

    def test_resize_clamps_to_screen(self):
        ov = _make_overlay()
        ov.adjust_origin_rect = QRect(100, 100, 400, 300)
        new_rect = ov.resized_rect_from_handle("r", QPoint(9999, 250))
        self.assertLessEqual(new_rect.right(), ov.width() - 1)


class SelectionAdjustTest(unittest.TestCase):
    """选区调整流程：begin → update → finish。"""

    def test_begin_sets_flags(self):
        ov = _make_overlay()
        ov.begin_selection_adjust("move", QPoint(300, 250))
        self.assertTrue(ov.adjusting_selection)
        self.assertEqual(ov.adjust_mode, "move")

    def test_begin_resize_sets_mode(self):
        ov = _make_overlay()
        ov.begin_selection_adjust("r", QPoint(500, 250))
        self.assertTrue(ov.adjusting_selection)
        self.assertEqual(ov.adjust_mode, "resize")

    def test_update_move_shifts_rect(self):
        ov = _make_overlay()
        ov.begin_selection_adjust("move", QPoint(300, 250))
        old_rect = QRect(ov.selection_rect)
        ov.update_selection_adjust(QPoint(350, 280))
        self.assertNotEqual(ov.selection_rect, old_rect)
        self.assertEqual(ov.selection_rect.width(), old_rect.width())
        self.assertEqual(ov.selection_rect.height(), old_rect.height())

    def test_update_resize_changes_dimensions(self):
        ov = _make_overlay()
        ov.begin_selection_adjust("r", QPoint(500, 250))
        old_width = ov.selection_rect.width()
        ov.update_selection_adjust(QPoint(550, 250))
        self.assertNotEqual(ov.selection_rect.width(), old_width)

    def test_finish_clears_state(self):
        ov = _make_overlay()
        ov.begin_selection_adjust("move", QPoint(300, 250))
        ov.update_selection_adjust(QPoint(350, 280))
        ov.finish_selection_adjust()
        self.assertFalse(ov.adjusting_selection)
        self.assertEqual(ov.adjust_mode, "")

    def test_adjust_clears_annotations_on_first_change(self):
        ov = _make_overlay()
        ov.annotations.append({"type": "arrow", "x1": 0, "y1": 0, "x2": 10, "y2": 10, "color": "#fff", "width": 2})
        ov.push_history()
        ov.begin_selection_adjust("move", QPoint(300, 250))
        ov.update_selection_adjust(QPoint(350, 280))
        self.assertEqual(len(ov.annotations), 0)
        self.assertEqual(len(ov.history), 0)


class EnterEditModeTest(unittest.TestCase):
    """进入编辑模式。"""

    def test_sets_mode_and_selection(self):
        ov = _make_overlay()
        ov.mode = "select"
        ov.enter_edit_mode(QRect(100, 100, 300, 200), QRect(100, 100, 300, 200))
        self.assertEqual(ov.mode, "edit")
        self.assertEqual(ov.selection_rect, QRect(100, 100, 300, 200))

    def test_creates_edit_pixmap(self):
        ov = _make_overlay()
        ov.mode = "select"
        ov.enter_edit_mode(QRect(100, 100, 300, 200), QRect(100, 100, 300, 200))
        self.assertFalse(ov.edit_pixmap.isNull())
        self.assertEqual(ov.edit_pixmap.width(), 300)
        self.assertEqual(ov.edit_pixmap.height(), 200)

    def test_clears_annotations_and_history(self):
        ov = _make_overlay()
        ov.mode = "select"
        ov.annotations.append({"type": "arrow", "x1": 0, "y1": 0, "x2": 10, "y2": 10, "color": "#fff", "width": 2})
        ov.push_history()
        ov.enter_edit_mode(QRect(100, 100, 300, 200), QRect(100, 100, 300, 200))
        self.assertEqual(len(ov.annotations), 0)
        self.assertEqual(len(ov.history), 0)

    def test_resets_tool(self):
        ov = _make_overlay()
        ov.mode = "select"
        ov.active_tool = "arrow"
        ov.enter_edit_mode(QRect(100, 100, 300, 200), QRect(100, 100, 300, 200))
        self.assertEqual(ov.active_tool, "none")

    def test_enter_edit_mode_message_shows_workflow_hint(self):
        ov = _make_overlay()
        ov.mode = "select"
        ov.config.auto_copy = False
        ov.config.workflow_preset = "auto_save"

        ov.enter_edit_mode(QRect(100, 100, 300, 200), QRect(100, 100, 300, 200))

        self.assertIn("自动保存", ov.message)
        self.assertIn("默认目录", ov.message)

    def test_privacy_first_skips_auto_copy_and_starts_detection(self):
        ov = _make_overlay()
        ov.mode = "select"
        ov.config.auto_copy = True
        ov.config.workflow_privacy_first = True
        calls = []
        ov.apply_mosaic_to_selection = lambda: calls.append(True)

        with (
            patch("quickshot.overlay._selection.copy_pixmap_to_clipboard") as copy_clipboard,
            patch("PyQt6.QtCore.QTimer.singleShot", side_effect=lambda _ms, callback: callback()),
        ):
            ov.enter_edit_mode(QRect(100, 100, 300, 200), QRect(100, 100, 300, 200))

        copy_clipboard.assert_not_called()
        self.assertEqual(calls, [True])


# ═══════════════════════════════════════════════════════════════════
#  DrawingMixin 测试
# ═══════════════════════════════════════════════════════════════════

class DrawArrowTest(unittest.TestCase):

    def test_draw_arrow_adds_annotation(self):
        ov = _make_overlay()
        ov.select_tool("arrow")
        ov.push_history()
        ov.draw_arrow_on_pixmap(QPoint(50, 50), QPoint(200, 150))
        self.assertEqual(len(ov.annotations), 1)
        self.assertEqual(ov.annotations[0]["type"], "arrow")

    def test_draw_arrow_records_coordinates(self):
        ov = _make_overlay()
        ov.select_tool("arrow")
        ov.push_history()
        ov.draw_arrow_on_pixmap(QPoint(50, 60), QPoint(200, 160))
        item = ov.annotations[0]
        self.assertEqual(item["x1"], 50)
        self.assertEqual(item["y1"], 60)
        self.assertEqual(item["x2"], 200)
        self.assertEqual(item["y2"], 160)


class DrawRectTest(unittest.TestCase):

    def test_draw_rect_adds_annotation(self):
        ov = _make_overlay()
        ov.push_history()
        ov.draw_rect_on_pixmap(QRect(50, 50, 100, 80))
        self.assertEqual(len(ov.annotations), 1)
        self.assertEqual(ov.annotations[0]["type"], "rect")

    def test_draw_rect_records_dimensions(self):
        ov = _make_overlay()
        ov.push_history()
        ov.draw_rect_on_pixmap(QRect(50, 50, 100, 80))
        item = ov.annotations[0]
        self.assertEqual(item["w"], 100)
        self.assertEqual(item["h"], 80)

    def test_draw_rect_with_fill(self):
        ov = _make_overlay()
        ov.fill_mode = "half"
        ov.push_history()
        ov.draw_rect_on_pixmap(QRect(50, 50, 100, 80))
        self.assertEqual(ov.annotations[0].get("fill"), "half")
        color = ov.edit_pixmap.toImage().pixelColor(100, 90)
        self.assertGreater(color.red(), 80)
        self.assertLess(color.green(), 80)

    def test_draw_rect_outside_pixmap_noop(self):
        ov = _make_overlay()
        count_before = len(ov.annotations)
        ov.draw_rect_on_pixmap(QRect(9999, 9999, 100, 80))
        self.assertEqual(len(ov.annotations), count_before)


class DrawEllipseTest(unittest.TestCase):

    def test_draw_ellipse_adds_annotation(self):
        ov = _make_overlay()
        ov.push_history()
        ov.draw_ellipse_on_pixmap(QRect(50, 50, 120, 80))
        self.assertEqual(len(ov.annotations), 1)
        self.assertEqual(ov.annotations[0]["type"], "ellipse")


class DrawDashedRectTest(unittest.TestCase):

    def test_draw_dashed_rect_adds_annotation(self):
        ov = _make_overlay()
        ov.push_history()
        ov.draw_dashed_rect_on_pixmap(QRect(50, 50, 100, 80))
        self.assertEqual(len(ov.annotations), 1)
        self.assertEqual(ov.annotations[0]["type"], "dashed_rect")


class DrawNumberTest(unittest.TestCase):

    def test_draw_number_increments_counter(self):
        ov = _make_overlay()
        ov.select_tool("number")
        ov.push_history()
        ov.draw_number_on_pixmap(QPoint(100, 100))
        self.assertEqual(ov.annotations[0]["num"], 1)
        self.assertEqual(ov.number_counter, 2)

    def test_draw_multiple_numbers(self):
        ov = _make_overlay()
        ov.select_tool("number")
        ov.push_history()
        ov.draw_number_on_pixmap(QPoint(100, 100))
        ov.draw_number_on_pixmap(QPoint(200, 200))
        self.assertEqual(ov.annotations[1]["num"], 2)
        self.assertEqual(ov.number_counter, 3)


class DrawFreehandTest(unittest.TestCase):

    def test_draw_freehand_adds_annotation(self):
        ov = _make_overlay()
        ov.select_tool("pen")
        ov.push_history()
        points = [QPoint(50, 50), QPoint(60, 60), QPoint(70, 55)]
        ov.draw_freehand_on_pixmap(points)
        self.assertEqual(len(ov.annotations), 1)
        self.assertEqual(ov.annotations[0]["type"], "pen")

    def test_draw_freehand_too_few_points_noop(self):
        ov = _make_overlay()
        count_before = len(ov.annotations)
        ov.draw_freehand_on_pixmap([QPoint(50, 50)])
        self.assertEqual(len(ov.annotations), count_before)


class DrawHighlightTest(unittest.TestCase):

    def test_draw_highlight_adds_annotation(self):
        ov = _make_overlay()
        ov.select_tool("highlight")
        ov.push_history()
        points = [QPoint(50, 50), QPoint(100, 50), QPoint(150, 50)]
        ov.draw_highlight_on_pixmap(points)
        self.assertEqual(len(ov.annotations), 1)
        self.assertEqual(ov.annotations[0]["type"], "highlight")


class DrawEraserTest(unittest.TestCase):

    def test_erase_stroke_restores_base_pixels_and_rebuilds(self):
        ov = _make_overlay()
        ov.stroke_color_name = "#ff0000"
        points = [QPoint(50, 50), QPoint(140, 50)]
        ov.draw_freehand_on_pixmap(points)
        self.assertEqual(ov.edit_pixmap.toImage().pixelColor(90, 50).name().lower(), "#ff0000")

        ov.stroke_width = 8
        ov.erase_stroke(points)

        self.assertEqual(ov.annotations[-1]["type"], "eraser")
        self.assertEqual(ov.edit_pixmap.toImage().pixelColor(90, 50).getRgb()[:3], (60, 60, 60))
        ov.rebuild_edit_pixmap()
        self.assertEqual(ov.edit_pixmap.toImage().pixelColor(90, 50).getRgb()[:3], (60, 60, 60))

    def test_eraser_size_controls_restored_area(self):
        def overlay_with_red_stroke() -> FloatingSnipOverlay:
            ov = _make_overlay()
            ov.stroke_color_name = "#ff0000"
            ov.stroke_width = 28
            ov.draw_freehand_on_pixmap([QPoint(40, 50), QPoint(160, 50)])
            self.assertGreater(ov.edit_pixmap.toImage().pixelColor(100, 59).red(), 200)
            return ov

        small = overlay_with_red_stroke()
        small.stroke_width = 3
        small.erase_stroke([QPoint(40, 50), QPoint(160, 50)])
        small_pixel = small.edit_pixmap.toImage().pixelColor(100, 59)

        large = overlay_with_red_stroke()
        large.stroke_width = 12
        large.erase_stroke([QPoint(40, 50), QPoint(160, 50)])
        large_pixel = large.edit_pixmap.toImage().pixelColor(100, 59)

        self.assertGreater(small_pixel.red(), 200)
        self.assertEqual(large_pixel.getRgb()[:3], (60, 60, 60))


if __name__ == "__main__":
    unittest.main()
