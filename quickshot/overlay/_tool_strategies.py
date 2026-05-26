"""标注工具策略模式 — 消除 _commit_annotation 和 paint_edit_mode 的 7 路 if-elif。"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Callable, List, Optional

from PyQt6.QtCore import QPoint, QRect
from PyQt6.QtGui import QPainter


@dataclass
class ToolContext:
    """工具策略需要的上下文，避免直接依赖 widget。"""
    start: Optional[QPoint]
    end: Optional[QPoint]
    path: List[QPoint]
    active_tool: str
    # 方法引用
    push_history: Callable
    draw_arrow_on_pixmap: Callable
    draw_rect_on_pixmap: Callable
    draw_ellipse_on_pixmap: Callable
    draw_dashed_rect_on_pixmap: Callable
    draw_freehand_on_pixmap: Callable
    draw_highlight_on_pixmap: Callable
    apply_mosaic: Callable
    apply_blur: Callable
    draw_arrow_preview: Callable
    draw_rect_preview: Callable
    draw_ellipse_preview: Callable
    draw_dashed_rect_preview: Callable
    draw_freehand_preview: Callable
    draw_mosaic_preview: Callable
    draw_blur_preview: Callable


class ToolStrategy(ABC):
    """标注工具策略基类。"""

    tool_name: str = ""

    @abstractmethod
    def commit(self, ctx: ToolContext) -> None:
        """鼠标释放时提交标注。"""

    @abstractmethod
    def preview(self, ctx: ToolContext, painter: QPainter) -> None:
        """拖动过程中绘制预览。"""

    def min_drag_distance(self) -> int:
        """最小有效拖动距离（manhattanLength）。"""
        return 6

    def min_rect_size(self) -> int:
        """矩形类工具的最小宽高。"""
        return 6


class ArrowStrategy(ToolStrategy):
    tool_name = "arrow"

    def commit(self, ctx: ToolContext) -> None:
        if ctx.start and ctx.end and (ctx.start - ctx.end).manhattanLength() >= self.min_drag_distance():
            ctx.push_history()
            ctx.draw_arrow_on_pixmap(ctx.start, ctx.end)

    def preview(self, ctx: ToolContext, painter: QPainter) -> None:
        if ctx.start and ctx.end:
            ctx.draw_arrow_preview(painter, ctx.start, ctx.end)


class RectStrategy(ToolStrategy):
    tool_name = "rect"

    def commit(self, ctx: ToolContext) -> None:
        if ctx.start and ctx.end:
            rect = QRect(ctx.start, ctx.end).normalized()
            if rect.width() >= self.min_rect_size() and rect.height() >= self.min_rect_size():
                ctx.push_history()
                ctx.draw_rect_on_pixmap(rect)

    def preview(self, ctx: ToolContext, painter: QPainter) -> None:
        if ctx.start and ctx.end:
            ctx.draw_rect_preview(painter, ctx.start, ctx.end)


class EllipseStrategy(ToolStrategy):
    tool_name = "ellipse"

    def commit(self, ctx: ToolContext) -> None:
        if ctx.start and ctx.end:
            rect = QRect(ctx.start, ctx.end).normalized()
            if rect.width() >= self.min_rect_size() and rect.height() >= self.min_rect_size():
                ctx.push_history()
                ctx.draw_ellipse_on_pixmap(rect)

    def preview(self, ctx: ToolContext, painter: QPainter) -> None:
        if ctx.start and ctx.end:
            ctx.draw_ellipse_preview(painter, ctx.start, ctx.end)


class DashedRectStrategy(ToolStrategy):
    tool_name = "dashed_rect"

    def commit(self, ctx: ToolContext) -> None:
        if ctx.start and ctx.end:
            rect = QRect(ctx.start, ctx.end).normalized()
            if rect.width() >= self.min_rect_size() and rect.height() >= self.min_rect_size():
                ctx.push_history()
                ctx.draw_dashed_rect_on_pixmap(rect)

    def preview(self, ctx: ToolContext, painter: QPainter) -> None:
        if ctx.start and ctx.end:
            ctx.draw_dashed_rect_preview(painter, ctx.start, ctx.end)


class PenStrategy(ToolStrategy):
    tool_name = "pen"

    def commit(self, ctx: ToolContext) -> None:
        if len(ctx.path) >= 2:
            ctx.push_history()
            ctx.draw_freehand_on_pixmap(ctx.path)

    def preview(self, ctx: ToolContext, painter: QPainter) -> None:
        ctx.draw_freehand_preview(painter)


class HighlightStrategy(ToolStrategy):
    tool_name = "highlight"

    def commit(self, ctx: ToolContext) -> None:
        if len(ctx.path) >= 2:
            ctx.push_history()
            ctx.draw_highlight_on_pixmap(ctx.path)

    def preview(self, ctx: ToolContext, painter: QPainter) -> None:
        ctx.draw_freehand_preview(painter)


class MosaicStrategy(ToolStrategy):
    tool_name = "mosaic"

    def commit(self, ctx: ToolContext) -> None:
        if ctx.start and ctx.end:
            rect = QRect(ctx.start, ctx.end).normalized()
            if rect.width() >= 8 and rect.height() >= 8:
                ctx.push_history()
                ctx.apply_mosaic(rect)

    def preview(self, ctx: ToolContext, painter: QPainter) -> None:
        if ctx.start and ctx.end:
            ctx.draw_mosaic_preview(painter, ctx.start, ctx.end)


class BlurStrategy(ToolStrategy):
    tool_name = "blur"

    def commit(self, ctx: ToolContext) -> None:
        if ctx.start and ctx.end:
            rect = QRect(ctx.start, ctx.end).normalized()
            if rect.width() >= 8 and rect.height() >= 8:
                ctx.push_history()
                ctx.apply_blur(rect)

    def preview(self, ctx: ToolContext, painter: QPainter) -> None:
        if ctx.start and ctx.end:
            ctx.draw_blur_preview(painter, ctx.start, ctx.end)


# ── 策略注册表 ──

TOOL_STRATEGIES = {
    "arrow": ArrowStrategy(),
    "rect": RectStrategy(),
    "ellipse": EllipseStrategy(),
    "dashed_rect": DashedRectStrategy(),
    "pen": PenStrategy(),
    "highlight": HighlightStrategy(),
    "mosaic": MosaicStrategy(),
    "blur": BlurStrategy(),
}
