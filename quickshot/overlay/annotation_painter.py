"""标注绘制原语：把单条 annotation 画到 QPainter / QPixmap 上。

纯函数模块，无内部状态、不依赖 widget。调用方需要把 painter 与
（必要时）选区/图像尺寸相关的几何信息显式传入。
"""

from __future__ import annotations

import math
from typing import Dict, List

from PyQt6.QtCore import QPoint, QPointF, QRect, QRectF, Qt
from PyQt6.QtGui import (
    QBrush,
    QColor,
    QFont,
    QFontMetrics,
    QPainter,
    QPainterPath,
    QPainterPathStroker,
    QPen,
    QPixmap,
    QPolygonF,
)


def _apply_fill(painter: QPainter, color: QColor, fill: str) -> None:
    """根据填充模式设置 brush。"""
    if fill == "half":
        c = QColor(color)
        c.setAlpha(70)
        painter.setBrush(QBrush(c))
    elif fill == "full":
        c = QColor(color)
        c.setAlpha(180)
        painter.setBrush(QBrush(c))
    else:
        painter.setBrush(Qt.BrushStyle.NoBrush)


def _calc_shape_inset(width: float, rect: QRectF) -> float:
    """计算形状绘制时的内缩量，防止线宽溢出矩形边界。"""
    return min(width / 2.0, max(0.0, rect.width() / 2.0 - 1.0), max(0.0, rect.height() / 2.0 - 1.0))


def draw_arrow(
    painter: QPainter,
    start: QPointF,
    end: QPointF,
    color: QColor,
    width: float,
    head_len: float,
) -> None:
    painter.save()
    pen = QPen(color, width)
    pen.setCapStyle(Qt.PenCapStyle.RoundCap)
    pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
    painter.setPen(pen)
    painter.setBrush(QBrush(color))
    painter.drawLine(start, end)
    angle = math.atan2(end.y() - start.y(), end.x() - start.x())
    left = QPointF(
        end.x() - head_len * math.cos(angle - math.pi / 6),
        end.y() - head_len * math.sin(angle - math.pi / 6),
    )
    right = QPointF(
        end.x() - head_len * math.cos(angle + math.pi / 6),
        end.y() - head_len * math.sin(angle + math.pi / 6),
    )
    painter.drawPolygon(QPolygonF([end, left, right]))
    painter.restore()


def draw_rect_annotation(
    painter: QPainter,
    rect: QRectF,
    color: QColor,
    width: float,
    fill: str = "none",
) -> None:
    if rect.width() <= 0 or rect.height() <= 0:
        return
    painter.save()
    pen = QPen(color, width)
    pen.setCapStyle(Qt.PenCapStyle.RoundCap)
    pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
    painter.setPen(pen)
    _apply_fill(painter, color, fill)
    inset = _calc_shape_inset(width, rect)
    painter.drawRoundedRect(rect.adjusted(inset, inset, -inset, -inset), 4.0, 4.0)
    painter.restore()


def draw_ellipse_annotation(
    painter: QPainter,
    rect: QRectF,
    color: QColor,
    width: float,
    fill: str = "none",
) -> None:
    if rect.width() <= 0 or rect.height() <= 0:
        return
    painter.save()
    pen = QPen(color, width)
    pen.setCapStyle(Qt.PenCapStyle.RoundCap)
    painter.setPen(pen)
    _apply_fill(painter, color, fill)
    inset = _calc_shape_inset(width, rect)
    painter.drawEllipse(rect.adjusted(inset, inset, -inset, -inset))
    painter.restore()


def draw_dashed_rect_annotation(
    painter: QPainter,
    rect: QRectF,
    color: QColor,
    width: float,
) -> None:
    if rect.width() <= 0 or rect.height() <= 0:
        return
    painter.save()
    pen = QPen(color, width)
    pen.setStyle(Qt.PenStyle.DashLine)
    pen.setDashOffset(0)
    pen.setCapStyle(Qt.PenCapStyle.RoundCap)
    pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
    painter.setPen(pen)
    painter.setBrush(Qt.BrushStyle.NoBrush)
    inset = min(width / 2.0, max(0.0, rect.width() / 2.0 - 1.0), max(0.0, rect.height() / 2.0 - 1.0))
    painter.drawRect(rect.adjusted(inset, inset, -inset, -inset))
    painter.restore()


