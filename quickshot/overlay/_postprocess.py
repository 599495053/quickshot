"""PostProcessMixin — 后处理变换：阴影、边框、水印。"""

from __future__ import annotations

import datetime

from PyQt6.QtGui import QColor, QFont, QFontMetrics, QPainter, QPixmap

from ..theme import qcolor_from_rgba_hex


class PostProcessMixin:

    def apply_shadow(self) -> None:
        if self.edit_pixmap.isNull():
            return
        self.push_history()
        offset = 8
        shadow_alpha = 100
        old_w = self.edit_pixmap.width()
        old_h = self.edit_pixmap.height()
        new_w = old_w + offset
        new_h = old_h + offset
        result = QPixmap(new_w, new_h)
        result.fill(QColor(0, 0, 0, 0))
        painter = QPainter(result)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.fillRect(offset, offset, old_w, old_h, QColor(0, 0, 0, shadow_alpha))
        painter.drawPixmap(0, 0, self.edit_pixmap)
        painter.end()
        self._extend_selection_rect(old_w, old_h, 0, 0, offset, offset)
        self.edit_pixmap = result
        self.edit_pixmap.setDevicePixelRatio(1.0)
        self.selection_snapshot_required = True
        self.update_selection_display_cache()
        self.message = "已添加阴影效果"
        self.update()

    def apply_border(self) -> None:
        if self.edit_pixmap.isNull():
            return
        self.push_history()
        thickness = max(2, int(self.stroke_width))
        border_color = QColor(self.stroke_color_name)
        if not border_color.isValid():
            border_color = QColor(0, 0, 0)
        old_w = self.edit_pixmap.width()
        old_h = self.edit_pixmap.height()
        new_w = old_w + thickness * 2
        new_h = old_h + thickness * 2
        result = QPixmap(new_w, new_h)
        result.fill(border_color)
        painter = QPainter(result)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.drawPixmap(thickness, thickness, self.edit_pixmap)
        painter.end()
        self._extend_selection_rect(old_w, old_h, thickness, thickness, thickness, thickness)
        self.edit_pixmap = result
        self.edit_pixmap.setDevicePixelRatio(1.0)
        self.selection_snapshot_required = True
        self.update_selection_display_cache()
        self.message = f"已添加 {thickness}px 边框"
        self.update()

    def _extend_selection_rect(self, old_pm_w: int, old_pm_h: int,
                                left_dev: int, top_dev: int,
                                right_dev: int, bottom_dev: int) -> None:
        """按当前 pixmap→selection_rect 的设备/逻辑像素比，等比扩展 selection_rect。"""
        if self.selection_rect.isNull() or old_pm_w <= 0 or old_pm_h <= 0:
            return
        rect_w = self.selection_rect.width()
        rect_h = self.selection_rect.height()
        if rect_w <= 0 or rect_h <= 0:
            return
        scale_x = rect_w / old_pm_w
        scale_y = rect_h / old_pm_h
        left = int(round(left_dev * scale_x)) if left_dev else 0
        top = int(round(top_dev * scale_y)) if top_dev else 0
        right = int(round(right_dev * scale_x)) if right_dev else 0
        bottom = int(round(bottom_dev * scale_y)) if bottom_dev else 0
        if left_dev > 0:
            left = max(1, left)
        if top_dev > 0:
            top = max(1, top)
        if right_dev > 0:
            right = max(1, right)
        if bottom_dev > 0:
            bottom = max(1, bottom)
        self.selection_rect = self.selection_rect.adjusted(-left, -top, right, bottom)

    def apply_watermark(self) -> None:
        if self.edit_pixmap.isNull():
            return
        self.push_history()
        text = getattr(self.config, "watermark_text", "") or ""
        if not text:
            text = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
        pixmap = self.edit_pixmap.copy()
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        font = QFont("Microsoft YaHei", 14, QFont.Weight.DemiBold)
        painter.setFont(font)
        watermark_color = qcolor_from_rgba_hex(getattr(self.config, "watermark_color", "#ffffff40"))
        painter.setPen(watermark_color)
        painter.translate(pixmap.width() / 2, pixmap.height() / 2)
        painter.rotate(-45)
        fm = QFontMetrics(font)
        text_w = fm.horizontalAdvance(text) + 80
        text_h = fm.height() + 60
        for y in range(-pixmap.height(), pixmap.height() * 2, text_h):
            for x in range(-pixmap.width(), pixmap.width() * 2, text_w):
                painter.drawText(x, y, text)
        painter.end()
        self.edit_pixmap = pixmap
        self.edit_pixmap.setDevicePixelRatio(1.0)
        self.selection_snapshot_required = True
        self.update_selection_display_cache()
        self.message = "已添加水印"
        self.update()
