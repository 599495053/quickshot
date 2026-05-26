"""TextDragState — 文字标注拖拽交互的状态封装。"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from PyQt6.QtCore import QPoint


@dataclass
class TextDragState:
    """文字标注拖拽的完整状态。

    将原先散落在 widget.py 中的 6 个变量（dragging_text_index,
    dragging_text_origin, dragging_text_start, dragging_text_current,
    hover_text_index, selected_text_index）封装为一个对象，
    由 _reset_text_state() 统一重置。
    """

    dragging_index: int = -1
    origin: Optional[QPoint] = field(default=None, repr=False)
    start: Optional[QPoint] = field(default=None, repr=False)
    current: Optional[QPoint] = field(default=None, repr=False)
    hover_index: int = -1
    selected_index: int = -1
    editing_index: int = -1

    @property
    def is_dragging(self) -> bool:
        return self.dragging_index >= 0

    def begin_drag(self, index: int, origin: QPoint, start: QPoint) -> None:
        """开始拖拽。"""
        self.dragging_index = index
        self.origin = QPoint(origin)
        self.start = QPoint(start)
        self.current = QPoint(start)

    def update_drag(self, current: QPoint) -> None:
        """更新拖拽位置。"""
        self.current = QPoint(current)

    def end_drag(self) -> tuple[Optional[QPoint], Optional[QPoint], Optional[QPoint]]:
        """结束拖拽，返回 (origin, start, current) 并重置拖拽状态。"""
        result = (self.origin, self.start, self.current)
        self.dragging_index = -1
        self.origin = None
        self.start = None
        self.current = None
        return result

    def cancel_drag(self) -> None:
        """取消拖拽。"""
        self.dragging_index = -1
        self.origin = None
        self.start = None
        self.current = None

    def reset(self) -> None:
        """重置所有文字交互状态。"""
        self.hover_index = -1
        self.selected_index = -1
        self.editing_index = -1
        self.cancel_drag()
