"""EventMixin 测试：命令分发、鼠标/键盘事件、工具栏动作。"""

from __future__ import annotations

import os
import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtCore import QRect, Qt  # noqa: E402
from PyQt6.QtGui import QColor, QPixmap  # noqa: E402
from PyQt6.QtWidgets import QApplication  # noqa: E402

from quickshot.config import Config  # noqa: E402
from quickshot.history import CaptureHistoryStore  # noqa: E402
from quickshot.overlay._events import build_tool_key_map  # noqa: E402
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


# ── 命令分发 ──

class ExecuteCommandTest(unittest.TestCase):

    def test_tool_command_selects_tool(self):
        ov = _make_overlay()
        ov._execute_command("arrow")
        self.assertEqual(ov.active_tool, "arrow")

    def test_copy_command(self):
        ov = _make_overlay()
        ov._execute_command("copy")
        self.assertIn("已复制", ov.message)

    def test_undo_command(self):
        ov = _make_overlay()
        ov.push_history()
        ov._execute_command("undo")
        self.assertEqual(len(ov.history), 0)

    def test_grid_command(self):
        ov = _make_overlay()
        self.assertFalse(ov.grid_visible)
        ov._execute_command("grid")
        self.assertTrue(ov.grid_visible)

    def test_color_command_calls_toggle_style_panel(self):
        ov = _make_overlay()
        ov._execute_command("color")
        self.assertEqual(ov.style_panel_kind, "style")

    def test_width_command_calls_toggle_style_panel(self):
        ov = _make_overlay()
        ov._execute_command("width")
        self.assertEqual(ov.style_panel_kind, "style")

    def test_unknown_command_noop(self):
        ov = _make_overlay()
        msg_before = ov.message
        ov._execute_command("nonexistent")
        self.assertEqual(ov.message, msg_before)


# ── 填充模式 ──

class FillModeTest(unittest.TestCase):

    def test_cycle_fill_mode_from_none(self):
        ov = _make_overlay()
        ov.fill_mode = "none"
        ov.cycle_fill_mode()
        self.assertEqual(ov.fill_mode, "half")

    def test_cycle_fill_mode_wraps(self):
        ov = _make_overlay()
        ov.fill_mode = "full"
        ov.cycle_fill_mode()
        self.assertEqual(ov.fill_mode, "none")

    def test_cycle_fill_mode_sets_message(self):
        ov = _make_overlay()
        ov.fill_mode = "none"
        ov.cycle_fill_mode()
        self.assertIn("半透明", ov.message)


# ── 网格切换 ──

class GridToggleInEventsTest(unittest.TestCase):

    def test_toggle_grid_on(self):
        ov = _make_overlay()
        ov.grid_visible = False
        ov.toggle_grid()
        self.assertTrue(ov.grid_visible)
        self.assertIn("开", ov.message)

    def test_toggle_grid_off(self):
        ov = _make_overlay()
        ov.grid_visible = True
        ov.toggle_grid()
        self.assertFalse(ov.grid_visible)
        self.assertIn("关", ov.message)


# ── 尺寸锁定 ──

class SizeLockTest(unittest.TestCase):

    def test_toggle_size_lock_on(self):
        ov = _make_overlay()
        ov.size_locked = False
        ov.toggle_size_lock()
        self.assertTrue(ov.size_locked)
        self.assertIn("尺寸锁定", ov.message)

    def test_toggle_size_lock_off(self):
        ov = _make_overlay()
        ov.size_locked = True
        ov.toggle_size_lock()
        self.assertFalse(ov.size_locked)
        self.assertIn("关", ov.message)

    def test_toggle_size_lock_no_selection(self):
        ov = _make_overlay()
        ov.selection_rect = QRect()
        ov.size_locked = False
        ov.toggle_size_lock()
        self.assertFalse(ov.size_locked)
        self.assertIn("请先选择", ov.message)


# ── 键盘事件 ──

