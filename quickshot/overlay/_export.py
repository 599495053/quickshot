"""ExportMixin — 复制、保存、贴图、完成、历史记录、工作流。"""

from __future__ import annotations

import datetime
import threading
from pathlib import Path
from typing import Dict, Optional

from PyQt6.QtWidgets import QFileDialog

from ..feedback import compact_error_message
from ..pin import show_pin_window
from ..pipeline import run_post_capture_pipeline, should_run_post_capture
from ..utils import copy_pixmap_to_clipboard, copy_text_to_clipboard, debug_log


class ExportMixin:

    def maybe_notify(self, text: str) -> None:
        if getattr(self.config, "show_notifications", True):
            self.notify.emit(text)

    def _copy_text_to_clipboard(self, text: str) -> None:
        copy_text_to_clipboard(text)

    def copy_current(self) -> None:
        if self.edit_pixmap.isNull():
            return
        if getattr(self, "privacy_preview_active", lambda: False)():
            self.message = "请先按 Enter 应用智能打码预览，或按 Esc 取消"
            self.update()
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
            self.message = compact_error_message("复制失败", exc)
        self.update()

    def finish(self) -> None:
        if getattr(self, "privacy_preview_active", lambda: False)():
            self.message = "请先按 Enter 应用智能打码预览，或按 Esc 取消"
            self.update()
            return
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

    _SAVE_FILTERS = (
        "PNG 图片 (*.png);;"
        "JPEG 图片 (*.jpg *.jpeg);;"
        "WebP 图片 (*.webp);;"
        "BMP 图片 (*.bmp);;"
        "所有文件 (*)"
    )

    _FORMAT_MAP = {
        ".png": ("PNG", "PNG"),
        ".jpg": ("JPEG", "JPEG"),
        ".jpeg": ("JPEG", "JPEG"),
        ".webp": ("WebP", "WEBP"),
        ".bmp": ("BMP", "BMP"),
    }

    def save_current(self) -> None:
        if self.edit_pixmap.isNull():
            return
        if getattr(self, "privacy_preview_active", lambda: False)():
            self.message = "请先按 Enter 应用智能打码预览，或按 Esc 取消"
            self.update()
            return
        save_dir = self.config.ensure_save_dir()
        default_fmt = getattr(self.config, "save_format", "png")
        ext = f".{default_fmt}" if default_fmt != "png" else ".png"
        filename = datetime.datetime.now().strftime(f"screenshot_%Y%m%d_%H%M%S{ext}")
        default_path = str(Path(save_dir) / filename)
        try:
            self.releaseKeyboard()
        except Exception as exc:
            debug_log(f"releaseKeyboard for save dialog failed: {exc}")
        filepath, selected_filter = QFileDialog.getSaveFileName(
            self, "保存截图", default_path, self._SAVE_FILTERS,
        )
        try:
            if self.isVisible():
                self.grabKeyboard()
        except Exception as exc:
            debug_log(f"regrabKeyboard after save dialog failed: {exc}")
        if filepath:
            # 根据文件扩展名确定格式
            ext = Path(filepath).suffix.lower()
            fmt_info = self._FORMAT_MAP.get(ext)
            if fmt_info is None:
                # 用户没写扩展名或写了未知扩展名，按 filter 推断
                if "JPEG" in selected_filter:
                    ext = ".jpg"
                    fmt_info = ("JPEG", "JPEG")
                elif "WebP" in selected_filter:
                    ext = ".webp"
                    fmt_info = ("WebP", "WEBP")
                elif "BMP" in selected_filter:
                    ext = ".bmp"
                    fmt_info = ("BMP", "BMP")
                else:
                    ext = ".png"
                    fmt_info = ("PNG", "PNG")
                if not filepath.lower().endswith(ext):
                    filepath += ext
            fmt_name, qt_fmt = fmt_info
            quality = -1  # 默认质量
            if qt_fmt == "JPEG":
                quality = getattr(self.config, "jpeg_quality", 90)
            try:
                saved = self.edit_pixmap.save(filepath, qt_fmt, quality)
                if not saved:
                    raise RuntimeError("pixmap.save returned False")
                self.record_capture_history("save")
                self.message = f"已保存（{fmt_name}）：{filepath}"
                self.maybe_notify(f"已保存：{Path(filepath).name}")
                self._maybe_run_post_capture_pipeline(saved_path=filepath)
            except Exception as exc:
                debug_log(f"save_current failed: {exc}")
                self.message = compact_error_message("保存失败", exc)
            self.update()

    def pin_current(self) -> None:
        if self.edit_pixmap.isNull():
            return
        if getattr(self, "privacy_preview_active", lambda: False)():
            self.message = "请先按 Enter 应用智能打码预览，或按 Esc 取消"
            self.update()
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
            self.message = compact_error_message("贴图失败", exc)
        self.close()

    def _maybe_run_post_capture_pipeline(self, saved_path: str = "") -> None:
        """触发截图后工作流（上传 → 复制 Markdown），后台线程执行避免阻塞 UI。"""
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

        # 捕获当前 config 值（避免后台线程访问 GUI 对象）
        config = self.config
        notify = self.notify
        clipboard_text_requested = self.clipboard_text_requested
        show_notifications = getattr(config, "show_notifications", True)

        def _copy_markdown_on_gui_thread(text: str) -> None:
            clipboard_text_requested.emit(text)

        def _run_pipeline() -> None:
            try:
                ctx = run_post_capture_pipeline(
                    image_path,
                    config,
                    clipboard_writer=_copy_markdown_on_gui_thread,
                )
                if ctx.messages or ctx.errors:
                    # Qt signal 跨线程 emit 会按接收者线程排队，避免后台线程直接碰 UI。
                    for msg in ctx.messages:
                        if show_notifications:
                            notify.emit(msg)
                    if ctx.errors:
                        debug_log(f"post-capture pipeline errors: {ctx.errors}")
                        if show_notifications:
                            notify.emit(compact_error_message("截图后工作流失败", ctx.errors[0], max_length=100))
            except Exception as exc:
                debug_log(f"post-capture pipeline failed: {exc}")
                if show_notifications:
                    notify.emit(compact_error_message("截图后工作流异常", exc, max_length=100))
            finally:
                if tmp_path:
                    try:
                        Path(tmp_path).unlink(missing_ok=True)
                    except OSError as exc:
                        debug_log(f"temp pipeline file cleanup failed: {exc}")

        threading.Thread(target=_run_pipeline, daemon=True, name="quickshot-pipeline").start()

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
