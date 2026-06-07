"""StylePanelPaintMixin — 样式面板渲染：颜色选择、线宽选择、预设按钮。"""

from __future__ import annotations

from PyQt6.QtCore import QRect, QRectF, Qt
from PyQt6.QtGui import QColor, QPainter, QPainterPath, QPen

from ..theme import (
    qc,
    overlay_panel_bg,
    overlay_panel_border,
)


class StylePanelPaintMixin:
    """样式面板绘制逻辑，从 PaintMixin 拆分以降低单文件复杂度。"""

    def draw_style_panel(self, painter: QPainter) -> None:
        self.update_style_panel_layout()
        if self.style_panel_rect.isNull():
            return

        self.draw_floating_bubble(
            painter,
            self.style_panel_rect,
            "",
            radius=10,
            bg=overlay_panel_bg(),
            border=overlay_panel_border(),
            shadow_layers=((7, 10), (3, 18), (1, 28)),
        )

        self._ensure_paint_cache()

        painter.save()

        # 在组合 style panel 中加轻量分组分隔线（纯视觉，不参与命中）
        if self.style_panel_kind == "style":
            painter.setPen(self._pen_panel_divider)
            color_row_bottom = min((rect.bottom() for option_id, rect in self.style_option_rects.items() if option_id.startswith("color:")), default=0)
            width_row_bottom = min((rect.bottom() for option_id, rect in self.style_option_rects.items() if option_id.startswith("width:")), default=0)
            if color_row_bottom:
                y = color_row_bottom + self.STYLE_ROW_GAP // 2
                painter.drawLine(self.style_panel_rect.left() + 10, y, self.style_panel_rect.right() - 10, y)
            if width_row_bottom and any(option_id.startswith("preset:") for option_id in self.style_option_rects):
                y = width_row_bottom + self.STYLE_ROW_GAP // 2
                painter.drawLine(self.style_panel_rect.left() + 10, y, self.style_panel_rect.right() - 10, y)

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
                painter.drawRoundedRect(QRectF(rect), 7, 7)
                sample_y = rect.center().y()
                self._pen_width_sample.setWidthF(max(1.8, min(5.0, width_value / 1.6)))
                painter.setPen(self._pen_width_sample)
                painter.drawLine(rect.left() + 7, sample_y, rect.right() - 7, sample_y)
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
                selected = (
                    str(preset.get("color", "#ff4646")) == self.stroke_color_name
                    and int(preset.get("width", 5)) == int(self.stroke_width)
                )
                bg = self._sp_selected_bg if selected else self._sp_preset_hover_bg if hovered else self._sp_preset_bg
                border = self._sp_selected_border if selected else self._sp_preset_hover_border if hovered else self._sp_preset_border
                painter.setPen(QPen(border, 1))
                painter.setBrush(bg)
                painter.drawRoundedRect(QRectF(rect), 7, 7)
                # 颜色小圆点
                color_dot = QRect(rect.left() + 7, rect.center().y() - 4, 8, 8)
                painter.setPen(Qt.PenStyle.NoPen)
                painter.setBrush(QColor(preset.get("color", "#ff4646")))
                painter.drawEllipse(color_dot)
                # 名称
                painter.setPen(self._sp_preset_text if not selected else qc("accent.base"))
                font = painter.font()
                font.setPixelSize(10)
                font.setBold(selected)
                painter.setFont(font)
                name = preset.get("name", "")
                painter.drawText(rect.adjusted(18, 0, -4, 0), Qt.AlignmentFlag.AlignVCenter, name[:6])
        painter.restore()
