import datetime
from pathlib import Path
from typing import List, Optional, Tuple

from PyQt6.QtCore import QPoint, QRect, QRectF, Qt
from PyQt6.QtGui import QAction, QColor, QFont, QKeySequence, QPainter, QPen, QPixmap, QTransform
from PyQt6.QtWidgets import QApplication, QFileDialog, QInputDialog, QMenu, QMessageBox, QWidget

from .config import Config
from .theme import floating_bg, floating_text
from .utils import APP_NAME, copy_pixmap_to_clipboard, load_app_icon

PIN_WINDOWS: List["PinWindow"] = []


def show_pin_window(pixmap: QPixmap, config: Config, pos: Optional[QPoint] = None, target_size: Optional[Tuple[int, int]] = None) -> Optional["PinWindow"]:
    if pixmap.isNull():
        return None
    pin = PinWindow(pixmap.copy(), config, target_size=target_size)
    PIN_WINDOWS.append(pin)
    pin.destroyed.connect(lambda _obj=None, w=pin: PIN_WINDOWS.remove(w) if w in PIN_WINDOWS else None)
    if pos is not None:
        pin.move(pos)
    pin.show()
    pin.raise_()
    pin.activateWindow()
    return pin


class PinWindow(QWidget):
    """桌面贴图窗口：截图后钉在桌面最上层，可拖动、缩放、复制、保存、关闭。"""

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

    def set_display_name(self, name: str) -> None:
        cleaned = name.strip()
        if cleaned:
            self.name = cleaned
            self.update()

    def match_keyword(self, keyword: str) -> bool:
        keyword = keyword.strip().lower()
        if not keyword:
            return True
        haystack = " ".join(
            [
                self.name,
                self.created_at.strftime("%Y-%m-%d %H:%M:%S"),
                f"{self.pixmap.width()}x{self.pixmap.height()}",
                f"{self.scale:.0%}",
                "置顶" if self.always_on_top else "普通",
                "锁定" if self.locked else "可拖动",
                f"{self.opacity_percent}%",
            ]
        ).lower()
        return keyword in haystack

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

        if self.hovered:
            self._draw_info_pill(painter)

    def _draw_info_pill(self, painter: QPainter) -> None:
        """绘制 hover 信息条：左上角显示当前状态。"""
        painter.setFont(QFont("Microsoft YaHei", 9))
        top_text = "置顶" if self.always_on_top else "普通"
        lock_text = "锁定" if self.locked else "可拖动"
        text = f"{self.name}　{int(self.scale * 100)}%　{top_text}　{lock_text}　透明 {self.opacity_percent}%"
        metrics = painter.fontMetrics()
        text_width = metrics.horizontalAdvance(text)
        # 自适应宽度，最大不超过窗口宽 - 16
        pill_w = min(self.width() - 16, max(220, text_width + 24))
        pill_h = 28
        # 居中或左上角自适应
        if self.width() < pill_w + 16:
            return  # 窗口太窄不画
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

    def enterEvent(self, event) -> None:
        self.hovered = True
        self.update()
        super().enterEvent(event)

    def leaveEvent(self, event) -> None:
        self.hovered = False
        self.update()
        super().leaveEvent(event)

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
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
        if self.dragging:
            self.move(event.globalPosition().toPoint() - self.drag_offset)
            event.accept()
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton and self.dragging:
            self.dragging = False
            self.setCursor(Qt.CursorShape.ArrowCursor if self.locked else Qt.CursorShape.OpenHandCursor)
            event.accept()
            return
        super().mouseReleaseEvent(event)

    def mouseDoubleClickEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
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

        # 状态切换
        rename_action = QAction("重命名 (R)", menu)
        lock_action = QAction("解锁拖动 (L)" if self.locked else "锁定位置 (L)", menu)
        top_action = QAction("取消置顶 (T)" if self.always_on_top else "置顶显示 (T)", menu)
        rename_action.triggered.connect(self.prompt_rename)
        lock_action.triggered.connect(self.toggle_locked)
        top_action.triggered.connect(self.toggle_always_on_top)
        menu.addAction(rename_action)
        menu.addAction(lock_action)
        menu.addAction(top_action)
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
                    QMessageBox.warning(self, "保存失败", "无法保存图片，请检查路径和权限。")
        except OSError as exc:
            QMessageBox.warning(self, "保存失败", f"保存图片时出错：{exc}")

    def keyPressEvent(self, event) -> None:
        key = event.key()
        modifiers = event.modifiers()
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
