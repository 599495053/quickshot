"""PaintMixin — 渲染：背景、遮罩、选区边框、把手、浮动气泡、消息。"""

from __future__ import annotations

from typing import Optional, Tuple

from PyQt6.QtCore import QPoint, QRect, QRectF, Qt
from PyQt6.QtGui import QColor, QFont, QFontMetrics, QPainter, QPen, QPixmap, QRegion

from . import annotation_painter
from ._paint_toolbar import ToolbarPaintMixin
from ._paint_style_panel import StylePanelPaintMixin
from ..theme import (
    STROKE_DEFAULT,
    floating_bg,
    floating_border,
    floating_text,
    overlay_dim,
    overlay_solid,
    overlay_tip_bg,
    overlay_tip_border,
    overlay_tip_text,
    overlay_toolbar_active_bg,
    overlay_toolbar_active_border,
    overlay_toolbar_danger_bg,
    overlay_toolbar_danger_bg_hover,
    overlay_toolbar_danger_border,
    overlay_toolbar_hover_bg,
    overlay_toolbar_icon,
    overlay_toolbar_primary_bg,
    overlay_toolbar_primary_bg_hover,
    overlay_toolbar_primary_border,
    overlay_toolbar_text,
    qc,
    qcolor_from_rgba_hex,
)


