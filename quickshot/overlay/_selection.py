"""SelectionMixin — 选区管理：编辑模式、调整、重建缓存。"""

from __future__ import annotations

from PyQt6.QtCore import QPoint, QRect, Qt
from PyQt6.QtGui import QPainter, QPixmap

from . import annotation_painter
from ..utils import copy_pixmap_to_clipboard


class SelectionMixin:

    # ── 编辑模式 ──

    def enter_edit_mode(self, logical_rect: QRect, physical_rect: QRect) -> None:
        logical_rect = logical_rect.intersected(self.rect())
        physical_rect = physical_rect.intersected(QRect(0, 0, self.raw_pixmap.width(), self.raw_pixmap.height()))
        if logical_rect.width() < 8 or logical_rect.height() < 8 or physical_rect.width() < 8 or physical_rect.height() < 8:
            self.close()
            return

        self.mode = "edit"
        self.selecting = False
        self.selection_rect = QRect(logical_rect)
        self.selection_physical_rect = QRect(physical_rect)
        # 保存最近选区用于复用
        self.__class__._last_selection_rect = QRect(logical_rect)
        self.__class__._last_selection_physical_rect = QRect(physical_rect)
        self.base_edit_pixmap = self.raw_pixmap.copy(self.selection_physical_rect)
        self.base_edit_pixmap.setDevicePixelRatio(1.0)
        self.edit_pixmap = self.base_edit_pixmap.copy()
        self.edit_pixmap.setDevicePixelRatio(1.0)
        self.history.clear()
        self.annotations.clear()
        self.active_tool = "none"
        self.dragging_annotation = False
        self.drag_start = None
        self.drag_end = None
        self.drag_path = []
        self._reset_text_state()
        self.number_counter = 1
        self.setCursor(Qt.CursorShape.ArrowCursor)
        self._edit_entered_at = __import__("time").monotonic()
        self.rebuild_edit_pixmap()

        if self.config.auto_copy:
            copy_pixmap_to_clipboard(self.edit_pixmap)
            self.message = f"已复制到剪贴板：{self.edit_pixmap.width()} × {self.edit_pixmap.height()}；框内可拖动，边缘可拉伸"
        else:
            self.message = f"已选择区域：{self.edit_pixmap.width()} × {self.edit_pixmap.height()}；框内可拖动，边缘可拉伸"
        self.update_toolbar_layout()
        self.update()

        # 自动 OCR 模式
        if getattr(self, 'auto_ocr', False):
            self.auto_ocr = False
            from PyQt6.QtCore import QTimer
            QTimer.singleShot(200, self.recognize_current_text)

    def update_selection_display_cache(self) -> None:
        if self.selection_rect.isNull():
            self.selection_display_pixmap = QPixmap()
            return

        rect = self.selection_rect.intersected(self.rect())
        if rect.width() <= 0 or rect.height() <= 0:
            self.selection_display_pixmap = QPixmap()
            return

        if self.adjusting_selection and not self.adjust_preview_pixmap.isNull():
            pm = self.adjust_preview_pixmap
            if pm.width() != self.edit_pixmap.width() or pm.height() != self.edit_pixmap.height():
                pm = self.edit_pixmap.copy()
            if self.adjust_mode == "resize":
                target_w = max(1, int(round(rect.width() * self.scale_x)))
                target_h = max(1, int(round(rect.height() * self.scale_y)))
                if target_w > 0 and target_h > 0:
                    pm = pm.scaled(
                        target_w, target_h,
                        Qt.AspectRatioMode.IgnoreAspectRatio,
                        Qt.TransformationMode.FastTransformation,
                    )
            else:
                pm = pm.copy()

            dpr_x = pm.width() / max(1, rect.width())
            dpr_y = pm.height() / max(1, rect.height())
            if abs(dpr_x - dpr_y) <= 0.03 and dpr_x > 0:
                pm.setDevicePixelRatio(dpr_x)
            else:
                pm.setDevicePixelRatio(max(0.1, (dpr_x + dpr_y) / 2.0))
            self.selection_display_pixmap = pm
            return

        # 编辑模式下使用 edit_pixmap（含标注、阴影、水印、历史图片等修改）
        if self.mode == "edit" and not self.edit_pixmap.isNull():
            # QPixmap.copy() 利用隐式共享（COW），仅增加引用计数，不复制像素
            pm = self.edit_pixmap.copy()
            dpr_x = pm.width() / max(1, rect.width())
            dpr_y = pm.height() / max(1, rect.height())
            if abs(dpr_x - dpr_y) <= 0.03 and dpr_x > 0:
                pm.setDevicePixelRatio(dpr_x)
            else:
                pm.setDevicePixelRatio(max(0.1, (dpr_x + dpr_y) / 2.0))
            self.selection_display_pixmap = pm
            return

        # 选择模式下从 raw_pixmap 裁剪显示
        physical_rect = self.logical_to_physical_rect(rect)
        if physical_rect.width() <= 0 or physical_rect.height() <= 0:
            self.selection_display_pixmap = QPixmap()
            return

        if not self.raw_pixmap.isNull():
            pm = self.raw_pixmap.copy(physical_rect)
            dpr_x = physical_rect.width() / max(1, rect.width())
            dpr_y = physical_rect.height() / max(1, rect.height())
            if abs(dpr_x - dpr_y) <= 0.03 and dpr_x > 0:
                pm.setDevicePixelRatio(dpr_x)
            else:
                pm.setDevicePixelRatio(max(0.1, (dpr_x + dpr_y) / 2.0))
            self.selection_display_pixmap = pm
            return

        if not self.edit_pixmap.isNull():
            self.selection_display_pixmap = self.edit_pixmap.scaled(
                rect.size(),
                Qt.AspectRatioMode.IgnoreAspectRatio,
                Qt.TransformationMode.FastTransformation,
            )
            self.selection_display_pixmap.setDevicePixelRatio(1.0)
        else:
            self.selection_display_pixmap = QPixmap()

    # ── 选区调整 ──

    def begin_selection_adjust(self, handle: str, pos: QPoint) -> None:
        ui_dirty = self.edit_repaint_rect()
        self.adjusting_selection = True
        self.adjust_mode = "move" if handle == "move" else "resize"
        self.adjust_handle = handle
        self.adjust_start = QPoint(pos)
        self.adjust_origin_rect = QRect(self.selection_rect)
        self.adjust_preview_pixmap = self.edit_pixmap.copy() if not self.edit_pixmap.isNull() else QPixmap()
        self.adjust_cleared_annotations = False
        self.adjust_changed = False
        self.setCursor(self.cursor_for_handle(handle))
        if not ui_dirty.isNull():
            self.update(ui_dirty.adjusted(-24, -24, 24, 24).intersected(self.rect()))

    def recapture_current_selection(self) -> bool:
        physical_rect = self.logical_to_physical_rect(self.selection_rect)
        if physical_rect.width() < 8 or physical_rect.height() < 8:
            return False
        self.selection_physical_rect = physical_rect
        self.base_edit_pixmap = self.raw_pixmap.copy(self.selection_physical_rect)
        self.base_edit_pixmap.setDevicePixelRatio(1.0)
        self.rebuild_edit_pixmap()
        return True

    def move_rect_within_screen(self, rect: QRect) -> QRect:
        moved = QRect(rect)
        bounds = self.rect()
        if moved.left() < bounds.left():
            moved.moveLeft(bounds.left())
        if moved.top() < bounds.top():
            moved.moveTop(bounds.top())
        if moved.right() > bounds.right():
            moved.moveRight(bounds.right())
        if moved.bottom() > bounds.bottom():
            moved.moveBottom(bounds.bottom())
        return moved

    def rebuild_edit_pixmap(self) -> None:
        if self.base_edit_pixmap.isNull():
            self.edit_pixmap = QPixmap()
            self.selection_display_pixmap = QPixmap()
            return

        pixmap = self.base_edit_pixmap.copy()
        pixmap.setDevicePixelRatio(1.0)
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        for item in self.annotations:
            annotation_painter.paint_annotation_on_pixmap(painter, item)
        painter.end()
        self.edit_pixmap = pixmap
        self.edit_pixmap.setDevicePixelRatio(1.0)
        self.update_selection_display_cache()

    def resized_rect_from_handle(self, handle: str, pos: QPoint) -> QRect:
        origin = QRect(self.adjust_origin_rect)
        bounds = self.rect()
        min_w = 28
        min_h = 28
        l, t, r, b = origin.left(), origin.top(), origin.right(), origin.bottom()
        x = max(bounds.left(), min(bounds.right(), pos.x()))
        y = max(bounds.top(), min(bounds.bottom(), pos.y()))

        if "l" in handle:
            l = min(x, r - min_w)
            l = max(bounds.left(), l)
        if "r" in handle:
            r = max(x, l + min_w)
            r = min(bounds.right(), r)
        if "t" in handle:
            t = min(y, b - min_h)
            t = max(bounds.top(), t)
        if "b" in handle:
            b = max(y, t + min_h)
            b = min(bounds.bottom(), b)

        if r - l < min_w:
            if "l" in handle:
                l = max(bounds.left(), r - min_w)
            else:
                r = min(bounds.right(), l + min_w)
        if b - t < min_h:
            if "t" in handle:
                t = max(bounds.top(), b - min_h)
            else:
                b = min(bounds.bottom(), t + min_h)
        return QRect(QPoint(l, t), QPoint(r, b)).normalized().intersected(bounds)

    def update_selection_adjust(self, pos: QPoint) -> None:
        if not self.adjusting_selection or self.adjust_origin_rect.isNull():
            return
        if self.adjust_mode == "move":
            delta = pos - self.adjust_start
            new_rect = QRect(self.adjust_origin_rect)
            new_rect.translate(delta)
            new_rect = self.move_rect_within_screen(new_rect)
        else:
            new_rect = self.resized_rect_from_handle(self.adjust_handle, pos)

        if new_rect.width() < 8 or new_rect.height() < 8:
            return
        if new_rect == self.selection_rect:
            return

        dirty = self.edit_repaint_rect()
        if not self.adjust_changed and (self.annotations or self.history):
            self.history.clear()
            self.annotations.clear()
            self.adjust_cleared_annotations = True
        self.adjust_changed = True
        self.selection_rect = QRect(new_rect)

        dirty = dirty.united(self.edit_repaint_rect()).adjusted(-12, -12, 12, 12).intersected(self.rect())
        if dirty.isNull():
            self.update()
        else:
            self.update(dirty)

    def finish_selection_adjust(self) -> None:
        self.adjusting_selection = False
        changed = self.adjust_changed
        self.adjust_mode = ""
        self.adjust_handle = ""
        self.adjust_start = QPoint()
        self.adjust_origin_rect = QRect()
        self.adjust_preview_pixmap = QPixmap()
        self.adjust_changed = False
        if not changed:
            self.update()
            return

        if not self.recapture_current_selection() or self.edit_pixmap.isNull():
            self.update()
            return

        if self.adjust_cleared_annotations:
            self.message = f"已调整选区：{self.edit_pixmap.width()} × {self.edit_pixmap.height()}；原标注已清空"
        else:
            self.message = f"已调整选区：{self.edit_pixmap.width()} × {self.edit_pixmap.height()}"
        if self.config.auto_copy:
            copy_pixmap_to_clipboard(self.edit_pixmap)
        self.update_toolbar_layout()
        self.update()

    # ── 工具栏按钮定位 ──

    def update_drag_button_layout(self) -> None:
        self.drag_button_rect = QRect()
        if self.selection_rect.isNull():
            return
        w = 118
        h = 28
        x = self.selection_rect.center().x() - w // 2
        y = self.selection_rect.top() - h - 10
        if y < 10:
            y = self.selection_rect.top() + 10
        x = max(10, min(self.width() - w - 10, x))
        self.drag_button_rect = QRect(x, y, w, h)

    def drag_button_at(self, pos: QPoint) -> bool:
        self.update_drag_button_layout()
        return not self.drag_button_rect.isNull() and self.drag_button_rect.contains(pos)

    # ── 选区把手碰撞检测 ──

    def selection_handle_at(self, pos: QPoint) -> str:
        if self.selection_rect.isNull() or not self.selection_rect.adjusted(-self.handle_margin, -self.handle_margin, self.handle_margin, self.handle_margin).contains(pos):
            return ""

        r = self.selection_rect
        m = self.handle_margin
        near_left = abs(pos.x() - r.left()) <= m
        near_right = abs(pos.x() - r.right()) <= m
        near_top = abs(pos.y() - r.top()) <= m
        near_bottom = abs(pos.y() - r.bottom()) <= m

        if near_left and near_top:
            return "tl"
        if near_right and near_top:
            return "tr"
        if near_left and near_bottom:
            return "bl"
        if near_right and near_bottom:
            return "br"
        if near_left and r.top() - m <= pos.y() <= r.bottom() + m:
            return "l"
        if near_right and r.top() - m <= pos.y() <= r.bottom() + m:
            return "r"
        if near_top and r.left() - m <= pos.x() <= r.right() + m:
            return "t"
        if near_bottom and r.left() - m <= pos.x() <= r.right() + m:
            return "b"
        if r.contains(pos):
            return "move"
        return ""

    @staticmethod
    def cursor_for_handle(handle: str):
        if handle in ("tl", "br"):
            return Qt.CursorShape.SizeFDiagCursor
        if handle in ("tr", "bl"):
            return Qt.CursorShape.SizeBDiagCursor
        if handle in ("l", "r"):
            return Qt.CursorShape.SizeHorCursor
        if handle in ("t", "b"):
            return Qt.CursorShape.SizeVerCursor
        if handle == "move":
            return Qt.CursorShape.SizeAllCursor
        return Qt.CursorShape.ArrowCursor
