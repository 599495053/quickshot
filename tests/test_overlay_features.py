"""Overlay 新功能测试：网格、尺寸锁定、工具切换、选区复用。

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

from PyQt6.QtCore import QPoint, QRect  # noqa: E402
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


class SizeLockTest(unittest.TestCase):
    """测试尺寸锁定功能。"""

    def test_size_lock_default_off(self) -> None:
        overlay = _make_overlay()
        self.assertFalse(overlay.size_locked)

    def test_toggle_size_lock_on(self) -> None:
        overlay = _make_overlay()
        overlay.toggle_size_lock()
        self.assertTrue(overlay.size_locked)
        self.assertEqual(overlay.locked_size, overlay.selection_rect.size())

    def test_toggle_size_lock_off(self) -> None:
        overlay = _make_overlay()
        overlay.toggle_size_lock()
        overlay.toggle_size_lock()
        self.assertFalse(overlay.size_locked)

    def test_size_lock_preserves_size(self) -> None:
        overlay = _make_overlay()
        original_size = overlay.selection_rect.size()
        overlay.toggle_size_lock()
        self.assertEqual(overlay.locked_size, original_size)


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


class ReuseSelectionTest(unittest.TestCase):
    """测试选区复用功能。"""

    def test_reuse_when_no_last_selection(self) -> None:
        overlay = _make_overlay()
        FloatingSnipOverlay._last_selection_rect = QRect()
        FloatingSnipOverlay._last_selection_physical_rect = QRect()
        result = overlay.reuse_last_selection()
        self.assertFalse(result)

    def test_reuse_saves_and_restores(self) -> None:
        overlay = _make_overlay()
        # 先进入编辑模式，会保存选区
        overlay.enter_edit_mode(QRect(100, 100, 400, 300), QRect(100, 100, 400, 300))
        saved_rect = QRect(FloatingSnipOverlay._last_selection_rect)

        # 修改选区
        overlay.selection_rect = QRect(50, 50, 200, 150)

        # 复用应该恢复
        overlay.reuse_last_selection()
        self.assertEqual(overlay.selection_rect, saved_rect)

    def test_reuse_with_size_lock(self) -> None:
        overlay = _make_overlay()
        overlay.enter_edit_mode(QRect(100, 100, 400, 300), QRect(100, 100, 400, 300))
        original_size = overlay.selection_rect.size()
        overlay.size_locked = True
        overlay.locked_size = original_size

        # 复用应该保持原来的选区
        overlay.reuse_last_selection()
        self.assertEqual(overlay.selection_rect.size(), original_size)


class ToolbarButtonTest(unittest.TestCase):
    """测试工具栏按钮布局和点击检测。"""

    def test_toolbar_items_count(self) -> None:
        items = FloatingSnipOverlay.toolbar_items()
        self.assertGreater(len(items), 0)

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