class PaintMixin(ToolbarPaintMixin, StylePanelPaintMixin):
    _ACTIVE_DIM_ALPHA = 132
    _DIM_BACKDROP_DOWNSCALE = 16

    # ── pen / 颜色缓存（懒初始化；主题切换时调 invalidate_paint_cache）──

    def _ensure_paint_cache(self) -> None:
        if getattr(self, "_paint_cache_ready", False):
            return
        accent = qc("accent.base")

        pen_handle = QPen(accent, 4)
        pen_handle.setCapStyle(Qt.PenCapStyle.RoundCap)
        pen_handle.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
        self._pen_handle = pen_handle

        self._color_drag_active_bg = overlay_toolbar_primary_bg()
        self._color_drag_active_border = overlay_toolbar_primary_border()
        self._color_drag_active_text = QColor(255, 255, 255)

        # QFont / QFontMetrics 缓存（paintEvent 中高频构造，提升到这里只构造一次）
        self._font_center_hint = QFont("Microsoft YaHei", 13, QFont.Weight.Medium)
        self._fm_center_hint = QFontMetrics(self._font_center_hint)
        self._font_label = QFont("Microsoft YaHei", 9, QFont.Weight.DemiBold)
        self._fm_label = QFontMetrics(self._font_label)
        self._font_tip = QFont("Microsoft YaHei", 9, QFont.Weight.Medium)
        self._fm_tip = QFontMetrics(self._font_tip)

        # ── 工具栏按钮状态颜色缓存 ──
        # 每种状态预建 (fill, border) QColor 对，避免 draw_toolbar 每帧 new
        self._tb_primary_fill = overlay_toolbar_primary_bg()
        self._tb_primary_fill_hover = overlay_toolbar_primary_bg_hover()
        self._tb_primary_border = overlay_toolbar_primary_border()
        self._tb_danger_fill = overlay_toolbar_danger_bg()
        self._tb_danger_fill_hover = overlay_toolbar_danger_bg_hover()
        self._tb_danger_border = overlay_toolbar_danger_border()
        self._tb_toggled_fill = overlay_toolbar_active_bg()
        self._tb_toggled_border = overlay_toolbar_active_border()
        self._tb_active_fill = overlay_toolbar_active_bg()
        self._tb_active_border = overlay_toolbar_active_border()
        self._tb_hover_fill = overlay_toolbar_hover_bg()
        self._tb_hover_border = qc("border.light", 235)
        self._tb_normal_fill = QColor(255, 255, 255, 0)
        self._tb_normal_border = QColor(0, 0, 0, 0)
        self._tb_accent_bar = qc("accent.base", 220)
        self._tb_group_bg = qc("surface.subtle", 220)
        self._tb_group_border = qc("border.light", 220)
        self._tb_cta_group_bg = qc("accent.soft", 150)
        self._tb_cta_group_border = qc("accent.outline", 170)
        # 图标颜色缓存
        self._tb_icon_white = QColor(255, 255, 255)
        self._tb_icon_active = qc("accent.base")
        self._tb_icon_normal = overlay_toolbar_icon()
        self._tb_icon_hover = overlay_toolbar_text()
        # 网格 pen 缓存
        grid_color = qcolor_from_rgba_hex(getattr(self.config, "grid_color", "#ffffff80"))
        grid_shadow = QColor(17, 24, 39, max(46, min(120, grid_color.alpha() + 28)))
        self._pen_grid_shadow = QPen(grid_shadow, 2, Qt.PenStyle.DashLine)
        self._pen_grid = QPen(grid_color, 1, Qt.PenStyle.DashLine)
        # separator pen 缓存
        self._pen_sep = QPen(qc("border.light", 235), 1)
        # 样式面板状态颜色缓存
        self._sp_selected_bg = qc("accent.soft", 245)
        self._sp_hover_bg = qc("surface.subtle", 245)
        self._sp_normal_bg = QColor(255, 255, 255, 0)
        self._sp_selected_border = qc("accent.outline", 235)
        self._sp_hover_border = qc("border.regular", 235)
        self._sp_normal_border = QColor(0, 0, 0, 0)
        # 样式面板绘制用 pen 缓存
        self._pen_color_sel = QPen(accent, 1.5)
        self._pen_color_hover = QPen(qc("border.regular", 235), 1.5)
        self._pen_color_dot = QPen(qc("text.primary", 90), 1)
        self._pen_check_white = QPen(QColor(255, 255, 255), 2, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin)
        self._pen_check_dark = QPen(qc("text.primary"), 2, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin)
        self._pen_width_sample = QPen(qc("text.secondary"), 1, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap)
        self._sp_preset_hover_bg = qc("surface.subtle", 245)
        self._sp_preset_bg = qc("surface.card", 235)
        self._sp_preset_hover_border = qc("accent.outline", 220)
        self._sp_preset_border = qc("border.light", 235)
        self._sp_preset_text = qc("text.secondary", 225)
        self._pen_panel_divider = QPen(qc("border.light", 225), 1)

        self._paint_cache_ready = True

    def invalidate_paint_cache(self) -> None:
        self._paint_cache_ready = False

    # ── 背景 ──

    def draw_frozen_desktop(self, painter: QPainter) -> None:
        if not self.display_pixmap.isNull():
            painter.save()
            painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, False)
            painter.drawPixmap(QPoint(0, 0), self.display_pixmap)
            painter.restore()
            return
        if not self.raw_pixmap.isNull():
            painter.save()
            painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, False)
            painter.drawPixmap(self.rect(), self.raw_pixmap, QRect(0, 0, self.raw_pixmap.width(), self.raw_pixmap.height()))
            painter.restore()

    def clear_canvas(self, painter: QPainter) -> None:
        painter.save()
        painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_Source)
        painter.fillRect(self.rect(), overlay_solid())
        painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceOver)
        painter.restore()

    def dim_shade(self) -> QColor:
        shade = QColor(overlay_dim())
        if self.soft_dim_backdrop_enabled():
            shade.setAlpha(max(shade.alpha(), self._ACTIVE_DIM_ALPHA))
        return shade

    def soft_dim_backdrop_enabled(self) -> bool:
        mode = getattr(self, "mode", "")
        return mode in {"select", "edit"} or getattr(self, "selecting", False) or getattr(self, "adjusting_selection", False)

    def dim_backdrop_pixmap(self, bounds: QRect) -> QPixmap:
        if self.raw_pixmap.isNull() or bounds.isNull() or bounds.width() <= 0 or bounds.height() <= 0:
            return QPixmap()
        key = (self.raw_pixmap.cacheKey(), bounds.width(), bounds.height())
        cached = getattr(self, "_dim_backdrop_cache", None)
        if cached is not None and cached[0] == key:
            return cached[1]

        small_w = max(1, bounds.width() // self._DIM_BACKDROP_DOWNSCALE)
        small_h = max(1, bounds.height() // self._DIM_BACKDROP_DOWNSCALE)
        small = self.raw_pixmap.scaled(
            small_w,
            small_h,
            Qt.AspectRatioMode.IgnoreAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
        backdrop = small.scaled(
            bounds.size(),
            Qt.AspectRatioMode.IgnoreAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
        self._dim_backdrop_cache = (key, backdrop)
        return backdrop

    def draw_dim_outside(self, painter: QPainter, clear_rect: QRect) -> None:
        shade = self.dim_shade()
        rect = clear_rect.normalized().intersected(self.rect())
        if rect.isNull() or rect.width() <= 0 or rect.height() <= 0:
            painter.fillRect(self.rect(), shade)
            return

        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, False)
        outside = QRegion(self.rect()).subtracted(QRegion(rect))
        painter.setClipRegion(outside)
        softened = self.soft_dim_backdrop_enabled()
        if softened:
            backdrop = self.dim_backdrop_pixmap(self.rect())
            if not backdrop.isNull():
                painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)
                painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_Source)
                painter.drawPixmap(self.rect(), backdrop)
                painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceOver)
                painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, False)
        painter.fillRect(self.rect(), shade)
        painter.restore()
        if not softened:
            self.draw_dim_edge_cleanup(painter, rect, shade)

    def draw_dim_edge_cleanup(self, painter: QPainter, rect: QRect, shade: QColor) -> None:
        """Heal outside-only 1px desktop scanlines near selection top/bottom edges."""
        if self.raw_pixmap.isNull() or rect.width() <= 0 or rect.height() <= 0:
            return
        bounds = self.rect()
        if bounds.isNull() or bounds.width() <= 0 or bounds.height() <= 0:
            return
        raw_key = self.raw_pixmap.cacheKey()
        cached = getattr(self, "_dim_edge_scan_cache", None)
        if cached is not None and cached[0] == raw_key:
            raw_image = cached[1]
        else:
            raw_image = self.raw_pixmap.toImage()
            self._dim_edge_scan_cache = (raw_key, raw_image)
        if raw_image.isNull():
            return
        scale_x = max(0.001, float(getattr(self, "scale_x", 1.0)))
        scale_y = max(0.001, float(getattr(self, "scale_y", 1.0)))
        physical_rect = self.logical_to_physical_rect(rect)
        if physical_rect.isNull() or physical_rect.width() <= 0 or physical_rect.height() <= 0:
            return
        edge_radius = min(14, max(1, raw_image.height()))
        outside_xs = (
            bounds.left() + 40,
            rect.left() - 10,
            rect.right() + 10,
            bounds.right() - 40,
        )
        sample_xs = tuple(
            max(0, min(raw_image.width() - 1, int(round(x * scale_x))))
            for x in outside_xs
            if bounds.left() <= x <= bounds.right() and not rect.left() <= x <= rect.right()
        )
        if not sample_xs:
            return

        line_cache: dict[int, bool] = {}

        def pixel_diff(x: int, y1: int, y2: int) -> int:
            c1 = raw_image.pixelColor(x, y1)
            c2 = raw_image.pixelColor(x, y2)
            return (
                abs(c1.red() - c2.red())
                + abs(c1.green() - c2.green())
                + abs(c1.blue() - c2.blue())
            )

        def is_horizontal_scanline(physical_y: int) -> bool:
            if physical_y in line_cache:
                return line_cache[physical_y]
            if physical_y <= 0 or physical_y >= raw_image.height() - 1:
                line_cache[physical_y] = False
                return False
            hits = 0
            for px in sample_xs:
                contrast = max(
                    pixel_diff(px, physical_y, physical_y - 1),
                    pixel_diff(px, physical_y, physical_y + 1),
                )
                if contrast >= 45:
                    hits += 1
            line_cache[physical_y] = hits >= max(1, len(sample_xs) // 2)
            return line_cache[physical_y]

        def replacement_y(physical_y: int, direction: int) -> int:
            max_offset = max(edge_radius * 4, 8)
            for offset in range(edge_radius + 1, max_offset + 1):
                candidate = physical_y + direction * offset
                if 0 <= candidate < raw_image.height() and not is_horizontal_scanline(candidate):
                    return candidate
            fallback = physical_y - direction
            return max(0, min(raw_image.height() - 1, fallback))

        top_rows = range(
            max(0, physical_rect.top() - edge_radius),
            min(raw_image.height() - 1, physical_rect.top() + edge_radius) + 1,
        )
        bottom_rows = range(
            max(0, physical_rect.bottom() - edge_radius),
            min(raw_image.height() - 1, physical_rect.bottom() + edge_radius) + 1,
        )

        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, False)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, False)
        outside = QRegion(bounds).subtracted(QRegion(rect))
        painter.setClipRegion(outside)
        for physical_y in tuple(top_rows) + tuple(bottom_rows):
            if not is_horizontal_scanline(physical_y):
                continue
            direction = -1 if abs(physical_y - physical_rect.top()) <= abs(physical_y - physical_rect.bottom()) else 1
            target = QRectF(
                float(bounds.left()),
                physical_y / scale_y,
                float(bounds.width()),
                1.0 / scale_y,
            )
            source_y = replacement_y(physical_y, direction)
            source = QRectF(0.0, float(source_y), float(raw_image.width()), 1.0)
            painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_Source)
            painter.drawPixmap(target, self.raw_pixmap, source)
            painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceOver)
            painter.fillRect(target, shade)
        painter.restore()

    def draw_interaction_blocker(self, painter: QPainter, rect: QRect) -> None:
        if rect.isNull() or rect.width() <= 0 or rect.height() <= 0:
            return
        painter.save()
        painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceOver)
        painter.fillRect(rect.intersected(self.rect()), QColor(0, 0, 0, 1))
        painter.restore()

    def draw_selection_snapshot(self, painter: QPainter, rect: Optional[QRect] = None) -> None:
        target_rect = QRect(rect) if rect is not None else QRect(self.selection_rect)
        if target_rect.isNull():
            return
        painter.save()
        painter.setClipRect(target_rect)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, False)
        if rect is None:
            if self.selection_display_pixmap.isNull():
                painter.restore()
                return
            painter.drawPixmap(target_rect, self.selection_display_pixmap)
        else:
            physical_rect = self.logical_to_physical_rect(target_rect)
            if physical_rect.width() > 0 and physical_rect.height() > 0 and not self.raw_pixmap.isNull():
                painter.drawPixmap(target_rect, self.raw_pixmap, physical_rect)
        painter.restore()

    def draw_grid(self, painter: QPainter) -> None:
        """绘制三分法网格辅助线。"""
        if self.selection_rect.isNull():
            return
        rect = self.selection_rect
        painter.save()
        painter.setClipRect(rect)
        self._ensure_paint_cache()
        # 垂直三等分线
        x1 = rect.x() + rect.width() // 3
        x2 = rect.x() + rect.width() * 2 // 3
        # 水平三等分线
        y1 = rect.y() + rect.height() // 3
        y2 = rect.y() + rect.height() * 2 // 3
        lines = (
            (x1, rect.y(), x1, rect.bottom()),
            (x2, rect.y(), x2, rect.bottom()),
            (rect.x(), y1, rect.right(), y1),
            (rect.x(), y2, rect.right(), y2),
        )
        painter.setPen(self._pen_grid_shadow)
        for line in lines:
            painter.drawLine(*line)
        painter.setPen(self._pen_grid)
        for line in lines:
            painter.drawLine(*line)
        painter.restore()

    # ── 标注叠加层 ──

    @staticmethod
    def _annotation_color(item: dict) -> QColor:
        """获取标注的 QColor（带缓存，避免每帧字符串解析）。"""
        cached = item.get("_qc")
        if cached is not None:
            return cached
        color = QColor(str(item.get("color", STROKE_DEFAULT)))
        item["_qc"] = color
        return color

    def draw_annotations_overlay(self, painter: QPainter) -> None:
        if self.selection_rect.isNull() or not self.annotations:
            return
        painter.save()
        painter.setClipRect(self.selection_rect)
        for index, item in enumerate(self.annotations):
            kind = item.get("type")
            if kind == "arrow":
                start = QPoint(int(item.get("x1", 0)), int(item.get("y1", 0)))
                end = QPoint(int(item.get("x2", 0)), int(item.get("y2", 0)))
                color = self._annotation_color(item)
                width = self.scaled_stroke_width(float(item.get("width", 5)))
                annotation_painter.draw_arrow(painter, self.image_to_widget(start), self.image_to_widget(end), color, width, max(12.0, width * 4.2))
            elif kind == "rect":
                rect = QRect(int(item.get("x", 0)), int(item.get("y", 0)), int(item.get("w", 0)), int(item.get("h", 0)))
                top_left = self.image_to_widget(rect.topLeft())
                bottom_right = self.image_to_widget(QPoint(rect.right() + 1, rect.bottom() + 1))
                color = self._annotation_color(item)
                annotation_painter.draw_rect_annotation(
                    painter,
                    QRectF(top_left, bottom_right).normalized(),
                    color,
                    self.scaled_stroke_width(float(item.get("width", 5))),
                )
            elif kind in ("pen", "highlight"):
                points = self.annotation_points_to_widget(item)
                color = self._annotation_color(item)
                if kind == "highlight":
                    color.setAlpha(96)
                annotation_painter.draw_polyline(painter, points, color, self.scaled_stroke_width(float(item.get("width", 5))))
            elif kind == "text":
                if index == self.dragging_text_index:
                    continue  # 正在拖动的文字由 draw_dragging_text_overlay 绘制
                self.draw_text_overlay(
                    painter,
                    QPoint(int(item.get("x", 0)), int(item.get("y", 0))),
                    str(item.get("text", "")),
                    int(item.get("size", 28)),
                    QColor(str(item.get("color", "#ffffff"))),
                )
                if self.selected_text_index == index and self.dragging_text_index < 0 and self.active_tool == "none":
                    self.draw_text_hover_outline(painter, item, selected=True)
                elif self.hover_text_index == index and self.dragging_text_index < 0 and self.active_tool == "none":
                    self.draw_text_hover_outline(painter, item, selected=False)
            elif kind == "mosaic":
                self.draw_mosaic_overlay(painter, item)
            elif kind == "ellipse":
                rect = QRect(int(item.get("x", 0)), int(item.get("y", 0)), int(item.get("w", 0)), int(item.get("h", 0)))
                top_left = self.image_to_widget(rect.topLeft())
                bottom_right = self.image_to_widget(QPoint(rect.right() + 1, rect.bottom() + 1))
                color = self._annotation_color(item)
                annotation_painter.draw_ellipse_annotation(
                    painter,
                    QRectF(top_left, bottom_right).normalized(),
                    color,
                    self.scaled_stroke_width(float(item.get("width", 5))),
                )
            elif kind == "dashed_rect":
                rect = QRect(int(item.get("x", 0)), int(item.get("y", 0)), int(item.get("w", 0)), int(item.get("h", 0)))
                top_left = self.image_to_widget(rect.topLeft())
                bottom_right = self.image_to_widget(QPoint(rect.right() + 1, rect.bottom() + 1))
                color = self._annotation_color(item)
                annotation_painter.draw_dashed_rect_annotation(
                    painter,
                    QRectF(top_left, bottom_right).normalized(),
                    color,
                    self.scaled_stroke_width(float(item.get("width", 5))),
                )
            elif kind == "number":
                center = self.image_to_widget(QPoint(int(item.get("x", 0)), int(item.get("y", 0))))
                color = self._annotation_color(item)
                annotation_painter.draw_number_badge(painter, center, int(item.get("num", 1)), color)
            elif kind == "blur":
                self.draw_mosaic_overlay(painter, item)
        painter.restore()

    def draw_mosaic_overlay(self, painter: QPainter, item: dict) -> None:
        patch = item.get("patch")
        if patch is None:
            return
        rect = QRect(int(item.get("x", 0)), int(item.get("y", 0)), int(item.get("w", 0)), int(item.get("h", 0)))
        if rect.width() <= 0 or rect.height() <= 0:
            return
        top_left = self.image_to_widget(rect.topLeft())
        bottom_right = self.image_to_widget(QPoint(rect.right() + 1, rect.bottom() + 1))
        target = QRectF(top_left, bottom_right).normalized()
        if target.width() <= 0 or target.height() <= 0:
            return
        tw = max(1, int(round(target.width())))
        th = max(1, int(round(target.height())))
        # 缓存缩放后的 pixmap：仅当 patch 或目标尺寸变化时才重新缩放
        cache_key = (id(patch), tw, th)
        cached = getattr(self, "_mosaic_scaled_cache", None)
        if cached is not None and cached[0] == cache_key:
            scaled = cached[1]
        else:
            scaled = patch.scaled(
                tw, th,
                Qt.AspectRatioMode.IgnoreAspectRatio, Qt.TransformationMode.FastTransformation,
            )
            scaled.setDevicePixelRatio(1.0)
            self._mosaic_scaled_cache = (cache_key, scaled)
        painter.drawPixmap(target.topLeft(), scaled)

    # ── 吸附参考线 ──

    def draw_snap_guides(self, painter: QPainter) -> None:
        """绘制吸附参考线（蓝色虚线标记被吸附的窗口边缘）。"""
        if not getattr(self.config, "show_snap_guides", False):
            return
        snap_edges = getattr(self, '_snap_edges', [])
        if not snap_edges:
            return
        painter.save()
        pen = QPen(QColor(59, 130, 246, 180), 1.5, Qt.PenStyle.DashLine)
        painter.setPen(pen)
        for edge_name, wrect in snap_edges:
            if edge_name == "left":
                painter.drawLine(wrect.topLeft(), wrect.bottomLeft())
            elif edge_name == "right":
                painter.drawLine(wrect.topRight(), wrect.bottomRight())
            elif edge_name == "top":
                painter.drawLine(wrect.topLeft(), wrect.topRight())
            elif edge_name == "bottom":
                painter.drawLine(wrect.bottomLeft(), wrect.bottomRight())
        painter.restore()

    # ── 浮动元素 ──

    def draw_center_hint(self, painter: QPainter, text: str) -> None:
        self._ensure_paint_cache()
        fm = self._fm_center_hint
        max_w = min(self.width() - 36, 620)
        shown = text
        if fm.horizontalAdvance(shown) + 44 > max_w:
            shown = fm.elidedText(shown, Qt.TextElideMode.ElideRight, max_w - 44)
        box_w = min(max_w, fm.horizontalAdvance(shown) + 44)
        box_h = 48
        box = QRect(int((self.width() - box_w) / 2), int((self.height() - box_h) / 2), box_w, box_h)
        self.draw_floating_bubble(
            painter,
            box,
            shown,
            font=self._font_center_hint,
            radius=12,
            bg=floating_bg(),
            border=floating_border(),
            text_color=floating_text(),
            shadow_layers=((8, 20), (3, 32)),
        )

    def draw_selection_border(self, painter: QPainter, rect: QRect) -> None:
        return

    def draw_handles(self, painter: QPainter, rect: QRect) -> None:
        self._ensure_paint_cache()
        painter.save()
        length = max(16, min(26, min(rect.width(), rect.height()) // 6))
        painter.setPen(self._pen_handle)

        l, t, r, b = rect.left(), rect.top(), rect.right(), rect.bottom()
        painter.drawLine(QPoint(l, t), QPoint(l + length, t))
        painter.drawLine(QPoint(l, t), QPoint(l, t + length))
        painter.drawLine(QPoint(r, t), QPoint(r - length, t))
        painter.drawLine(QPoint(r, t), QPoint(r, t + length))
        painter.drawLine(QPoint(l, b), QPoint(l + length, b))
        painter.drawLine(QPoint(l, b), QPoint(l, b - length))
        painter.drawLine(QPoint(r, b), QPoint(r - length, b))
        painter.drawLine(QPoint(r, b), QPoint(r, b - length))
        painter.restore()

    def draw_size_label(self, painter: QPainter, rect: QRect, width: int, height: int) -> None:
        label = self.size_label_rect(rect, width, height)
        if label.isNull():
            return
        text = f"{width} × {height}"
        self._ensure_paint_cache()
        is_dragging = getattr(self, "selecting", False) or getattr(self, "adjusting_selection", False)
        shadow = () if is_dragging else ((5, 18), (2, 28))
        self.draw_floating_bubble(
            painter,
            label,
            text,
            font=self._font_label,
            radius=9,
            bg=floating_bg(),
            border=floating_border(),
            text_color=floating_text(),
            shadow_layers=shadow,
        )

    def draw_drag_button(self, painter: QPainter) -> None:
        self.update_drag_button_layout()
        if self.drag_button_rect.isNull():
            return
        self._ensure_paint_cache()
        if self.hover_drag_button or self.adjust_handle == "drag_button":
            bg = self._color_drag_active_bg
            border = self._color_drag_active_border
            text_color = self._color_drag_active_text
        else:
            bg = floating_bg()
            border = floating_border()
            text_color = floating_text()

        self.draw_floating_bubble(
            painter,
            self.drag_button_rect,
            "↔ 拖动选区",
            font=self._font_label,
            radius=12,
            bg=bg,
            border=border,
            text_color=text_color,
            shadow_layers=((6, 18), (2, 28)),
        )

    def draw_floating_bubble(
        self,
        painter: QPainter,
        rect: QRect,
        text: str = "",
        *,
        font: Optional[QFont] = None,
        radius: int = 9,
        bg: Optional[QColor] = None,
        border: Optional[QColor] = None,
        text_color: Optional[QColor] = None,
        shadow_layers: Optional[Tuple[Tuple[int, int], ...]] = None,
    ) -> None:
        if rect.isNull():
            return

        bg = bg or floating_bg()
        border = border or floating_border()
        text_color = text_color or floating_text()
        if shadow_layers is None:
            shadow_layers = ((5, 25), (2, 40))

        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)

        bubble = QRectF(rect)
        painter.setPen(Qt.PenStyle.NoPen)
        for offset, alpha in shadow_layers:
            painter.setBrush(QColor(0, 0, 0, alpha))
            painter.drawRoundedRect(bubble.adjusted(-offset, -offset, offset, offset), radius + offset, radius + offset)

        painter.setBrush(bg)
        if border.alpha() > 0:
            painter.setPen(QPen(border, 1))
        else:
            painter.setPen(Qt.PenStyle.NoPen)
        painter.drawRoundedRect(bubble, radius, radius)

        if text:
            if font is not None:
                painter.setFont(font)
            painter.setPen(text_color)
            painter.drawText(rect, Qt.AlignmentFlag.AlignCenter, text)

        painter.restore()

    # ── 工具栏 ──


    # ── 尺寸/消息布局 ──


    def size_label_rect(self, rect: QRect, width: int, height: int) -> QRect:
        if rect.isNull() or rect.width() <= 0 or rect.height() <= 0:
            return QRect()
        text = f"{width} × {height}"
        self._ensure_paint_cache()
        label_w = self._fm_label.horizontalAdvance(text) + 22
        label_h = 28
        x = rect.left()
        y = rect.top() - label_h - 10
        if y < 8:
            y = rect.top() + 10
        if x + label_w > self.width() - 8:
            x = self.width() - label_w - 8
        x = max(8, x)
        return QRect(x, y, label_w, label_h)

    def current_message_rect(self) -> QRect:
        if not self.message:
            return QRect()
        self._update_toolbar_layout_if_needed()
        self._ensure_paint_cache()
        metrics = self._fm_tip
        max_w = min(self.width() - 16, 560)
        text = self.message
        if metrics.horizontalAdvance(text) + 28 > max_w:
            text = metrics.elidedText(text, Qt.TextElideMode.ElideMiddle, max_w - 28)
        label_w = min(max_w, metrics.horizontalAdvance(text) + 28)
        label_h = 30
        x = self.toolbar_rect.left() if not self.toolbar_rect.isNull() else self.selection_rect.left()
        y = (self.toolbar_rect.bottom() + 10) if not self.toolbar_rect.isNull() else (self.selection_rect.bottom() + 10)
        if y + label_h > self.height() - 8:
            y = self.toolbar_rect.top() - label_h - 10 if not self.toolbar_rect.isNull() else self.selection_rect.top() - label_h - 10
        x = max(8, min(self.width() - label_w - 8, x))
        y = max(8, min(self.height() - label_h - 8, y))
        return QRect(x, y, label_w, label_h)

    def edit_repaint_rect(self) -> QRect:
        if self.selection_rect.isNull():
            return self.rect()
        self._update_toolbar_layout_if_needed()
        label_w = self.edit_pixmap.width() if not self.edit_pixmap.isNull() else self.selection_rect.width()
        label_h = self.edit_pixmap.height() if not self.edit_pixmap.isNull() else self.selection_rect.height()
        dirty = QRect(self.selection_rect).adjusted(-44, -56, 44, 56)
        size_label = self.size_label_rect(self.selection_rect, label_w, label_h)
        if not size_label.isNull():
            dirty = dirty.united(size_label.adjusted(-12, -12, 12, 12))
        if not self.toolbar_rect.isNull():
            dirty = dirty.united(self.toolbar_rect.adjusted(-18, -18, 18, 18))
        if not self.style_panel_rect.isNull():
            dirty = dirty.united(self.style_panel_rect.adjusted(-14, -14, 14, 14))
        message_rect = self.current_message_rect()
        if not message_rect.isNull():
            dirty = dirty.united(message_rect.adjusted(-12, -12, 12, 12))
        if not self.last_message_rect.isNull():
            dirty = dirty.united(self.last_message_rect.adjusted(-12, -12, 12, 12))
        return dirty.intersected(self.rect())

    def draw_message(self, painter: QPainter) -> None:
        if not self.message:
            self.last_message_rect = QRect()
            return
        self._update_toolbar_layout_if_needed()
        self._ensure_paint_cache()
        font = self._font_tip
        fm = self._fm_tip
        max_w = min(self.width() - 16, 560)
        text = self.message
        if fm.horizontalAdvance(text) + 28 > max_w:
            text = fm.elidedText(text, Qt.TextElideMode.ElideMiddle, max_w - 28)
        label_w = min(max_w, fm.horizontalAdvance(text) + 28)
        label_h = 30
        x = self.toolbar_rect.left() if not self.toolbar_rect.isNull() else self.selection_rect.left()
        y = (self.toolbar_rect.bottom() + 10) if not self.toolbar_rect.isNull() else (self.selection_rect.bottom() + 10)
        if y + label_h > self.height() - 8:
            y = self.toolbar_rect.top() - label_h - 10 if not self.toolbar_rect.isNull() else self.selection_rect.top() - label_h - 10
        x = max(8, min(self.width() - label_w - 8, x))
        y = max(8, min(self.height() - label_h - 8, y))
        rect = QRect(x, y, label_w, label_h)
        self.last_message_rect = QRect(rect)
        self.draw_floating_bubble(
            painter,
            rect,
            text,
            font=font,
            radius=9,
            bg=overlay_tip_bg(),
            border=overlay_tip_border(),
            text_color=overlay_tip_text(),
            shadow_layers=((5, 10), (2, 18)),
        )
