"""Overlay 新功能测试：网格、工具切换、工具栏按钮、样式面板。

覆盖 widget.py 中新增的交互功能，确保这些功能在各种场景下正常工作。
"""

from __future__ import annotations

import os
import sys
import unittest
from pathlib import Path

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
    cfg.grid_color = "#ffffff80"
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


class GridToggleTest(unittest.TestCase):
    """测试网格辅助功能。"""

    def test_grid_default_off(self) -> None:
        overlay = _make_overlay()
        self.assertFalse(overlay.grid_visible)

    def test_toggle_grid_on(self) -> None:
        overlay = _make_overlay()
        overlay.toggle_grid()
        self.assertTrue(overlay.grid_visible)
        self.assertIn("网格", overlay.message)

    def test_toggle_grid_off(self) -> None:
        overlay = _make_overlay()
        overlay.toggle_grid()
        overlay.toggle_grid()
        self.assertFalse(overlay.grid_visible)

    def test_grid_paint_no_error(self) -> None:
        overlay = _make_overlay()
        overlay.grid_visible = True
        from PyQt6.QtGui import QPainter
        canvas = QPixmap(800, 600)
        painter = QPainter(canvas)
        try:
            overlay.draw_grid(painter)
        finally:
            painter.end()

    def test_default_grid_color_uses_trailing_alpha(self) -> None:
        overlay = _make_overlay()
        from PyQt6.QtGui import QPainter
        canvas = QPixmap(800, 600)
        painter = QPainter(canvas)
        try:
            overlay.draw_grid(painter)
            pen_color = overlay._pen_grid.color()
        finally:
            painter.end()
        self.assertEqual((pen_color.red(), pen_color.green(), pen_color.blue(), pen_color.alpha()), (255, 255, 255, 128))


class ToolSwitchTest(unittest.TestCase):
    """测试工具切换功能。"""

    def test_initial_last_tool_is_none(self) -> None:
        overlay = _make_overlay()
        self.assertEqual(overlay.last_tool, "none")

    def test_select_tool_updates_last_tool(self) -> None:
        overlay = _make_overlay()
        overlay.select_tool("arrow")
        self.assertEqual(overlay.active_tool, "arrow")
        overlay.select_tool("rect")
        self.assertEqual(overlay.last_tool, "arrow")
        self.assertEqual(overlay.active_tool, "rect")

    def test_switch_to_last_tool(self) -> None:
        overlay = _make_overlay()
        overlay.select_tool("arrow")
        overlay.select_tool("rect")
        overlay.switch_to_last_tool()
        self.assertEqual(overlay.active_tool, "arrow")

    def test_switch_to_last_tool_when_none(self) -> None:
        overlay = _make_overlay()
        overlay.switch_to_last_tool()
        self.assertEqual(overlay.active_tool, "none")

    def test_deselect_tool_toggles(self) -> None:
        overlay = _make_overlay()
        overlay.select_tool("arrow")
        overlay.select_tool("arrow")
        self.assertEqual(overlay.active_tool, "none")


class ToolbarButtonTest(unittest.TestCase):
    """测试工具栏按钮布局和点击检测。"""

    def test_toolbar_items_count(self) -> None:
        items = FloatingSnipOverlay.toolbar_items()
        self.assertGreater(len(items), 0)

    def test_toolbar_omits_size_lock_and_reuse(self) -> None:
        keys = [item[0] for item in FloatingSnipOverlay.toolbar_items()]
        self.assertNotIn("size_lock", keys)
        self.assertNotIn("reuse", keys)
        self.assertNotIn("shadow", keys)
        self.assertNotIn("border", keys)
        self.assertNotIn("picker", keys)
        self.assertIn("eraser", keys)

    def test_button_at_returns_key(self) -> None:
        overlay = _make_overlay()
        overlay.update_toolbar_layout()
        # 找到第一个按钮的位置
        for key, rect in overlay.toolbar_buttons.items():
            center = rect.center()
            result = overlay.button_at(center)
            self.assertEqual(result, key)
            break

    def test_button_at_empty_pos(self) -> None:
        overlay = _make_overlay()
        overlay.update_toolbar_layout()
        result = overlay.button_at(QPoint(0, 0))
        self.assertEqual(result, "")

    def test_toolbar_wraps_inside_narrow_overlay(self) -> None:
        overlay = _make_overlay()
        overlay.resize(640, 520)
        overlay.selection_rect = QRect(80, 120, 420, 220)

        overlay.update_toolbar_layout()

        self.assertGreater(overlay.toolbar_rect.height(), 50)
        self.assertGreaterEqual(overlay.toolbar_rect.left(), 10)
        self.assertLessEqual(overlay.toolbar_rect.right(), overlay.width() - 10)
        for rect in overlay.toolbar_buttons.values():
            self.assertTrue(overlay.toolbar_rect.contains(rect))

    def test_button_at_works_after_toolbar_wrap(self) -> None:
        overlay = _make_overlay()
        overlay.resize(640, 520)
        overlay.selection_rect = QRect(80, 120, 420, 220)
        overlay.update_toolbar_layout()

        for key, rect in overlay.toolbar_buttons.items():
            with self.subTest(key=key):
                self.assertEqual(overlay.button_at(rect.center()), key)

    def test_toolbar_tip_rect_tracks_hover_anchor(self) -> None:
        overlay = _make_overlay()
        overlay.update_toolbar_layout()
        anchor = overlay.toolbar_buttons["arrow"].center()

        tip_rect = overlay.toolbar_tip_rect("Arrow tool", anchor)

        self.assertFalse(tip_rect.isNull())
        self.assertLess(abs(tip_rect.left() - (anchor.x() + 14)), 3)
        self.assertNotEqual(tip_rect.center().x(), overlay.toolbar_rect.center().x())


