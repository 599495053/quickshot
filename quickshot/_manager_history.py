"""历史库窗口：左侧条目列表 + 右侧预览/OCR 编辑/操作。"""

import os
import re
from pathlib import Path
from typing import Dict, List, Optional

from PyQt6.QtCore import QEvent, QSize, QTimer, Qt
from PyQt6.QtGui import QPixmap
from PyQt6.QtWidgets import (
    QAbstractItemView,
    QApplication,
    QComboBox,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QScrollArea,
    QSplitter,
    QVBoxLayout,
    QWidget,
)

from ._manager_delegates import HistoryItemDelegate, build_header_card
from .config import Config
from .history import CaptureHistoryStore
from .pin import show_pin_window
from .preview_scaler import AsyncPreviewScaler
from .theme import manager_extras_stylesheet
from .ui import APP_STYLE, make_card, set_button_role
from .utils import APP_NAME, copy_pixmap_to_clipboard, debug_log, load_app_icon


class HistoryWindow(QWidget):
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

        self.status_label = QLabel("")
        self.status_label.setObjectName("status")

        filter_row = QHBoxLayout()
        filter_row.setContentsMargins(0, 0, 0, 0)
        filter_row.setSpacing(8)
        filter_row.addWidget(self.search_edit, 1)
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
        ocr_layout.setContentsMargins(16, 16, 16, 16)
        ocr_layout.setSpacing(10)

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
        actions_inner.setContentsMargins(16, 16, 16, 16)
        actions_inner.setSpacing(8)
        actions_title = QLabel("快捷操作")
        actions_title.setObjectName("sectionTitle")

        grid = QGridLayout()
        grid.setContentsMargins(0, 0, 0, 0)
        grid.setSpacing(6)
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
        sep.setStyleSheet("color: #d7deea; background: #d7deea; max-width: 1px;")
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
        splitter.setSizes([350, 760])

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
        self.items = self.store.search(
            self.search_edit.text(),
            source,
            tag=tag,
            favorite_only=favorite_only,
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
            pixmap = QPixmap(str(self.store.image_path(item)))
            if not pixmap.isNull():
                thumb = pixmap.scaled(
                    HistoryItemDelegate.THUMB_W,
                    HistoryItemDelegate.THUMB_H,
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation,
                )
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

    def selected_item_ids(self) -> List[str]:
        item_ids: List[str] = []
        for list_item in self.list_widget.selectedItems():
            item_id = str(list_item.data(Qt.ItemDataRole.UserRole) or "")
            if item_id:
                item_ids.append(item_id)
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

    def copy_image(self) -> None:
        if not self.current_pixmap.isNull():
            copy_pixmap_to_clipboard(self.current_pixmap)

    def pin_image(self) -> None:
        if not self.current_pixmap.isNull():
            show_pin_window(self.current_pixmap, self.config)

    def export_image(self) -> None:
        selected_ids = self.selected_item_ids()
        if len(selected_ids) > 1:
            self.export_selected()
            return
        item = self.current_item()
        if item is None or self.current_pixmap.isNull():
            return
        from PyQt6.QtWidgets import QFileDialog

        default_name = str(item.get("filename", "capture.png"))
        default_path = str(Path(self.config.ensure_save_dir()) / default_name)
        filepath, _ = QFileDialog.getSaveFileName(self, "导出历史截图", default_path, "PNG 图片 (*.png)")
        if filepath:
            if not filepath.lower().endswith(".png"):
                filepath += ".png"
            self.current_pixmap.save(filepath, "PNG")

    def export_selected(self) -> None:
        selected_ids = self.selected_item_ids()
        if not selected_ids:
            QMessageBox.information(self, "未选择", "请先选择要导出的历史截图。")
            return

        selected_items = [item for item in self.items if str(item.get("id", "")) in selected_ids]
        if not selected_items:
            QMessageBox.information(self, "未选择", "当前没有可导出的历史截图。")
            return

        from PyQt6.QtWidgets import QFileDialog

        export_dir = QFileDialog.getExistingDirectory(self, "选择批量导出目录", self.config.ensure_save_dir())
        if not export_dir:
            return

        target_dir = Path(export_dir)
        exported = 0
        failed = 0
        for item in selected_items:
            source_path = self.store.image_path(item)
            if not source_path.exists():
                failed += 1
                continue
            target_path = target_dir / str(item.get("filename", "capture.png"))
            if target_path.exists():
                stem = target_path.stem
                suffix = target_path.suffix or ".png"
                index = 2
                while target_path.exists():
                    target_path = target_dir / f"{stem}_{index}{suffix}"
                    index += 1
            try:
                target_path.write_bytes(source_path.read_bytes())
                exported += 1
            except OSError as exc:
                debug_log(f"export copy failed for {source_path}: {exc}")
                failed += 1

        if failed > 0:
            QMessageBox.warning(
                self,
                "导出完成",
                f"已导出 {exported} 张截图，另有 {failed} 张导出失败。",
            )
        else:
            QMessageBox.information(self, "导出完成", f"已导出 {exported} 张截图。")

    def export_all_zip(self) -> None:
        items = self.items
        if not items:
            QMessageBox.information(self, "历史库为空", "当前没有可导出的历史截图。")
            return
        from PyQt6.QtWidgets import QFileDialog
        import zipfile

        default_path = str(Path(self.config.ensure_save_dir()) / "quickshot_history.zip")
        filepath, _ = QFileDialog.getSaveFileName(self, "导出全部历史截图", default_path, "ZIP 压缩包 (*.zip)")
        if not filepath:
            return
        if not filepath.lower().endswith(".zip"):
            filepath += ".zip"
        exported = 0
        failed = 0
        try:
            with zipfile.ZipFile(filepath, "w", zipfile.ZIP_DEFLATED) as zf:
                for item in items:
                    source_path = self.store.image_path(item)
                    if not source_path.exists():
                        failed += 1
                        continue
                    arcname = str(item.get("filename", f"capture_{exported}.png"))
                    try:
                        zf.write(str(source_path), arcname)
                        exported += 1
                    except (OSError, zipfile.BadZipFile) as exc:
                        debug_log(f"zip write failed for {source_path}: {exc}")
                        failed += 1
        except Exception as exc:
            QMessageBox.warning(self, "导出失败", f"创建压缩包失败：{exc}")
            return
        if failed > 0:
            QMessageBox.warning(self, "导出完成", f"已导出 {exported} 张到压缩包，{failed} 张失败。\n{filepath}")
        else:
            QMessageBox.information(self, "导出完成", f"已导出全部 {exported} 张截图到压缩包。\n{filepath}")

    def copy_text(self) -> None:
        text = self.ocr_edit.toPlainText().strip()
        if text:
            QApplication.clipboard().setText(text)

    def ocr_current(self) -> None:
        item = self.current_item()
        if item is None:
            return
        existing_text = str(item.get("ocr_text", "")).strip()
        path = self.store.image_path(item)
        if not path.exists():
            return
        pixmap = QPixmap(str(path))
        if pixmap.isNull():
            return
        from .ocr import OcrJob

        if hasattr(self, "_ocr_job") and self._ocr_job is not None:
            return
        if existing_text:
            self.ocr_edit.setPlainText(existing_text)
            self.ocr_hint.setText("正在重新识别...")
        else:
            self.ocr_edit.setPlainText("正在识别文字，首次使用可能稍慢...")
        self._ocr_job = OcrJob(pixmap.toImage())
        self._ocr_job.succeeded.connect(self._on_ocr_done)
        self._ocr_job.failed.connect(self._on_ocr_failed)
        self._ocr_job.finished.connect(self._on_ocr_finished)
        self._ocr_job.start()

    def _on_ocr_done(self, result) -> None:
        text = (result.text or "").strip()
        engine = result.engine_label or ""
        elapsed = result.elapsed_seconds
        if text:
            self.ocr_edit.setPlainText(text)
            self.ocr_hint.setText(f"识别引擎：{engine}  ·  耗时：{elapsed:.1f}s")
            item = self.current_item()
            if item:
                self.store.update_ocr_text(str(item.get("id", "")), text)
        else:
            note = result.note or "未识别到文字"
            self.ocr_hint.setText(f"{note}（{engine}，{elapsed:.1f}s）")

    def _on_ocr_failed(self, error_text: str) -> None:
        self.ocr_edit.setPlainText(f"识别失败：{error_text}")
        self.ocr_hint.setText("识别失败，请稍后重试")

    def _on_ocr_finished(self) -> None:
        self._ocr_job = None

    def open_current_item(self) -> None:
        self.pin_image()

    def show_stats(self) -> None:
        items = self.store.existing_items()
        total_size = self.store.usage_bytes(items)
        total_size_mb = total_size / (1024 * 1024)
        QMessageBox.information(
            self,
            "历史库统计",
            f"当前截图数量：{len(items)} 张\n占用空间：{total_size_mb:.2f} MB\n保留上限：{self.config.history_limit} 张",
        )

    def open_history_dir(self) -> None:
        path = self.config.ensure_history_dir()
        try:
            os.startfile(path)  # type: ignore[attr-defined]
        except Exception as exc:
            QMessageBox.warning(self, "打开失败", f"无法打开历史目录：{exc}")

    def select_all_items(self) -> None:
        if self.items:
            self.list_widget.selectAll()

    def clear_all(self) -> None:
        if not self.store.existing_items():
            QMessageBox.information(self, "历史库为空", "当前没有可清理的历史截图。")
            return
        result = QMessageBox.question(
            self,
            "清空历史库",
            "确认清空全部历史截图吗？此操作不会影响当前贴图或剪贴板内容。",
        )
        if result != QMessageBox.StandardButton.Yes:
            return
        removed = self.store.clear_all()
        self.reload_items()
        QMessageBox.information(self, "清理完成", f"已清空 {removed} 张历史截图。")

    def delete_selected(self) -> None:
        selected_ids = self.selected_item_ids()
        if not selected_ids:
            QMessageBox.information(self, "未选择", "请先选择要删除的历史截图。")
            return
        result = QMessageBox.question(
            self,
            "删除选中",
            f"确认删除选中的 {len(selected_ids)} 张历史截图吗？",
        )
        if result != QMessageBox.StandardButton.Yes:
            return
        for item_id in selected_ids:
            self.store.delete_item(item_id)
        self.reload_items()
        QMessageBox.information(self, "删除完成", f"已删除 {len(selected_ids)} 张历史截图。")

    def delete_current(self) -> None:
        item_id = self.current_item_id()
        if not item_id:
            return
        result = QMessageBox.question(
            self,
            "删除当前",
            "确认删除当前历史截图吗？",
        )
        if result != QMessageBox.StandardButton.Yes:
            return
        self.store.delete_item(item_id)
        self.reload_items()

    def toggle_favorite(self) -> None:
        """切换当前项的收藏状态。"""
        item_id = self.current_item_id()
        if not item_id:
            return
        is_fav = self.store.toggle_favorite(item_id)
        self.favorite_btn.setText("取消收藏" if is_fav else "收藏")
        self.reload_items()

    def manage_tags(self) -> None:
        """管理当前项的标签。"""
        item_id = self.current_item_id()
        if not item_id:
            return
        item = self.current_item()
        if not item:
            return
        tags = item.get("tags", [])
        from PyQt6.QtWidgets import QInputDialog
        tag, ok = QInputDialog.getText(self, "添加标签", "输入标签名（留空查看现有标签）：")
        if not ok:
            return
        if tag.strip():
            self.store.add_tag(item_id, tag.strip())
            self.reload_items()
        elif tags:
            items = [f"• {t}" for t in tags]
            QMessageBox.information(self, "当前标签", "\n".join(items) if items else "暂无标签")

    def batch_tag_selected(self) -> None:
        """批量为选中项添加标签。"""
        selected_ids = self.selected_item_ids()
        if not selected_ids:
            QMessageBox.information(self, "未选择", "请先选择要添加标签的历史截图。")
            return
        from PyQt6.QtWidgets import QInputDialog
        tag, ok = QInputDialog.getText(self, "批量添加标签", f"为 {len(selected_ids)} 张截图添加标签：")
        if not ok or not tag.strip():
            return
        for item_id in selected_ids:
            self.store.add_tag(item_id, tag.strip())
        self.reload_items()
        QMessageBox.information(self, "添加完成", f"已为 {len(selected_ids)} 张截图添加标签：{tag.strip()}")

    def _handle_key_event(self, event) -> bool:
        if event.key() == Qt.Key.Key_Escape:
            self.close()
            return True
        ctrl = bool(event.modifiers() & Qt.KeyboardModifier.ControlModifier)
        if ctrl and event.key() == Qt.Key.Key_A:
            self.select_all_items()
            return True
        if event.key() in (Qt.Key.Key_Delete, Qt.Key.Key_Backspace):
            if len(self.selected_item_ids()) > 1:
                self.delete_selected()
            else:
                self.delete_current()
            return True
        if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            self.open_current_item()
            return True
        return False

    def keyPressEvent(self, event) -> None:
        focus = self.focusWidget()
        if isinstance(focus, (QLineEdit, QPlainTextEdit)):
            super().keyPressEvent(event)
            return
        if not self._handle_key_event(event):
            super().keyPressEvent(event)

    def eventFilter(self, obj, event) -> bool:
        if obj is self.list_widget and event.type() == QEvent.Type.KeyPress:
            if self._handle_key_event(event):
                return True
        if hasattr(self, "_preview_scroll") and obj is self._preview_scroll.viewport() and event.type() == QEvent.Type.Wheel:
            if self.current_pixmap.isNull():
                return False
            delta = event.angleDelta().y()
            if delta > 0:
                self._zoom_in()
            elif delta < 0:
                self._zoom_out()
            return True
        return super().eventFilter(obj, event)

    def on_ocr_text_changed(self) -> None:
        if self._loading_ocr:
            return
        self._ocr_debounce.start()

    def _flush_ocr_text(self) -> None:
        self.store.update_ocr_text(self.current_item_id(), self.ocr_edit.toPlainText())

    def clean_lines(self) -> None:
        lines = [line.strip() for line in self.ocr_edit.toPlainText().splitlines()]
        self.ocr_edit.setPlainText("\n".join(line for line in lines if line))

    def clean_soft(self) -> None:
        lines = [line.strip() for line in self.ocr_edit.toPlainText().splitlines()]
        normalized = []
        for line in lines:
            if not line:
                continue
            normalized.append(" ".join(line.split()))
        self.ocr_edit.setPlainText("\n".join(normalized))

    def clean_hard(self) -> None:
        text = self.ocr_edit.toPlainText().replace("\t", " ")
        lines = []
        for line in text.splitlines():
            compact = " ".join(line.split())
            if compact:
                lines.append(compact)
        self.ocr_edit.setPlainText(" ".join(lines))

    def search_ocr_text(self) -> None:
        import urllib.parse
        import webbrowser
        text = self.ocr_edit.toPlainText().strip()
        if not text:
            self.ocr_hint.setText("没有可搜索的文本")
            return
        url = f"https://www.baidu.com/s?wd={urllib.parse.quote(text)}"
        try:
            webbrowser.open(url)
        except Exception as exc:
            self.ocr_hint.setText(f"打开浏览器失败：{exc}")

    def translate_ocr_text(self) -> None:
        text = self.ocr_edit.toPlainText().strip()
        if not text:
            self.ocr_hint.setText("没有可翻译的文本")
            return

        sender = self.sender()
        if sender:
            sender.setEnabled(False)
            sender.setText("翻译中…")
        self.ocr_hint.setText("正在翻译，请稍候…")

        from .translator import TranslateJob

        self._translate_job = TranslateJob(text, parent=self)
        self._translate_job.succeeded.connect(self._on_translate_succeeded)
        self._translate_job.failed.connect(self._on_translate_failed)
        self._translate_job.finished.connect(lambda: self._on_translate_finished(sender))
        self._translate_job.start()

    def _on_translate_succeeded(self, result: str) -> None:
        self.translate_edit.setPlainText(result)
        self.translate_title.show()
        self.translate_edit.show()
        self._translate_copy_btn.show()
        self.ocr_hint.setText("翻译完成")

    def _on_translate_failed(self, error: str) -> None:
        self.ocr_hint.setText(error)

    def _on_translate_finished(self, button) -> None:
        if button:
            button.setEnabled(True)
            button.setText("翻译")

    def copy_translation(self) -> None:
        text = self.translate_edit.toPlainText().strip()
        if text:
            QApplication.clipboard().setText(text)
            self.ocr_hint.setText("已复制翻译结果")

    def edit_current(self) -> None:
        if self.current_pixmap.isNull():
            return
        if hasattr(self, "_reedit_callback") and self._reedit_callback:
            self._reedit_callback(self.current_pixmap.copy())
