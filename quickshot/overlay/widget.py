"""FloatingSnipOverlay — 全屏截图层：先框选，之后在选区下方显示悬浮工具栏并直接编辑。"""

from __future__ import annotations

import traceback
from typing import Dict, List, Optional, Tuple

from PyQt6.QtCore import QEvent, QPoint, QPointF, QRect, QRectF, QSize, Qt, QTimer, pyqtSignal
from PyQt6.QtGui import QColor, QImage, QPainter, QPen, QPixmap
from PyQt6.QtWidgets import QWidget

from ..config import Config
from ..constants import DOUBLE_CLICK_GUARD_MS, HANDLE_MARGIN, TEXT_FONT_SIZE_DEFAULT
from ..history import CaptureHistoryStore
from ..ocr import OcrJob
from ..theme import (
    STROKE_DEFAULT,
    overlay_dim,
    qc,
)
from ..utils import APP_NAME, debug_log
from .coords import CoordinateSystem
from .icons import IconCache
from ._drawing import DrawingMixin
from ._events import EventMixin
from ._history import HistoryMixin
from ._ocr import OcrMixin
from ._paint import PaintMixin
from ._privacy_preview import PrivacyPreviewMixin
from ._selection import SelectionMixin
from ._snap import SnapMixin
from ._text_drag import TextDragState
from ._text_editor import TextEditorMixin
from ._toolbar import ToolbarMixin
from ._tool_strategies import TOOL_STRATEGIES