class KeyPressEventTest(unittest.TestCase):

    def _make_key_event(self, key, modifiers=Qt.KeyboardModifier.NoModifier):
        evt = MagicMock()
        evt.key.return_value = key
        evt.modifiers.return_value = modifiers
        return evt

    def test_escape_closes_overlay(self):
        ov = _make_overlay()
        closed = []
        ov.close = lambda: closed.append(True)
        ov._handle_key_press(self._make_key_event(Qt.Key.Key_Escape))
        self.assertEqual(closed, [True])

    def test_ctrl_z_undo(self):
        ov = _make_overlay()
        ov.push_history()
        ov._handle_key_press(self._make_key_event(
            Qt.Key.Key_Z, Qt.KeyboardModifier.ControlModifier
        ))
        self.assertEqual(len(ov.history), 0)

    def test_ctrl_c_copy(self):
        ov = _make_overlay()
        ov._handle_key_press(self._make_key_event(
            Qt.Key.Key_C, Qt.KeyboardModifier.ControlModifier
        ))
        self.assertIn("已复制", ov.message)

    def test_tool_key_a_selects_arrow(self):
        ov = _make_overlay()
        ov._handle_key_press(self._make_key_event(Qt.Key.Key_A))
        self.assertEqual(ov.active_tool, "arrow")

    def test_tool_key_r_selects_rect(self):
        ov = _make_overlay()
        ov._handle_key_press(self._make_key_event(Qt.Key.Key_R))
        self.assertEqual(ov.active_tool, "rect")

    def test_tool_key_t_selects_text(self):
        ov = _make_overlay()
        ov._handle_key_press(self._make_key_event(Qt.Key.Key_T))
        self.assertEqual(ov.active_tool, "text")

    def test_g_key_toggles_grid(self):
        ov = _make_overlay()
        ov.grid_visible = False
        ov._handle_key_press(self._make_key_event(Qt.Key.Key_G))
        self.assertTrue(ov.grid_visible)

    def test_tab_switches_to_last_tool(self):
        ov = _make_overlay()
        ov.select_tool("arrow")
        ov.select_tool("rect")
        ov._handle_key_press(self._make_key_event(Qt.Key.Key_Tab))
        self.assertEqual(ov.active_tool, "arrow")

    def test_delete_clears_selected_text(self):
        ov = _make_overlay()
        ov.annotations.append({"type": "text", "x": 10, "y": 10, "text": "hi", "size": 28, "color": "#fff"})
        ov.selected_text_index = 0
        ov._handle_key_press(self._make_key_event(Qt.Key.Key_Delete))
        self.assertEqual(len(ov.annotations), 0)

    def test_delete_clears_annotations_when_no_text_selected(self):
        ov = _make_overlay()
        ov.push_history()
        ov.annotations.append({"type": "arrow", "x1": 0, "y1": 0, "x2": 10, "y2": 10, "color": "#fff", "width": 2})
        ov.selected_text_index = -1
        ov._handle_key_press(self._make_key_event(Qt.Key.Key_Delete))
        self.assertEqual(len(ov.annotations), 0)

    def test_enter_finishes(self):
        ov = _make_overlay()
        finished = []
        ov.finish = lambda: finished.append(True)
        ov._handle_key_press(self._make_key_event(Qt.Key.Key_Return))
        self.assertEqual(finished, [True])

    def test_o_key_toggles_ocr_region(self):
        ov = _make_overlay()
        ov.ocr_region_mode = False
        ov._handle_key_press(self._make_key_event(Qt.Key.Key_O))
        self.assertTrue(ov.ocr_region_mode)
        self.assertIn("OCR", ov.message)

    def test_o_key_exits_ocr_region(self):
        ov = _make_overlay()
        ov.ocr_region_mode = True
        # recognize_current_text will be called, mock it
        ov.recognize_current_text = MagicMock()
        ov._handle_key_press(self._make_key_event(Qt.Key.Key_O))
        self.assertFalse(ov.ocr_region_mode)


