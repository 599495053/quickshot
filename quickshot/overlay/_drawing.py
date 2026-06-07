"""DrawingMixin — 标注绘制（箭头/矩形/画笔/高亮/马赛克）+ 实时预览。"""

from __future__ import annotations

from typing import List

from PyQt6.QtCore import QPointF, QRect, QRectF, Qt
from PyQt6.QtGui import QColor, QImage, QPainter, QPen

from ..constants import HIGHLIGHT_ALPHA, HIGHLIGHT_WIDTH_MULTIPLIER, MOSAIC_BLOCK_SIZE
from . import annotation_painter
from ..theme import qc


def _blur_radius_for_rect(rect: QRect) -> float:
    ksize = max(3, min(51, (rect.width() + rect.height()) // 8))
    if ksize % 2 == 0:
        ksize += 1
    return max(0.8, 0.3 * (((ksize - 1) * 0.5) - 1) + 0.8)


def _blur_qimage(crop: QImage, rect: QRect) -> QImage:
    from PIL import Image, ImageFilter

    source = crop.convertToFormat(QImage.Format.Format_RGBA8888)
    width = source.width()
    height = source.height()
    ptr = source.constBits()
    ptr.setsize(source.sizeInBytes())
    data = bytes(ptr)

    image = Image.frombuffer("RGBA", (width, height), data, "raw", "RGBA", source.bytesPerLine(), 1)
    blurred = image.filter(ImageFilter.GaussianBlur(radius=_blur_radius_for_rect(rect)))
    result_data = blurred.tobytes("raw", "RGBA")
    result = QImage(result_data, width, height, QImage.Format.Format_RGBA8888)
    return result.copy()


class DrawingMixin:

    # ── 绘制到 pixmap（提交） ──

    def draw_arrow_on_pixmap(self, start: QPointF, end: QPointF) -> None:
        color = QColor(self.stroke_color_name)
        width = float(self.stroke_width)
        painter = QPainter(self.edit_pixmap)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        annotation_painter.draw_arrow(painter, QPointF(start), QPointF(end), color, width, max(16.0, width * 4.4))
        painter.end()
        self.annotations.append({
            "type": "arrow",
            "x1": int(start.x()), "y1": int(start.y()),
            "x2": int(end.x()), "y2": int(end.y()),
            "color": self.stroke_color_name,
            "width": int(self.stroke_width),
        })
        self.update_selection_display_cache()

    def draw_rect_on_pixmap(self, rect: QRect) -> None:
        rect = rect.intersected(QRect(0, 0, self.edit_pixmap.width(), self.edit_pixmap.height()))
        if rect.width() <= 0 or rect.height() <= 0:
            return
        fill = getattr(self, "fill_mode", "none")
        painter = QPainter(self.edit_pixmap)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        annotation_painter.draw_rect_annotation(painter, QRectF(rect), QColor(self.stroke_color_name), float(self.stroke_width), fill)
        painter.end()
        item = {
            "type": "rect",
            "x": int(rect.x()), "y": int(rect.y()),
            "w": int(rect.width()), "h": int(rect.height()),
            "color": self.stroke_color_name,
            "width": int(self.stroke_width),
        }
        if fill != "none":
            item["fill"] = fill
        self.annotations.append(item)
        self.update_selection_display_cache()

    def draw_ellipse_on_pixmap(self, rect: QRect) -> None:
        rect = rect.intersected(QRect(0, 0, self.edit_pixmap.width(), self.edit_pixmap.height()))
        if rect.width() <= 0 or rect.height() <= 0:
            return
        fill = getattr(self, "fill_mode", "none")
        painter = QPainter(self.edit_pixmap)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        annotation_painter.draw_ellipse_annotation(painter, QRectF(rect), QColor(self.stroke_color_name), float(self.stroke_width), fill)
        painter.end()
        item = {
            "type": "ellipse",
            "x": int(rect.x()), "y": int(rect.y()),
            "w": int(rect.width()), "h": int(rect.height()),
            "color": self.stroke_color_name,
            "width": int(self.stroke_width),
        }
        if fill != "none":
            item["fill"] = fill
        self.annotations.append(item)
        self.update_selection_display_cache()

    def draw_dashed_rect_on_pixmap(self, rect: QRect) -> None:
        rect = rect.intersected(QRect(0, 0, self.edit_pixmap.width(), self.edit_pixmap.height()))
        if rect.width() <= 0 or rect.height() <= 0:
            return
        painter = QPainter(self.edit_pixmap)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        annotation_painter.draw_dashed_rect_annotation(painter, QRectF(rect), QColor(self.stroke_color_name), float(self.stroke_width))
        painter.end()
        self.annotations.append({
            "type": "dashed_rect",
            "x": int(rect.x()), "y": int(rect.y()),
            "w": int(rect.width()), "h": int(rect.height()),
            "color": self.stroke_color_name,
            "width": int(self.stroke_width),
        })
        self.update_selection_display_cache()

    def draw_number_on_pixmap(self, pos: QPointF) -> None:
        num = getattr(self, "number_counter", 1)
        painter = QPainter(self.edit_pixmap)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        annotation_painter.draw_number_badge(painter, pos, num, QColor(self.stroke_color_name))
        painter.end()
        self.annotations.append({
            "type": "number",
            "x": int(pos.x()), "y": int(pos.y()),
            "num": num,
            "color": self.stroke_color_name,
        })
        self.number_counter = num + 1
        self.update_selection_display_cache()

    def draw_freehand_on_pixmap(self, points: List) -> None:
        if len(points) < 2:
            return
        painter = QPainter(self.edit_pixmap)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        annotation_painter.draw_polyline(painter, [QPointF(point.x(), point.y()) for point in points], QColor(self.stroke_color_name), float(self.stroke_width))
        painter.end()
        self.annotations.append({
            "type": "pen",
            "points": [(int(point.x()), int(point.y())) for point in points],
            "color": self.stroke_color_name,
            "width": int(self.stroke_width),
        })
        self.update_selection_display_cache()

    def draw_highlight_on_pixmap(self, points: List) -> None:
        if len(points) < 2:
            return
        painter = QPainter(self.edit_pixmap)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceOver)
        color = QColor(self.stroke_color_name)
        color.setAlpha(HIGHLIGHT_ALPHA)
        width = float(max(12, self.stroke_width * HIGHLIGHT_WIDTH_MULTIPLIER))
        annotation_painter.draw_polyline(painter, [QPointF(point.x(), point.y()) for point in points], color, width)
        painter.end()
        self.annotations.append({
            "type": "highlight",
            "points": [(int(point.x()), int(point.y())) for point in points],
            "color": self.stroke_color_name,
            "width": int(width),
        })
        self.update_selection_display_cache()

    def apply_mosaic(self, rect: QRect) -> None:
        rect = rect.intersected(QRect(0, 0, self.edit_pixmap.width(), self.edit_pixmap.height()))
        if rect.width() <= 0 or rect.height() <= 0:
            return

        # 优化：使用缓存的 QImage，避免频繁的 toImage() 转换（O(n) → O(1)）
        image = self._get_cached_edit_image()
        if image is None:
            return

        crop = image.copy(rect)
        block = MOSAIC_BLOCK_SIZE
        small_w = max(1, rect.width() // block)
        small_h = max(1, rect.height() // block)
        small = crop.scaled(small_w, small_h, Qt.AspectRatioMode.IgnoreAspectRatio, Qt.TransformationMode.FastTransformation)
        mosaic = small.scaled(rect.width(), rect.height(), Qt.AspectRatioMode.IgnoreAspectRatio, Qt.TransformationMode.FastTransformation)

        # 直接在 edit_pixmap 上绘制，避免创建新 QPixmap
        painter = QPainter(self.edit_pixmap)
        painter.drawImage(rect.topLeft(), mosaic)
        painter.end()

        # 保存 patch 供 rebuild_edit_pixmap 重放时使用
        patch = self.edit_pixmap.copy(rect)

        # 使缓存失效，下次调用时会重新生成
        self.invalidate_image_cache()
        self.selection_snapshot_required = True

        self.annotations.append({
            "type": "mosaic",
            "x": int(rect.x()), "y": int(rect.y()),
            "w": int(rect.width()), "h": int(rect.height()),
            "patch": patch,
        })
        self.update_selection_display_cache()

    def apply_blur(self, rect: QRect) -> None:
        rect = rect.intersected(QRect(0, 0, self.edit_pixmap.width(), self.edit_pixmap.height()))
        if rect.width() <= 0 or rect.height() <= 0:
            return

        # 优化：使用缓存的 QImage，避免频繁的 toImage() 转换（O(n) → O(1)）
        image = self._get_cached_edit_image()
        if image is None:
            return

        crop = image.copy(rect)
        result = _blur_qimage(crop, rect)

        # 直接在 edit_pixmap 上绘制，避免创建新 QPixmap
        painter = QPainter(self.edit_pixmap)
        painter.drawImage(rect.topLeft(), result)
        painter.end()

        # 保存 patch 供 rebuild_edit_pixmap 重放时使用
        patch = self.edit_pixmap.copy(rect)

        # 使缓存失效，下次调用时会重新生成
        self.invalidate_image_cache()
        self.selection_snapshot_required = True

        self.annotations.append({
            "type": "blur",
            "x": int(rect.x()), "y": int(rect.y()),
            "w": int(rect.width()), "h": int(rect.height()),
            "patch": patch,
        })
        self.update_selection_display_cache()

    # ── 实时预览（拖动过程中） ──

    def draw_arrow_preview(self, painter: QPainter, start, end) -> None:
        s = self.image_to_widget(start)
        e = self.image_to_widget(end)
        width = self.scaled_stroke_width(float(self.stroke_width))
        annotation_painter.draw_arrow(painter, s, e, QColor(self.stroke_color_name), width, max(12.0, width * 4.2))

    def draw_rect_preview(self, painter: QPainter, start, end) -> None:
        s = self.image_to_widget(start)
        e = self.image_to_widget(end)
        rect = QRectF(s, e).normalized()
        if rect.width() <= 0 or rect.height() <= 0:
            return
        annotation_painter.draw_rect_annotation(painter, rect, QColor(self.stroke_color_name), self.scaled_stroke_width(float(self.stroke_width)))

    def draw_ellipse_preview(self, painter: QPainter, start, end) -> None:
        s = self.image_to_widget(start)
        e = self.image_to_widget(end)
        rect = QRectF(s, e).normalized()
        if rect.width() <= 0 or rect.height() <= 0:
            return
        annotation_painter.draw_ellipse_annotation(painter, rect, QColor(self.stroke_color_name), self.scaled_stroke_width(float(self.stroke_width)))

    def draw_dashed_rect_preview(self, painter: QPainter, start, end) -> None:
        s = self.image_to_widget(start)
        e = self.image_to_widget(end)
        rect = QRectF(s, e).normalized()
        if rect.width() <= 0 or rect.height() <= 0:
            return
        annotation_painter.draw_dashed_rect_annotation(painter, rect, QColor(self.stroke_color_name), self.scaled_stroke_width(float(self.stroke_width)))

    def draw_freehand_preview(self, painter: QPainter) -> None:
        points = [self.image_to_widget(point) for point in getattr(self, "drag_path", [])]
        if len(points) < 2:
            return
        color = QColor(self.stroke_color_name)
        width = float(self.stroke_width)
        if self.active_tool == "highlight":
            color.setAlpha(HIGHLIGHT_ALPHA)
            width = max(12.0, width * HIGHLIGHT_WIDTH_MULTIPLIER)
        annotation_painter.draw_polyline(painter, points, color, self.scaled_stroke_width(width))

    def draw_mosaic_preview(self, painter: QPainter, start, end) -> None:
        s = self.image_to_widget(start)
        e = self.image_to_widget(end)
        rect = QRectF(s, e).normalized()
        pen = QPen(QColor(255, 255, 255), 2, Qt.PenStyle.DashLine)
        painter.setPen(pen)
        painter.setBrush(qc("accent.base", 50))
        painter.drawRoundedRect(rect, 4, 4)

    def draw_blur_preview(self, painter: QPainter, start, end) -> None:
        s = self.image_to_widget(start)
        e = self.image_to_widget(end)
        rect = QRectF(s, e).normalized()
        pen = QPen(QColor(200, 200, 255), 2, Qt.PenStyle.DashLine)
        painter.setPen(pen)
        painter.setBrush(QColor(100, 100, 255, 40))
        painter.drawRoundedRect(rect, 4, 4)
