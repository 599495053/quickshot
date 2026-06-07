"""ToolbarPaintMixin — 工具栏渲染：按钮背景、图标、分组、提示气泡。"""

from __future__ import annotations

from PyQt6.QtCore import QPoint, QRect, QRectF, Qt
from PyQt6.QtGui import QColor, QPainter, QPen

from ..theme import (
    qc,
    overlay_toolbar_bg,
    overlay_toolbar_border,
    overlay_tip_bg,
    overlay_tip_border,
    overlay_tip_text,
)


class ToolbarPaintMixin:
    """工具栏绘制逻辑，从 PaintMixin 拆分以降低单文件复杂度。"""

    def draw_toolbar(self, painter: QPainter) -> None:
        self._update_toolbar_layout_if_needed()
        self.update_style_panel_layout()
        if self.toolbar_rect.isNull():
            return

        painter.save()

        panel = QRectF(self.toolbar_rect)

        for offset, alpha in ((7, 8), (3, 14), (1, 22)):
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QColor(15, 23, 42, alpha))
            painter.drawRoundedRect(panel.adjusted(-offset, -offset, offset, offset), 11 + offset, 11 + offset)

        painter.setBrush(overlay_toolbar_bg())
        painter.setPen(QPen(overlay_toolbar_border(), 1))
        painter.drawRoundedRect(panel, 11, 11)

        self._ensure_paint_cache()
        items = self.toolbar_items()  # 缓存为局部变量，下面 3 处复用

        # 轻分组底色：让信息密度高的单行 toolbar 更有层次，但不改变 hit rect
        groups = []
        current_group = []
        for key, _label, _icon, _tip in items:
            if key == 'sep':
                if current_group:
                    groups.append(current_group)
                current_group = []
                continue
            rect = self.toolbar_buttons.get(key)
            if rect is not None:
                current_group.append((key, rect))
        if current_group:
            groups.append(current_group)
        for group in groups:
            left = group[0][1].left() - 3
            right = group[-1][1].right() + 3
            top = self.toolbar_rect.top() + 4
            bottom = self.toolbar_rect.bottom() - 4
            group_rect = QRectF(left, top, right - left + 1, bottom - top + 1)
            is_cta_group = any(k in ("cancel", "done") for k, _ in group)
            painter.setPen(QPen(self._tb_cta_group_border if is_cta_group else self._tb_group_border, 1))
            painter.setBrush(self._tb_cta_group_bg if is_cta_group else self._tb_group_bg)
            painter.drawRoundedRect(group_rect, 9, 9)

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
                painter.drawLine(QPoint(sx, self.toolbar_rect.top() + 10), QPoint(sx, self.toolbar_rect.bottom() - 10))

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

            rr = QRectF(rect).adjusted(2.0, 2.0, -2.0, -2.0)
            icon_rect = QRect(rect.left() + 8, rect.top() + 8, rect.width() - 16, rect.height() - 16)
            if primary:
                icon_rect.adjust(1, 1, -1, -1)

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
                painter.drawRoundedRect(rr, 8.5, 8.5)
            elif hovered:
                painter.setPen(QPen(self._tb_hover_border, 1))
                painter.setBrush(self._tb_hover_fill)
                painter.drawRoundedRect(rr, 8.5, 8.5)

            if active or toggled:
                accent_rect = QRectF(rect.left() + 9, rect.bottom() - 4, rect.width() - 18, 3)
                painter.setPen(Qt.PenStyle.NoPen)
                painter.setBrush(self._tb_accent_bar)
                painter.drawRoundedRect(accent_rect, 1.5, 1.5)

            if primary:
                # done 做成更强主按钮感：双层卡片 + 白图标
                inner = QRectF(rr).adjusted(0.5, 0.5, -0.5, -0.5)
                painter.setPen(QPen(qc("accent.base", 55), 1))
                painter.setBrush(fill)
                painter.drawRoundedRect(inner, 8.5, 8.5)
                painter.setPen(QPen(qc("accent.base", 18), 1))
                painter.setBrush(Qt.BrushStyle.NoBrush)
                painter.drawRoundedRect(inner.adjusted(1.0, 1.0, -1.0, -1.0), 7.5, 7.5)
                icon_color = self._tb_icon_white
            elif danger:
                if fill.alpha() > 0:
                    painter.setPen(QPen(border, 1))
                    painter.setBrush(fill)
                    painter.drawRoundedRect(rr, 8.5, 8.5)
                icon_color = qc("danger.base")
            elif active or toggled:
                icon_color = self._tb_icon_active
            else:
                icon_color = self._tb_icon_hover if hovered else self._tb_icon_normal

            self.icons.draw(painter, key, icon_rect, icon_color)

        if self.hover_button:
            for key, _label, _icon, tip in items:
                if key == self.hover_button:
                    self.draw_toolbar_tip(painter, tip)
                    break

        painter.restore()

    def draw_toolbar_tip(self, painter: QPainter, text: str) -> None:
        if self.toolbar_rect.isNull() or not text or self.style_panel_kind:
            return
        self._ensure_paint_cache()
        font = self._font_tip
        metrics = self._fm_tip
        w = metrics.horizontalAdvance(text) + 22
        h = 28
        x = self.toolbar_rect.center().x() - w // 2
        y = self.toolbar_rect.top() - h - 10
        if y < 8:
            y = self.toolbar_rect.bottom() + 10
        x = max(8, min(self.width() - w - 8, x))
        r = QRect(x, y, w, h)
        self.draw_floating_bubble(
            painter,
            r,
            text,
            font=font,
            radius=9,
            bg=overlay_tip_bg(),
            border=overlay_tip_border(),
            text_color=overlay_tip_text(),
            shadow_layers=((5, 10), (2, 18)),
        )