class BuildToolKeyMapTest(unittest.TestCase):

    def test_conflicting_custom_key_preserves_default_owner(self):
        cfg = type("Cfg", (), {"edit_tool_hotkeys": {"arrow": "R"}})()
        mapping = build_tool_key_map(cfg)
        self.assertEqual(mapping.get(Qt.Key.Key_A), "arrow")
        self.assertEqual(mapping.get(Qt.Key.Key_R), "rect")

    def test_non_conflicting_custom_key_moves_tool(self):
        cfg = type("Cfg", (), {"edit_tool_hotkeys": {"arrow": "C"}})()
        mapping = build_tool_key_map(cfg)
        self.assertNotIn(Qt.Key.Key_A, mapping)
        self.assertEqual(mapping.get(Qt.Key.Key_C), "arrow")


# ── 工具栏动作 ──

class ToolbarActionTest(unittest.TestCase):

    def test_handle_toolbar_action_selects_tool(self):
        ov = _make_overlay()
        ov.handle_toolbar_action("arrow")
        self.assertEqual(ov.active_tool, "arrow")

    def test_handle_toolbar_action_copy(self):
        ov = _make_overlay()
        ov.handle_toolbar_action("copy")
        self.assertIn("已复制", ov.message)

    def test_handle_toolbar_action_blocked_during_ocr(self):
        ov = _make_overlay()
        ov._ocr_running = True
        ov.ocr_running = lambda: True
        ov.handle_toolbar_action("copy")
        self.assertIn("请稍候", ov.message)


class FailureFeedbackTest(unittest.TestCase):

    def test_ocr_failure_message_points_to_diagnostics(self):
        ov = _make_overlay()
        ov.on_ocr_job_failed(r"PowerShell failed at D:\private\ocr.png")
        self.assertIn("文字识别失败", ov.message)
        self.assertIn("可复制诊断信息后反馈", ov.message)
        self.assertNotIn(r"D:\private", ov.message)

    def test_privacy_blur_failure_message_points_to_diagnostics(self):
        ov = _make_overlay()
        ov._on_privacy_blur_failed("RapidOCR down")
        self.assertIn("智能隐私打码失败", ov.message)
        self.assertIn("可复制诊断信息后反馈", ov.message)


# ── 选区微调 ──

class NudgeSelectionTest(unittest.TestCase):

    def _make_arrow_event(self, key, modifiers=Qt.KeyboardModifier.NoModifier):
        evt = MagicMock()
        evt.key.return_value = key
        evt.modifiers.return_value = modifiers
        return evt

    def test_nudge_up(self):
        ov = _make_overlay()
        old_top = ov.selection_rect.top()
        ov.nudge_selection(self._make_arrow_event(Qt.Key.Key_Up))
        self.assertEqual(ov.selection_rect.top(), old_top - 1)

    def test_nudge_down(self):
        ov = _make_overlay()
        old_top = ov.selection_rect.top()
        ov.nudge_selection(self._make_arrow_event(Qt.Key.Key_Down))
        self.assertEqual(ov.selection_rect.top(), old_top + 1)

    def test_nudge_with_shift_10px(self):
        ov = _make_overlay()
        old_left = ov.selection_rect.left()
        ov.nudge_selection(self._make_arrow_event(
            Qt.Key.Key_Left, Qt.KeyboardModifier.ShiftModifier
        ))
        self.assertEqual(ov.selection_rect.left(), old_left - 10)

    def test_nudge_noop_when_no_selection(self):
        ov = _make_overlay()
        ov.selection_rect = QRect()
        ov.nudge_selection(self._make_arrow_event(Qt.Key.Key_Up))
        # 不崩溃

    def test_nudge_noop_when_tool_active(self):
        ov = _make_overlay()
        ov.select_tool("arrow")
        old_rect = QRect(ov.selection_rect)
        ov.nudge_selection(self._make_arrow_event(Qt.Key.Key_Up))
        self.assertEqual(ov.selection_rect, old_rect)


if __name__ == "__main__":
    unittest.main()
