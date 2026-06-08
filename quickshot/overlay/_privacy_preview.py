"""PrivacyPreviewMixin — smart privacy masking review before applying mosaic."""

from __future__ import annotations

from typing import Iterable, Tuple

from PyQt6.QtCore import QPoint, QPointF, QRect, QRectF, Qt
from PyQt6.QtGui import QColor, QPainter, QPen


class PrivacyPreviewMixin:
    """Temporary editable OCR privacy rectangles.

    Rectangles live in edit-image coordinates and are committed to real mosaic
    annotations only after the user confirms the preview.
    """

    PRIVACY_PREVIEW_MIN_SIZE = 4
    PRIVACY_PREVIEW_HANDLE_PX = 8

    def _init_privacy_preview_state(self) -> None:
        self.privacy_preview_rects: list[QRect] = []
        self.privacy_preview_selected_index = -1
        self._privacy_preview_dragging = False
        self._privacy_preview_drag_mode = ""
        self._privacy_preview_drag_handle = ""
        self._privacy_preview_drag_start = QPoint()
        self._privacy_preview_origin_rect = QRect()

    def privacy_preview_active(self) -> bool:
        return bool(getattr(self, "privacy_preview_rects", []))

    def _privacy_preview_bounds(self) -> QRect:
        if self.edit_pixmap.isNull():
            return QRect()
        return QRect(0, 0, self.edit_pixmap.width(), self.edit_pixmap.height())

    def _sanitize_privacy_rect(self, rect: QRect) -> QRect:
        bounds = self._privacy_preview_bounds()
        if bounds.isNull():
            return QRect()
        normalized = QRect(rect).normalized().intersected(bounds)
        if normalized.width() < self.PRIVACY_PREVIEW_MIN_SIZE or normalized.height() < self.PRIVACY_PREVIEW_MIN_SIZE:
            return QRect()
        return normalized

    def start_privacy_preview(self, rects: Iterable[Tuple[int, int, int, int]]) -> bool:
        candidates: list[QRect] = []
        for x, y, w, h in rects:
            rect = self._sanitize_privacy_rect(QRect(int(x), int(y), int(w), int(h)))
            if not rect.isNull():
                candidates.append(rect)
        if not candidates:
            self.cancel_privacy_preview(silent=True)
            return False

        self.privacy_preview_rects = candidates
        self.privacy_preview_selected_index = 0
        self._privacy_preview_dragging = False
        self._privacy_preview_drag_mode = ""
        self._privacy_preview_drag_handle = ""
        self.active_tool = "none"
        self.dragging_annotation = False
        self.drag_start = None
        self.drag_end = None
        self.drag_path = []
        self.close_style_panel()
        self.message = (
            f"已识别 {len(candidates)} 处疑似隐私信息；可拖动/拉伸框调整，"
            "Delete 删除，Enter 应用，Esc 取消"
        )
        self.update()
        return True

    def cancel_privacy_preview(self, silent: bool = False) -> None:
        if not hasattr(self, "privacy_preview_rects"):
            return
        had_preview = bool(self.privacy_preview_rects)
        self.privacy_preview_rects = []
        self.privacy_preview_selected_index = -1
        self._privacy_preview_dragging = False
        self._privacy_preview_drag_mode = ""
        self._privacy_preview_drag_handle = ""
        self._privacy_preview_drag_start = QPoint()
        self._privacy_preview_origin_rect = QRect()
        if had_preview and not silent:
            self.message = "已取消智能打码预览"
            self.update()

    def apply_privacy_preview(self) -> None:
        rects = [QRect(rect) for rect in getattr(self, "privacy_preview_rects", []) if not rect.isNull()]
        if not rects:
            self.cancel_privacy_preview(silent=True)
            self.message = "没有可应用的智能打码区域"
            self.update()
            return

        self.push_history()
        applied = 0
        for rect in rects:
            before = len(self.annotations)
            self.apply_mosaic(QRect(rect))
            if len(self.annotations) > before:
                applied += 1

        self.cancel_privacy_preview(silent=True)
        self.message = f"已对 {applied} 处隐私信息打码" if applied else "没有可应用的智能打码区域"
        self.update()

    def delete_selected_privacy_preview_rect(self) -> None:
        rects = getattr(self, "privacy_preview_rects", [])
        index = int(getattr(self, "privacy_preview_selected_index", -1))
        if not rects or not (0 <= index < len(rects)):
            self.message = "没有选中的智能打码区域"
            self.update()
            return
        rects.pop(index)
        if rects:
            self.privacy_preview_selected_index = min(index, len(rects) - 1)
            self.message = f"已删除候选区域，剩余 {len(rects)} 处；Enter 应用"
        else:
            self.cancel_privacy_preview(silent=True)
            self.message = "已删除全部候选区域"
        self.update()

    def _privacy_preview_rect_to_widget(self, rect: QRect) -> QRectF:
        top_left = self.image_to_widget(rect.topLeft())
        bottom_right = self.image_to_widget(QPoint(rect.right() + 1, rect.bottom() + 1))
        return QRectF(top_left, bottom_right).normalized()

    def _privacy_preview_hit_test(self, pos: QPoint) -> tuple[int, str]:
        rects = getattr(self, "privacy_preview_rects", [])
        if not rects:
            return -1, ""
        order = list(range(len(rects)))
        selected = int(getattr(self, "privacy_preview_selected_index", -1))
        if 0 <= selected < len(rects):
            order.remove(selected)
            order.append(selected)

        handle = self.PRIVACY_PREVIEW_HANDLE_PX
        point = QPointF(pos)
        for index in reversed(order):
            widget_rect = self._privacy_preview_rect_to_widget(rects[index])
            if widget_rect.width() <= 0 or widget_rect.height() <= 0:
                continue
            cx = widget_rect.center().x()
            cy = widget_rect.center().y()
            handle_rects = (
                ("tl", QRectF(widget_rect.left() - handle, widget_rect.top() - handle, handle * 2, handle * 2)),
                ("tr", QRectF(widget_rect.right() - handle, widget_rect.top() - handle, handle * 2, handle * 2)),
                ("bl", QRectF(widget_rect.left() - handle, widget_rect.bottom() - handle, handle * 2, handle * 2)),
                ("br", QRectF(widget_rect.right() - handle, widget_rect.bottom() - handle, handle * 2, handle * 2)),
                ("l", QRectF(widget_rect.left() - handle, cy - handle, handle * 2, handle * 2)),
                ("r", QRectF(widget_rect.right() - handle, cy - handle, handle * 2, handle * 2)),
                ("t", QRectF(cx - handle, widget_rect.top() - handle, handle * 2, handle * 2)),
                ("b", QRectF(cx - handle, widget_rect.bottom() - handle, handle * 2, handle * 2)),
            )
            for name, handle_rect in handle_rects:
                if handle_rect.contains(point):
                    return index, name
            if widget_rect.adjusted(-4, -4, 4, 4).contains(point):
                return index, "move"
        return -1, ""

    def _privacy_preview_cursor_for_handle(self, handle: str):
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

    def _move_privacy_preview_rect(self, rect: QRect, delta: QPoint) -> QRect:
        bounds = self._privacy_preview_bounds()
        if bounds.isNull():
            return QRect(rect)
        x = max(bounds.left(), min(bounds.right() - rect.width() + 1, rect.x() + delta.x()))
        y = max(bounds.top(), min(bounds.bottom() - rect.height() + 1, rect.y() + delta.y()))
        moved = QRect(rect)
        moved.moveTo(x, y)
        return moved

    def _resize_privacy_preview_rect(self, rect: QRect, handle: str, delta: QPoint) -> QRect:
        bounds = self._privacy_preview_bounds()
        if bounds.isNull():
            return QRect(rect)
        min_size = self.PRIVACY_PREVIEW_MIN_SIZE
        left = rect.left()
        top = rect.top()
        right = rect.right() + 1
        bottom = rect.bottom() + 1

        if "l" in handle:
            left = max(bounds.left(), min(right - min_size, left + delta.x()))
        if "r" in handle:
            right = min(bounds.right() + 1, max(left + min_size, right + delta.x()))
        if "t" in handle:
            top = max(bounds.top(), min(bottom - min_size, top + delta.y()))
        if "b" in handle:
            bottom = min(bounds.bottom() + 1, max(top + min_size, bottom + delta.y()))
        return QRect(left, top, right - left, bottom - top)

    def begin_privacy_preview_drag(self, pos: QPoint) -> bool:
        index, handle = self._privacy_preview_hit_test(pos)
        if index < 0:
            self.message = "点击候选框可选择；Enter 应用，Esc 取消"
            self.update()
            return True
        image_pos = self.widget_to_image(pos, clamped=True)
        if image_pos is None:
            return True
        self.privacy_preview_selected_index = index
        self._privacy_preview_dragging = True
        self._privacy_preview_drag_mode = "move" if handle == "move" else "resize"
        self._privacy_preview_drag_handle = handle
        self._privacy_preview_drag_start = QPoint(image_pos)
        self._privacy_preview_origin_rect = QRect(self.privacy_preview_rects[index])
        self.setCursor(self._privacy_preview_cursor_for_handle(handle))
        self.update()
        return True

    def update_privacy_preview_drag(self, pos: QPoint) -> bool:
        if not self.privacy_preview_active():
            return False
        if self._privacy_preview_dragging:
            image_pos = self.widget_to_image(pos, clamped=True)
            if image_pos is None:
                return True
            index = int(getattr(self, "privacy_preview_selected_index", -1))
            if 0 <= index < len(self.privacy_preview_rects):
                delta = image_pos - self._privacy_preview_drag_start
                if self._privacy_preview_drag_mode == "move":
                    rect = self._move_privacy_preview_rect(self._privacy_preview_origin_rect, delta)
                else:
                    rect = self._resize_privacy_preview_rect(
                        self._privacy_preview_origin_rect,
                        self._privacy_preview_drag_handle,
                        delta,
                    )
                self.privacy_preview_rects[index] = rect
                self.update()
            return True

        hover = self.button_at(pos)
        if hover != getattr(self, "hover_button", ""):
            self.hover_button = hover
            self.hover_style_option = ""
            self.hover_drag_button = False
            self.update()
        index, handle = self._privacy_preview_hit_test(pos)
        cursor = Qt.CursorShape.PointingHandCursor if hover else self._privacy_preview_cursor_for_handle(handle)
        if cursor != self._last_cursor_shape:
            self._last_cursor_shape = cursor
            self.setCursor(cursor)
        if index >= 0 and index != self.privacy_preview_selected_index:
            self.privacy_preview_selected_index = index
            self.update()
        return True

    def finish_privacy_preview_drag(self, pos: QPoint) -> bool:
        if not self._privacy_preview_dragging:
            return False
        self.update_privacy_preview_drag(pos)
        self._privacy_preview_dragging = False
        self._privacy_preview_drag_mode = ""
        self._privacy_preview_drag_handle = ""
        self.message = "已调整候选区域；Enter 应用，Esc 取消"
        self.update()
        return True

    def nudge_selected_privacy_preview_rect(self, key, modifiers) -> bool:
        rects = getattr(self, "privacy_preview_rects", [])
        index = int(getattr(self, "privacy_preview_selected_index", -1))
        if not rects or not (0 <= index < len(rects)):
            return False
        step = 10 if modifiers & Qt.KeyboardModifier.ShiftModifier else 1
        dx = dy = 0
        if key == Qt.Key.Key_Left:
            dx = -step
        elif key == Qt.Key.Key_Right:
            dx = step
        elif key == Qt.Key.Key_Up:
            dy = -step
        elif key == Qt.Key.Key_Down:
            dy = step
        else:
            return False
        rects[index] = self._move_privacy_preview_rect(rects[index], QPoint(dx, dy))
        self.message = f"已微调候选区域 ({dx:+d}, {dy:+d})；Enter 应用"
        self.update()
        return True

    def handle_privacy_preview_key(self, key, modifiers) -> bool:
        ctrl = bool(modifiers & Qt.KeyboardModifier.ControlModifier)
        if key in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            self.apply_privacy_preview()
            return True
        if key in (Qt.Key.Key_Delete, Qt.Key.Key_Backspace):
            self.delete_selected_privacy_preview_rect()
            return True
        if key in (Qt.Key.Key_Left, Qt.Key.Key_Right, Qt.Key.Key_Up, Qt.Key.Key_Down):
            return self.nudge_selected_privacy_preview_rect(key, modifiers)
        if ctrl and key in (Qt.Key.Key_C, Qt.Key.Key_S):
            self.message = "请先按 Enter 应用智能打码，或按 Esc 取消预览"
            self.update()
            return True
        self.message = "智能打码预览中：Enter 应用，Delete 删除，Esc 取消"
        self.update()
        return True

    def draw_privacy_preview(self, painter: QPainter) -> None:
        rects = getattr(self, "privacy_preview_rects", [])
        if self.selection_rect.isNull() or not rects:
            return
        painter.save()
        painter.setClipRect(self.selection_rect)
        selected = int(getattr(self, "privacy_preview_selected_index", -1))
        for index, rect in enumerate(rects):
            widget_rect = self._privacy_preview_rect_to_widget(rect)
            if widget_rect.width() <= 0 or widget_rect.height() <= 0:
                continue
            is_selected = index == selected
            border = QColor(14, 165, 233, 235) if is_selected else QColor(251, 191, 36, 220)
            fill = QColor(14, 165, 233, 42) if is_selected else QColor(251, 191, 36, 34)
            painter.setPen(QPen(border, 2.0 if is_selected else 1.5, Qt.PenStyle.DashLine))
            painter.setBrush(fill)
            painter.drawRoundedRect(widget_rect, 4, 4)

            if is_selected:
                painter.setPen(Qt.PenStyle.NoPen)
                painter.setBrush(QColor(255, 255, 255, 235))
                handle = self.PRIVACY_PREVIEW_HANDLE_PX - 2
                points = (
                    widget_rect.topLeft(),
                    widget_rect.topRight(),
                    widget_rect.bottomLeft(),
                    widget_rect.bottomRight(),
                    QPoint(int(widget_rect.center().x()), int(widget_rect.top())),
                    QPoint(int(widget_rect.center().x()), int(widget_rect.bottom())),
                    QPoint(int(widget_rect.left()), int(widget_rect.center().y())),
                    QPoint(int(widget_rect.right()), int(widget_rect.center().y())),
                )
                painter.setPen(QPen(border, 1.3))
                for point in points:
                    painter.drawRect(QRectF(point.x() - handle / 2, point.y() - handle / 2, handle, handle))
        painter.restore()