class FloatingBubbleLayoutTest(unittest.TestCase):

    def test_size_label_uses_bottom_when_top_space_is_tight(self) -> None:
        overlay = _make_overlay()
        target = QRect(100, 4, 180, 80)

        label = overlay.size_label_rect(target, 180, 80)

        self.assertGreater(label.top(), target.bottom())
        self.assertFalse(label.intersects(target))

    def test_size_label_avoids_toolbar_when_selection_near_bottom(self) -> None:
        overlay = _make_overlay()
        target = QRect(120, 500, 360, 80)
        overlay.selection_rect = target
        overlay.update_toolbar_layout()

        label = overlay.size_label_rect(target, 360, 80)

        self.assertFalse(label.intersects(overlay.toolbar_rect))
        self.assertTrue(overlay.rect().contains(label))

    def test_message_rect_avoids_wrapped_toolbar(self) -> None:
        overlay = _make_overlay()
        overlay.resize(640, 520)
        overlay.selection_rect = QRect(80, 120, 420, 220)
        overlay.message = "Toolbar message"
        overlay.update_toolbar_layout()

        message_rect = overlay.current_message_rect()

        self.assertFalse(message_rect.isNull())
        self.assertFalse(message_rect.intersects(overlay.toolbar_rect))
        self.assertTrue(overlay.rect().contains(message_rect))

    def test_message_rect_avoids_bottom_selection_when_space_is_tight(self) -> None:
        overlay = _make_overlay()
        overlay.resize(640, 520)
        overlay.selection_rect = QRect(80, 420, 420, 80)
        overlay.message = "Bottom message"
        overlay.update_toolbar_layout()

        message_rect = overlay.current_message_rect()

        self.assertTrue(overlay.rect().contains(message_rect))
        self.assertFalse(message_rect.intersects(overlay.selection_rect))

    def test_window_hover_label_avoids_size_label_and_target_rect(self) -> None:
        overlay = _make_overlay()
        target = QRect(100, 430, 250, 80)
        size_label = overlay.size_label_rect(target, target.width(), target.height())

        hover_label = overlay.window_hover_label_rect(target, 220, 30)

        self.assertFalse(hover_label.isNull())
        self.assertFalse(hover_label.intersects(target))
        self.assertFalse(hover_label.intersects(size_label))
        self.assertTrue(overlay.rect().contains(hover_label))


class StylePanelTest(unittest.TestCase):
    """测试样式面板功能。"""

    def test_toggle_style_panel_color(self) -> None:
        overlay = _make_overlay()
        # 先确保 style_panel_kind 为空
        overlay.style_panel_kind = ""
        overlay.toggle_style_panel("color")
        self.assertEqual(overlay.style_panel_kind, "style")
        # 再次切换应该关闭
        overlay.toggle_style_panel("color")
        self.assertEqual(overlay.style_panel_kind, "")

    def test_close_style_panel(self) -> None:
        overlay = _make_overlay()
        overlay.select_tool("arrow")
        overlay.close_style_panel()
        self.assertEqual(overlay.style_panel_kind, "")

    def test_style_tools_open_style_panel(self) -> None:
        overlay = _make_overlay()
        for tool in ("arrow", "rect", "ellipse", "dashed_rect", "pen", "highlight"):
            with self.subTest(tool=tool):
                overlay.select_tool(tool)
                self.assertEqual(overlay.style_panel_kind, "style")
                overlay.select_tool(tool)  # 退出当前工具，避免影响下一个 subTest

    def test_non_style_tools_keep_style_panel_closed(self) -> None:
        overlay = _make_overlay()
        for tool in ("text", "number", "eraser", "mosaic", "blur"):
            with self.subTest(tool=tool):
                overlay.select_tool(tool)
                self.assertEqual(overlay.style_panel_kind, "")
                overlay.active_tool = "none"

    def test_color_panel_contains_picker_action(self) -> None:
        overlay = _make_overlay()
        overlay.update_toolbar_layout()
        overlay.toggle_style_panel("color")

        self.assertIn("action:picker", overlay.style_option_rects)

    def test_color_panel_picker_action_selects_picker(self) -> None:
        overlay = _make_overlay()
        overlay.update_toolbar_layout()
        overlay.toggle_style_panel("color")

        overlay.apply_style_panel_option("action:picker")

        self.assertEqual(overlay.active_tool, "picker")
        self.assertEqual(overlay.style_panel_kind, "")

    def test_click_outside_style_panel_closes_it(self) -> None:
        overlay = _make_overlay()
        overlay.select_tool("arrow")
        overlay.update_toolbar_layout()
        overlay.update_style_panel_layout()
        self.assertEqual(overlay.style_panel_kind, "style")
        outside = QPoint(0, 0)

        class _Evt:
            def button(self):
                return Qt.MouseButton.LeftButton

            def position(self):
                class _Pos:
                    def toPoint(self_inner):
                        return outside
                return _Pos()

        overlay._handle_mouse_press(_Evt())
        self.assertEqual(overlay.style_panel_kind, "")

    def test_cycle_stroke_color(self) -> None:
        overlay = _make_overlay()
        original = overlay.stroke_color_name
        overlay.cycle_stroke_color()
        self.assertNotEqual(overlay.stroke_color_name, original)

    def test_cycle_stroke_width(self) -> None:
        overlay = _make_overlay()
        original = overlay.stroke_width
        overlay.cycle_stroke_width()
        self.assertNotEqual(overlay.stroke_width, original)


if __name__ == "__main__":
    unittest.main()
