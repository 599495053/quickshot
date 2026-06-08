"""选区吸附窗口功能测试。

覆盖：
- _apply_snap 吸附算法
- _refresh_snap_windows 缓存机制
- 吸附阈值和边界条件
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from PyQt6.QtCore import QPoint, QRect  # noqa: E402


class MockOverlay:
    """模拟 overlay 对象，仅实现吸附所需的方法。"""

    def __init__(self, threshold=10):
        self._snap_window_logical_rects = []
        self._window_candidates = []
        self._snap_edges = []
        self._snap_windows_loaded = False
        self._snap_refresh_pending = False
        self._hover_window_candidate = None
        self._press_hover_window_candidate = None
        self.mode = "select"
        self.selecting = False

        class Config:
            snap_to_windows = True
            snap_threshold_px = threshold

        self.config = Config()

    def physical_abs_to_logical_rect(self, abs_rect):
        # 简化：直接返回相同的矩形
        left, top, width, height = abs_rect
        return QRect(left, top, width, height), QRect(left, top, width, height)

    def logical_to_physical_rect(self, rect):
        return QRect(rect)

    def rect(self):
        return QRect(0, 0, 800, 600)

    def _init_snap_state(self):
        self._snap_window_logical_rects = []
        self._window_candidates = []
        self._snap_edges = []
        self._snap_windows_loaded = False
        self._snap_refresh_pending = False
        self._hover_window_candidate = None
        self._press_hover_window_candidate = None


# 导入 mixin 方法
from quickshot.overlay._snap import SnapMixin  # noqa: E402
from quickshot.overlay._window_candidates import (  # noqa: E402
    build_window_candidates,
    candidate_at,
    legacy_logical_rects,
)


class ApplySnapTest(unittest.TestCase):
    def setUp(self):
        self.overlay = MockOverlay(threshold=10)
        # 手动绑定 mixin 方法
        self.overlay._apply_snap = SnapMixin._apply_snap.__get__(self.overlay)
        self.overlay._window_logical_rects_for_snap = SnapMixin._window_logical_rects_for_snap.__get__(self.overlay)
        self.overlay._refresh_snap_windows = SnapMixin._refresh_snap_windows.__get__(self.overlay)
        self.overlay._init_snap_state = SnapMixin._init_snap_state.__get__(self.overlay)
        self.overlay._schedule_snap_prewarm = SnapMixin._schedule_snap_prewarm.__get__(self.overlay)
        self.overlay._run_snap_prewarm = SnapMixin._run_snap_prewarm.__get__(self.overlay)
        self.overlay._hover_window_candidate_at = SnapMixin._hover_window_candidate_at.__get__(self.overlay)
        self.overlay._hover_window_at = SnapMixin._hover_window_at.__get__(self.overlay)
        self.overlay._hover_window_physical_rect = SnapMixin._hover_window_physical_rect.__get__(self.overlay)
        self.overlay._clear_hover_window = SnapMixin._clear_hover_window.__get__(self.overlay)
        self.overlay._update_hover_window = SnapMixin._update_hover_window.__get__(self.overlay)
        self.overlay._init_snap_state()

    def test_no_windows_returns_original(self):
        """无窗口时返回原始矩形。"""
        raw = QRect(100, 100, 200, 200)
        result, edges = self.overlay._apply_snap(raw)
        self.assertEqual(result, raw)
        self.assertEqual(edges, [])

    def test_snap_left_edge(self):
        """选区左边靠近窗口左边时吸附。"""
        # 窗口在 (200, 200, 300, 300)
        self.overlay._snap_window_logical_rects = [
            (1, QRect(200, 200, 300, 300), "TestWindow")
        ]
        # 选区左边在 195（距离窗口左边 200 差 5px < threshold 10）
        raw = QRect(195, 100, 100, 100)
        result, edges = self.overlay._apply_snap(raw)
        self.assertEqual(result.left(), 200)  # 吸附到 200
        self.assertTrue(any(e[0] == "left" for e in edges))

    def test_snap_right_edge(self):
        """选区右边靠近窗口右边时吸附。"""
        self.overlay._snap_window_logical_rects = [
            (1, QRect(200, 200, 300, 300), "TestWindow")  # right=499
        ]
        # 选区右边在 502（距离窗口右边 499 差 3px）
        raw = QRect(400, 100, 103, 100)  # right=502
        result, edges = self.overlay._apply_snap(raw)
        self.assertEqual(result.right(), 499)  # 吸附到 499

    def test_no_snap_when_far(self):
        """距离超过阈值时不吸附。"""
        self.overlay._snap_window_logical_rects = [
            (1, QRect(200, 200, 300, 300), "TestWindow")
        ]
        raw = QRect(100, 100, 50, 50)  # 距离窗口边 > 10px
        result, edges = self.overlay._apply_snap(raw)
        self.assertEqual(result, raw)
        self.assertEqual(edges, [])

    def test_snap_top_and_bottom(self):
        """上边和下边独立吸附。"""
        self.overlay._snap_window_logical_rects = [
            (1, QRect(100, 200, 300, 300), "TestWindow")  # top=200, bottom=499
        ]
        # 选区上边在 198（差 2px），下边在 501（差 2px）
        raw = QRect(50, 198, 200, 304)  # bottom=501
        result, edges = self.overlay._apply_snap(raw)
        self.assertEqual(result.top(), 200)
        self.assertEqual(result.bottom(), 499)

    def test_snap_selects_nearest_window(self):
        """多个窗口时选择最近的。"""
        self.overlay._snap_window_logical_rects = [
            (1, QRect(200, 200, 100, 100), "Window1"),  # left=200
            (2, QRect(205, 200, 100, 100), "Window2"),  # left=205
        ]
        # 选区左边在 203，距离 Window1(200) 差 3px，距离 Window2(205) 差 2px
        raw = QRect(203, 100, 100, 100)
        result, edges = self.overlay._apply_snap(raw)
        self.assertEqual(result.left(), 205)  # 吸附到更近的 Window2

    def test_independent_edge_snapping(self):
        """四边独立吸附到不同窗口。"""
        self.overlay._snap_window_logical_rects = [
            (1, QRect(100, 100, 200, 200), "Win1"),  # left=100, top=100
            (2, QRect(400, 400, 200, 200), "Win2"),  # right=599, bottom=599
        ]
        raw = QRect(98, 98, 503, 503)  # left=98, top=98, right=600, bottom=600
        result, edges = self.overlay._apply_snap(raw)
        self.assertEqual(result.left(), 100)   # 吸附到 Win1
        self.assertEqual(result.top(), 100)    # 吸附到 Win1
        self.assertEqual(result.bottom(), 599)  # 吸附到 Win2

    def test_schedule_snap_prewarm_uses_timer_once(self):
        """预热应只排队一次，避免重复枚举窗口。"""
        with patch("quickshot.overlay._snap.QTimer.singleShot") as single_shot:
            self.overlay._schedule_snap_prewarm(40)
            self.overlay._schedule_snap_prewarm(40)

        self.assertTrue(self.overlay._snap_refresh_pending)
        single_shot.assert_called_once()

    def test_schedule_snap_prewarm_skips_edit_mode(self):
        """非选择模式不应排队吸附预热。"""
        self.overlay.mode = "edit"
        with patch("quickshot.overlay._snap.QTimer.singleShot") as single_shot:
            self.overlay._schedule_snap_prewarm(40)

        self.assertFalse(self.overlay._snap_refresh_pending)
        single_shot.assert_not_called()

    def test_prewarm_defers_while_selecting(self):
        """用户正在拖选时不枚举窗口，避免拖动中卡顿。"""
        self.overlay.selecting = True
        self.overlay._refresh_snap_windows = MagicMock()

        with patch("quickshot.overlay._snap.QTimer.singleShot") as single_shot:
            self.overlay._run_snap_prewarm()

        self.overlay._refresh_snap_windows.assert_not_called()
        self.assertTrue(self.overlay._snap_refresh_pending)
        single_shot.assert_called_once()

    def test_prewarm_refreshes_when_idle(self):
        """覆盖层空闲时才真正刷新吸附窗口缓存。"""
        calls = []

        def refresh():
            calls.append(True)
            self.overlay._snap_windows_loaded = True

        self.overlay.selecting = False
        self.overlay._refresh_snap_windows = refresh

        self.overlay._run_snap_prewarm()

        self.assertEqual(calls, [True])
        self.assertTrue(self.overlay._snap_windows_loaded)

    def test_hover_window_at_returns_first_containing_window(self):
        """窗口悬停命中时返回最靠前的缓存窗口。"""
        self.overlay._snap_window_logical_rects = [
            (1, QRect(100, 100, 300, 200), "Front"),
            (2, QRect(120, 120, 100, 80), "Behind"),
        ]

        rect, title = self.overlay._hover_window_at(QPoint(130, 130))

        self.assertEqual(rect, QRect(100, 100, 300, 200))
        self.assertEqual(title, "Front")

    def test_refresh_snap_windows_builds_candidates(self):
        """刷新窗口缓存时应保留逻辑和物理候选，供悬停点击复用。"""
        self.overlay.physical_abs_to_logical_rect = MagicMock(
            return_value=(QRect(10, 20, 200, 120), QRect(20, 40, 400, 240))
        )
        with patch(
            "quickshot.window_enum.enumerate_visible_windows",
            return_value=[(7, QRect(20, 40, 400, 240), "  App  Window  ")],
        ):
            self.overlay._refresh_snap_windows()

        self.assertTrue(self.overlay._snap_windows_loaded)
        self.assertEqual(len(self.overlay._window_candidates), 1)
        self.assertEqual(self.overlay._snap_window_logical_rects, [(7, QRect(10, 20, 200, 120), "App Window")])

        changed = self.overlay._update_hover_window(QPoint(30, 40))
        self.assertTrue(changed)
        self.assertEqual(self.overlay._hover_window_physical_rect(), QRect(20, 40, 400, 240))

    def test_update_hover_window_clears_when_snap_disabled(self):
        """关闭窗口吸附时，悬停候选也应同步清空。"""
        self.overlay._hover_window_logical_rect = QRect(100, 100, 300, 200)
        self.overlay._hover_window_title = "Window"
        self.overlay.config.snap_to_windows = False

        changed = self.overlay._update_hover_window(QPoint(150, 150))

        self.assertTrue(changed)
        self.assertTrue(self.overlay._hover_window_logical_rect.isNull())
        self.assertEqual(self.overlay._hover_window_title, "")

    def test_refresh_snap_windows_handles_enumeration_failure(self):
        """窗口枚举失败时应降级为空缓存，不影响截图。"""
        with patch("quickshot.window_enum.enumerate_visible_windows", side_effect=RuntimeError("boom")):
            self.overlay._refresh_snap_windows()

        self.assertTrue(self.overlay._snap_windows_loaded)
        self.assertEqual(self.overlay._snap_window_logical_rects, [])
        self.assertEqual(self.overlay._window_candidates, [])


class WindowCandidateTest(unittest.TestCase):

    def test_build_window_candidates_preserves_z_order_for_hit_testing(self):
        raw_windows = [
            (1, QRect(0, 0, 300, 200), " Front "),
            (2, QRect(40, 40, 80, 80), "Behind"),
        ]

        candidates = build_window_candidates(
            raw_windows,
            lambda rect: (QRect(*rect), QRect(*rect)),
            QRect(0, 0, 400, 300),
        )

        self.assertEqual([candidate.hwnd for candidate in candidates], [1, 2])
        self.assertEqual(candidates[0].title, "Front")
        self.assertEqual(candidate_at(candidates, QPoint(50, 50)).hwnd, 1)

    def test_build_window_candidates_clips_logical_bounds_and_filters_invalid(self):
        raw_windows = [
            (1, QRect(-20, 10, 60, 50), "Partial"),
            (2, QRect(500, 500, 100, 100), "Offscreen"),
            (3, QRect(20, 20, 4, 80), "Tiny"),
            (4, QRect(30, 30, 80, 80), "   "),
        ]

        candidates = build_window_candidates(
            raw_windows,
            lambda rect: (QRect(*rect), QRect(*rect)),
            QRect(0, 0, 200, 120),
        )

        self.assertEqual(len(candidates), 1)
        self.assertEqual(candidates[0].logical_rect, QRect(0, 10, 40, 50))
        self.assertEqual(legacy_logical_rects(candidates), [(1, QRect(0, 10, 40, 50), "Partial")])

    def test_build_window_candidates_skips_failed_conversions(self):
        raw_windows = [
            (1, QRect(0, 0, 100, 80), "Bad"),
            (2, QRect(20, 20, 120, 90), "Good"),
        ]

        def convert(rect):
            if rect[0] == 0:
                raise RuntimeError("bad geometry")
            return QRect(*rect), QRect(*rect)

        candidates = build_window_candidates(raw_windows, convert, QRect(0, 0, 200, 160))

        self.assertEqual([candidate.hwnd for candidate in candidates], [2])


if __name__ == "__main__":
    unittest.main()
