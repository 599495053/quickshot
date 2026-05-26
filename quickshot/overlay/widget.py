"""FloatingSnipOverlay — 全屏截图层：先框选，之后在选区下方显示悬浮工具栏并直接编辑。"""

from __future__ import annotations

import traceback
from typing import Dict, List, Optional, Tuple

from PyQt6.QtCore import QEvent, QPoint, QPointF, QRect, QRectF, QSize, Qt, pyqtSignal
from PyQt6.QtGui import QColor, QPainter, QPixmap, QKeySequence, QShortcut
from PyQt6.QtWidgets import QFrame, QHBoxLayout, QLabel, QPlainTextEdit, QPushButton, QSpinBox, QVBoxLayout, QWidget

from ..config import Config
from ..history import CaptureHistoryStore
from ..ocr import OcrJob
from ..theme import (
    STROKE_DEFAULT,
    overlay_dim,
    qc,
    text_panel_stylesheet,
)
from ..utils import APP_NAME, debug_log
from .coords import CoordinateSystem
from .icons import IconCache
from ._drawing import DrawingMixin
from ._events import EventMixin
from ._history import HistoryMixin
from ._ocr import OcrMixin
from ._paint import PaintMixin
from ._selection import SelectionMixin
from ._text_drag import TextDragState
from ._text_editor import TextEditorMixin
from ._toolbar import DRAW_TOOLS, ToolbarMixin
from ._tool_strategies import TOOL_STRATEGIES, ToolContext


