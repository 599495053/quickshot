"""历史库窗口：左侧条目列表 + 右侧预览/OCR 编辑/操作。"""

import re
from typing import Dict, List, Optional

from PyQt6.QtCore import QSize, QTimer, Qt
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
    QPlainTextEdit,
    QPushButton,
    QScrollArea,
    QSplitter,
    QVBoxLayout,
    QWidget,
)

from ._manager_delegates import HistoryItemDelegate, build_header_card
from ._manager_history_actions import HistoryActions
from .config import Config
from .history import CaptureHistoryStore
from .preview_scaler import AsyncPreviewScaler
from .theme import manager_extras_stylesheet
from .ui import APP_STYLE, make_card, set_button_role
from .utils import APP_NAME, load_app_icon


class HistoryWindow(HistoryActions, QWidget):
    SOURCE_LABELS = {
        "all": "全部",
        "capture": "截图",
        "copy": "复制",
        "ocr": "识文",
    }

    def __init__(self, store: CaptureHistoryStore, config: Config) -> None:
        super().__init__()
        self.store = store
        self.config = config
        self.items: List[Dict[str, object]] = []
        self.current_pixmap = QPixmap()
        self._preview_zoom = 0.0  # 0=适应窗口, >0=缩放比例
        self._loading_ocr = False
        self._ocr_debounce = QTimer(self)
        self._ocr_debounce.setSingleShot(True)
        self._ocr_debounce.setInterval(400)
        self._ocr_debounce.timeout.connect(self._flush_ocr_text)

        self._search_debounce = QTimer(self)
        self._search_debounce.setSingleShot(True)
        self._search_debounce.setInterval(300)
        self._search_debounce.timeout.connect(self.reload_items)
        self._reedit_callback = None

        self._preview_scaler = AsyncPreviewScaler(self)
        self._preview_scaler.ready.connect(self._on_preview_ready)

        # 缩略图 LRU 缓存：id -> QPixmap，避免每次搜索/筛选都从磁盘重新加载
        self._thumb_cache: Dict[str, QPixmap] = {}
        self._thumb_cache_max = 300

        self.setWindowTitle(f"{APP_NAME} 历史库")
        self.setWindowIcon(load_app_icon())
        self.resize(1160, 760)

        header_card = build_header_card(
            "历史库",
            "按来源和关键词快速筛选截图，右侧可预览并直接补充 OCR 文本。",
        )

        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText("搜索时间、文件名、OCR 文本")
        self.search_edit.textChanged.connect(self._search_debounce.start)

        self.source_filter = QComboBox()
        self.source_filter.addItem("全部来源", "all")
        self.source_filter.addItem("截图", "capture")
        self.source_filter.addItem("复制", "copy")
        self.source_filter.addItem("识文", "ocr")
        self.source_filter.addItem("收藏", "favorite")
        self.source_filter.currentIndexChanged.connect(self.reload_items)

        self.tag_filter = QComboBox()
        self.tag_filter.addItem("全部标签", "")
        self.tag_filter.currentIndexChanged.connect(self.reload_items)

        self.time_filter = QComboBox()
        self.time_filter.addItem("全部时间", "all")
        self.time_filter.addItem("今天", "today")
        self.time_filter.addItem("本周", "week")
        self.time_filter.addItem("本月", "month")
        self.time_filter.currentIndexChanged.connect(self.reload_items)

        self.status_label = QLabel("")
        self.status_label.setObjectName("status")

        filter_row = QHBoxLayout()
        filter_row.setContentsMargins(0, 0, 0, 0)
        filter_row.setSpacing(8)
        filter_row.addWidget(self.search_edit, 1)
        filter_row.addWidget(self.time_filter)
        filter_row.addWidget(self.source_filter)
        filter_row.addWidget(self.tag_filter)

        self.list_widget = QListWidget()
        self.list_widget.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.list_widget.setItemDelegate(HistoryItemDelegate(self.list_widget))
        self.list_widget.setSpacing(2)
        self.list_widget.currentRowChanged.connect(self.on_selection_changed)
        self.list_widget.itemSelectionChanged.connect(self.update_status_label)
        self.list_widget.itemActivated.connect(lambda _item: self.open_current_item())
        self.list_widget.installEventFilter(self)

        left_card = make_card()
        left_layout = QVBoxLayout()
        left_layout.setContentsMargins(14, 14, 14, 14)
        left_layout.setSpacing(9)
        left_layout.addLayout(filter_row)
        left_layout.addWidget(self.status_label)
        left_layout.addWidget(self.list_widget, 1)
        left_card.setLayout(left_layout)

        preview_card = make_card()
        preview_layout = QVBoxLayout()
        preview_layout.setContentsMargins(16, 15, 16, 16)
        preview_layout.setSpacing(9)
        preview_title_row = QHBoxLayout()
        preview_title_row.setContentsMargins(0, 0, 0, 0)
        preview_title_row.setSpacing(8)
        preview_title = QLabel("截图预览")
        preview_title.setObjectName("sectionTitle")
        preview_title_row.addWidget(preview_title)
        preview_title_row.addStretch(1)
        zoom_fit_btn = set_button_role(QPushButton("适应"), compact=True)
        zoom_fit_btn.clicked.connect(lambda: self._set_preview_zoom(0.0))
        zoom_orig_btn = set_button_role(QPushButton("原始"), compact=True)
        zoom_orig_btn.clicked.connect(self._zoom_original)
        zoom_in_btn = set_button_role(QPushButton("放大"), compact=True)
        zoom_in_btn.clicked.connect(self._zoom_in)
        zoom_out_btn = set_button_role(QPushButton("缩小"), compact=True)
        zoom_out_btn.clicked.connect(self._zoom_out)
        self._zoom_label = QLabel("")
        self._zoom_label.setObjectName("meta")
        preview_title_row.addWidget(self._zoom_label)
        preview_title_row.addWidget(zoom_fit_btn)
        preview_title_row.addWidget(zoom_orig_btn)
        preview_title_row.addWidget(zoom_in_btn)
        preview_title_row.addWidget(zoom_out_btn)
        self.meta_label = QLabel("")
        self.meta_label.setObjectName("meta")
        self.meta_label.setWordWrap(True)

        self.preview_label = QLabel("暂无历史截图")
        self.preview_label.setObjectName("preview")
        self.preview_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.preview_label.setMinimumSize(420, 300)

        preview_scroll = QScrollArea()
        preview_scroll.setWidgetResizable(False)
        preview_scroll.setFrameShape(QFrame.Shape.NoFrame)
        preview_scroll.setWidget(self.preview_label)
        preview_scroll.viewport().installEventFilter(self)
        self._preview_scroll = preview_scroll

        preview_layout.addLayout(preview_title_row)
        preview_layout.addWidget(self.meta_label)
        preview_layout.addWidget(preview_scroll, 1)
        preview_card.setLayout(preview_layout)

        ocr_card = make_card()
        ocr_layout = QVBoxLayout()
        ocr_layout.setContentsMargins(16, 15, 16, 16)
        ocr_layout.setSpacing(9)

        ocr_title_row = QHBoxLayout()
        ocr_title_row.setContentsMargins(0, 0, 0, 0)
        ocr_title_row.setSpacing(8)
        ocr_title = QLabel("OCR 文本")
        ocr_title.setObjectName("sectionTitle")
        self.ocr_hint = QLabel("识别文本可在这里补充或修正，内容会自动保存。")
        self.ocr_hint.setObjectName("helper")
        self.ocr_hint.setWordWrap(True)
        ocr_title_row.addWidget(ocr_title)
        ocr_title_row.addStretch(1)
        clean_btn = set_button_role(QPushButton("整理空行"), compact=True)
        clean_btn.clicked.connect(self.clean_lines)
        clean_soft_btn = set_button_role(QPushButton("轻清洗"), compact=True)
        clean_soft_btn.clicked.connect(self.clean_soft)
        clean_hard_btn = set_button_role(QPushButton("强清洗"), compact=True)
        clean_hard_btn.clicked.connect(self.clean_hard)
        search_btn = set_button_role(QPushButton("搜索"), compact=True)
        search_btn.clicked.connect(self.search_ocr_text)
        translate_btn = set_button_role(QPushButton("翻译"), compact=True)
        translate_btn.clicked.connect(self.translate_ocr_text)
        ocr_title_row.addWidget(clean_btn)
        ocr_title_row.addWidget(clean_soft_btn)
        ocr_title_row.addWidget(clean_hard_btn)
        ocr_title_row.addWidget(search_btn)
        ocr_title_row.addWidget(translate_btn)

        self.ocr_edit = QPlainTextEdit()
        self.ocr_edit.setPlaceholderText("OCR 文本会显示在这里，也可以手动补充后保存")
        self.ocr_edit.textChanged.connect(self.on_ocr_text_changed)

        self.translate_title = QLabel("翻译结果")
        self.translate_title.setObjectName("sectionTitle")
        self.translate_title.hide()
        self.translate_edit = QPlainTextEdit()
        self.translate_edit.setReadOnly(True)
        self.translate_edit.setPlaceholderText("翻译结果将显示在这里")
        self.translate_edit.hide()
        translate_copy_btn = set_button_role(QPushButton("复制译文"), compact=True)
        translate_copy_btn.clicked.connect(self.copy_translation)
        translate_copy_btn.hide()
        self._translate_copy_btn = translate_copy_btn

        copy_image_btn = set_button_role(QPushButton("复制图片"))
        copy_image_btn.clicked.connect(self.copy_image)
        pin_btn = set_button_role(QPushButton("贴图"), "primary")
        pin_btn.clicked.connect(self.pin_image)
        export_btn = set_button_role(QPushButton("导出"))
        export_btn.clicked.connect(self.export_image)
        copy_text_btn = set_button_role(QPushButton("复制文本"))
        copy_text_btn.clicked.connect(self.copy_text)
        ocr_btn = set_button_role(QPushButton("识文"))
        ocr_btn.clicked.connect(self.ocr_current)
        stats_btn = set_button_role(QPushButton("统计"), compact=True)
        stats_btn.clicked.connect(self.show_stats)
        open_dir_btn = set_button_role(QPushButton("打开目录"), compact=True)
        open_dir_btn.clicked.connect(self.open_history_dir)
        select_all_btn = set_button_role(QPushButton("全选"), compact=True)
        select_all_btn.clicked.connect(self.select_all_items)
        clear_all_btn = set_button_role(QPushButton("清空全部"), "destructive", True)
        clear_all_btn.clicked.connect(self.clear_all)
        delete_selected_btn = set_button_role(QPushButton("删除选中"), "destructive", True)
        delete_selected_btn.clicked.connect(self.delete_selected)
        delete_btn = set_button_role(QPushButton("删除当前"), "destructive", True)
        delete_btn.clicked.connect(self.delete_current)
        refresh_btn = set_button_role(QPushButton("刷新"), compact=True)
        refresh_btn.clicked.connect(self.reload_items)
        export_all_btn = set_button_role(QPushButton("导出压缩包"), compact=True)
        export_all_btn.clicked.connect(self.export_all_zip)
        edit_btn = set_button_role(QPushButton("编辑"), "primary", True)
        edit_btn.clicked.connect(self.edit_current)
        self.favorite_btn = set_button_role(QPushButton("收藏"), compact=True)
        self.favorite_btn.clicked.connect(self.toggle_favorite)
        tag_btn = set_button_role(QPushButton("标签"), compact=True)
        tag_btn.clicked.connect(self.manage_tags)
        batch_tag_btn = set_button_role(QPushButton("批量标签"), compact=True)
        batch_tag_btn.clicked.connect(self.batch_tag_selected)

        ocr_layout.addLayout(ocr_title_row)
        ocr_layout.addWidget(self.ocr_hint)
        ocr_layout.addWidget(self.ocr_edit, 1)
        ocr_layout.addWidget(self.translate_title)
        ocr_layout.addWidget(self.translate_edit, 1)
        ocr_layout.addWidget(self._translate_copy_btn)
        ocr_card.setLayout(ocr_layout)

        actions_card = make_card()
        actions_inner = QVBoxLayout()
        actions_inner.setContentsMargins(16, 14, 16, 15)
        actions_inner.setSpacing(8)
        actions_title = QLabel("快捷操作")
        actions_title.setObjectName("sectionTitle")

        grid = QGridLayout()
        grid.setContentsMargins(0, 0, 0, 0)
        grid.setHorizontalSpacing(7)
        grid.setVerticalSpacing(7)
        grid.addWidget(copy_image_btn,     0, 0)
        grid.addWidget(pin_btn,            0, 1)
        grid.addWidget(export_btn,         0, 2)
        grid.addWidget(copy_text_btn,      0, 3)
        grid.addWidget(self.favorite_btn,  0, 4)
        grid.addWidget(select_all_btn,     0, 5)
        grid.addWidget(delete_btn,         0, 6)
        grid.addWidget(delete_selected_btn,0, 7)
        grid.addWidget(clear_all_btn,      0, 8)
        grid.addWidget(stats_btn,          1, 0)
        grid.addWidget(open_dir_btn,       1, 1)
        grid.addWidget(ocr_btn,            1, 2)
        grid.addWidget(refresh_btn,        1, 3)
        grid.addWidget(tag_btn,            1, 4)
        grid.addWidget(batch_tag_btn,      1, 5)
        grid.addWidget(edit_btn,           1, 6)
        grid.addWidget(export_all_btn,     1, 7, 1, 2)

        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.VLine)
        sep.setStyleSheet("color: #e5e7eb; background: #e5e7eb; max-width: 1px;")
        grid.addWidget(sep, 0, 4, 2, 1)

        actions_inner.addWidget(actions_title)
        actions_inner.addLayout(grid)
        actions_card.setLayout(actions_inner)

        right_panel = QWidget()
        right_layout = QVBoxLayout()
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(12)
        right_layout.addWidget(preview_card, 3)
        right_layout.addWidget(ocr_card, 2)
        right_layout.addWidget(actions_card)
        right_panel.setLayout(right_layout)

        splitter = QSplitter()
        splitter.addWidget(left_card)
        splitter.addWidget(right_panel)
        splitter.setSizes([370, 760])

        layout = QVBoxLayout()
        layout.setContentsMargins(18, 16, 18, 18)
        layout.setSpacing(12)
        layout.addWidget(header_card)
        layout.addWidget(splitter, 1)
        self.setLayout(layout)
        self.apply_style()
        self._setup_keyboard_shortcuts()
        self.reload_items()

    def _setup_keyboard_shortcuts(self) -> None:
        """设置键盘快捷键。"""
        from PyQt6.QtGui import QShortcut, QKeySequence

        # Ctrl+C - 复制选中图片
        copy_shortcut = QShortcut(QKeySequence("Ctrl+C"), self)
        copy_shortcut.activated.connect(self.copy_current_image)

        # Ctrl+O - 运行 OCR
        ocr_shortcut = QShortcut(QKeySequence("Ctrl+O"), self)
        ocr_shortcut.activated.connect(self.run_ocr_on_current)

        # F2 - 添加标签（聚焦到标签输入框）
        rename_shortcut = QShortcut(QKeySequence("F2"), self)
        rename_shortcut.activated.connect(self.focus_tag_input)

        # Space - 切换收藏状态
        fav_shortcut = QShortcut(QKeySequence("Space"), self)
        fav_shortcut.activated.connect(self.toggle_favorite_current)

        # Delete - 删除选中（已有）
        # Escape - 关闭窗口（已有）
        # Ctrl+A - 全选（已有）
        # Enter - 打开详情（已有）

    def focus_tag_input(self) -> None:
        """聚焦到标签输入框，方便用户添加标签。"""
        # 如果有标签输入框，聚焦它；否则显示提示
        if hasattr(self, 'tag_edit') and self.tag_edit:
            self.tag_edit.setFocus()
            self.tag_edit.selectAll()

    def copy_current_image(self) -> None:
        """复制当前选中的图片到剪贴板。"""
        item = self.current_item()
        if not item:
            return
        from PyQt6.QtGui import QPixmap
        pixmap = QPixmap(str(self.store.image_path(item)))
        if not pixmap.isNull():
            from .utils import copy_pixmap_to_clipboard
            copy_pixmap_to_clipboard(pixmap)

    def run_ocr_on_current(self) -> None:
        """对当前选中项运行 OCR。"""
        item = self.current_item()
        if not item:
            return
        self.run_ocr_on_item(item)

    def toggle_favorite_current(self) -> None:
        """切换当前项的收藏状态。"""
        item = self.current_item()
        if not item:
            return
        item_id = str(item.get("id", ""))
        if item_id:
            new_state = self.store.toggle_favorite(item_id)
            self.favorite_btn.setText("已收藏" if new_state else "收藏")
            self.update_status_label()

    def apply_style(self) -> None:
        self.setStyleSheet(APP_STYLE + manager_extras_stylesheet())

    def item_title(self, item: Dict[str, object]) -> str:
        created = str(item.get("created_at", "")).replace("T", " ")
        size = f"{item.get('width', '')} × {item.get('height', '')}"
        source = self.SOURCE_LABELS.get(str(item.get("source", "capture")), str(item.get("source", "capture")))
        query = self.search_edit.text().strip()
        hint = self.item_match_hint(item, query)
        lines = [f"{created}    [{source}]", size]
        if hint:
            lines.append(hint)
        return "\n".join(lines)

    def item_match_hint(self, item: Dict[str, object], query: str) -> str:
        if not query:
            ocr_text = str(item.get("ocr_text", "")).strip()
            if ocr_text:
                preview = re.sub(r"\s+", " ", ocr_text)
                return preview[:42] + ("..." if len(preview) > 42 else "")
            return ""

        keyword = query.lower()
        ocr_text = re.sub(r"\s+", " ", str(item.get("ocr_text", "")).strip())
        filename = str(item.get("filename", "")).strip()
        for text in (ocr_text, filename):
            if not text:
                continue
            index = text.lower().find(keyword)
            if index < 0:
                continue
            start = max(0, index - 10)
            end = min(len(text), index + len(query) + 18)
            snippet = text[start:end].strip()
            if start > 0:
                snippet = "..." + snippet
            if end < len(text):
                snippet = snippet + "..."
            return snippet
        return ""

    def reload_items(self) -> None:
        current_id = self.current_item_id()
        source = str(self.source_filter.currentData() or "all")
        favorite_only = source == "favorite"
        if favorite_only:
            source = "all"
        tag = str(self.tag_filter.currentData() or "")
        time_range = str(self.time_filter.currentData() or "all")
        self.items = self.store.search(
            self.search_edit.text(),
            source,
            tag=tag,
            favorite_only=favorite_only,
            time_range=time_range,
        )
        self._refresh_tag_filter()
        self.list_widget.setUpdatesEnabled(False)
        self.list_widget.blockSignals(True)
        try:
            self.list_widget.clear()
            select_row = 0
            query = self.search_edit.text().strip()
            for row, item in enumerate(self.items):
                list_item = QListWidgetItem("")
                list_item.setData(Qt.ItemDataRole.UserRole, item.get("id", ""))
                list_item.setToolTip(str(self.store.image_path(item)))
                list_item.setSizeHint(QSize(0, HistoryItemDelegate.ITEM_H))
                created = str(item.get("created_at", "")).replace("T", " ")
                source = self.SOURCE_LABELS.get(str(item.get("source", "capture")), str(item.get("source", "capture")))
                size = f"{item.get('width', '')} × {item.get('height', '')}"
                ocr_text = str(item.get("ocr_text", "")).strip()
                ocr_hint = self.item_match_hint(item, query) if query else (ocr_text[:60] + "..." if len(ocr_text) > 60 else ocr_text)
                list_item.setData(Qt.ItemDataRole.UserRole + 2, created)
                list_item.setData(Qt.ItemDataRole.UserRole + 3, source)
                list_item.setData(Qt.ItemDataRole.UserRole + 4, size)
                list_item.setData(Qt.ItemDataRole.UserRole + 5, ocr_hint)
                self.list_widget.addItem(list_item)
                if current_id and item.get("id") == current_id:
                    select_row = row
        finally:
            self.list_widget.blockSignals(False)
            self.list_widget.setUpdatesEnabled(True)
        self.update_status_label()
        if self.items:
            self.list_widget.setCurrentRow(min(select_row, len(self.items) - 1))
            self._start_thumbnail_loading()
        else:
            self.current_pixmap = QPixmap()
            if self.search_edit.text().strip() or str(self.source_filter.currentData() or "all") != "all":
                self.preview_label.setText("没有匹配的历史截图")
            else:
                self.preview_label.setText("暂无历史截图")
            self.preview_label.setPixmap(QPixmap())
            self.meta_label.setText("")
            self.ocr_edit.setPlainText("")

    def _refresh_tag_filter(self) -> None:
        """刷新标签筛选下拉框，保留当前选择。"""
        current_tag = str(self.tag_filter.currentData() or "")
        self.tag_filter.blockSignals(True)
        self.tag_filter.clear()
        self.tag_filter.addItem("全部标签", "")
        all_tags = set()
        for item in self.items:
            for tag in item.get("tags", []):
                all_tags.add(tag)
        for tag in sorted(all_tags):
            self.tag_filter.addItem(tag, tag)
        # 恢复选择
        if current_tag:
            for i in range(self.tag_filter.count()):
                if self.tag_filter.itemData(i) == current_tag:
                    self.tag_filter.setCurrentIndex(i)
                    break
        self.tag_filter.blockSignals(False)

    def _start_thumbnail_loading(self) -> None:
        self._thumb_load_index = 0
        self._thumb_load_batch_size = 20
        QTimer.singleShot(0, self._load_thumbnail_batch)

    def _load_thumbnail_batch(self) -> None:
        start = self._thumb_load_index
        end = min(start + self._thumb_load_batch_size, self.list_widget.count())
        for row in range(start, end):
            if row >= len(self.items):
                break
            item = self.items[row]
            list_item = self.list_widget.item(row)
            if list_item is None or list_item.data(Qt.ItemDataRole.UserRole + 1) is not None:
                continue
            item_id = str(item.get("id", ""))
            thumb = self._thumb_cache.get(item_id)
            if thumb is None:
                pixmap = QPixmap(str(self.store.image_path(item)))
                if not pixmap.isNull():
                    thumb = pixmap.scaled(
                        HistoryItemDelegate.THUMB_W,
                        HistoryItemDelegate.THUMB_H,
                        Qt.AspectRatioMode.KeepAspectRatio,
                        Qt.TransformationMode.SmoothTransformation,
                    )
                    # LRU 缓存：超出上限时淘汰最旧的条目
                    if len(self._thumb_cache) >= self._thumb_cache_max:
                        try:
                            self._thumb_cache.pop(next(iter(self._thumb_cache)))
                        except StopIteration:
                            pass
                    self._thumb_cache[item_id] = thumb
            if thumb is not None:
                list_item.setData(Qt.ItemDataRole.UserRole + 1, thumb)
                list_item.setSizeHint(QSize(0, HistoryItemDelegate.ITEM_H))
        self._thumb_load_index = end
        if end < self.list_widget.count():
            QTimer.singleShot(0, self._load_thumbnail_batch)

    def update_status_label(self) -> None:
        source_key = str(self.source_filter.currentData() or "all")
        source_text = self.SOURCE_LABELS.get(source_key, source_key)
        query = self.search_edit.text().strip()
        selected_count = len(self.selected_item_ids())
        parts = [f"当前显示 {len(self.items)} 项", f"来源：{source_text}"]
        if query:
            parts.append(f"关键词：{query}")
        if selected_count:
            parts.append(f"已选 {selected_count} 项")
        self.status_label.setText("  ·  ".join(parts))

    def current_item_id(self) -> str:
        row = self.list_widget.currentRow()
        if 0 <= row < len(self.items):
            return str(self.items[row].get("id", ""))
        return ""

    def current_item(self) -> Optional[Dict[str, object]]:
        row = self.list_widget.currentRow()
        if 0 <= row < len(self.items):
            return self.items[row]
        return None

    def selected_item_ids(self) -> set:
        item_ids: set = set()
        for list_item in self.list_widget.selectedItems():
            item_id = str(list_item.data(Qt.ItemDataRole.UserRole) or "")
            if item_id:
                item_ids.add(item_id)
        return item_ids

    def on_selection_changed(self, row: int) -> None:
        self.update_status_label()
        if row < 0 or row >= len(self.items):
            return
        self._preview_zoom = 0.0
        item = self.items[row]
        image_path = self.store.image_path(item)
        self.current_pixmap = QPixmap(str(image_path))
        if self.current_pixmap.isNull():
            self.preview_label.setPixmap(QPixmap())
            self.preview_label.setText("图片文件不存在")
        else:
            self.update_preview()
        created = str(item.get("created_at", "")).replace("T", " ")
        tags = item.get("tags", [])
        tag_str = f"  标签: {', '.join(tags)}" if tags else ""
        fav_str = "  ★收藏" if item.get("favorite", False) else ""
        self.meta_label.setText(
            f"{created}    {item.get('width', '')} × {item.get('height', '')}{fav_str}{tag_str}\n{image_path}"
        )
        self.favorite_btn.setText("取消收藏" if item.get("favorite", False) else "收藏")
        self._loading_ocr = True
        self.ocr_edit.setPlainText(str(item.get("ocr_text", "")))
        self._loading_ocr = False

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self.update_preview()

    def update_preview(self) -> None:
        if self.current_pixmap.isNull():
            self._preview_scaler.cancel()
            self.preview_label.setText("暂无历史截图")
            self.preview_label.setPixmap(QPixmap())
            self._zoom_label.setText("")
            return
        orig_w = self.current_pixmap.width()
        orig_h = self.current_pixmap.height()
        if self._preview_zoom == 0.0:
            vp = self._preview_scroll.viewport().size()
            target_w = max(1, vp.width())
            target_h = max(1, vp.height())
            scale = min(target_w / max(1, orig_w), target_h / max(1, orig_h))
            display_w = max(1, int(orig_w * scale))
            display_h = max(1, int(orig_h * scale))
            self.preview_label.setMinimumSize(420, 300)
        else:
            scale = self._preview_zoom
            display_w = max(1, int(orig_w * scale))
            display_h = max(1, int(orig_h * scale))
            self.preview_label.setMinimumSize(1, 1)

        self.preview_label.setText("")
        self.preview_label.setFixedSize(display_w, display_h)
        self._preview_scaler.request(
            self.current_pixmap.toImage(),
            display_w,
            display_h,
            Qt.AspectRatioMode.IgnoreAspectRatio,
        )

        pct = int(scale * 100)
        self._zoom_label.setText(f"{pct}%")

    def _on_preview_ready(self, pixmap: QPixmap) -> None:
        if pixmap.isNull():
            return
        self.preview_label.setPixmap(pixmap)

    def _set_preview_zoom(self, zoom: float) -> None:
        self._preview_zoom = zoom
        self.update_preview()

    def _zoom_original(self) -> None:
        if self.current_pixmap.isNull():
            return
        vp = self._preview_scroll.viewport().size()
        fit_scale = min(vp.width() / max(1, self.current_pixmap.width()),
                        vp.height() / max(1, self.current_pixmap.height()))
        self._preview_zoom = max(1.0, fit_scale)
        self.update_preview()

    def _zoom_in(self) -> None:
        if self.current_pixmap.isNull():
            return
        if self._preview_zoom == 0.0:
            vp = self._preview_scroll.viewport().size()
            fit_scale = min(vp.width() / max(1, self.current_pixmap.width()),
                            vp.height() / max(1, self.current_pixmap.height()))
            self._preview_zoom = fit_scale
        self._preview_zoom = min(8.0, self._preview_zoom * 1.25)
        self.update_preview()

    def _zoom_out(self) -> None:
        if self.current_pixmap.isNull():
            return
        if self._preview_zoom == 0.0:
            return
        self._preview_zoom = max(0.05, self._preview_zoom / 1.25)
        if self._preview_zoom < 0.06:
            self._preview_zoom = 0.0
        self.update_preview()
