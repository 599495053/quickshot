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

from PyQt6.QtCore import QPoint, QRect, Qt  # noqa: E402
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


def _make_mouse_event(pos: QPoint, button=Qt.MouseButton.LeftButton):
    evt = MagicMock()
    evt.button.return_value = button
    evt.position.return_value.toPoint.return_value = pos
    return evt


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


class SelectModeResponsivenessTest(unittest.TestCase):
    """选择模式交互应保持轻量，避免首帧拖动卡顿。"""

    def _make_move_event(self, pos: QPoint):
        evt = MagicMock()
        evt.position.return_value.toPoint.return_value = pos
        return evt

    def test_select_press_does_not_refresh_snap_windows_synchronously(self):
        ov = _make_overlay()
        ov.mode = "select"
        ov._snap_windows_loaded = False
        ov._refresh_snap_windows = MagicMock()
        ov._schedule_snap_prewarm = MagicMock()
        ov.request_frame_update = MagicMock()
        ov.update = MagicMock()

        ov._handle_mouse_press_select_mode(QPoint(120, 130))

        self.assertTrue(ov.selecting)
        self.assertEqual(ov.start, QPoint(120, 130))
        ov._refresh_snap_windows.assert_not_called()
        ov._schedule_snap_prewarm.assert_called_once()
        ov.request_frame_update.assert_called_once()
        ov.update.assert_not_called()

    def test_select_move_skips_repaint_when_selection_is_unchanged(self):
        ov = _make_overlay()
        ov.mode = "select"
        ov.selecting = True
        ov.start = QPoint(120, 130)
        ov.end = QPoint(120, 130)
        ov._snap_window_logical_rects = []
        ov._snap_windows_loaded = True
        ov.request_frame_update = MagicMock()

        ov._handle_mouse_move(self._make_move_event(QPoint(120, 130)))

        ov.request_frame_update.assert_not_called()


class SelectModeWindowHoverTest(unittest.TestCase):
    """选择模式窗口候选：单击截窗口，拖拽仍框选。"""

    def test_move_updates_hover_window(self):
        ov = _make_overlay()
        ov.mode = "select"
        ov.selecting = False
        ov._snap_windows_loaded = True
        ov._snap_window_logical_rects = [(1, QRect(100, 100, 300, 200), "App")]

        ov._handle_mouse_move(_make_mouse_event(QPoint(150, 150)))

        self.assertEqual(ov._hover_window_logical_rect, QRect(100, 100, 300, 200))
        self.assertEqual(ov._hover_window_title, "App")

    def test_click_hover_window_enters_edit_mode(self):
        ov = _make_overlay()
        ov.mode = "select"
        ov.selecting = False
        ov._snap_windows_loaded = True
        ov._snap_window_logical_rects = [(1, QRect(100, 100, 300, 200), "App")]

        event = _make_mouse_event(QPoint(150, 150))
        ov._handle_mouse_press(event)
        ov._handle_mouse_release(event)

        self.assertEqual(ov.mode, "edit")
        self.assertEqual(ov.selection_rect, QRect(100, 100, 300, 200))
        self.assertEqual(ov.selection_physical_rect, QRect(100, 100, 300, 200))

    def test_drag_from_hover_window_keeps_manual_selection(self):
        ov = _make_overlay()
        ov.mode = "select"
        ov.selecting = False
        ov._snap_windows_loaded = True
        ov._snap_window_logical_rects = [(1, QRect(100, 100, 300, 200), "App")]

        ov._handle_mouse_press(_make_mouse_event(QPoint(150, 150)))
        ov._handle_mouse_move(_make_mouse_event(QPoint(260, 240)))
        ov._handle_mouse_release(_make_mouse_event(QPoint(260, 240)))

        self.assertEqual(ov.mode, "edit")
        self.assertEqual(ov.selection_rect, QRect(150, 150, 111, 91))

    def test_select_mode_r_reuses_last_selection(self):
        ov = _make_overlay()
        ov.mode = "select"
        old_logical = FloatingSnipOverlay._last_selection_rect
        old_physical = FloatingSnipOverlay._last_selection_physical_rect
        try:
            FloatingSnipOverlay._last_selection_rect = QRect(220, 180, 120, 90)
            FloatingSnipOverlay._last_selection_physical_rect = QRect(220, 180, 120, 90)
            evt = MagicMock()
            evt.key.return_value = Qt.Key.Key_R
            evt.modifiers.return_value = Qt.KeyboardModifier.NoModifier

            ov._handle_key_press(evt)

            self.assertEqual(ov.mode, "edit")
            self.assertEqual(ov.selection_rect, QRect(220, 180, 120, 90))
        finally:
            FloatingSnipOverlay._last_selection_rect = old_logical
            FloatingSnipOverlay._last_selection_physical_rect = old_physical


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


