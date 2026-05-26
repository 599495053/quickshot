"""PaintMixin — 渲染：背景、遮罩、选区边框、把手、浮动气泡、消息。"""

from __future__ import annotations

from typing import Optional, Tuple

from PyQt6.QtCore import QPoint, QRect, QRectF, Qt
from PyQt6.QtGui import QColor, QFont, QFontMetrics, QPainter, QPainterPath, QPen

from . import annotation_painter
from ..theme import (
    STROKE_DEFAULT,
    floating_bg,
    floating_border,
    floating_text,
    handle_fill,
    overlay_dim,
    overlay_solid,
    qc,
)


class PaintMixin:

    # ── pen / 颜色缓存（懒初始化；主题切换时调 invalidate_paint_cache）──

    def _ensure_paint_cache(self) -> None:
        if getattr(self, "_paint_cache_ready", False):
            return
        accent = qc("accent.base")

        pen_glow = QPen(qc("accent.base", 60), 3)
        pen_glow.setJoinStyle(Qt.PenJoinStyle.MiterJoin)
        self._pen_selection_glow = pen_glow

        pen_outer = QPen(QColor(255, 255, 255, 180), 1)
        pen_outer.setJoinStyle(Qt.PenJoinStyle.MiterJoin)
        self._pen_selection_outer = pen_outer

        pen_border = QPen(accent, 1.5)
        pen_border.setJoinStyle(Qt.PenJoinStyle.MiterJoin)
        self._pen_selection_border = pen_border

        pen_handle = QPen(accent, 4)
        pen_handle.setCapStyle(Qt.PenCapStyle.RoundCap)
        pen_handle.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
        self._pen_handle = pen_handle

        self._color_drag_active_bg = QColor(34, 142, 255, 245)
        self._color_drag_active_border = QColor(115, 190, 255, 245)
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
        self._tb_primary_fill = QColor(34, 197, 94, 160)
        self._tb_primary_fill_hover = QColor(34, 197, 94, 220)
        self._tb_primary_border = QColor(34, 197, 94, 200)
        self._tb_danger_fill = QColor(239, 68, 68, 140)
        self._tb_danger_fill_hover = QColor(239, 68, 68, 220)
        self._tb_danger_border = QColor(239, 68, 68, 200)
        self._tb_toggled_fill = QColor(59, 130, 246, 180)
        self._tb_toggled_border = QColor(59, 130, 246, 220)
        self._tb_active_fill = QColor(59, 130, 246, 120)
        self._tb_active_border = QColor(59, 130, 246, 180)
        self._tb_hover_fill = QColor(255, 255, 255, 35)
        self._tb_hover_border = QColor(255, 255, 255, 50)
        self._tb_normal_fill = QColor(255, 255, 255, 0)
        self._tb_normal_border = QColor(0, 0, 0, 0)
        self._tb_accent_bar = QColor(96, 165, 250)
        # 图标颜色缓存
        self._tb_icon_white = QColor(255, 255, 255)
        self._tb_icon_active = QColor(147, 197, 253)
        self._tb_icon_normal = QColor(209, 213, 219)
        # 网格 pen 缓存
        self._pen_grid = QPen(QColor(getattr(self.config, "grid_color", "#ffffff80")), 1, Qt.PenStyle.DashLine)
        # separator pen 缓存
        self._pen_sep = QPen(QColor(255, 255, 255, 40), 1)
        # 样式面板状态颜色缓存
        self._sp_selected_bg = QColor(59, 130, 246, 60)
        self._sp_hover_bg = QColor(255, 255, 255, 25)
        self._sp_normal_bg = QColor(255, 255, 255, 0)
        self._sp_selected_border = QColor(96, 165, 250)
        self._sp_hover_border = QColor(255, 255, 255, 60)
        self._sp_normal_border = QColor(0, 0, 0, 0)
        # 样式面板绘制用 pen 缓存
        self._pen_color_sel = QPen(accent, 1.5)
        self._pen_color_hover = QPen(QColor(255, 255, 255, 80), 1.5)
        self._pen_color_dot = QPen(qc("text.primary", 90), 1)
        self._pen_check_white = QPen(QColor(255, 255, 255), 2, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin)
        self._pen_check_dark = QPen(qc("text.primary"), 2, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin)
        self._pen_width_sample = QPen(QColor(255, 255, 255), 1, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap)

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

    def draw_dim_outside(self, painter: QPainter, clear_rect: QRect) -> None:
        shade = overlay_dim()
        rect = clear_rect.normalized().intersected(self.rect())
        if rect.isNull() or rect.width() <= 0 or rect.height() <= 0:
            painter.fillRect(self.rect(), shade)
            return

        w = self.width()
        h = self.height()
        top_h = max(0, rect.top())
        bottom_y = rect.bottom() + 1
        bottom_h = max(0, h - bottom_y)
        left_w = max(0, rect.left())
        right_x = rect.right() + 1
        right_w = max(0, w - right_x)

        if top_h > 0:
            painter.fillRect(QRect(0, 0, w, top_h), shade)
        if bottom_h > 0:
            painter.fillRect(QRect(0, bottom_y, w, bottom_h), shade)
        if left_w > 0:
            painter.fillRect(QRect(0, rect.top(), left_w, rect.height()), shade)
        if right_w > 0:
            painter.fillRect(QRect(right_x, rect.top(), right_w, rect.height()), shade)

    def draw_interaction_blocker(self, painter: QPainter, rect: QRect) -> None:
        if rect.isNull() or rect.width() <= 0 or rect.height() <= 0:
            return
        painter.save()
        painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceOver)
        painter.fillRect(rect.intersected(self.rect()), QColor(0, 0, 0, 1))
        painter.restore()

    def draw_selection_snapshot(self, painter: QPainter) -> None:
        if self.selection_rect.isNull() or self.selection_display_pixmap.isNull():
            return
        painter.save()
        painter.setClipRect(self.selection_rect)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, False)
        painter.drawPixmap(self.selection_rect, self.selection_display_pixmap)
        painter.restore()

    def draw_grid(self, painter: QPainter) -> None:
        """绘制三分法网格辅助线。"""
        if self.selection_rect.isNull():
            return
        rect = self.selection_rect
        painter.save()
        painter.setClipRect(rect)
        self._ensure_paint_cache()
        painter.setPen(self._pen_grid)
        # 垂直三等分线
        x1 = rect.x() + rect.width() // 3
        x2 = rect.x() + rect.width() * 2 // 3
        painter.drawLine(x1, rect.y(), x1, rect.bottom())
        painter.drawLine(x2, rect.y(), x2, rect.bottom())
        # 水平三等分线
        y1 = rect.y() + rect.height() // 3
        y2 = rect.y() + rect.height() * 2 // 3
        painter.drawLine(rect.x(), y1, rect.right(), y1)
        painter.drawLine(rect.x(), y2, rect.right(), y2)
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
        self._ensure_paint_cache()
        painter.save()
        stable = QRectF(rect).adjusted(0.5, 0.5, -0.5, -0.5)
        painter.setBrush(Qt.BrushStyle.NoBrush)

        painter.setPen(self._pen_selection_glow)
        painter.drawRect(stable.adjusted(-1.0, -1.0, 1.0, 1.0))

        painter.setPen(self._pen_selection_outer)
        painter.drawRect(stable)

        painter.setPen(self._pen_selection_border)
        painter.drawRect(stable.adjusted(1.0, 1.0, -1.0, -1.0))
        painter.restore()

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

        if rect.width() > 120 and rect.height() > 90:
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(handle_fill())
            size = 6
            half = size // 2
            for p in [
                QPoint(rect.center().x(), rect.top()),
                QPoint(rect.center().x(), rect.bottom()),
                QPoint(rect.left(), rect.center().y()),
                QPoint(rect.right(), rect.center().y()),
            ]:
                painter.drawRoundedRect(p.x() - half, p.y() - half, size, size, 3, 3)
        painter.restore()

    def draw_size_label(self, painter: QPainter, rect: QRect, width: int, height: int) -> None:
        label = self.size_label_rect(rect, width, height)
        if label.isNull():
            return
        text = f"{width} × {height}"
        self._ensure_paint_cache()
        self.draw_floating_bubble(
            painter,
            label,
            text,
            font=self._font_label,
            radius=9,
            bg=floating_bg(),
            border=floating_border(),
            text_color=floating_text(),
            shadow_layers=((5, 18), (2, 28)),
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
        shadow_layers = shadow_layers or ((5, 25), (2, 40))

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

    def draw_toolbar(self, painter: QPainter) -> None:
        self._update_toolbar_layout_if_needed()
        self.update_style_panel_layout()
        if self.toolbar_rect.isNull():
            return

        painter.save()

        panel = QRectF(self.toolbar_rect)

        for offset, alpha in ((5, 18), (2, 35)):
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QColor(0, 0, 0, alpha))
            painter.drawRoundedRect(panel.adjusted(-offset, -offset, offset, offset), 7 + offset, 7 + offset)

        painter.setBrush(floating_bg())
        painter.setPen(QPen(floating_border(), 1))
        painter.drawRoundedRect(panel, 7, 7)

        self._ensure_paint_cache()
        items = self.toolbar_items()  # 缓存为局部变量，下面 3 处复用
        painter.setPen(self._pen_sep)
        for index, (key, _label, _icon, _tip) in enumerate(items):
            if key != 'sep':
                continue
            left_button = None
            right_button = None
            for prev_key, *_ in reversed(items[:index]):
                if prev_key != 'sep' and prev_key in self.toolbar_buttons:
                    left_button = self.toolbar_buttons[prev_key]
                    break
            for next_key, *_ in items[index + 1:]:
                if next_key != 'sep' and next_key in self.toolbar_buttons:
                    right_button = self.toolbar_buttons[next_key]
                    break
            if left_button is not None and right_button is not None:
                sx = (left_button.right() + right_button.left()) // 2
                painter.drawLine(QPoint(sx, self.toolbar_rect.top() + 9), QPoint(sx, self.toolbar_rect.bottom() - 9))

        for key, label, _icon, _tip in items:
            if key == 'sep':
                continue
            rect = self.toolbar_buttons.get(key)
            if rect is None:
                continue

            active = key == self.active_tool
            hovered = key == self.hover_button
            primary = key == 'done'
            danger = key == 'cancel'
            toggled = key in ("color", "width") and self.style_panel_kind in ("style", key)

            rr = QRectF(rect).adjusted(1.5, 1.5, -1.5, -1.5)
            icon_rect = QRect(rect.left() + 7, rect.top() + 7, rect.width() - 14, rect.height() - 14)

            if primary:
                fill = self._tb_primary_fill_hover if hovered else self._tb_primary_fill
                border = self._tb_primary_border
            elif danger:
                fill = self._tb_danger_fill_hover if hovered else self._tb_danger_fill
                border = self._tb_danger_border
            elif toggled:
                fill = self._tb_toggled_fill
                border = self._tb_toggled_border
            elif active:
                fill = self._tb_active_fill
                border = self._tb_active_border
            elif hovered:
                fill = self._tb_hover_fill
                border = self._tb_hover_border
            else:
                fill = self._tb_normal_fill
                border = self._tb_normal_border

            if fill.alpha() > 0:
                painter.setPen(QPen(border, 1))
                painter.setBrush(fill)
                painter.drawRoundedRect(rr, 6.5, 6.5)

            if active or toggled:
                accent_rect = QRectF(rect.left() + 9, rect.bottom() - 4, rect.width() - 18, 2.5)
                painter.setPen(Qt.PenStyle.NoPen)
                painter.setBrush(self._tb_accent_bar)
                painter.drawRoundedRect(accent_rect, 1.1, 1.1)

            if primary or danger:
                icon_color = self._tb_icon_white
            elif active or toggled:
                icon_color = self._tb_icon_active
            else:
                icon_color = self._tb_icon_normal if not hovered else self._tb_icon_white

            self.icons.draw(painter, key, icon_rect, icon_color)

        if self.hover_button:
            for key, _label, _icon, tip in items:
                if key == self.hover_button:
                    self.draw_toolbar_tip(painter, tip)
                    break

        painter.restore()

    def draw_style_panel(self, painter: QPainter) -> None:
        self.update_style_panel_layout()
        if self.style_panel_rect.isNull():
            return

        self.draw_floating_bubble(
            painter,
            self.style_panel_rect,
            "",
            radius=8,
            bg=floating_bg(),
            border=floating_border(),
            shadow_layers=((6, 18), (2, 35)),
        )

        self._ensure_paint_cache()

        painter.save()

        if self.style_panel_kind in ("color", "style"):
            for option_id, rect in self.style_option_rects.items():
                if not option_id.startswith("color:"):
                    continue
                color_name = option_id.split(":", 1)[1]
                selected = color_name == self.stroke_color_name
                hovered = option_id == self.hover_style_option
                outer = QRectF(rect).adjusted(-1.5, -1.5, 1.5, 1.5)
                if selected or hovered:
                    painter.setPen(self._pen_color_sel if selected else self._pen_color_hover)
                    painter.setBrush(self._sp_selected_bg if selected else self._sp_hover_bg)
                    painter.drawEllipse(outer)
                painter.setPen(self._pen_color_dot)
                painter.setBrush(QColor(color_name))
                painter.drawEllipse(QRectF(rect))
                if selected:
                    cx = rect.center().x()
                    cy = rect.center().y()
                    r = rect.width() * 0.28
                    path = QPainterPath()
                    path.moveTo(cx - r, cy)
                    path.lineTo(cx - r * 0.25, cy + r * 0.7)
                    path.lineTo(cx + r, cy - r * 0.6)
                    painter.setPen(self._pen_check_white if color_name.lower() not in ("#ffffff", "#ffcc00") else self._pen_check_dark)
                    painter.setBrush(Qt.BrushStyle.NoBrush)
                    painter.drawPath(path)
        if self.style_panel_kind in ("width", "style"):
            for option_id, rect in self.style_option_rects.items():
                if not option_id.startswith("width:"):
                    continue
                width_text = option_id.split(":", 1)[1]
                try:
                    width_value = int(width_text)
                except ValueError:
                    continue
                selected = width_value == int(self.stroke_width)
                hovered = option_id == self.hover_style_option
                bg = self._sp_selected_bg if selected else self._sp_hover_bg if hovered else self._sp_normal_bg
                border = self._sp_selected_border if selected else self._sp_hover_border if hovered else self._sp_normal_border
                painter.setPen(QPen(border, 1))
                painter.setBrush(bg)
                painter.drawRoundedRect(QRectF(rect), 6, 6)
                sample_y = rect.center().y()
                self._pen_width_sample.setWidthF(max(1.8, min(5.0, width_value / 1.6)))
                painter.setPen(self._pen_width_sample)
                painter.drawLine(rect.left() + 6, sample_y, rect.right() - 6, sample_y)
        # 预设按钮
        if self.style_panel_kind == "style":
            presets = getattr(self.config, "annotation_presets", [])
            for option_id, rect in self.style_option_rects.items():
                if not option_id.startswith("preset:"):
                    continue
                try:
                    idx = int(option_id.split(":", 1)[1])
                except ValueError:
                    continue
                if idx >= len(presets):
                    continue
                preset = presets[idx]
                hovered = option_id == self.hover_style_option
                bg = QColor(255, 255, 255, 25) if hovered else QColor(255, 255, 255, 10)
                border = QColor(255, 255, 255, 60) if hovered else QColor(255, 255, 255, 30)
                painter.setPen(QPen(border, 1))
                painter.setBrush(bg)
                painter.drawRoundedRect(QRectF(rect), 4, 4)
                # 颜色小圆点
                color_dot = QRect(rect.left() + 4, rect.center().y() - 4, 8, 8)
                painter.setPen(Qt.PenStyle.NoPen)
                painter.setBrush(QColor(preset.get("color", "#ff4646")))
                painter.drawEllipse(color_dot)
                # 名称
                painter.setPen(QColor(255, 255, 255, 200))
                font = painter.font()
                font.setPixelSize(10)
                painter.setFont(font)
                name = preset.get("name", "")
                painter.drawText(rect.adjusted(14, 0, 0, 0), Qt.AlignmentFlag.AlignVCenter, name[:6])
        painter.restore()

    def draw_toolbar_tip(self, painter: QPainter, text: str) -> None:
        if self.toolbar_rect.isNull() or not text or self.style_panel_kind:
            return
        self._ensure_paint_cache()
        font = self._font_tip
        metrics = self._fm_tip
        w = metrics.horizontalAdvance(text) + 22
        h = 28
        anchor_rect = self.toolbar_buttons.get(self.hover_button, self.toolbar_rect)
        x = anchor_rect.center().x() - w // 2
        y = anchor_rect.top() - h - 10
        if y < 8:
            y = anchor_rect.bottom() + 10
        x = max(8, min(self.width() - w - 8, x))
        r = QRect(x, y, w, h)
        self.draw_floating_bubble(
            painter,
            r,
            text,
            font=font,
            radius=8,
            bg=floating_bg(),
            border=floating_border(),
            text_color=floating_text(),
            shadow_layers=((5, 18), (2, 28)),
        )

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
        self.update_toolbar_layout()
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
        self.update_toolbar_layout()
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
        self.update_toolbar_layout()
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
            bg=floating_bg(),
            border=floating_border(),
            text_color=floating_text(),
            shadow_layers=((5, 18), (2, 28)),
        )
