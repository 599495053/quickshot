import datetime
from pathlib import Path
from typing import List, Optional, Tuple

from PyQt6.QtCore import QPointF, QPoint, QRect, QRectF, Qt
from PyQt6.QtGui import QAction, QColor, QFont, QKeySequence, QPainter, QPen, QPixmap, QPolygonF, QTransform
from PyQt6.QtWidgets import QApplication, QFileDialog, QInputDialog, QMenu, QMessageBox, QWidget

from .config import Config
from .theme import floating_bg, floating_text
from .utils import APP_NAME, copy_pixmap_to_clipboard, debug_log, load_app_icon

PIN_WINDOWS: List["PinWindow"] = []


def _safe_remove_pin(w: "PinWindow") -> None:
    try:
        PIN_WINDOWS.remove(w)
    except ValueError:
        pass


def show_pin_window(pixmap: QPixmap, config: Config, pos: Optional[QPoint] = None, target_size: Optional[Tuple[int, int]] = None) -> Optional["PinWindow"]:
    if pixmap.isNull():
        return None
    pin = PinWindow(pixmap.copy(), config, target_size=target_size)
    PIN_WINDOWS.append(pin)
    pin.destroyed.connect(lambda _obj=None, w=pin: _safe_remove_pin(w))
    if pos is not None:
        pin.move(pos)
    pin.show()
    pin.raise_()
    pin.activateWindow()
    return pin