class FloatingSnipOverlay(
    TextEditorMixin,
    PrivacyPreviewMixin,
    EventMixin,
    SelectionMixin,
    DrawingMixin,
    ToolbarMixin,
    PaintMixin,
    OcrMixin,
    HistoryMixin,
    SnapMixin,
    QWidget,
):

    closed = pyqtSignal()
    notify = pyqtSignal(str)
    clipboard_text_requested = pyqtSignal(str)
    history_updated = pyqtSignal()
    TEXT_COLOR_OPTIONS = [
        ("#ffffff", "白"),
        ("#ff4d4f", "红"),
        ("#ffd43b", "黄"),
        ("#40c057", "绿"),
        ("#339af0", "蓝"),
        ("#212529", "黑"),
    ]

    # 双击防误触最小间隔（毫秒）
    DOUBLE_CLICK_GUARD_MS = DOUBLE_CLICK_GUARD_MS
    # 最近区域复用：类级别存储上次选区
    _last_selection_rect: Optional[QRect] = None
    _last_selection_physical_rect: Optional[QRect] = None

    def __init__(
        self,
        raw_pixmap: QPixmap,
        display_pixmap: QPixmap,
        logical_geometry: QRect,
        scale_x: float,
        scale_y: float,
        physical_left: int,
        physical_top: int,
        config: Config,
        history_store: Optional[CaptureHistoryStore] = None,
    ) -> None:
        super().__init__()
        self.raw_pixmap = raw_pixmap
        self.display_pixmap = display_pixmap
        self.logical_geometry = QRect(logical_geometry)
        self.scale_x = float(scale_x)
        self.scale_y = float(scale_y)
        self.physical_left = int(physical_left)
        self.physical_top = int(physical_top)
        self.coords = CoordinateSystem(self.scale_x, self.scale_y, self.physical_left, self.physical_top)
        self.config = config
        self.history_store = history_store
        self.history_item_id = ""

        self.mode = "select"
        self.start = QPoint()
        self.end = QPoint()
        self.selecting = False
        self.auto_ocr = False
        self._pending_frame_update_rect = QRect()
        self._pending_full_frame_update = False

        self.selection_rect = QRect()
        self.selection_physical_rect = QRect()
        self.base_edit_pixmap = QPixmap()
        self.edit_pixmap = QPixmap()
        self.selection_display_pixmap = QPixmap()
        self.selection_snapshot_required = False
        self.adjust_preview_pixmap = QPixmap()
        self.history: List[Tuple[QPixmap, List[Dict[str, object]], bool]] = []
        self.redo_stack: List[Tuple[QPixmap, List[Dict[str, object]], bool]] = []
        self.annotations: List[Dict[str, object]] = []
        self._init_privacy_preview_state()

        self.active_tool = "none"
        self.last_tool = "none"
        self.dragging_annotation = False
        self.drag_start: Optional[QPoint] = None
        self.drag_end: Optional[QPoint] = None
        self.drag_path: List[QPoint] = []

        # 吸附状态
        self._init_snap_state()
        self.text_drag = TextDragState()

        self.toolbar_rect = QRect()
        self.toolbar_buttons: Dict[str, QRect] = {}
        self._toolbar_layout_geometry: Optional[Tuple[int, int, int, int, int, int]] = None
        self.icons = IconCache()
        self.drag_button_rect = QRect()
        self.hover_drag_button = False
        self.hover_button = ""
        self.hover_style_option = ""
        self.last_message_rect = QRect()
        self.message = "拖动鼠标选择截图区域   Esc 取消"
        self.text_font_size = TEXT_FONT_SIZE_DEFAULT
        self.text_color_name = "#ffffff"
        self.text_panel_color_name = self.text_color_name
        self._text_metrics_cache: Dict[int, object] = {}
        self.text_anchor: Optional[QPoint] = None
        self.editing_text_index = -1
        self.stroke_color_name = STROKE_DEFAULT
        self.stroke_width = 5
        self.stroke_colors = [STROKE_DEFAULT, "#ff8c00", "#ffcc00", "#18a058", "#1488ff", "#9c27b0", "#00bcd4", "#ffffff", "#111827"]
        self.stroke_widths = [3, 5, 8, 12]
        self.fill_mode = "none"  # none / half / full
        self.grid_visible = False
        self.size_locked = False
        self.locked_size = QSize()
        self.style_panel_kind = ""
        self.style_panel_rect = QRect()
        self.style_option_rects: Dict[str, QRect] = {}

        self.adjusting_selection = False
        self.adjust_mode = ""
        self.adjust_handle = ""
        self.adjust_start = QPoint()
        self.adjust_origin_rect = QRect()
        self.adjust_cleared_annotations = False
        self.adjust_changed = False
        self.handle_margin = HANDLE_MARGIN
        self.ocr_job: Optional[OcrJob] = None
        self.number_counter = 1
        self.ocr_region_mode = False

        self._edit_entered_at = 0

        # QPixmap.toImage() 缓存：避免频繁转换导致性能瓶颈
        self._cached_edit_image: Optional[QImage] = None
        self._last_pixmap_id: int = 0

        self.setWindowTitle(APP_NAME)
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
        )
        self.setGeometry(self.logical_geometry)
        self.setMouseTracking(True)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setCursor(Qt.CursorShape.CrossCursor)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, False)

        self._frame_update_timer = QTimer(self)
        self._frame_update_timer.setSingleShot(True)
        self._frame_update_timer.setInterval(0)
        self._frame_update_timer.timeout.connect(self._flush_frame_update)
        self.clipboard_text_requested.connect(self._copy_text_to_clipboard)

        self._init_text_editor_panel()

    # ── 兼容属性（委托到 text_drag，供 _paint.py / _text_editor.py 等使用）──

    @property
    def hover_text_index(self) -> int:
        return self.text_drag.hover_index

    @hover_text_index.setter
    def hover_text_index(self, value: int) -> None:
        self.text_drag.hover_index = value

    @property
    def selected_text_index(self) -> int:
        return self.text_drag.selected_index

    @selected_text_index.setter
    def selected_text_index(self, value: int) -> None:
        self.text_drag.selected_index = value

    @property
    def dragging_text_index(self) -> int:
        return self.text_drag.dragging_index

    @dragging_text_index.setter
    def dragging_text_index(self, value: int) -> None:
        self.text_drag.dragging_index = value

    @property
    def dragging_text_origin(self) -> Optional[QPoint]:
        return self.text_drag.origin

    @dragging_text_origin.setter
    def dragging_text_origin(self, value: Optional[QPoint]) -> None:
        self.text_drag.origin = value

    @property
    def dragging_text_start(self) -> Optional[QPoint]:
        return self.text_drag.start

    @dragging_text_start.setter
    def dragging_text_start(self, value: Optional[QPoint]) -> None:
        self.text_drag.start = value

    @property
    def dragging_text_current(self) -> Optional[QPoint]:
        return self.text_drag.current

    @dragging_text_current.setter
    def dragging_text_current(self, value: Optional[QPoint]) -> None:
        self.text_drag.current = value

    # ── 生命周期事件 ──

    def showEvent(self, event) -> None:
        super().showEvent(event)
        self.raise_()
        self.activateWindow()
        if self.mode == "select":
            self.setCursor(Qt.CursorShape.CrossCursor)
        try:
            self.grabKeyboard()
        except Exception as exc:
            debug_log(f"grabKeyboard failed: {exc}")


    def closeEvent(self, event) -> None:
        self.detach_ocr_job()
        if hasattr(self, '_privacy_blur_job') and self._privacy_blur_job:
            self._privacy_blur_job.cleanup()
            self._privacy_blur_job = None
        try:
            self.releaseKeyboard()
        except Exception as exc:
            debug_log(f"releaseKeyboard failed: {exc}")
        self.closed.emit()
        super().closeEvent(event)

    def request_frame_update(self, rect: Optional[QRect] = None) -> None:
        """Coalesce high-frequency drag repaints into the next frame."""
        if rect is None or rect.isNull():
            self._pending_full_frame_update = True
            self._pending_frame_update_rect = QRect()
        elif not self._pending_full_frame_update:
            clipped = QRect(rect).intersected(self.rect())
            if not clipped.isNull():
                if self._pending_frame_update_rect.isNull():
                    self._pending_frame_update_rect = clipped
                else:
                    self._pending_frame_update_rect = self._pending_frame_update_rect.united(clipped)
        if not self._frame_update_timer.isActive():
            self._frame_update_timer.start()

    def _flush_frame_update(self) -> None:
        if self._pending_full_frame_update or self._pending_frame_update_rect.isNull():
            self.update()
        else:
            self.update(self._pending_frame_update_rect)
        self._pending_full_frame_update = False
        self._pending_frame_update_rect = QRect()

    def selection_frame_dirty_rect(
        self,
        old_rect: Optional[QRect],
        new_rect: Optional[QRect],
        padding: int = 72,
    ) -> QRect:
        """Dirty region for moving/resizing the selection and its full-width dim edges."""
        bounds = self.rect()
        dirty = QRect()
        strip = max(12, padding // 4)
        for source in (old_rect, new_rect):
            if source is None:
                continue
            rect = QRect(source).normalized().intersected(bounds)
            if rect.isNull() or rect.width() <= 0 or rect.height() <= 0:
                continue
            expanded = rect.adjusted(-padding, -padding, padding, padding).intersected(bounds)
            dirty = expanded if dirty.isNull() else dirty.united(expanded)

            # draw_dim_outside() changes full-width top/bottom bands when the
            # selection edge moves. Repaint those strips to avoid stale 1px lines.
            for y in (rect.top(), rect.bottom() + 1):
                band = QRect(bounds.left(), y - strip, bounds.width(), strip * 2 + 1).intersected(bounds)
                if not band.isNull():
                    dirty = band if dirty.isNull() else dirty.united(band)

            # Left/right dim bands only cover the selection height, but a taller
            # strip is cheap and prevents edge residue during fast diagonal moves.
            y_top = max(bounds.top(), rect.top() - padding)
            y_bottom = min(bounds.bottom(), rect.bottom() + padding)
            for x in (rect.left(), rect.right() + 1):
                band = QRect(x - strip, y_top, strip * 2 + 1, y_bottom - y_top + 1).intersected(bounds)
                if not band.isNull():
                    dirty = band if dirty.isNull() else dirty.united(band)
        return dirty.intersected(bounds)

    def eventFilter(self, watched, event) -> bool:
        editor = getattr(self, "text_editor", None)
        if watched is editor and event.type() == QEvent.Type.KeyPress:
            key = event.key()
            if key == Qt.Key.Key_Escape:
                self.cancel_inline_text()
                return True
            if key in (Qt.Key.Key_Return, Qt.Key.Key_Enter) and event.modifiers() & Qt.KeyboardModifier.ControlModifier:
                self.commit_inline_text()
                return True
        return super().eventFilter(watched, event)

    # ── 坐标委托 ──

    def clamp_point(self, point: QPoint) -> QPoint:
        return self.coords.clamp_point(point, self.rect())

    def current_select_rect(self) -> QRect:
        if self.start.isNull() and self.end.isNull():
            return QRect()
        rect = QRect(self.start, self.end).normalized().intersected(self.rect())
        if self.size_locked and not self.locked_size.isEmpty() and not rect.isNull():
            target_w = self.locked_size.width()
            target_h = self.locked_size.height()
            if self.start.x() <= self.end.x():
                new_x = self.start.x()
            else:
                new_x = self.start.x() - target_w
            if self.start.y() <= self.end.y():
                new_y = self.start.y()
            else:
                new_y = self.start.y() - target_h
            rect = QRect(new_x, new_y, target_w, target_h).intersected(self.rect())
        return rect

    def logical_to_physical_rect(self, rect: QRect) -> QRect:
        return self.coords.logical_to_physical_rect(rect, self.raw_pixmap.size())

    def physical_abs_to_logical_rect(self, abs_rect: Tuple[int, int, int, int]) -> Tuple[QRect, QRect]:
        return self.coords.physical_abs_to_logical_rect(abs_rect, self.raw_pixmap.size(), self.rect())

    def set_initial_capture_from_physical_abs(self, abs_rect: Tuple[int, int, int, int]) -> None:
        logical, physical = self.physical_abs_to_logical_rect(abs_rect)
        if logical.width() >= 8 and logical.height() >= 8 and physical.width() >= 8 and physical.height() >= 8:
            self.enter_edit_mode(logical, physical)

    def widget_to_image(self, pos: QPoint, clamped: bool = False) -> Optional[QPoint]:
        if self.edit_pixmap.isNull():
            return None
        return self.coords.widget_to_image(pos, self.selection_rect, self.edit_pixmap.size(), clamped=clamped)

    def image_to_widget(self, point: QPoint) -> QPointF:
        return self.coords.image_to_widget(point, self.selection_rect, self.edit_pixmap.size())

    def scaled_stroke_width(self, width: float) -> float:
        return self.coords.scaled_stroke_width(width, self.selection_rect, self.edit_pixmap.size())

    def annotation_points_to_widget(self, item: Dict[str, object]) -> List[QPointF]:
        return self.coords.annotation_points_to_widget(item, self.selection_rect, self.edit_pixmap.size())

    def _get_cached_edit_image(self) -> Optional[QImage]:
        """获取缓存的 QImage，避免频繁的 QPixmap.toImage() 转换。

        QPixmap.toImage() 是 O(n) 操作，对于高分辨率截图（如 4K）会拷贝数百 MB 数据。
        通过缓存 QImage 版本，可以将重复调用从 O(n) 降为 O(1)。

        Returns:
            QImage: 缓存的图像，如果 edit_pixmap 为空则返回 None
        """
        if self.edit_pixmap.isNull():
            self._cached_edit_image = None
            self._last_pixmap_id = 0
            return None

        current_id = self.edit_pixmap.cacheKey()
        if self._cached_edit_image is None or self._last_pixmap_id != current_id:
            # 缓存失效，重新转换
            self._cached_edit_image = self.edit_pixmap.toImage().convertToFormat(
                QImage.Format.Format_ARGB32
            )
            self._last_pixmap_id = current_id

        return self._cached_edit_image

    def invalidate_image_cache(self) -> None:
        """使图像缓存失效，在 edit_pixmap 变化后调用。"""
        self._cached_edit_image = None
        self._last_pixmap_id = 0

    # ── 事件薄壳委托 ──

    def mousePressEvent(self, event) -> None:
        try:
            self._handle_mouse_press(event)
        except Exception as exc:
            debug_log(f"mousePressEvent CRASH: {exc}\n{traceback.format_exc()}")

    def mouseMoveEvent(self, event) -> None:
        try:
            self._handle_mouse_move(event)
        except Exception as exc:
            debug_log(f"mouseMoveEvent CRASH: {exc}\n{traceback.format_exc()}")

    def mouseReleaseEvent(self, event) -> None:
        try:
            self._handle_mouse_release(event)
        except Exception as exc:
            debug_log(f"mouseReleaseEvent CRASH: {exc}\n{traceback.format_exc()}")

    def mouseDoubleClickEvent(self, event) -> None:
        try:
            self._handle_mouse_double_click(event)
        except Exception as exc:
            debug_log(f"mouseDoubleClickEvent CRASH: {exc}\n{traceback.format_exc()}")
        super().mouseDoubleClickEvent(event)

    def keyPressEvent(self, event) -> None:
        try:
            self._handle_key_press(event)
        except Exception as exc:
            debug_log(f"keyPressEvent CRASH: {exc}\n{traceback.format_exc()}")

    # ── paintEvent ──

    def paintEvent(self, event) -> None:
        try:
            painter = QPainter(self)
            painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
            self.clear_canvas(painter)
            self.draw_frozen_desktop(painter)

            if self.mode == "select":
                self.paint_select_mode(painter)
            else:
                self.paint_edit_mode(painter)
        except Exception as exc:
            debug_log(f"paintEvent CRASH: {exc}\n{traceback.format_exc()}")

    def paint_select_mode(self, painter: QPainter) -> None:
        rect = self.current_select_rect()
        if rect.isNull() or rect.width() <= 0 or rect.height() <= 0:
            painter.fillRect(self.rect(), overlay_dim())
            self.draw_center_hint(painter, "拖动鼠标选择截图区域   Esc 取消")
            return

        self.draw_dim_outside(painter, rect)
        self.draw_snap_guides(painter)
        self.draw_selection_border(painter, rect)
        self.draw_handles(painter, rect)

    def paint_edit_mode(self, painter: QPainter) -> None:
        if self.selection_rect.isNull() or self.edit_pixmap.isNull():
            painter.fillRect(self.rect(), overlay_dim())
            self.draw_center_hint(painter, "没有截图内容")
            return

        self.draw_dim_outside(painter, self.selection_rect)
        if not self.adjusting_selection:
            if self.selection_snapshot_required:
                self.draw_selection_snapshot(painter)
            self.draw_annotations_overlay(painter)
            self.draw_privacy_preview(painter)
        if self.grid_visible:
            self.draw_grid(painter)
        self.draw_selection_border(painter, self.selection_rect)
        self.draw_handles(painter, self.selection_rect)

        if self.dragging_annotation and self.drag_start is not None and self.drag_end is not None:
            strategy = TOOL_STRATEGIES.get(self.active_tool)
            if strategy:
                ctx = self._build_tool_context()
                strategy.preview(ctx, painter)
            elif self.active_tool == "none" and getattr(self, "ocr_region_mode", False):
                from PyQt6.QtGui import QPen
                s = self.image_to_widget(self.drag_start)
                e = self.image_to_widget(self.drag_end)
                rect = QRectF(s, e).normalized()
                pen = QPen(QColor(59, 130, 246, 200), 2, Qt.PenStyle.DashLine)
                painter.setPen(pen)
                painter.setBrush(QColor(59, 130, 246, 40))
                painter.drawRoundedRect(rect, 4, 4)
        elif self.text_drag.is_dragging:
            self.draw_dragging_text_overlay(painter)

        if self.text_panel_visible() and self.text_anchor is not None:
            anchor = self.image_to_widget(self.text_anchor)
            painter.save()
            painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(qc("accent.base", 230))
            painter.drawEllipse(QRectF(anchor.x() - 4, anchor.y() - 4, 8, 8))
            painter.setBrush(QColor(255, 255, 255, 220))
            painter.drawEllipse(QRectF(anchor.x() - 2, anchor.y() - 2, 4, 4))
            painter.restore()

        if not self.adjusting_selection:
            self.draw_toolbar(painter)
            self.draw_style_panel(painter)
            if self.active_tool == "picker":
                self._draw_magnifier(painter)
            self.draw_message(painter)
        else:
            self.draw_message(painter)

    def _draw_magnifier(self, painter: QPainter) -> None:
        """取色器激活时，在光标附近显示放大镜和颜色预览。"""
        cursor_pos = self.mapFromGlobal(self.cursor().pos())
        if not self.selection_rect.contains(cursor_pos):
            return
        if self.edit_pixmap.isNull():
            return

        image_pos = self.widget_to_image(cursor_pos)
        if image_pos is None:
            return

        # 放大镜参数
        mag_size = 120       # 放大镜直径
        zoom = 8             # 放大倍数
        src_radius = mag_size // zoom // 2  # 源图像采样半径

        # 放大镜位置（光标右下方，避免遮挡）
        mx = cursor_pos.x() + 20
        my = cursor_pos.y() + 20
        # 防止超出窗口
        if mx + mag_size > self.width():
            mx = cursor_pos.x() - mag_size - 20
        if my + mag_size > self.height():
            my = cursor_pos.y() - mag_size - 20

        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)

        # 裁剪圆形区域
        from PyQt6.QtGui import QPainterPath
        path = QPainterPath()
        cx, cy = mx + mag_size / 2, my + mag_size / 2
        path.addEllipse(QRectF(mx, my, mag_size, mag_size))
        painter.setClipPath(path)

        # 绘制放大后的图像
        src_rect = QRect(
            int(image_pos.x()) - src_radius,
            int(image_pos.y()) - src_radius,
            src_radius * 2 + 1,
            src_radius * 2 + 1,
        )
        dest_rect = QRectF(mx, my, mag_size, mag_size)
        painter.drawPixmap(dest_rect, self.edit_pixmap, QRectF(src_rect))

        # 绘制十字准线
        painter.setPen(QPen(QColor(255, 255, 255, 180), 1))
        painter.drawLine(QPointF(cx, my + 2), QPointF(cx, my + mag_size - 2))
        painter.drawLine(QPointF(mx + 2, cy), QPointF(mx + mag_size - 2, cy))
        painter.setPen(QPen(QColor(0, 0, 0, 120), 1))
        painter.drawLine(QPointF(cx - 6, cy), QPointF(cx + 6, cy))
        painter.drawLine(QPointF(cx, cy - 6), QPointF(cx, cy + 6))

        # 绘制边框
        painter.setClipping(False)
        painter.setPen(QPen(QColor(255, 255, 255, 200), 2))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawEllipse(QRectF(mx, my, mag_size, mag_size))

        # 绘制颜色预览方块 - 使用缓存的 QImage 提升性能
        ix, iy = int(image_pos.x()), int(image_pos.y())
        if 0 <= ix < self.edit_pixmap.width() and 0 <= iy < self.edit_pixmap.height():
            # 优化：使用缓存的 QImage，避免每次取色都进行完整转换（O(n) → O(1)）
            cached_image = self._get_cached_edit_image()
            if cached_image is not None:
                color = cached_image.pixelColor(ix, iy)
            else:
                # 降级方案：直接访问 pixmap（较慢但安全）
                color = self.edit_pixmap.toImage().pixelColor(ix, iy)
            preview_size = 24
            px = mx + mag_size - preview_size - 4
            py = my + 4
            painter.setPen(QPen(QColor(255, 255, 255, 200), 1))
            painter.setBrush(color)
            painter.drawRect(QRectF(px, py, preview_size, preview_size))

        painter.restore()