# ── QFont / QFontMetrics 缓存 ──
_NUMBER_FONT: QFont | None = None
_NUMBER_METRICS: QFontMetrics | None = None
_TEXT_FONT_CACHE: dict[int, tuple[QFont, QFontMetrics]] = {}


def _get_number_font() -> tuple[QFont, QFontMetrics]:
    global _NUMBER_FONT, _NUMBER_METRICS
    if _NUMBER_FONT is None:
        _NUMBER_FONT = QFont("Microsoft YaHei")
        _NUMBER_FONT.setWeight(QFont.Weight.Bold)
        _NUMBER_FONT.setPixelSize(14)
        _NUMBER_METRICS = QFontMetrics(_NUMBER_FONT)
    return _NUMBER_FONT, _NUMBER_METRICS


def _get_text_font(pixel_size: int) -> tuple[QFont, QFontMetrics]:
    cached = _TEXT_FONT_CACHE.get(pixel_size)
    if cached is not None:
        return cached
    font = QFont("Microsoft YaHei")
    font.setWeight(QFont.Weight.Bold)
    font.setPixelSize(pixel_size)
    metrics = QFontMetrics(font)
    _TEXT_FONT_CACHE[pixel_size] = (font, metrics)
    return font, metrics


def draw_number_badge(
    painter: QPainter,
    center: QPointF,
    num: int,
    color: QColor,
) -> None:
    radius = 16.0
    center = QPointF(center)
    painter.save()
    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(color)
    painter.drawEllipse(center, radius, radius)
    font, _ = _get_number_font()
    painter.setFont(font)
    painter.setPen(QColor(255, 255, 255))
    painter.drawText(
        QRectF(center.x() - radius, center.y() - radius, radius * 2, radius * 2),
        Qt.AlignmentFlag.AlignCenter,
        str(num),
    )
    painter.restore()


def draw_polyline(
    painter: QPainter,
    points: List[QPointF],
    color: QColor,
    width: float,
) -> None:
    if len(points) < 2:
        return
    painter.save()
    pen = QPen(color, width)
    pen.setCapStyle(Qt.PenCapStyle.RoundCap)
    pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
    painter.setPen(pen)
    path = QPainterPath()
    path.moveTo(points[0])
    for pt in points[1:]:
        path.lineTo(pt)
    painter.drawPath(path)
    painter.restore()


def eraser_width_from_stroke(width: float) -> float:
    return max(8.0, float(width) * 2.0)


def eraser_path(points: List[QPointF], width: float) -> QPainterPath:
    path = QPainterPath()
    if not points:
        return path
    path.moveTo(points[0])
    for pt in points[1:]:
        path.lineTo(pt)
    stroker = QPainterPathStroker()
    stroker.setWidth(eraser_width_from_stroke(width))
    stroker.setCapStyle(Qt.PenCapStyle.RoundCap)
    stroker.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
    return stroker.createStroke(path)


def restore_source_along_path(
    painter: QPainter,
    points: List[QPointF],
    width: float,
    source: QPixmap,
) -> None:
    if len(points) < 2 or source.isNull():
        return
    path = eraser_path(points, width)
    if path.isEmpty():
        return
    painter.save()
    painter.setClipPath(path)
    painter.drawPixmap(0, 0, source)
    painter.restore()


def paint_eraser_on_pixmap(painter: QPainter, item: Dict[str, object], source: QPixmap) -> None:
    raw_points = item.get("points", [])
    points = [QPointF(int(raw[0]), int(raw[1])) for raw in raw_points if isinstance(raw, (tuple, list)) and len(raw) == 2]
    restore_source_along_path(painter, points, float(item.get("width", 5)), source)


def text_annotation_path(top_left: QPointF, text: str, font: QFont, metrics: QFontMetrics | None = None) -> QPainterPath:
    path = QPainterPath()
    if metrics is None:
        metrics = QFontMetrics(font)
    y = top_left.y() + metrics.ascent()
    for line in text.splitlines():
        if line:
            path.addText(QPointF(top_left.x(), y), font, line)
        y += metrics.lineSpacing()
    return path


def draw_text_annotation(
    painter: QPainter,
    top_left: QPointF,
    text: str,
    pixel_size: int,
    color: QColor,
) -> None:
    ps = max(8, int(round(pixel_size)))
    font, metrics = _get_text_font(ps)
    path = text_annotation_path(top_left, text, font, metrics)
    if path.isEmpty():
        return
    outline_width = max(2, int(round(pixel_size * 0.18)))
    painter.save()
    painter.setPen(QPen(QColor(0, 0, 0, 220), outline_width))
    painter.drawPath(path)
    painter.fillPath(path, QBrush(color))
    painter.restore()


