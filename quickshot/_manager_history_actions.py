"""HistoryActions — 历史库操作 mixin：导出/删除/收藏/标签/OCR/翻译/清洗。"""

from __future__ import annotations

import os
from pathlib import Path

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QApplication, QFileDialog, QMessageBox

from .pin import show_pin_window
from .utils import copy_pixmap_to_clipboard, debug_log


class HistoryActions:
    """HistoryWindow 的操作方法 mixin。"""

    # ── 基础操作 ──

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
            QMessageBox.warning(self, "导出完成", f"已导出 {exported} 张截图，另有 {failed} 张导出失败。")
        else:
            QMessageBox.information(self, "导出完成", f"已导出 {exported} 张截图。")

    def export_all_zip(self) -> None:
        items = self.items
        if not items:
            QMessageBox.information(self, "历史库为空", "当前没有可导出的历史截图。")
            return
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

    # ── 文本操作 ──

    def copy_text(self) -> None:
        text = self.ocr_edit.toPlainText().strip()
        if text:
            QApplication.clipboard().setText(text)

    # ── OCR ──

    def ocr_current(self) -> None:
        from PyQt6.QtGui import QPixmap as QPix
        item = self.current_item()
        if item is None:
            return
        existing_text = str(item.get("ocr_text", "")).strip()
        path = self.store.image_path(item)
        if not path.exists():
            return
        pixmap = QPix(str(path))
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

    def _cleanup_jobs(self) -> None:
        """窗口关闭时清理异步任务，防止信号持有已销毁窗口引用。"""
        if hasattr(self, "_ocr_job") and self._ocr_job is not None:
            try:
                self._ocr_job.succeeded.disconnect()
                self._ocr_job.failed.disconnect()
                self._ocr_job.finished.disconnect()
            except Exception:
                pass
            self._ocr_job = None
        if hasattr(self, "_translate_job") and self._translate_job is not None:
            try:
                self._translate_job.succeeded.disconnect()
                self._translate_job.failed.disconnect()
                self._translate_job.finished.disconnect()
            except Exception:
                pass
            self._translate_job = None

    # ── 窗口事件 ──

    def closeEvent(self, event) -> None:
        self._cleanup_jobs()
        super().closeEvent(event)

    # ── 管理操作 ──

    def open_current_item(self) -> None:
        self.pin_image()

    def show_stats(self) -> None:
        items = self.store.existing_items()
        total_size = self.store.usage_bytes(items)
        total_size_mb = total_size / (1024 * 1024)
        QMessageBox.information(
            self, "历史库统计",
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
        result = QMessageBox.question(self, "清空历史库", "确认清空全部历史截图吗？此操作不会影响当前贴图或剪贴板内容。")
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
        result = QMessageBox.question(self, "删除选中", f"确认删除选中的 {len(selected_ids)} 张历史截图吗？")
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
        result = QMessageBox.question(self, "删除当前", "确认删除当前历史截图吗？")
        if result != QMessageBox.StandardButton.Yes:
            return
        self.store.delete_item(item_id)
        self.reload_items()

    def toggle_favorite(self) -> None:
        item_id = self.current_item_id()
        if not item_id:
            return
        is_fav = self.store.toggle_favorite(item_id)
        self.favorite_btn.setText("取消收藏" if is_fav else "收藏")
        self.reload_items()

    def manage_tags(self) -> None:
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

    # ── 键盘 ──

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
        from PyQt6.QtWidgets import QLineEdit, QPlainTextEdit
        focus = self.focusWidget()
        if isinstance(focus, (QLineEdit, QPlainTextEdit)):
            super().keyPressEvent(event)
            return
        if not self._handle_key_event(event):
            super().keyPressEvent(event)

    def eventFilter(self, obj, event) -> bool:
        from PyQt6.QtCore import QEvent
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

    # ── OCR 文本面板 ──

    def on_ocr_text_changed(self) -> None:
        if self._loading_ocr:
            return
        self._ocr_debounce.start()

    def _flush_ocr_text(self) -> None:
        self.store.update_ocr_text(self.current_item_id(), self.ocr_edit.toPlainText())

    def clean_lines(self) -> None:
        from .ocr import clean_lines_text
        self.ocr_edit.setPlainText(clean_lines_text(self.ocr_edit.toPlainText()))

    def clean_soft(self) -> None:
        from .ocr import clean_soft_text
        self.ocr_edit.setPlainText(clean_soft_text(self.ocr_edit.toPlainText()))

    def clean_hard(self) -> None:
        from .ocr import clean_hard_text
        self.ocr_edit.setPlainText(clean_hard_text(self.ocr_edit.toPlainText()))

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

    # ── 翻译 ──

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
