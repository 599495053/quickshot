"""SnapMixin — 选区吸附窗口边缘。

在 select 模式拖拽时，自动吸附到可见窗口边界，
并在 overlay 上绘制吸附参考线。
"""

from __future__ import annotations

from typing import Optional

from PyQt6.QtCore import QPoint, QRect, QTimer

from ._window_candidates import WindowCandidate, build_window_candidates, candidate_at, legacy_logical_rects


class SnapMixin:
    """选区吸附窗口边缘。"""

    def _init_snap_state(self) -> None:
        """初始化吸附状态（在 __init__ 中调用）。"""
        self._snap_window_logical_rects: list[tuple[int, QRect, str]] = []
        self._window_candidates: list[WindowCandidate] = []
        self._snap_edges: list[tuple[str, QRect]] = []
        self._snap_windows_loaded = False
        self._snap_refresh_pending = False
        self._hover_window_candidate: Optional[WindowCandidate] = None
        self._hover_window_logical_rect = QRect()
        self._hover_window_title = ""
        self._press_hover_window_candidate: Optional[WindowCandidate] = None
        self._press_hover_window_logical_rect = QRect()
        self._press_hover_window_physical_rect = QRect()

    def _schedule_snap_prewarm(self, delay_ms: int = 120) -> None:
        """在覆盖层空闲时预热窗口吸附数据，避免首次按下鼠标时卡顿。"""
        if not getattr(self.config, 'snap_to_windows', True):
            return
        if getattr(self, "mode", "select") != "select":
            return
        if self._snap_windows_loaded or self._snap_refresh_pending:
            return
        self._snap_refresh_pending = True
        QTimer.singleShot(max(0, int(delay_ms)), self._run_snap_prewarm)

    def _run_snap_prewarm(self) -> None:
        """执行吸附预热；用户正在拖拽时后延，保证拖动跟手。"""
        self._snap_refresh_pending = False
        if not getattr(self.config, 'snap_to_windows', True):
            return
        if self._snap_windows_loaded or getattr(self, "mode", "select") != "select":
            return
        if getattr(self, "selecting", False):
            self._schedule_snap_prewarm(80)
            return
        self._refresh_snap_windows()

    def _refresh_snap_windows(self) -> None:
        """刷新可吸附窗口列表（仅在 select 模式首次拖拽时调用，结果缓存）。"""
        from ..utils import debug_log
        from ..window_enum import enumerate_visible_windows

        try:
            raw_windows = enumerate_visible_windows()
        except Exception as exc:
            debug_log(f"snap window enumeration failed: {exc}")
            raw_windows = []
        try:
            self._window_candidates = build_window_candidates(
                raw_windows,
                self.physical_abs_to_logical_rect,
                self.rect(),
            )
            self._snap_window_logical_rects = legacy_logical_rects(self._window_candidates)
        except Exception as exc:
            debug_log(f"snap window candidates failed: {exc}")
            self._window_candidates = []
            self._snap_window_logical_rects = []
        self._snap_windows_loaded = True

    def _window_logical_rects_for_snap(self) -> list[tuple[int, QRect, str]]:
        if self._window_candidates:
            return legacy_logical_rects(self._window_candidates)
        return self._snap_window_logical_rects

    def _apply_snap(self, raw_rect: QRect) -> tuple[QRect, list[tuple[str, QRect]]]:
        """对原始选区矩形应用吸附。

        返回 (吸附后矩形, [(吸附边描述, 被吸附窗口rect), ...])。
        """
        window_rects = self._window_logical_rects_for_snap()
        if not window_rects:
            return raw_rect, []

        threshold = getattr(self.config, 'snap_threshold_px', 10)

        left = raw_rect.left()
        top = raw_rect.top()
        right = raw_rect.right()
        bottom = raw_rect.bottom()

        # 每条边独立寻找最近的吸附候选
        best_left = (left, None)
        best_top = (top, None)
        best_right = (right, None)
        best_bottom = (bottom, None)

        for _hwnd, wrect, _title in window_rects:
            wl, wt, wr, wb = wrect.left(), wrect.top(), wrect.right(), wrect.bottom()

            # 水平方向：选区左边/右边 吸附到 窗口左边/右边
            for win_val in (wl, wr):
                d = abs(left - win_val)
                if d < threshold and (best_left[1] is None or d < abs(best_left[0] - win_val)):
                    best_left = (win_val, wrect)
                d = abs(right - win_val)
                if d < threshold and (best_right[1] is None or d < abs(best_right[0] - win_val)):
                    best_right = (win_val, wrect)

            # 垂直方向：选区上边/下边 吸附到 窗口上边/下边
            for win_val in (wt, wb):
                d = abs(top - win_val)
                if d < threshold and (best_top[1] is None or d < abs(best_top[0] - win_val)):
                    best_top = (win_val, wrect)
                d = abs(bottom - win_val)
                if d < threshold and (best_bottom[1] is None or d < abs(best_bottom[0] - win_val)):
                    best_bottom = (win_val, wrect)

        new_left = best_left[0]
        new_top = best_top[0]
        new_right = best_right[0]
        new_bottom = best_bottom[0]

        snapped = QRect(new_left, new_top, new_right - new_left + 1, new_bottom - new_top + 1)

        snap_edges: list[tuple[str, QRect]] = []
        if best_left[1] is not None:
            snap_edges.append(("left", best_left[1]))
        if best_top[1] is not None:
            snap_edges.append(("top", best_top[1]))
        if best_right[1] is not None:
            snap_edges.append(("right", best_right[1]))
        if best_bottom[1] is not None:
            snap_edges.append(("bottom", best_bottom[1]))

        return snapped, snap_edges

    def _hover_window_candidate_at(self, pos: QPoint) -> Optional[WindowCandidate]:
        """Return the topmost cached candidate containing pos."""
        if self._window_candidates:
            return candidate_at(self._window_candidates, pos)
        for index, (hwnd, rect, title) in enumerate(self._snap_window_logical_rects):
            if rect.contains(pos):
                return WindowCandidate(hwnd, rect, self.logical_to_physical_rect(rect), title, index)
        return None

    def _hover_window_at(self, pos: QPoint) -> tuple[QRect, str]:
        """Return the topmost cached window containing pos."""
        candidate = self._hover_window_candidate_at(pos)
        if candidate is not None:
            return QRect(candidate.logical_rect), candidate.title
        return QRect(), ""

    def _hover_window_physical_rect(self, logical_rect: Optional[QRect] = None) -> QRect:
        if logical_rect is None and self._hover_window_candidate is not None:
            return QRect(self._hover_window_candidate.physical_rect)
        if logical_rect is not None and self._hover_window_candidate is not None:
            if QRect(logical_rect) == self._hover_window_candidate.logical_rect:
                return QRect(self._hover_window_candidate.physical_rect)
        rect = logical_rect if logical_rect is not None else self._hover_window_logical_rect
        if rect is None or rect.isNull() or rect.width() <= 0 or rect.height() <= 0:
            return QRect()
        return self.logical_to_physical_rect(rect)

    def _clear_hover_window(self) -> None:
        self._hover_window_candidate = None
        self._hover_window_logical_rect = QRect()
        self._hover_window_title = ""
        self._press_hover_window_candidate = None
        self._press_hover_window_logical_rect = QRect()
        self._press_hover_window_physical_rect = QRect()

    def _update_hover_window(self, pos: QPoint) -> bool:
        """Update select-mode hover window and return True if it changed."""
        if not getattr(self.config, 'snap_to_windows', True):
            if not self._hover_window_logical_rect.isNull() or self._hover_window_title:
                self._clear_hover_window()
                return True
            return False
        if not self._snap_windows_loaded:
            if not self._snap_refresh_pending:
                self._schedule_snap_prewarm(40)
            return False

        candidate = self._hover_window_candidate_at(pos)
        rect = QRect(candidate.logical_rect) if candidate is not None else QRect()
        title = candidate.title if candidate is not None else ""
        if rect == self._hover_window_logical_rect and title == self._hover_window_title:
            return False
        self._hover_window_candidate = candidate
        self._hover_window_logical_rect = rect
        self._hover_window_title = title
        return True
