"""贴图管理窗口：左侧贴图列表 + 右侧预览/操作。"""

from typing import List, Optional

from PyQt6.QtCore import QEvent, QSize, QTimer, Qt
from PyQt6.QtGui import QPixmap
from PyQt6.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSplitter,
    QVBoxLayout,
    QWidget,
)

from ._manager_delegates import PinItemDelegate, build_header_card
from .pin import PIN_WINDOWS, PinWindow
from .preview_scaler import AsyncPreviewScaler
from .theme import manager_extras_stylesheet
from .ui import APP_STYLE, make_card, set_button_role
from .utils import APP_NAME, copy_pixmap_to_clipboard, debug_log, load_app_icon


class PinManagerWindow(QWidget):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle(f"{APP_NAME} 贴图管理")
        self.setWindowIcon(load_app_icon())
        self.resize(1100, 680)
        self.sort_mode = "created_desc"
        self._cached_filtered_pins: Optional[List[PinWindow]] = None
        self.current_pixmap = QPixmap()

        self._search_debounce = QTimer(self)
        self._search_debounce.setSingleShot(True)
        self._search_debounce.setInterval(300)
        self._search_debounce.timeout.connect(self.reload_items)

        self._preview_scaler = AsyncPreviewScaler(self)
        self._preview_scaler.ready.connect(self._on_preview_ready)

        header_card = build_header_card(
            "贴图管理",
            "集中查看当前贴图，支持搜索、排序、锁定、置顶和批量透明度调整。",
        )

        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText("搜索名称、时间、尺寸、状态")
        self.search_edit.textChanged.connect(self._search_debounce.start)

        self.sort_combo = QComboBox()
        self.sort_combo.addItem("最新优先", "created_desc")
        self.sort_combo.addItem("最早优先", "created_asc")
        self.sort_combo.addItem("名称 A-Z", "name_asc")
        self.sort_combo.addItem("尺寸从大到小", "area_desc")
        self.sort_combo.currentIndexChanged.connect(self.on_sort_changed)

        self.status_label = QLabel("")
        self.status_label.setObjectName("status")

        filter_row = QHBoxLayout()
        filter_row.setContentsMargins(0, 0, 0, 0)
        filter_row.setSpacing(8)
        filter_row.addWidget(self.search_edit, 1)
        filter_row.addWidget(self.sort_combo)

        self.list_widget = QListWidget()
        self.list_widget.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.list_widget.setItemDelegate(PinItemDelegate(self.list_widget))
        self.list_widget.setSpacing(2)
        self.list_widget.currentRowChanged.connect(self.on_selection_changed)
        self.list_widget.itemSelectionChanged.connect(self.update_status_label)
        self.list_widget.itemActivated.connect(lambda _item: self.focus_current())
        self.list_widget.installEventFilter(self)

        left_card = make_card()
        left_layout = QVBoxLayout()
        left_layout.setContentsMargins(16, 16, 16, 16)
        left_layout.setSpacing(10)
        left_layout.addLayout(filter_row)
        left_layout.addWidget(self.status_label)
        left_layout.addWidget(self.list_widget, 1)
        left_card.setLayout(left_layout)

        preview_card = make_card()
        preview_layout = QVBoxLayout()
        preview_layout.setContentsMargins(16, 16, 16, 16)
        preview_layout.setSpacing(8)
        preview_title = QLabel("贴图预览")
        preview_title.setObjectName("sectionTitle")
        self.pin_meta_label = QLabel("")
        self.pin_meta_label.setObjectName("meta")
        self.pin_meta_label.setWordWrap(True)

        self.preview_label = QLabel("暂无贴图")
        self.preview_label.setObjectName("preview")
        self.preview_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.preview_label.setMinimumSize(320, 240)

        preview_scroll = QScrollArea()
        preview_scroll.setWidgetResizable(True)
        preview_scroll.setFrameShape(QFrame.Shape.NoFrame)
        preview_scroll.setWidget(self.preview_label)

        preview_layout.addWidget(preview_title)
        preview_layout.addWidget(self.pin_meta_label)
        preview_layout.addWidget(preview_scroll, 1)
        preview_card.setLayout(preview_layout)

        actions_card = make_card()
        actions_layout = QVBoxLayout()
        actions_layout.setContentsMargins(16, 16, 16, 16)
        actions_layout.setSpacing(10)
        actions_title = QLabel("快捷操作")
        actions_title.setObjectName("sectionTitle")

        focus_btn = set_button_role(QPushButton("显示"), "primary")
        focus_btn.clicked.connect(self.focus_current)
        copy_btn = QPushButton("复制")
        copy_btn.clicked.connect(self.copy_current)
        rename_btn = QPushButton("重命名")
        rename_btn.clicked.connect(self.rename_current)
        toggle_top_btn = QPushButton("置顶")
        toggle_top_btn.clicked.connect(self.toggle_current_top)
        lock_btn = QPushButton("锁定")
        lock_btn.clicked.connect(self.toggle_current_lock)
        opacity_up_btn = QPushButton("加深")
        opacity_up_btn.clicked.connect(lambda: self.adjust_current_opacity(10))
        opacity_down_btn = QPushButton("减淡")
        opacity_down_btn.clicked.connect(lambda: self.adjust_current_opacity(-10))
        select_all_btn = QPushButton("全选")
        select_all_btn.clicked.connect(self.select_all_items)
        close_btn = set_button_role(QPushButton("关闭"), "destructive")
        close_btn.clicked.connect(self.close_current)
        close_sel_btn = set_button_role(QPushButton("关闭选中"), "destructive")
        close_sel_btn.clicked.connect(self.close_selected)
        close_all_btn = set_button_role(QPushButton("关闭全部"), "destructive")
        close_all_btn.clicked.connect(self.close_all)
        refresh_btn = QPushButton("刷新")
        refresh_btn.clicked.connect(self.reload_items)

        grid = QGridLayout()
        grid.setContentsMargins(0, 0, 0, 0)
        grid.setSpacing(6)
        grid.addWidget(focus_btn,       0, 0)
        grid.addWidget(copy_btn,        0, 1)
        grid.addWidget(rename_btn,      0, 2)
        grid.addWidget(toggle_top_btn,  0, 3)
        grid.addWidget(select_all_btn,  0, 5)
        grid.addWidget(close_btn,       0, 6)
        grid.addWidget(close_sel_btn,   0, 7)
        grid.addWidget(close_all_btn,   0, 8)
        grid.addWidget(opacity_up_btn,  1, 0)
        grid.addWidget(opacity_down_btn,1, 1)
        grid.addWidget(lock_btn,        1, 2)
        grid.addWidget(refresh_btn,     1, 3)

        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.VLine)
        sep.setStyleSheet("color: #d7deea; background: #d7deea; max-width: 1px;")
        grid.addWidget(sep, 0, 4, 2, 1)

        actions_layout.addWidget(actions_title)
        actions_layout.addLayout(grid)
        actions_card.setLayout(actions_layout)

        right_panel = QWidget()
        right_layout = QVBoxLayout()
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(12)
        right_layout.addWidget(preview_card, 1)
        right_layout.addWidget(actions_card)
        right_panel.setLayout(right_layout)

        splitter = QSplitter()
        splitter.addWidget(left_card)
        splitter.addWidget(right_panel)
        splitter.setSizes([350, 700])

        layout = QVBoxLayout()
        layout.setContentsMargins(18, 18, 18, 18)
        layout.setSpacing(12)
        layout.addWidget(header_card)
        layout.addWidget(splitter, 1)
        self.setLayout(layout)
        self.apply_style()
        self.reload_items()

    def apply_style(self) -> None:
        self.setStyleSheet(APP_STYLE + manager_extras_stylesheet())

    def live_pins(self) -> List[PinWindow]:
        return [pin for pin in PIN_WINDOWS if pin is not None and pin.isVisible()]

    def _invalidate_filtered_cache(self) -> None:
        self._cached_filtered_pins = None

    def filtered_pins(self) -> List[PinWindow]:
        if self._cached_filtered_pins is not None:
            return self._cached_filtered_pins
        keyword = self.search_edit.text().strip()
        pins = [pin for pin in self.live_pins() if pin.match_keyword(keyword)]
        mode = self.sort_mode
        if mode == "created_asc":
            pins.sort(key=lambda pin: pin.created_at)
        elif mode == "name_asc":
            pins.sort(key=lambda pin: (pin.name.lower(), pin.created_at))
        elif mode == "area_desc":
            pins.sort(key=lambda pin: (pin.pixmap.width() * pin.pixmap.height(), pin.created_at), reverse=True)
        else:
            pins.sort(key=lambda pin: pin.created_at, reverse=True)
        self._cached_filtered_pins = pins
        return pins

    def pin_title(self, pin: PinWindow) -> str:
        top_text = "置顶" if pin.always_on_top else "普通"
        lock_text = "锁定" if pin.locked else "可拖动"
        lines = [
            pin.name,
            f"{pin.pixmap.width()} × {pin.pixmap.height()}    缩放 {pin.scale:.0%}    透明 {pin.opacity_percent}%",
            f"{top_text}    {lock_text}    {pin.created_at.strftime('%Y-%m-%d %H:%M:%S')}",
        ]
        return "\n".join(lines)

    def reload_items(self) -> None:
        self._invalidate_filtered_cache()
        current = self.current_pin()
        pins = self.filtered_pins()
        self.list_widget.setUpdatesEnabled(False)
        self.list_widget.blockSignals(True)
        try:
            self.list_widget.clear()
            select_row = 0
            for row, pin in enumerate(pins):
                item = QListWidgetItem()
                item.setSizeHint(QSize(0, PinItemDelegate.ITEM_H))
                item.setData(Qt.ItemDataRole.UserRole, row)
                thumb = pin.pixmap.scaled(
                    PinItemDelegate.THUMB_W,
                    PinItemDelegate.THUMB_H,
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation,
                )
                item.setData(Qt.ItemDataRole.UserRole + 1, thumb)
                item.setData(Qt.ItemDataRole.UserRole + 2, pin.name)
                size_text = f"{pin.pixmap.width()} × {pin.pixmap.height()}    缩放 {pin.scale:.0%}    透明 {pin.opacity_percent}%"
                item.setData(Qt.ItemDataRole.UserRole + 3, size_text)
                top_text = "置顶" if pin.always_on_top else "普通"
                lock_text = "锁定" if pin.locked else "可拖动"
                item.setData(Qt.ItemDataRole.UserRole + 4, f"{top_text}    {lock_text}")
                item.setData(Qt.ItemDataRole.UserRole + 5, pin.created_at.strftime("%Y-%m-%d %H:%M:%S"))
                self.list_widget.addItem(item)
                if current is pin:
                    select_row = row
        finally:
            self.list_widget.blockSignals(False)
            self.list_widget.setUpdatesEnabled(True)
        self.update_status_label(pins)
        if pins:
            self.list_widget.setCurrentRow(min(select_row, len(pins) - 1))

    def current_pin(self) -> Optional[PinWindow]:
        row = self.list_widget.currentRow()
        pins = self.filtered_pins()
        if 0 <= row < len(pins):
            return pins[row]
        return None

    def selected_pins(self) -> List[PinWindow]:
        selected_rows = []
        for item in self.list_widget.selectedItems():
            row = item.data(Qt.ItemDataRole.UserRole)
            if isinstance(row, int):
                selected_rows.append(row)
        pins = self.filtered_pins()
        return [pins[row] for row in selected_rows if 0 <= row < len(pins)]

    def update_status_label(self, pins: Optional[List[PinWindow]] = None) -> None:
        pins = pins if pins is not None else self.filtered_pins()
        keyword = self.search_edit.text().strip()
        sort_text = self.sort_combo.currentText()
        selected_count = len(self.selected_pins())
        parts = [f"当前显示 {len(pins)} 项", f"排序：{sort_text}"]
        if keyword:
            parts.append(f"关键词：{keyword}")
        if selected_count:
            parts.append(f"已选 {selected_count} 项")
        self.status_label.setText("  ·  ".join(parts))

    def on_sort_changed(self) -> None:
        self.sort_mode = str(self.sort_combo.currentData() or "created_desc")
        self.reload_items()

    def on_selection_changed(self, row: int) -> None:
        try:
            self.update_status_label()
            self.update_pin_preview()
            pin = self.current_pin()
            if pin is not None and pin.isVisible():
                pin.raise_()
        except Exception as exc:
            debug_log(f"on_selection_changed error: {exc}")

    def update_pin_preview(self) -> None:
        try:
            pin = self.current_pin()
            if pin is None or pin.pixmap.isNull():
                self._preview_scaler.cancel()
                self.preview_label.setText("暂无贴图")
                self.preview_label.setPixmap(QPixmap())
                self.pin_meta_label.setText("")
                return
            sz = self.preview_label.size()
            w = max(1, sz.width())
            h = max(1, sz.height())
            self.preview_label.setText("")
            self._preview_scaler.request(
                pin.pixmap.toImage(),
                w,
                h,
                Qt.AspectRatioMode.KeepAspectRatio,
            )
            meta = (
                f"名称：{pin.name}  ·  "
                f"尺寸：{pin.pixmap.width()} × {pin.pixmap.height()}  ·  "
                f"缩放：{pin.scale:.0%}  ·  "
                f"透明度：{pin.opacity_percent}%\n"
                f"置顶：{'是' if pin.always_on_top else '否'}  ·  "
                f"锁定：{'是' if pin.locked else '否'}  ·  "
                f"创建：{pin.created_at.strftime('%Y-%m-%d %H:%M:%S')}"
            )
            self.pin_meta_label.setText(meta)
        except Exception as exc:
            debug_log(f"update_pin_preview error: {exc}")

    def _on_preview_ready(self, pixmap: QPixmap) -> None:
        if pixmap.isNull():
            return
        self.preview_label.setPixmap(pixmap)

    def copy_current(self) -> None:
        pin = self.current_pin()
        if pin is not None:
            copy_pixmap_to_clipboard(pin.pixmap)

    def copy_selected(self) -> None:
        pins = self.selected_pins()
        if pins:
            copy_pixmap_to_clipboard(pins[-1].pixmap)

    def rename_current(self) -> None:
        pin = self.current_pin()
        if pin is not None:
            pin.prompt_rename()
            self.reload_items()

    def focus_current(self) -> None:
        pin = self.current_pin()
        if pin is not None:
            pin.show()
            pin.raise_()
            pin.activateWindow()
        else:
            debug_log("focus_current: no pin selected")

    def toggle_current_top(self) -> None:
        pin = self.current_pin()
        if pin is not None:
            pin.toggle_always_on_top()
            self.reload_items()

    def toggle_selected_top(self) -> None:
        pins = self.selected_pins()
        if not pins:
            return
        enable_top = any(not pin.always_on_top for pin in pins)
        for pin in pins:
            pin.set_always_on_top(enable_top)
        self.reload_items()

    def toggle_current_lock(self) -> None:
        pin = self.current_pin()
        if pin is not None:
            pin.toggle_locked()
            self.reload_items()

    def toggle_selected_lock(self) -> None:
        pins = self.selected_pins()
        if not pins:
            return
        enable_lock = any(not pin.locked for pin in pins)
        for pin in pins:
            pin.set_locked(enable_lock)
        self.reload_items()

    def adjust_current_opacity(self, delta: int) -> None:
        pin = self.current_pin()
        if pin is not None:
            pin.adjust_opacity(delta)
            self.reload_items()

    def adjust_selected_opacity(self, delta: int) -> None:
        pins = self.selected_pins()
        if not pins:
            return
        for pin in pins:
            pin.adjust_opacity(delta)
        self.reload_items()

    def select_all_items(self) -> None:
        if self.filtered_pins():
            self.list_widget.selectAll()

    def close_current(self) -> None:
        pin = self.current_pin()
        if pin is None:
            return
        reply = QMessageBox.question(
            self, "确认关闭", f"确认关闭贴图「{pin.name}」吗？",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return
        pin.close()
        QTimer.singleShot(50, self.reload_items)

    def close_selected(self) -> None:
        pins = self.selected_pins()
        if not pins:
            return
        reply = QMessageBox.question(
            self, "确认关闭", f"确认关闭选中的 {len(pins)} 个贴图吗？",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return
        for pin in pins:
            pin.close()
        QTimer.singleShot(50, self.reload_items)

    def close_all(self) -> None:
        pins = self.live_pins()
        if not pins:
            return
        reply = QMessageBox.question(
            self, "确认关闭", f"确认关闭全部 {len(pins)} 个贴图吗？",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return
        for pin in pins:
            pin.close()
        QTimer.singleShot(50, self.reload_items)

    def _handle_key_event(self, event) -> bool:
        ctrl = bool(event.modifiers() & Qt.KeyboardModifier.ControlModifier)
        if event.key() == Qt.Key.Key_Escape:
            self.close()
            return True
        if ctrl and event.key() == Qt.Key.Key_A:
            self.select_all_items()
            return True
        if event.key() in (Qt.Key.Key_Delete, Qt.Key.Key_Backspace):
            if len(self.selected_pins()) > 1:
                self.close_selected()
            else:
                self.close_current()
            return True
        if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            self.focus_current()
            return True
        return False

    def keyPressEvent(self, event) -> None:
        if not self._handle_key_event(event):
            super().keyPressEvent(event)

    def eventFilter(self, obj, event) -> bool:
        if obj is self.list_widget and event.type() == QEvent.Type.KeyPress:
            if self._handle_key_event(event):
                return True
        return super().eventFilter(obj, event)