def paint_annotation_on_pixmap(painter: QPainter, item: Dict[str, object]) -> None:
    """把一条 annotation 直接画到 pixmap 上（图像坐标系，1:1 像素）。"""
    kind = item.get("type")
    if kind == "arrow":
        start = QPoint(int(item.get("x1", 0)), int(item.get("y1", 0)))
        end = QPoint(int(item.get("x2", 0)), int(item.get("y2", 0)))
        color = QColor(str(item.get("color", "#ff4646")))
        width = float(item.get("width", 5))
        draw_arrow(painter, QPointF(start), QPointF(end), color, width, max(16.0, width * 4.4))
    elif kind == "rect":
        rect = QRect(int(item.get("x", 0)), int(item.get("y", 0)), int(item.get("w", 0)), int(item.get("h", 0)))
        draw_rect_annotation(painter, QRectF(rect), QColor(str(item.get("color", "#ff4646"))), float(item.get("width", 5)), str(item.get("fill", "none")))
    elif kind in ("pen", "highlight"):
        raw_points = item.get("points", [])
        points = [QPointF(int(raw[0]), int(raw[1])) for raw in raw_points if isinstance(raw, (tuple, list)) and len(raw) == 2]
        if kind == "highlight":
            color = QColor(str(item.get("color", "#ff4646")))
            color.setAlpha(96)
            draw_polyline(painter, points, color, float(item.get("width", 12)))
        else:
            draw_polyline(painter, points, QColor(str(item.get("color", "#ff4646"))), float(item.get("width", 5)))
    elif kind == "text":
        draw_text_annotation(
            painter,
            QPointF(int(item.get("x", 0)), int(item.get("y", 0))),
            str(item.get("text", "")),
            int(item.get("size", 28)),
            QColor(str(item.get("color", "#ffffff"))),
        )
    elif kind == "mosaic":
        patch = item.get("patch")
        if not isinstance(patch, QPixmap) or patch.isNull():
            return
        rect = QRect(int(item.get("x", 0)), int(item.get("y", 0)), int(item.get("w", 0)), int(item.get("h", 0)))
        if rect.width() <= 0 or rect.height() <= 0:
            return
        scaled_patch = patch
        if patch.width() != rect.width() or patch.height() != rect.height():
            scaled_patch = patch.scaled(rect.size(), Qt.AspectRatioMode.IgnoreAspectRatio, Qt.TransformationMode.FastTransformation)
            scaled_patch.setDevicePixelRatio(1.0)
        painter.drawPixmap(rect.topLeft(), scaled_patch)
    elif kind == "ellipse":
        rect = QRect(int(item.get("x", 0)), int(item.get("y", 0)), int(item.get("w", 0)), int(item.get("h", 0)))
        draw_ellipse_annotation(painter, QRectF(rect), QColor(str(item.get("color", "#ff4646"))), float(item.get("width", 5)), str(item.get("fill", "none")))
    elif kind == "dashed_rect":
        rect = QRect(int(item.get("x", 0)), int(item.get("y", 0)), int(item.get("w", 0)), int(item.get("h", 0)))
        draw_dashed_rect_annotation(painter, QRectF(rect), QColor(str(item.get("color", "#ff4646"))), float(item.get("width", 5)))
    elif kind == "number":
        center = QPointF(int(item.get("x", 0)), int(item.get("y", 0)))
        draw_number_badge(painter, center, int(item.get("num", 1)), QColor(str(item.get("color", "#ff4646"))))
    elif kind == "blur":
        patch = item.get("patch")
        if not isinstance(patch, QPixmap) or patch.isNull():
            return
        rect = QRect(int(item.get("x", 0)), int(item.get("y", 0)), int(item.get("w", 0)), int(item.get("h", 0)))
        if rect.width() <= 0 or rect.height() <= 0:
            return
        scaled_patch = patch
        if patch.width() != rect.width() or patch.height() != rect.height():
            scaled_patch = patch.scaled(rect.size(), Qt.AspectRatioMode.IgnoreAspectRatio, Qt.TransformationMode.FastTransformation)
            scaled_patch.setDevicePixelRatio(1.0)
        painter.drawPixmap(rect.topLeft(), scaled_patch)