class PinWindow(QWidget):
    """桌面贴图窗口：截图后钉在桌面最上层，可拖动、缩放、复制、保存、关闭。"""

    QUICKBAR_ITEMS = ("edit", "top", "lock", "through", "zoom_out", "zoom_in", "copy", "close")
    QUICKBAR_TIPS = {
        "edit": "编辑标注",
        "top": "置顶显示",
        "lock": "锁定位置",
        "through": "鼠标穿透",
        "zoom_out": "缩小",
        "zoom_in": "放大",
        "copy": "复制贴图",
        "close": "关闭贴图",
    }

    def __init__(self, pixmap: QPixmap, config: Config, target_size: Optional[Tuple[int, int]] = None) -> None:
        super().__init__()
        self.pixmap = pixmap.copy()
        self.pixmap.setDevicePixelRatio(1.0)
        self.config = config
        self.created_at = datetime.datetime.now()
        self.name = f"贴图 {self.created_at.strftime('%H:%M:%S')}"
        self.scale = 1.0
        self.opacity_percent = 100
        self.locked = False
        self.dragging = False
        self.drag_offset = QPoint()
        self.hovered = False
        self.always_on_top = True
        self.mouse_passthrough = False
        self._quickbar_rect = QRect()
        self._quickbar_buttons: dict = {}
        self._quickbar_hover = ""

        # ── 编辑模式状态 ──
        self.edit_mode = False
        self._base_pixmap = QPixmap()
        self.annotations: list = []
        self._edit_history: list = []
        self._redo_stack: list = []
        self.active_tool = "none"
        self.stroke_color = "#ff4646"
        self.stroke_width = 5
        self._edit_dragging = False
        self._edit_drag_start: Optional[QPoint] = None
        self._edit_drag_end: Optional[QPoint] = None
        self._edit_drag_path: list = []
        self._edit_hover_btn = ""
        self._edit_toolbar_rect = QRect()
        self._edit_toolbar_buttons: dict = {}
        self._icons = None  # lazy import to avoid circular dependency

        self.setWindowTitle(f"{APP_NAME} 贴图")
        self.setWindowIcon(load_app_icon())
        self.apply_window_flags()
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose, True)
        self.setMouseTracking(True)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setCursor(Qt.CursorShape.OpenHandCursor)
        self.setWindowOpacity(1.0)

        self.apply_initial_size(target_size)

    def apply_initial_size(self, target_size: Optional[Tuple[int, int]] = None) -> None:
        if self.pixmap.isNull():
            self.resize(240, 160)
            return
        app = QApplication.instance()
        screen = app.primaryScreen() if app else None
        available = screen.availableGeometry() if screen else QRect(0, 0, 1200, 800)
        w = self.pixmap.width()
        h = self.pixmap.height()
        if target_size is not None:
            # 从截图贴图：按选区逻辑尺寸缩放，超出屏幕时等比缩小
            tw, th = target_size
            ratio = min(tw / max(1, w), th / max(1, h))
            # 确保不超出屏幕
            max_w = available.width() - 40
            max_h = available.height() - 40
            ratio = min(ratio, max_w / max(1, w), max_h / max(1, h))
            self.scale = max(0.15, ratio)
        else:
            # 从历史库贴图：按屏幕 55% 自适应
            max_w = max(260, int(available.width() * 0.55))
            max_h = max(180, int(available.height() * 0.55))
            ratio = min(1.0, max_w / max(1, w), max_h / max(1, h))
            self.scale = max(0.15, ratio)
        self.resize_to_scale()
        x = available.center().x() - self.width() // 2
        y = available.center().y() - self.height() // 2
        self.move(max(available.left(), x), max(available.top(), y))

    def apply_window_flags(self) -> None:
        flags = Qt.WindowType.FramelessWindowHint | Qt.WindowType.Tool
        if self.always_on_top:
            flags |= Qt.WindowType.WindowStaysOnTopHint
        if self.mouse_passthrough:
            flags |= Qt.WindowType.WindowTransparentForInput
        self.setWindowFlags(flags)

    def set_always_on_top(self, enabled: bool) -> None:
        enabled = bool(enabled)
        if self.always_on_top == enabled:
            return
        geometry = self.geometry()
        self.always_on_top = enabled
        self.apply_window_flags()
        self.setGeometry(geometry)
        self.show()
        if enabled:
            self.raise_()
            self.activateWindow()
        self.update()

    def toggle_always_on_top(self) -> None:
        self.set_always_on_top(not self.always_on_top)

    def set_mouse_passthrough(self, enabled: bool) -> None:
        enabled = bool(enabled)
        if self.mouse_passthrough == enabled:
            return
        if enabled and self.edit_mode:
            self.exit_edit_mode(True)
        geometry = self.geometry()
        self.mouse_passthrough = enabled
        self.dragging = False
        self.hovered = False if enabled else self.underMouse()
        self._quickbar_hover = ""
        self.setToolTip("")
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, enabled)
        self.apply_window_flags()
        self.setGeometry(geometry)
        self.show()
        if not enabled and self.always_on_top:
            self.raise_()
            self.activateWindow()
        self.update()

    def toggle_mouse_passthrough(self) -> None:
        self.set_mouse_passthrough(not self.mouse_passthrough)

    def set_display_name(self, name: str) -> None:
        cleaned = name.strip()
        if cleaned:
            self.name = cleaned
            self.update()

    def match_keyword(self, keyword: str) -> bool:
        keyword = keyword.strip().lower()
        if not keyword:
            return True
        status_labels = self.status_labels()
        haystack = " ".join(
            [
                self.name,
                self.created_at.strftime("%Y-%m-%d %H:%M:%S"),
                f"{self.pixmap.width()}x{self.pixmap.height()}",
                f"{self.scale:.0%}",
                *status_labels,
                f"{self.opacity_percent}%",
            ]
        ).lower()
        return keyword in haystack

    def status_labels(self) -> List[str]:
        return [
            "置顶" if self.always_on_top else "普通",
            "锁定" if self.locked else "可拖动",
            "鼠标穿透" if self.mouse_passthrough else "可点击",
        ]

    def prompt_rename(self) -> None:
        name, ok = QInputDialog.getText(self, "重命名贴图", "名称", text=self.name)
        if ok:
            self.set_display_name(name)

    def set_locked(self, enabled: bool) -> None:
        self.locked = bool(enabled)
        self.setCursor(Qt.CursorShape.ArrowCursor if self.locked else Qt.CursorShape.OpenHandCursor)
        self.update()

    def toggle_locked(self) -> None:
        self.set_locked(not self.locked)

    def set_opacity_percent(self, value: int) -> None:
        self.opacity_percent = max(35, min(100, int(value)))
        self.setWindowOpacity(self.opacity_percent / 100.0)
        self.update()

    def adjust_opacity(self, delta: int) -> None:
        self.set_opacity_percent(self.opacity_percent + delta)

    def resize_to_scale(self) -> None:
        w = max(80, int(round(self.pixmap.width() * self.scale)))
        h = max(60, int(round(self.pixmap.height() * self.scale)))
        self.resize(w, h)
        self.update()

    def set_scale_keep_center(self, new_scale: float) -> None:
        """更改缩放比并保持窗口中心位置不变。"""
        if self.pixmap.isNull():
            return
        new_scale = max(0.12, min(4.0, float(new_scale)))
        if abs(new_scale - self.scale) < 1e-4:
            return
        old_center = self.geometry().center()
        self.scale = new_scale
        self.resize_to_scale()
        self.move(old_center - QPoint(self.width() // 2, self.height() // 2))

    def zoom_in(self, factor: float = 1.1) -> None:
        self.set_scale_keep_center(self.scale * factor)

    def zoom_out(self, factor: float = 1.1) -> None:
        self.set_scale_keep_center(self.scale / factor)

    def reset_scale(self) -> None:
        self.set_scale_keep_center(1.0)

    def nudge_position(self, dx: int, dy: int) -> None:
        """方向键微调窗口位置。"""
        if self.locked:
            return
        pos = self.pos()
        self.move(pos.x() + dx, pos.y() + dy)

    def flip_horizontal(self) -> None:
        if self.pixmap.isNull():
            return
        self.pixmap = self.pixmap.transformed(QTransform().scale(-1, 1))
        self.update()

    def flip_vertical(self) -> None:
        if self.pixmap.isNull():
            return
        self.pixmap = self.pixmap.transformed(QTransform().scale(1, -1))
        self.update()

    # ── 编辑模式 ──

    EDIT_TOOLS = [
        ("arrow", "箭头"), ("rect", "矩形"), ("pen", "画笔"),
        ("mosaic", "马赛克"),
    ]

    def enter_edit_mode(self) -> None:
        if self.edit_mode:
            return
        if self.mouse_passthrough:
            self.set_mouse_passthrough(False)
        self._base_pixmap = self.pixmap.copy()
        self._edit_history.clear()
        self._redo_stack.clear()
        self.annotations.clear()
        self.edit_mode = True
        self.active_tool = "arrow"
        self.setCursor(Qt.CursorShape.CrossCursor)
        self.update()

    def exit_edit_mode(self, apply: bool = True) -> None:
        if not self.edit_mode:
            return
        if not apply:
            self.pixmap = self._base_pixmap
        self._base_pixmap = QPixmap()
        self.edit_mode = False
        self.active_tool = "none"
        self._edit_dragging = False
        self._edit_history.clear()
        self._redo_stack.clear()
        self.annotations.clear()
        self.setCursor(Qt.CursorShape.OpenHandCursor if not self.locked else Qt.CursorShape.ArrowCursor)
        self.update()

    def _select_edit_tool(self, tool: str) -> None:
        self.active_tool = tool if self.active_tool != tool else "none"
        self.setCursor(Qt.CursorShape.CrossCursor if self.active_tool != "none" else Qt.CursorShape.ArrowCursor)
        self.update()

    def _widget_to_pixmap(self, pos: QPoint) -> QPoint:
        """将窗口坐标转换为 pixmap 像素坐标。"""
        if self.width() <= 0 or self.height() <= 0:
            return pos
        px = pos.x() * self.pixmap.width() / self.width()
        py = pos.y() * self.pixmap.height() / self.height()
        return QPoint(int(px), int(py))

    def _update_edit_toolbar(self) -> None:
        if not self.edit_mode:
            self._edit_toolbar_rect = QRect()
            self._edit_toolbar_buttons.clear()
            return
        btn_size = 32
        pad = 6
        spacing = 3
        total_w = pad * 2 + len(self.EDIT_TOOLS) * btn_size + (len(self.EDIT_TOOLS) - 1) * spacing
        x = max(0, self.width() // 2 - total_w // 2)
        y = self.height() - btn_size - pad * 2 - 4
        self._edit_toolbar_rect = QRect(x, y, total_w, btn_size + pad * 2)
        bx = x + pad
        for key, _label in self.EDIT_TOOLS:
            self._edit_toolbar_buttons[key] = QRect(bx, y + pad, btn_size, btn_size)
            bx += btn_size + spacing

    def _edit_toolbar_button_at(self, pos: QPoint) -> str:
        for key, rect in self._edit_toolbar_buttons.items():
            if rect.contains(pos):
                return key
        return ""

    def _push_edit_history(self) -> None:
        self._edit_history.append((self.pixmap.copy(), [dict(a) for a in self.annotations]))
        self._redo_stack.clear()

    def undo_annotation(self) -> None:
        if not self._edit_history:
            return
        self._redo_stack.append((self.pixmap.copy(), [dict(a) for a in self.annotations]))
        pm, anns = self._edit_history.pop()
        self.pixmap = pm
        self.annotations = anns
        self.update()

    def redo_annotation(self) -> None:
        if not self._redo_stack:
            return
        self._edit_history.append((self.pixmap.copy(), [dict(a) for a in self.annotations]))
        pm, anns = self._redo_stack.pop()
        self.pixmap = pm
        self.annotations = anns
        self.update()

    def _commit_edit_annotation(self) -> None:
        from .overlay import annotation_painter
        start = self._edit_drag_start
        end = self._edit_drag_end
        if start is None or end is None:
            return
        # 窗口坐标 → pixmap 像素坐标
        ps = self._widget_to_pixmap(start)
        pe = self._widget_to_pixmap(end)
        painter = QPainter(self.pixmap)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        color = QColor(self.stroke_color)
        width = float(self.stroke_width)

        if self.active_tool == "arrow" and (ps - pe).manhattanLength() >= 6:
            annotation_painter.draw_arrow(painter, QPointF(ps), QPointF(pe), color, width, max(16, width * 4.4))
            self.annotations.append({"type": "arrow", "x1": ps.x(), "y1": ps.y(), "x2": pe.x(), "y2": pe.y(), "color": self.stroke_color, "width": int(width)})
        elif self.active_tool == "rect":
            rect = QRect(ps, pe).normalized()
            if rect.width() >= 6 and rect.height() >= 6:
                annotation_painter.draw_rect_annotation(painter, QRectF(rect), color, width)
                self.annotations.append({"type": "rect", "x": rect.x(), "y": rect.y(), "w": rect.width(), "h": rect.height(), "color": self.stroke_color, "width": int(width)})
        elif self.active_tool == "pen" and len(self._edit_drag_path) >= 2:
            pixmap_points = [self._widget_to_pixmap(p) for p in self._edit_drag_path]
            points = [QPointF(p) for p in pixmap_points]
            annotation_painter.draw_polyline(painter, points, color, width)
            self.annotations.append({"type": "pen", "points": [(p.x(), p.y()) for p in pixmap_points], "color": self.stroke_color, "width": int(width)})
        elif self.active_tool == "mosaic":
            rect = QRect(ps, pe).normalized()
            if rect.width() >= 8 and rect.height() >= 8:
                painter.end()  # 先结束 painter，再修改 pixmap
                self._apply_pin_mosaic(rect)
                return
        painter.end()

    def _apply_pin_mosaic(self, rect: QRect) -> None:
        from PyQt6.QtGui import QImage
        try:
            # 裁剪到 pixmap 边界内
            safe_rect = rect.intersected(QRect(0, 0, self.pixmap.width(), self.pixmap.height()))
            if safe_rect.width() < 4 or safe_rect.height() < 4:
                return
            image = self.pixmap.toImage().convertToFormat(QImage.Format.Format_ARGB32)
            crop = image.copy(safe_rect)
            if crop.isNull() or crop.width() == 0 or crop.height() == 0:
                return
            block = 14
            sw = max(1, safe_rect.width() // block)
            sh = max(1, safe_rect.height() // block)
            small = crop.scaled(sw, sh, Qt.AspectRatioMode.IgnoreAspectRatio, Qt.TransformationMode.FastTransformation)
            mosaic = small.scaled(safe_rect.size(), Qt.AspectRatioMode.IgnoreAspectRatio, Qt.TransformationMode.FastTransformation)
            p = QPainter(image)
            p.drawImage(safe_rect.topLeft(), mosaic)
            p.end()
            self.pixmap = QPixmap.fromImage(image)
        except Exception as exc:
            debug_log(f"pin mosaic failed: {exc}")

    def _draw_edit_toolbar(self, painter: QPainter) -> None:
        self._update_edit_toolbar()
        if self._edit_toolbar_rect.isNull():
            return
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(0, 0, 0, 140))
        painter.drawRoundedRect(QRectF(self._edit_toolbar_rect), 8, 8)
        for key, label in self.EDIT_TOOLS:
            btn = self._edit_toolbar_buttons.get(key)
            if btn is None:
                continue
            is_active = key == self.active_tool
            is_hover = key == self._edit_hover_btn
            rr = QRectF(btn).adjusted(2, 2, -2, -2)
            if is_active:
                painter.setBrush(QColor(59, 130, 246, 200))
                painter.setPen(Qt.PenStyle.NoPen)
                painter.drawRoundedRect(rr, 6, 6)
            elif is_hover:
                painter.setBrush(QColor(255, 255, 255, 40))
                painter.setPen(Qt.PenStyle.NoPen)
                painter.drawRoundedRect(rr, 6, 6)
            # 图标或文字 fallback
            icon_rect = btn.adjusted(6, 6, -6, -6)
            if self._icons is None:
                from .overlay.icons import IconCache
                self._icons = IconCache()
            self._icons.draw(painter, key, icon_rect, QColor(255, 255, 255))

    def _draw_edit_preview(self, painter: QPainter) -> None:
        from .overlay import annotation_painter
        if not self._edit_drag_start or not self._edit_drag_end:
            return
        # 将窗口坐标转为 pixmap 坐标，再按 pixmap→窗口比例缩放绘制
        # 这样预览大小与最终提交的标注一致
        ps = self._widget_to_pixmap(self._edit_drag_start)
        pe = self._widget_to_pixmap(self._edit_drag_end)
        sx = self.width() / max(1, self.pixmap.width())
        sy = self.height() / max(1, self.pixmap.height())

        def _to_widget(p: QPoint) -> QPointF:
            return QPointF(p.x() * sx, p.y() * sy)

        painter.save()
        color = QColor(self.stroke_color)
        # 线宽也要按缩放比例
        width = float(self.stroke_width) * min(sx, sy)
        pen = QPen(color, width)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
        painter.setPen(pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        ws, we = _to_widget(ps), _to_widget(pe)
        if self.active_tool == "arrow":
            annotation_painter.draw_arrow(painter, ws, we, color, width, max(16, width * 4.4))
        elif self.active_tool == "rect":
            rect = QRectF(ws, we).normalized()
            annotation_painter.draw_rect_annotation(painter, rect, color, width)
        elif self.active_tool == "pen" and len(self._edit_drag_path) >= 2:
            points = [_to_widget(self._widget_to_pixmap(p)) for p in self._edit_drag_path]
            annotation_painter.draw_polyline(painter, points, color, width)
        elif self.active_tool == "mosaic":
            rect = QRectF(ws, we).normalized()
            painter.setBrush(QColor(128, 128, 128, 100))
            painter.drawRect(rect)
        painter.restore()

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)
        painter.fillRect(self.rect(), Qt.GlobalColor.transparent)
        if not self.pixmap.isNull():
            painter.drawPixmap(QRect(0, 0, self.width(), self.height()), self.pixmap)

        # 边框：未悬停时极轻，悬停时强调蓝
        if self.hovered:
            painter.setPen(QPen(QColor(0, 180, 255, 230), 2))
        else:
            painter.setPen(QPen(QColor(0, 0, 0, 70), 1))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawRect(self.rect().adjusted(0, 0, -1, -1))

        if self.edit_mode:
            self._draw_edit_toolbar(painter)
            if self._edit_dragging:
                self._draw_edit_preview(painter)
        elif self.hovered:
            self._draw_quickbar(painter)
            self._draw_info_pill(painter)

    def _draw_info_pill(self, painter: QPainter) -> None:
        """绘制 hover 信息条：左上角显示当前状态。"""
        painter.setFont(QFont("Microsoft YaHei", 9))
        status_text = "　".join(self.status_labels())
        text = f"{self.name}　{int(self.scale * 100)}%　{status_text}　透明 {self.opacity_percent}%"
        metrics = painter.fontMetrics()
        max_w = self.width() - 16
        if not self._quickbar_rect.isNull():
            max_w = max(0, self._quickbar_rect.left() - 16)
        if max_w < 120:
            return
        text = metrics.elidedText(text, Qt.TextElideMode.ElideRight, max_w - 24)
        text_width = metrics.horizontalAdvance(text)
        pill_w = min(max_w, max(120, text_width + 24))
        pill_h = 28
        pill = QRect(8, 8, pill_w, pill_h)

        # 阴影
        shadow_color = QColor(0, 0, 0, 60)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(shadow_color)
        painter.drawRoundedRect(QRectF(pill.adjusted(0, 2, 0, 2)), 12, 12)

        # 主体
        painter.setBrush(floating_bg())
        painter.drawRoundedRect(QRectF(pill), 12, 12)

        painter.setPen(floating_text())
        painter.drawText(pill, Qt.AlignmentFlag.AlignCenter, text)

    def _quickbar_visible_items(self) -> Tuple[str, ...]:
        items = list(self.QUICKBAR_ITEMS)
        button_size = 28
        pad = 6
        gap = 4

        def total_width() -> int:
            return pad * 2 + len(items) * button_size + max(0, len(items) - 1) * gap

        available = self.width() - 16
        drop_order = ("copy", "edit", "zoom_out", "zoom_in", "through", "lock", "top")
        while items and total_width() > available:
            dropped = False
            for key in drop_order:
                if key in items:
                    items.remove(key)
                    dropped = True
                    break
            if not dropped:
                break
        return tuple(items)

    def _update_quickbar_layout(self) -> None:
        self._quickbar_buttons.clear()
        self._quickbar_rect = QRect()
        if self.mouse_passthrough or self.width() < 54 or self.height() < 54:
            return
        items = self._quickbar_visible_items()
        if not items:
            return
        button_size = 28
        pad = 6
        gap = 4
        total_w = pad * 2 + len(items) * button_size + max(0, len(items) - 1) * gap
        total_h = button_size + pad * 2
        x = max(8, self.width() - total_w - 8)
        y = 8
        self._quickbar_rect = QRect(x, y, total_w, total_h)
        bx = x + pad
        by = y + pad
        for key in items:
            self._quickbar_buttons[key] = QRect(bx, by, button_size, button_size)
            bx += button_size + gap

    def _quickbar_button_at(self, pos: QPoint) -> str:
        self._update_quickbar_layout()
        for key, rect in self._quickbar_buttons.items():
            if rect.contains(pos):
                return key
        return ""

    def _draw_quickbar(self, painter: QPainter) -> None:
        self._update_quickbar_layout()
        if self._quickbar_rect.isNull():
            return
        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.setPen(QPen(QColor(255, 255, 255, 58), 1))
        painter.setBrush(QColor(17, 24, 39, 160))
        painter.drawRoundedRect(QRectF(self._quickbar_rect), 10, 10)
        for key, rect in self._quickbar_buttons.items():
            active = (
                (key == "top" and self.always_on_top)
                or (key == "lock" and self.locked)
                or (key == "through" and self.mouse_passthrough)
            )
            hovered = key == self._quickbar_hover
            button_rect = QRectF(rect).adjusted(2, 2, -2, -2)
            if key == "close" and hovered:
                bg = QColor(220, 38, 38, 210)
            elif active:
                bg = QColor(79, 70, 229, 220)
            elif hovered:
                bg = QColor(255, 255, 255, 44)
            else:
                bg = QColor(255, 255, 255, 0)
            if bg.alpha() > 0:
                painter.setPen(Qt.PenStyle.NoPen)
                painter.setBrush(bg)
                painter.drawRoundedRect(button_rect, 7, 7)
            self._draw_quickbar_icon(painter, key, rect.adjusted(6, 6, -6, -6), QColor(255, 255, 255))
        painter.restore()

    def _draw_quickbar_icon(self, painter: QPainter, key: str, rect: QRect, color: QColor) -> None:
        icon_map = {
            "edit": "pen",
            "top": "pin",
            "copy": "copy",
            "close": "cancel",
        }
        icon_key = icon_map.get(key)
        if icon_key:
            if self._icons is None:
                from .overlay.icons import IconCache
                self._icons = IconCache()
            self._icons.draw(painter, icon_key, rect, color)
            return

        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        pen = QPen(color, 2, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin)
        painter.setPen(pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        r = QRectF(rect)
        cx = r.center().x()
        cy = r.center().y()
        if key == "lock":
            body = QRectF(r.left() + 2, cy - 1, r.width() - 4, r.height() / 2 + 2)
            painter.drawRoundedRect(body, 2.5, 2.5)
            shackle = QRectF(r.left() + 4, r.top() + 1, r.width() - 8, r.height() - 5)
            painter.drawArc(shackle, 0, 180 * 16)
            if not self.locked:
                painter.drawLine(QPointF(r.left() + 1, r.bottom() - 1), QPointF(r.right() - 1, r.top() + 1))
        elif key == "through":
            points = QPolygonF(
                [
                    QPointF(r.left() + 2, r.top() + 1),
                    QPointF(r.left() + 2, r.bottom() - 2),
                    QPointF(cx - 1, cy + 2),
                    QPointF(cx + 2, r.bottom() - 1),
                    QPointF(r.right() - 1, r.bottom() - 4),
                    QPointF(cx + 2, cy),
                    QPointF(r.right() - 2, cy - 1),
                ]
            )
            painter.drawPolygon(points)
            painter.drawLine(QPointF(r.left(), r.bottom()), QPointF(r.right(), r.top()))
        elif key == "zoom_out":
            painter.drawLine(QPointF(r.left() + 2, cy), QPointF(r.right() - 2, cy))
        elif key == "zoom_in":
            painter.drawLine(QPointF(r.left() + 2, cy), QPointF(r.right() - 2, cy))
            painter.drawLine(QPointF(cx, r.top() + 2), QPointF(cx, r.bottom() - 2))
        painter.restore()

    def _perform_quickbar_action(self, key: str) -> None:
        if key == "edit":
            self.enter_edit_mode()
        elif key == "top":
            self.toggle_always_on_top()
        elif key == "lock":
            self.toggle_locked()
        elif key == "through":
            self.toggle_mouse_passthrough()
        elif key == "zoom_out":
            self.zoom_out()
        elif key == "zoom_in":
            self.zoom_in()
        elif key == "copy":
            copy_pixmap_to_clipboard(self.pixmap)
        elif key == "close":
            self.close()
        self.update()

    def enterEvent(self, event) -> None:
        self.hovered = True
        self.update()
        super().enterEvent(event)

    def leaveEvent(self, event) -> None:
        self.hovered = False
        self._quickbar_hover = ""
        self.setToolTip("")
        self.update()
        super().leaveEvent(event)

    def mousePressEvent(self, event) -> None:
        if self.edit_mode:
            pos = event.position().toPoint()
            btn = self._edit_toolbar_button_at(pos)
            if btn:
                self._select_edit_tool(btn)
                return
            if event.button() == Qt.MouseButton.LeftButton and self.active_tool != "none":
                self._push_edit_history()
                self._edit_drag_start = pos
                self._edit_drag_end = pos
                if self.active_tool == "pen":
                    self._edit_drag_path = [pos]
                self._edit_dragging = True
                self.update()
                return
            return
        if event.button() == Qt.MouseButton.LeftButton:
            pos = event.position().toPoint()
            quickbar_button = self._quickbar_button_at(pos)
            if quickbar_button:
                self._perform_quickbar_action(quickbar_button)
                event.accept()
                return
            if self.locked:
                self.raise_()
                self.activateWindow()
                event.accept()
                return
            self.dragging = True
            self.drag_offset = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
            self.setCursor(Qt.CursorShape.ClosedHandCursor)
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event) -> None:
        if self.edit_mode and self._edit_dragging:
            pos = event.position().toPoint()
            self._edit_drag_end = pos
            if self.active_tool == "pen":
                if not self._edit_drag_path or (self._edit_drag_path[-1] - pos).manhattanLength() >= 2:
                    self._edit_drag_path.append(pos)
            self.update()
            return
        if self.edit_mode:
            pos = event.position().toPoint()
            btn = self._edit_toolbar_button_at(pos)
            if btn != self._edit_hover_btn:
                self._edit_hover_btn = btn
            self.update()
            return
        if self.dragging:
            self.move(event.globalPosition().toPoint() - self.drag_offset)
            event.accept()
            return
        pos = event.position().toPoint()
        btn = self._quickbar_button_at(pos) if self.hovered else ""
        if btn != self._quickbar_hover:
            self._quickbar_hover = btn
            self.setToolTip(self.QUICKBAR_TIPS.get(btn, "") if btn else "")
            self.update()
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event) -> None:
        if self.edit_mode and self._edit_dragging:
            self._edit_drag_end = event.position().toPoint()
            self._commit_edit_annotation()
            self._edit_dragging = False
            self._edit_drag_start = None
            self._edit_drag_end = None
            self._edit_drag_path = []
            self.update()
            return
        if event.button() == Qt.MouseButton.LeftButton and self.dragging:
            self.dragging = False
            self.setCursor(Qt.CursorShape.ArrowCursor if self.locked else Qt.CursorShape.OpenHandCursor)
            event.accept()
            return
        super().mouseReleaseEvent(event)

    def mouseDoubleClickEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            if self.edit_mode:
                return
            self.close()
            event.accept()
            return
        super().mouseDoubleClickEvent(event)

    def wheelEvent(self, event) -> None:
        if self.pixmap.isNull() or self.locked:
            return
        delta = event.angleDelta().y()
        if delta == 0:
            return
        factor = 1.08 if delta > 0 else (1.0 / 1.08)
        new_scale = max(0.12, min(4.0, self.scale * factor))
        if abs(new_scale - self.scale) < 1e-4:
            event.accept()
            return
        # 让光标下方的像素点在缩放后保持在原位置
        cursor_widget = event.position().toPoint()
        ratio = new_scale / self.scale
        # 缩放后该点在窗口内的新坐标
        new_widget_x = cursor_widget.x() * ratio
        new_widget_y = cursor_widget.y() * ratio
        # 计算窗口需要移动的偏移量，让屏幕上的光标位置不变
        global_cursor = event.globalPosition().toPoint()
        new_top_left_x = global_cursor.x() - int(round(new_widget_x))
        new_top_left_y = global_cursor.y() - int(round(new_widget_y))
        self.scale = new_scale
        self.resize_to_scale()
        self.move(new_top_left_x, new_top_left_y)
        event.accept()

    def contextMenuEvent(self, event) -> None:
        menu = QMenu(self)

        if self.edit_mode:
            exit_save = QAction("完成编辑 (Enter)", menu)
            exit_save.triggered.connect(lambda: self.exit_edit_mode(True))
            exit_cancel = QAction("取消编辑 (Esc)", menu)
            exit_cancel.triggered.connect(lambda: self.exit_edit_mode(False))
            undo_action = QAction("撤销 (Ctrl+Z)", menu)
            undo_action.triggered.connect(self.undo_annotation)
            redo_action = QAction("重做 (Ctrl+Y)", menu)
            redo_action.triggered.connect(self.redo_annotation)
            menu.addAction(exit_save)
            menu.addAction(exit_cancel)
            menu.addSeparator()
            menu.addAction(undo_action)
            menu.addAction(redo_action)
            menu.exec(event.globalPos())
            return

        # 编辑入口
        edit_action = QAction("编辑标注 (E)", menu)
        edit_action.triggered.connect(self.enter_edit_mode)
        menu.addAction(edit_action)
        menu.addSeparator()

        # 状态切换
        rename_action = QAction("重命名 (R)", menu)
        lock_action = QAction("解锁拖动 (L)" if self.locked else "锁定位置 (L)", menu)
        top_action = QAction("取消置顶 (T)" if self.always_on_top else "置顶显示 (T)", menu)
        through_action = QAction("关闭鼠标穿透 (X)" if self.mouse_passthrough else "开启鼠标穿透 (X)", menu)
        rename_action.triggered.connect(self.prompt_rename)
        lock_action.triggered.connect(self.toggle_locked)
        top_action.triggered.connect(self.toggle_always_on_top)
        through_action.triggered.connect(self.toggle_mouse_passthrough)
        menu.addAction(rename_action)
        menu.addAction(lock_action)
        menu.addAction(top_action)
        menu.addAction(through_action)
        menu.addSeparator()

        # 缩放预设
        zoom_menu = menu.addMenu("缩放")
        for label, value in (("50%", 0.5), ("75%", 0.75), ("100% (0)", 1.0), ("150%", 1.5), ("200%", 2.0)):
            action = QAction(label, zoom_menu)
            action.triggered.connect(lambda _checked=False, v=value: self.set_scale_keep_center(v))
            zoom_menu.addAction(action)

        # 翻转
        flip_menu = menu.addMenu("翻转")
        flip_h = QAction("水平翻转", flip_menu)
        flip_v = QAction("垂直翻转", flip_menu)
        flip_h.triggered.connect(self.flip_horizontal)
        flip_v.triggered.connect(self.flip_vertical)
        flip_menu.addAction(flip_h)
        flip_menu.addAction(flip_v)

        # 透明度
        opacity_menu = menu.addMenu("透明度")
        for value in (100, 85, 70, 55, 40):
            action = QAction(f"{value}%", opacity_menu)
            action.triggered.connect(lambda _checked=False, v=value: self.set_opacity_percent(v))
            opacity_menu.addAction(action)
        menu.addSeparator()

        # 输出
        copy_action = QAction("复制贴图 (Ctrl+C)", menu)
        save_action = QAction("保存贴图 (Ctrl+S)", menu)
        copy_action.triggered.connect(lambda: copy_pixmap_to_clipboard(self.pixmap))
        save_action.triggered.connect(self.save_pin)
        menu.addAction(copy_action)
        menu.addAction(save_action)
        menu.addSeparator()

        # 关闭
        close_action = QAction("关闭贴图 (Esc)", menu)
        close_action.triggered.connect(self.close)
        menu.addAction(close_action)

        menu.exec(event.globalPos())

    def save_pin(self) -> None:
        if self.pixmap.isNull():
            return
        try:
            save_dir = self.config.ensure_save_dir()
            filename = datetime.datetime.now().strftime("pin_%Y%m%d_%H%M%S.png")
            default_path = str(Path(save_dir) / filename)
            filepath, _ = QFileDialog.getSaveFileName(
                self, "保存贴图", default_path, "PNG 图片 (*.png)",
            )
            if filepath:
                if not filepath.lower().endswith(".png"):
                    filepath += ".png"
                if not self.pixmap.save(filepath, "PNG"):
                    QMessageBox.warning(
                        self, "保存失败",
                        "无法保存图片，请检查：\n"
                        "1. 磁盘空间是否充足\n"
                        "2. 是否有写入权限\n"
                        "3. 文件是否被其他程序占用"
                    )
        except PermissionError:
            QMessageBox.warning(
                self, "保存失败",
                "无法写入该目录，可能是权限不足。\n\n"
                "建议：\n"
                "1. 选择其他保存位置（如桌面）\n"
                "2. 以管理员身份运行程序"
            )
        except OSError as exc:
            QMessageBox.warning(
                self, "保存失败",
                f"保存失败：{exc}\n\n请检查磁盘空间是否充足。"
            )

    def keyPressEvent(self, event) -> None:
        key = event.key()
        modifiers = event.modifiers()

        if self.edit_mode:
            ctrl = bool(modifiers & Qt.KeyboardModifier.ControlModifier)
            if key == Qt.Key.Key_Escape:
                self.exit_edit_mode(False)
                return
            if key in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
                self.exit_edit_mode(True)
                return
            if ctrl and key == Qt.Key.Key_Z:
                self.undo_annotation()
                return
            if ctrl and key == Qt.Key.Key_Y:
                self.redo_annotation()
                return
            tool_map = {Qt.Key.Key_A: "arrow", Qt.Key.Key_R: "rect", Qt.Key.Key_B: "pen", Qt.Key.Key_M: "mosaic"}
            tool = tool_map.get(key)
            if tool:
                self._select_edit_tool(tool)
                return
            return

        # 进入编辑模式
        if key == Qt.Key.Key_E:
            self.enter_edit_mode()
            return

        # 系统级快捷键优先
        if event.matches(QKeySequence.StandardKey.Copy):
            copy_pixmap_to_clipboard(self.pixmap)
            return
        if event.matches(QKeySequence.StandardKey.Save):
            self.save_pin()
            return
        if event.matches(QKeySequence.StandardKey.Close):
            self.close()
            return
        # 单键快捷
        if key == Qt.Key.Key_Escape:
            self.close()
            return
        if key == Qt.Key.Key_L:
            self.toggle_locked()
            return
        if key == Qt.Key.Key_T:
            self.toggle_always_on_top()
            return
        if key == Qt.Key.Key_X:
            self.toggle_mouse_passthrough()
            return
        if key == Qt.Key.Key_R:
            self.prompt_rename()
            return
        if key == Qt.Key.Key_S:
            self.save_pin()
            return
        if key in (Qt.Key.Key_Plus, Qt.Key.Key_Equal):
            self.zoom_in()
            return
        if key == Qt.Key.Key_Minus:
            self.zoom_out()
            return
        if key == Qt.Key.Key_0:
            self.reset_scale()
            return
        # 方向键微调位置（按住 Shift 步长 10px，否则 1px）
        step = 10 if modifiers & Qt.KeyboardModifier.ShiftModifier else 1
        if key == Qt.Key.Key_Left:
            self.nudge_position(-step, 0)
            return
        if key == Qt.Key.Key_Right:
            self.nudge_position(step, 0)
            return
        if key == Qt.Key.Key_Up:
            self.nudge_position(0, -step)
            return
        if key == Qt.Key.Key_Down:
            self.nudge_position(0, step)
            return
        super().keyPressEvent(event)
