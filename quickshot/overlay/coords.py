"""坐标系统：处理物理屏幕 <-> 逻辑窗口 <-> 图像三层坐标转换。

CoordinateSystem 只负责按 (scale_x, scale_y, physical_left, physical_top)
做转换；其它依赖（widget 几何、image 尺寸、原始 pixmap 尺寸）由调用方
显式传入，类自身不持有 widget/pixmap 引用。
"""

from __future__ import annotations

from typing import Dict, List, Optional, Tuple

from PyQt6.QtCore import QPoint, QPointF, QRect, QSize


class CoordinateSystem:
    def __init__(self, scale_x: float, scale_y: float, physical_left: int, physical_top: int):
        self.scale_x = float(scale_x)
        self.scale_y = float(scale_y)
        self.physical_left = int(physical_left)
        self.physical_top = int(physical_top)

    @staticmethod
    def clamp_point(point: QPoint, widget_rect: QRect) -> QPoint:
        return QPoint(
            max(widget_rect.left(), min(widget_rect.right(), point.x())),
            max(widget_rect.top(), min(widget_rect.bottom(), point.y())),
        )

    def logical_to_physical_rect(self, rect: QRect, raw_size: QSize) -> QRect:
        if rect.isNull() or rect.width() <= 0 or rect.height() <= 0:
            return QRect()

        left = int(round(rect.left() * self.scale_x))
        top = int(round(rect.top() * self.scale_y))
        right = int(round((rect.left() + rect.width()) * self.scale_x))
        bottom = int(round((rect.top() + rect.height()) * self.scale_y))

        left = max(0, min(raw_size.width(), left))
        top = max(0, min(raw_size.height(), top))
        right = max(left + 1, min(raw_size.width(), right))
        bottom = max(top + 1, min(raw_size.height(), bottom))
        return QRect(left, top, right - left, bottom - top)

    def physical_abs_to_logical_rect(
        self,
        abs_rect: Tuple[int, int, int, int],
        raw_size: QSize,
        widget_rect: QRect,
    ) -> Tuple[QRect, QRect]:
        left, top, width, height = abs_rect
        relative_physical = QRect(
            int(left - self.physical_left),
            int(top - self.physical_top),
            int(width),
            int(height),
        ).intersected(QRect(0, 0, raw_size.width(), raw_size.height()))

        if relative_physical.width() <= 0 or relative_physical.height() <= 0:
            return QRect(), QRect()

        logical = QRect(
            int(round(relative_physical.left() / self.scale_x)),
            int(round(relative_physical.top() / self.scale_y)),
            int(round(relative_physical.width() / self.scale_x)),
            int(round(relative_physical.height() / self.scale_y)),
        ).intersected(widget_rect)
        return logical, relative_physical

    @staticmethod
    def widget_to_image(pos: QPoint, selection_rect: QRect, image_size: QSize, clamped: bool = False) -> Optional[QPoint]:
        if image_size.isEmpty() or selection_rect.isNull():
            return None
        if not selection_rect.contains(pos):
            if not clamped:
                return None
            # 钳位到选区边界，允许拖拽标注时鼠标超出选区
            pos = QPoint(
                max(selection_rect.left(), min(pos.x(), selection_rect.right())),
                max(selection_rect.top(), min(pos.y(), selection_rect.bottom())),
            )
        x = int((pos.x() - selection_rect.left()) * image_size.width() / max(1, selection_rect.width()))
        y = int((pos.y() - selection_rect.top()) * image_size.height() / max(1, selection_rect.height()))
        x = max(0, min(image_size.width() - 1, x))
        y = max(0, min(image_size.height() - 1, y))
        return QPoint(x, y)

    @staticmethod
    def image_to_widget(point: QPoint, selection_rect: QRect, image_size: QSize) -> QPointF:
        if image_size.isEmpty() or selection_rect.isNull():
            return QPointF(0, 0)
        x = selection_rect.left() + point.x() * selection_rect.width() / max(1, image_size.width())
        y = selection_rect.top() + point.y() * selection_rect.height() / max(1, image_size.height())
        return QPointF(x, y)

    @staticmethod
    def scaled_stroke_width(width: float, selection_rect: QRect, image_size: QSize) -> float:
        if image_size.isEmpty() or selection_rect.isNull():
            return max(1.0, width)
        scale = min(
            selection_rect.width() / max(1, image_size.width()),
            selection_rect.height() / max(1, image_size.height()),
        )
        return max(1.4, width * scale)

    @classmethod
    def annotation_points_to_widget(
        cls,
        item: Dict[str, object],
        selection_rect: QRect,
        image_size: QSize,
    ) -> List[QPointF]:
        points: List[QPointF] = []
        raw_points = item.get("points", [])
        if not isinstance(raw_points, list):
            return points
        for raw in raw_points:
            if not isinstance(raw, (tuple, list)) or len(raw) != 2:
                continue
            try:
                points.append(
                    cls.image_to_widget(
                        QPoint(int(raw[0]), int(raw[1])),
                        selection_rect,
                        image_size,
                    )
                )
            except (TypeError, ValueError):
                # raw 元素非数值时跳过单个点，整体路径还能继续
                continue
        return points
