"""ExportMixin — 复制、保存、贴图、完成、历史记录、工作流。"""

from __future__ import annotations

import datetime
from pathlib import Path
from typing import Dict, Optional

from PyQt6.QtWidgets import QFileDialog

from ..pin import show_pin_window
from ..pipeline import run_post_capture_pipeline, should_run_post_capture
from ..utils import copy_pixmap_to_clipboard, debug_log


class ExportMixin:

    def maybe_notify(self, text: str) -> None:
        if getattr(self.config, "show_notifications", True):
            self.notify.emit(text)

    def copy_current(self) -> None:
        if self.edit_pixmap.isNull():
            return
        try:
            copy_pixmap_to_clipboard(self.edit_pixmap)
            self.record_capture_history("copy")
            self.message = f"已复制到剪贴板：{self.edit_pixmap.width()} × {self.edit_pixmap.height()}"
            self.maybe_notify("已复制到剪贴板")
            self._maybe_run_post_capture_pipeline()
            # 自动 OCR 异步触发，识别完成后覆盖剪贴板
            if getattr(self.config, "workflow_auto_ocr", False):
                self.message = "正在识别文字..."
                self.start_silent_auto_ocr()
        except Exception as exc:
            debug_log(f"copy_current failed: {exc}")
            self.message = f"复制失败：{exc}"
        self.update()

    def finish(self) -> None:
        # 自动 OCR 时延迟关闭，避免 close 后 OCR 写剪贴板被系统覆盖
        if (
            getattr(self.config, "workflow_auto_ocr", False)
            and not self.edit_pixmap.isNull()
            and not self.ocr_running()
        ):
            try:
                copy_pixmap_to_clipboard(self.edit_pixmap)
                self.record_capture_history("copy")
                self._maybe_run_post_capture_pipeline()
            except Exception as exc:
                debug_log(f"finish auto_ocr prepare failed: {exc}")
            self.message = "正在识别文字，识别完成后将自动关闭..."
            self.update()

            def _close_after_ocr(_ok: bool) -> None:
                try:
                    self.close()
                except Exception as exc:  # noqa: BLE001
                    debug_log(f"close after silent OCR failed: {exc}")

            started = self.start_silent_auto_ocr(on_done=_close_after_ocr)
            if not started:
                # 没启动起来直接走老路径
                self.close()
            return
        self.copy_current()
        self.close()

    def save_current(self) -> None:
        if self.edit_pixmap.isNull():
            return
        save_dir = self.config.ensure_save_dir()
        filename = datetime.datetime.now().strftime("screenshot_%Y%m%d_%H%M%S.png")
        default_path = str(Path(save_dir) / filename)
        try:
            self.releaseKeyboard()
        except Exception as exc:
            debug_log(f"releaseKeyboard for save dialog failed: {exc}")
        filepath, _ = QFileDialog.getSaveFileName(
            self, "保存截图", default_path, "PNG 图片 (*.png)",
        )
        try:
            if self.isVisible():
                self.grabKeyboard()
        except Exception as exc:
            debug_log(f"regrabKeyboard after save dialog failed: {exc}")
        if filepath:
            if not filepath.lower().endswith(".png"):
                filepath += ".png"
            try:
                saved = self.edit_pixmap.save(filepath, "PNG")
                if not saved:
                    raise RuntimeError("pixmap.save returned False")
                self.record_capture_history("save")
                self.message = f"已保存：{filepath}"
                self.maybe_notify(f"已保存：{Path(filepath).name}")
                self._maybe_run_post_capture_pipeline(saved_path=filepath)
            except Exception as exc:
                debug_log(f"save_current failed: {exc}")
                self.message = f"保存失败：{exc}"
            self.update()

    def pin_current(self) -> None:
        if self.edit_pixmap.isNull():
            return
        try:
            self.record_capture_history("pin")
            pos = self.mapToGlobal(self.selection_rect.topLeft())
            target_size = (self.selection_rect.width(), self.selection_rect.height())
            show_pin_window(self.edit_pixmap, self.config, pos=pos, target_size=target_size)
            self.message = "已贴到桌面：左键拖动，滚轮缩放，右键菜单，双击关闭"
            self.maybe_notify("已贴到桌面")
        except Exception as exc:
            debug_log(f"pin_current failed: {exc}")
            self.message = f"贴图失败：{exc}"
        self.close()

    def _maybe_run_post_capture_pipeline(self, saved_path: str = "") -> None:
        """触发截图后工作流（上传 → 复制 Markdown）。"""
        if not should_run_post_capture(self.config):
            return
        image_path = saved_path
        if not image_path:
            image_path = self._history_image_path()
        tmp_path = ""
        if not image_path:
            tmp_path = self._write_pipeline_temp_png()
            image_path = tmp_path
        if not image_path:
            return
        try:
            ctx = run_post_capture_pipeline(image_path, self.config)
            for msg in ctx.messages:
                self.maybe_notify(msg)
            if ctx.errors:
                debug_log(f"post-capture pipeline errors: {ctx.errors}")
        finally:
            if tmp_path:
                try:
                    Path(tmp_path).unlink(missing_ok=True)
                except OSError as exc:
                    debug_log(f"temp pipeline file cleanup failed: {exc}")

    def _history_image_path(self) -> str:
        history_id = getattr(self, "history_item_id", "")
        if not history_id or self.history_store is None:
            return ""
        try:
            for item in self.history_store.existing_items():
                if str(item.get("id", "")) == history_id:
                    path = self.history_store.image_path(item)
                    return str(path) if path and Path(path).exists() else ""
        except Exception as exc:  # noqa: BLE001
            debug_log(f"history_image_path failed: {exc}")
        return ""

    def _write_pipeline_temp_png(self) -> str:
        import tempfile
        try:
            fd, tmp = tempfile.mkstemp(prefix="quickshot_pipeline_", suffix=".png")
            import os
            os.close(fd)
            if not self.edit_pixmap.save(tmp, "PNG"):
                Path(tmp).unlink(missing_ok=True)
                return ""
            return tmp
        except OSError as exc:
            debug_log(f"write pipeline temp png failed: {exc}")
            return ""

    def record_capture_history(self, source: str, ocr_text: str = "") -> Optional[Dict[str, object]]:
        if not self.config.auto_history or self.history_store is None or self.edit_pixmap.isNull():
            return None
        if self.history_item_id:
            self.history_store.update_capture(
                self.history_item_id,
                self.edit_pixmap,
                source=source,
                ocr_text=ocr_text,
            )
            self.history_updated.emit()
            return {"id": self.history_item_id}
        item = self.history_store.add_capture(self.edit_pixmap, source=source, ocr_text=ocr_text)
        if item:
            self.history_item_id = str(item.get("id", ""))
            self.history_updated.emit()
        return item