# ── 智能隐私打码预览 ──

class PrivacyPreviewTest(unittest.TestCase):

    def test_privacy_blur_success_creates_preview_without_applying_mosaic(self):
        ov = _make_overlay()
        ov._on_privacy_blur_succeeded([(10, 20, 80, 24), (140, 70, 90, 28)])
        self.assertEqual(len(ov.privacy_preview_rects), 2)
        self.assertEqual(ov.privacy_preview_selected_index, 0)
        self.assertEqual(ov.annotations, [])
        self.assertIn("Enter 应用", ov.message)

    def test_apply_privacy_preview_commits_mosaic_once(self):
        ov = _make_overlay()
        ov._on_privacy_blur_succeeded([(10, 20, 80, 24), (140, 70, 90, 28)])
        ov.apply_privacy_preview()
        self.assertFalse(ov.privacy_preview_active())
        self.assertEqual([item["type"] for item in ov.annotations], ["mosaic", "mosaic"])
        self.assertEqual(len(ov.history), 1)
        self.assertIn("已对 2 处", ov.message)

    def test_delete_selected_privacy_preview_rect(self):
        ov = _make_overlay()
        ov._on_privacy_blur_succeeded([(10, 20, 80, 24), (140, 70, 90, 28)])
        ov.privacy_preview_selected_index = 0
        ov.delete_selected_privacy_preview_rect()
        self.assertEqual(len(ov.privacy_preview_rects), 1)
        self.assertIn("剩余 1 处", ov.message)

    def test_escape_cancels_privacy_preview(self):
        ov = _make_overlay()
        ov._on_privacy_blur_succeeded([(10, 20, 80, 24)])
        self.assertTrue(ov.privacy_preview_active())
        ov._handle_escape_key()
        self.assertFalse(ov.privacy_preview_active())
        self.assertIn("已取消", ov.message)

    def test_export_is_blocked_while_privacy_preview_is_active(self):
        ov = _make_overlay()
        ov._on_privacy_blur_succeeded([(10, 20, 80, 24)])
        ov.copy_current()
        self.assertTrue(ov.privacy_preview_active())
        self.assertIn("请先按 Enter", ov.message)

    def test_arrow_key_nudges_selected_privacy_preview_rect(self):
        ov = _make_overlay()
        ov._on_privacy_blur_succeeded([(10, 20, 80, 24)])
        ov.handle_privacy_preview_key(Qt.Key.Key_Right, Qt.KeyboardModifier.ShiftModifier)
        self.assertEqual(ov.privacy_preview_rects[0].x(), 20)
        self.assertIn("已微调", ov.message)

    def test_mouse_drag_moves_privacy_preview_rect(self):
        ov = _make_overlay()
        ov._on_privacy_blur_succeeded([(10, 20, 80, 24)])
        self.assertTrue(ov.begin_privacy_preview_drag(QPoint(120, 130)))
        self.assertTrue(ov.update_privacy_preview_drag(QPoint(140, 150)))
        self.assertTrue(ov.finish_privacy_preview_drag(QPoint(140, 150)))
        rect = ov.privacy_preview_rects[0]
        self.assertEqual((rect.x(), rect.y()), (30, 40))

    def test_mouse_drag_resizes_privacy_preview_rect(self):
        ov = _make_overlay()
        ov._on_privacy_blur_succeeded([(10, 20, 80, 24)])
        self.assertTrue(ov.begin_privacy_preview_drag(QPoint(190, 144)))
        self.assertTrue(ov.update_privacy_preview_drag(QPoint(200, 154)))
        self.assertTrue(ov.finish_privacy_preview_drag(QPoint(200, 154)))
        rect = ov.privacy_preview_rects[0]
        self.assertEqual((rect.width(), rect.height()), (90, 34))


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