class FloatingSnipOverlay(
    TextEditorMixin,
    EventMixin,
    SelectionMixin,
    DrawingMixin,
    ToolbarMixin,
    PaintMixin,
    OcrMixin,
    HistoryMixin,
    QWidget,
):

    closed = pyqtSignal()
    notify = pyqtSignal(str)
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
    DOUBLE_CLICK_GUARD_MS = 400
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

        self.selection_rect = QRect()
        self.selection_physical_rect = QRect()
        self.base_edit_pixmap = QPixmap()
        self.edit_pixmap = QPixmap()
        self.selection_display_pixmap = QPixmap()
        self.adjust_preview_pixmap = QPixmap()
        self.history: List[Tuple[QPixmap, List[Dict[str, object]]]] = []
        self.redo_stack: List[Tuple[QPixmap, List[Dict[str, object]]]] = []
        self.annotations: List[Dict[str, object]] = []

        self.active_tool = "none"
        self.last_tool = "none"
        self.dragging_annotation = False
        self.drag_start: Optional[QPoint] = None
        self.drag_end: Optional[QPoint] = None
        self.drag_path: List[QPoint] = []
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
        self.text_font_size = 28
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
        self.handle_margin = 9
        self.ocr_job: Optional[OcrJob] = None
        self.number_counter = 1
        self.ocr_region_mode = False

        self._edit_entered_at = 0

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

        self.text_editor_panel = QFrame(self)
        self.text_editor_panel.setObjectName("textEditorPanel")
        self.text_editor_panel.hide()

        panel_layout = QVBoxLayout()
        panel_layout.setContentsMargins(10, 10, 10, 10)
        panel_layout.setSpacing(8)

        top_row = QHBoxLayout()
        top_row.setContentsMargins(0, 0, 0, 0)
        top_row.setSpacing(8)

        panel_hint = QLabel("文字")
        panel_hint.setObjectName("textPanelHint")
        self.text_hint_label = QLabel("Ctrl+Enter 添加")
        self.text_hint_label.setObjectName("textPanelSubHint")

        self.text_editor = QPlainTextEdit(self.text_editor_panel)
        self.text_editor.setObjectName("textEditor")
        self.text_editor.setPlaceholderText("输入文字")
        self.text_editor.setTabChangesFocus(True)
        self.text_editor.setFixedHeight(72)
        self.text_editor.installEventFilter(self)

        options_row = QHBoxLayout()
        options_row.setContentsMargins(0, 0, 0, 0)
        options_row.setSpacing(8)

        size_label = QLabel("字")
        size_label.setObjectName("textPanelField")
        self.text_size_spin = QSpinBox(self.text_editor_panel)
        self.text_size_spin.setRange(12, 72)
        self.text_size_spin.setSingleStep(2)
        self.text_size_spin.setValue(max(12, min(72, int(self.text_font_size))))
        self.text_size_spin.setButtonSymbols(QSpinBox.ButtonSymbols.NoButtons)
        self.text_size_spin.setFixedWidth(52)
        self.text_size_spin.valueChanged.connect(self.on_text_size_changed)

        color_label = QLabel("色")
        color_label.setObjectName("textPanelField")

        self.text_color_buttons: Dict[str, QPushButton] = {}
        color_row = QHBoxLayout()
        color_row.setContentsMargins(0, 0, 0, 0)
        color_row.setSpacing(5)
        for color_name, color_title in self.TEXT_COLOR_OPTIONS:
            button = QPushButton(self.text_editor_panel)
            button.setFixedSize(20, 20)
            button.setToolTip(color_title)
            button.clicked.connect(lambda _checked=False, c=color_name: self.select_text_color(c))
            self.text_color_buttons[color_name] = button
            color_row.addWidget(button)
        color_row.addStretch(0)

        options_row.addWidget(size_label)
        options_row.addWidget(self.text_size_spin, 0)
        options_row.addWidget(color_label)
        options_row.addLayout(color_row, 0)
        options_row.addStretch(1)

        action_row = QHBoxLayout()
        action_row.setContentsMargins(0, 0, 0, 0)
        action_row.setSpacing(6)

        self.text_cancel_btn = QPushButton("取消", self.text_editor_panel)
        self.text_cancel_btn.clicked.connect(self.cancel_inline_text)
        self.text_add_btn = QPushButton("添加", self.text_editor_panel)
        self.text_add_btn.clicked.connect(self.commit_inline_text)
        self.text_add_btn.setDefault(True)

        action_row.addStretch(1)
        action_row.addWidget(self.text_add_btn)
        action_row.addWidget(self.text_cancel_btn)

        top_row.addWidget(panel_hint)
        top_row.addWidget(self.text_hint_label)
        top_row.addStretch(1)

        panel_layout.addLayout(top_row)
        panel_layout.addWidget(self.text_editor)
        panel_layout.addLayout(options_row)
        panel_layout.addLayout(action_row)
        self.text_editor_panel.setLayout(panel_layout)
        self.text_editor_panel.setFixedWidth(320)
        self.text_editor_panel.setStyleSheet(text_panel_stylesheet())
        self.select_text_color(self.text_color_name)

        self.text_commit_shortcut = QShortcut(QKeySequence("Ctrl+Return"), self.text_editor_panel)
        self.text_commit_shortcut.activated.connect(self.commit_inline_text)
        self.text_commit_shortcut.setEnabled(False)
        self.text_commit_shortcut2 = QShortcut(QKeySequence("Ctrl+Enter"), self.text_editor_panel)
        self.text_commit_shortcut2.activated.connect(self.commit_inline_text)
        self.text_commit_shortcut2.setEnabled(False)
        self.text_cancel_shortcut = QShortcut(QKeySequence(Qt.Key.Key_Escape), self.text_editor_panel)
        self.text_cancel_shortcut.activated.connect(self.cancel_inline_text)
        self.text_cancel_shortcut.setEnabled(False)

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

        physical_rect = self.logical_to_physical_rect(rect)
        self.draw_dim_outside(painter, rect.adjusted(1, 1, -1, -1))
        self.draw_selection_border(painter, rect)
        self.draw_handles(painter, rect)
        self.draw_size_label(painter, rect, physical_rect.width(), physical_rect.height())

    def paint_edit_mode(self, painter: QPainter) -> None:
        if self.selection_rect.isNull() or self.edit_pixmap.isNull():
            painter.fillRect(self.rect(), overlay_dim())
            self.draw_center_hint(painter, "没有截图内容")
            return

        self.draw_dim_outside(painter, self.selection_rect)
        if not self.adjusting_selection:
            self.draw_selection_snapshot(painter)
            self.draw_annotations_overlay(painter)
        if self.grid_visible:
            self.draw_grid(painter)
        self.draw_selection_border(painter, self.selection_rect)
        self.draw_handles(painter, self.selection_rect)
        self.draw_size_label(painter, self.selection_rect, self.edit_pixmap.width(), self.edit_pixmap.height())

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
            self.draw_message(painter)
        else:
            self.draw_message(painter)
