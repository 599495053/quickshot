"""TextEditorMixin — 文字标注：打开/编辑/提交/取消/渲染。"""

from __future__ import annotations

from typing import Dict

from PyQt6.QtCore import QPoint, QPointF, QRectF, Qt
from PyQt6.QtGui import QColor, QFont, QFontMetrics, QKeySequence, QPainter, QPen, QShortcut
from PyQt6.QtWidgets import QFrame, QHBoxLayout, QLabel, QPlainTextEdit, QPushButton, QSpinBox, QVBoxLayout

from . import annotation_painter
from ..theme import ACCENT_BASE, BORDER_REGULAR, qc
from ..utils import debug_log


class TextEditorMixin:

    def _init_text_editor_panel(self) -> None:
        """初始化内联文本编辑面板（从 widget.__init__ 提取）。"""
        from ..theme import text_panel_stylesheet

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

    # ── 查询 ──

    def text_panel_visible(self) -> bool:
        return self.text_editor_panel.isVisible()

    def text_editor_has_draft(self) -> bool:
        return bool(self.text_editor.toPlainText().strip())

    # ── 快捷操作 ──

    def settle_inline_text(self) -> bool:
        if not self.text_panel_visible():
            return False
        if self.text_editor_has_draft():
            self.commit_inline_text()
            return True
        self.cancel_inline_text()
        return False

    def on_text_size_changed(self, value: int) -> None:
        self.text_font_size = int(value)

    def select_text_color(self, color_name: str) -> None:
        self.text_panel_color_name = color_name
        for button_color, button in self.text_color_buttons.items():
            border = ACCENT_BASE if button_color == color_name else BORDER_REGULAR
            width = 2 if button_color == color_name else 1
            button.setStyleSheet(
                f"background:{button_color}; border:{width}px solid {border}; border-radius:12px; padding:0;"
            )

    # ── 打开 / 关闭 ──

    def close_inline_text(self, clear_anchor: bool = True) -> None:
        self.text_editor_panel.hide()
        self.text_commit_shortcut.setEnabled(False)
        self.text_commit_shortcut2.setEnabled(False)
        self.text_cancel_shortcut.setEnabled(False)
        self.text_editor.clearFocus()
        if clear_anchor:
            self.text_anchor = None
        self.editing_text_index = -1
        try:
            if self.isVisible():
                self.grabKeyboard()
        except Exception as exc:
            debug_log(f"regrabKeyboard after inline text failed: {exc}")
        self.update()

    def cancel_inline_text(self) -> None:
        if not self.text_panel_visible():
            return
        was_editing = self.editing_text_index >= 0
        self.close_inline_text()
        self.message = "已取消修改文字" if was_editing else "已取消添加文字"
        self.update()
        self.setFocus(Qt.FocusReason.OtherFocusReason)

    # ── 定位 ──

    def position_text_editor_panel(self, point: QPoint) -> None:
        self.text_editor_panel.adjustSize()
        panel_w = max(300, self.text_editor_panel.width())
        panel_h = max(144, self.text_editor_panel.height())
        anchor_widget = self.image_to_widget(point)
        gap = 12
        candidates = [
            QPointF(anchor_widget.x() + gap, anchor_widget.y() + gap),
            QPointF(anchor_widget.x() + gap, anchor_widget.y() - panel_h - gap),
            QPointF(anchor_widget.x() - panel_w - gap, anchor_widget.y() + gap),
            QPointF(anchor_widget.x() - panel_w - gap, anchor_widget.y() - panel_h - gap),
        ]

        def clamp_xy(px: float, py: float) -> tuple[int, int]:
            x = int(max(10, min(self.width() - panel_w - 10, px)))
            y = int(max(10, min(self.height() - panel_h - 10, py)))
            return x, y

        best_x, best_y = clamp_xy(candidates[0].x(), candidates[0].y())
        best_score = float("-inf")
        anchor_box = QRectF(anchor_widget.x() - 14, anchor_widget.y() - 14, 28, 28)
        for candidate in candidates:
            x, y = clamp_xy(candidate.x(), candidate.y())
            rect = QRectF(x, y, panel_w, panel_h)
            overlap = rect.intersects(anchor_box)
            overflow_penalty = 0
            if rect.left() <= 10 or rect.right() >= self.width() - 10:
                overflow_penalty += 1
            if rect.top() <= 10 or rect.bottom() >= self.height() - 10:
                overflow_penalty += 1
            distance = abs((rect.left() + rect.width() / 2) - anchor_widget.x()) + abs((rect.top() + rect.height() / 2) - anchor_widget.y())
            score = -distance - overflow_penalty * 120 - (600 if overlap else 0)
            if score > best_score:
                best_score = score
                best_x, best_y = x, y

        x, y = best_x, best_y
        self.text_editor_panel.setGeometry(x, y, panel_w, panel_h)

    # ── 打开编辑器 / 提交 ──

    def open_inline_text_editor(self, point: QPoint, existing_text: str = "", editing_index: int = -1) -> None:
        if self.text_panel_visible() and editing_index < 0 and existing_text == "":
            existing_text = self.text_editor.toPlainText()
        self.close_style_panel()
        self.dragging_annotation = False
        self.drag_start = None
        self.drag_end = None
        self.drag_path = []
        self.text_anchor = QPoint(point)
        self.editing_text_index = editing_index
        if editing_index >= 0:
            self.selected_text_index = editing_index
        self.text_size_spin.blockSignals(True)
        self.text_size_spin.setValue(max(12, min(72, int(self.text_font_size))))
        self.text_size_spin.blockSignals(False)
        self.select_text_color(self.text_color_name)
        self.text_editor.setPlainText(existing_text)
        self.position_text_editor_panel(point)
        self.text_editor_panel.show()
        self.text_editor_panel.raise_()
        self.text_commit_shortcut.setEnabled(True)
        self.text_commit_shortcut2.setEnabled(True)
        self.text_cancel_shortcut.setEnabled(True)
        try:
            self.releaseKeyboard()
        except Exception as exc:
            debug_log(f"releaseKeyboard for inline text failed: {exc}")
        self.text_editor.setFocus(Qt.FocusReason.OtherFocusReason)
        self.message = "输入文字后按 Ctrl+Enter 添加" if editing_index < 0 else "修改文字后按 Ctrl+Enter 应用"
        self.update()

    def commit_inline_text(self) -> None:
        if not self.text_panel_visible() or self.text_anchor is None:
            return
        text = self.text_editor.toPlainText().strip()
        if not text:
            self.message = "请输入文字内容"
            self.update()
            self.text_editor.setFocus(Qt.FocusReason.OtherFocusReason)
            return

        point = QPoint(self.text_anchor)
        font_size = int(self.text_size_spin.value())
        color_name = self.text_panel_color_name
        self.text_font_size = font_size
        self.text_color_name = color_name

        self.push_history()
        if 0 <= self.editing_text_index < len(self.annotations):
            item = self.annotations[self.editing_text_index]
            if item.get("type") == "text":
                item["x"] = int(point.x())
                item["y"] = int(point.y())
                item["text"] = text
                item["size"] = int(font_size)
                item["color"] = color_name
            self.rebuild_edit_pixmap()
            success_message = "已更新文字标注"
        else:
            self.annotations.append({
                "type": "text",
                "x": int(point.x()), "y": int(point.y()),
                "text": text, "size": int(font_size), "color": color_name,
            })
            self.rebuild_edit_pixmap()
            success_message = "已添加文字，可继续点击添加；字号和颜色会沿用上次选择"
        self.close_inline_text()
        self.active_tool = "none"
        self.close_style_panel()
        self.message = success_message
        self.update()
        self.setFocus(Qt.FocusReason.OtherFocusReason)

    # ── 文字标注绘制 ──

    def draw_text_overlay(self, painter: QPainter, point: QPoint, text: str, font_size: int, color: QColor) -> None:
        if not text:
            return
        scale = min(
            self.selection_rect.width() / max(1, self.edit_pixmap.width()),
            self.selection_rect.height() / max(1, self.edit_pixmap.height()),
        )
        annotation_painter.draw_text_annotation(painter, self.image_to_widget(point), text, max(10, int(round(font_size * scale))), color)

    def draw_text_hover_outline(self, painter: QPainter, item: Dict[str, object], selected: bool = False) -> None:
        rect = self.text_item_widget_rect(item)
        if rect.isNull():
            return
        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        if selected:
            painter.setPen(QPen(qc("accent.hover", 235), 1.8, Qt.PenStyle.SolidLine))
            painter.setBrush(qc("accent.base", 24))
        else:
            painter.setPen(QPen(qc("accent.base", 215), 1.5, Qt.PenStyle.DashLine))
            painter.setBrush(qc("accent.base", 18))
        painter.drawRoundedRect(rect, 6, 6)
        painter.restore()

    def draw_dragging_text_overlay(self, painter: QPainter) -> None:
        if self.dragging_text_index < 0 or self.dragging_text_index >= len(self.annotations):
            return
        item = self.annotations[self.dragging_text_index]
        origin = self.dragging_text_origin
        start = self.dragging_text_start
        current = self.dragging_text_current
        if item.get("type") != "text" or origin is None or start is None or current is None:
            return

        point = QPoint(origin.x() + current.x() - start.x(), origin.y() + current.y() - start.y())
        point.setX(max(0, min(self.edit_pixmap.width() - 1, point.x())))
        point.setY(max(0, min(self.edit_pixmap.height() - 1, point.y())))

        painter.save()
        painter.setOpacity(0.88)
        self.draw_text_overlay(
            painter,
            point,
            str(item.get("text", "")),
            int(item.get("size", 28)),
            QColor(str(item.get("color", "#ffffff"))),
        )
        hover_item = dict(item)
        hover_item["x"] = point.x()
        hover_item["y"] = point.y()
        self.draw_text_hover_outline(painter, hover_item, selected=True)
        painter.restore()

    # ── 碰撞检测 ──

    def text_item_widget_rect(self, item: Dict[str, object]) -> QRectF:
        if item.get("type") != "text" or self.selection_rect.isNull() or self.edit_pixmap.isNull():
            return QRectF()
        text = str(item.get("text", ""))
        if not text:
            return QRectF()

        point = QPoint(int(item.get("x", 0)), int(item.get("y", 0)))
        scale = min(
            self.selection_rect.width() / max(1, self.edit_pixmap.width()),
            self.selection_rect.height() / max(1, self.edit_pixmap.height()),
        )
        pixel_size = max(10, int(round(int(item.get("size", 28)) * scale)))
        metrics = self._text_metrics_cache.get(pixel_size)
        if metrics is None:
            font = QFont("Microsoft YaHei")
            font.setWeight(QFont.Weight.Bold)
            font.setPixelSize(pixel_size)
            metrics = QFontMetrics(font)
            self._text_metrics_cache[pixel_size] = metrics

        lines = text.splitlines() or [text]
        max_width = 0
        for line in lines:
            max_width = max(max_width, metrics.horizontalAdvance(line) if line else max(1, pixel_size // 2))
        total_height = max(1, len(lines)) * metrics.lineSpacing()
        top_left = self.image_to_widget(point)
        rect = QRectF(top_left.x(), top_left.y(), max_width, total_height)
        pad = max(6.0, pixel_size * 0.22)
        return rect.adjusted(-pad, -pad, pad, pad)

    def text_annotation_at(self, pos: QPoint) -> int:
        for index in range(len(self.annotations) - 1, -1, -1):
            item = self.annotations[index]
            if item.get("type") != "text":
                continue
            rect = self.text_item_widget_rect(item)
            if not rect.isNull() and rect.contains(QPointF(pos)):
                return index
        return -1
