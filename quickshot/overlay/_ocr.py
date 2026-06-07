"""OcrMixin — OCR 任务生命周期。"""

from __future__ import annotations

from PyQt6.QtCore import QRect, Qt
from PyQt6.QtWidgets import QApplication

from ..dialogs import OcrResultDialog
from ..ocr import OcrResult, create_ocr_job
from ..utils import copy_text_to_clipboard, debug_log


class OcrMixin:

    def _clear_ocr_dialog_ref(self) -> None:
        """OCR 对话框关闭后清除引用。"""
        if hasattr(self, "_ocr_dialog"):
            self._ocr_dialog = None

    def ocr_running(self) -> bool:
        return self.ocr_job is not None and self.ocr_job.is_running()

    def detach_ocr_job(self) -> None:
        if self.ocr_job is None:
            return
        # PyQt 在 signal 与槽未连接时 disconnect 抛 TypeError；逐个静默是预期行为
        for signal, slot in (
            (self.ocr_job.succeeded, self.on_ocr_job_succeeded),
            (self.ocr_job.failed, self.on_ocr_job_failed),
            (self.ocr_job.finished, self.on_ocr_job_finished),
        ):
            try:
                signal.disconnect(slot)
            except TypeError:
                pass
        self.ocr_job = None

    def recognize_current_text(self) -> None:
        if self.edit_pixmap.isNull():
            return
        if self.ocr_running():
            self.message = "正在识别当前截图，请稍候..."
            self.update()
            return

        self.active_tool = "none"
        self.close_style_panel()
        self.dragging_annotation = False
        self.drag_start = None
        self.drag_end = None
        self.drag_path = []
        self.message = "正在识别文字，首次使用可能稍慢..."
        self.detach_ocr_job()
        self.ocr_job = create_ocr_job(self.edit_pixmap.toImage())
        self.ocr_job.succeeded.connect(self.on_ocr_job_succeeded)
        self.ocr_job.failed.connect(self.on_ocr_job_failed)
        self.ocr_job.finished.connect(self.on_ocr_job_finished)
        self.ocr_job.start()
        self.update()

    def recognize_region(self, region: QRect) -> None:
        if self.edit_pixmap.isNull() or self.ocr_running():
            return
        region = region.intersected(QRect(0, 0, self.edit_pixmap.width(), self.edit_pixmap.height()))
        if region.width() < 8 or region.height() < 8:
            self.message = "选区太小，请拖动更大的区域"
            self.update()
            return
        crop = self.edit_pixmap.copy(region)
        crop.setDevicePixelRatio(1.0)
        self.active_tool = "none"
        self.close_style_panel()
        self.dragging_annotation = False
        self.drag_start = None
        self.drag_end = None
        self.drag_path = []
        self.message = "正在识别选区文字..."
        self.detach_ocr_job()
        self.ocr_job = create_ocr_job(crop.toImage())
        self.ocr_job.succeeded.connect(self.on_ocr_job_succeeded)
        self.ocr_job.failed.connect(self.on_ocr_job_failed)
        self.ocr_job.finished.connect(self.on_ocr_job_finished)
        self.ocr_job.start()
        self.update()

    def on_ocr_job_succeeded(self, result: OcrResult) -> None:
        self.apply_ocr_result(result)

    def on_ocr_job_failed(self, error_text: str) -> None:
        debug_log(f"OCR failed: {error_text}")
        self.message = "文字识别失败，请稍后重试"
        self.maybe_notify("文字识别失败")
        if "语言包" in error_text or "PowerShell" in error_text:
            self.message = f"文字识别失败：{error_text}"
        self.update()

    def on_ocr_job_finished(self) -> None:
        self.ocr_job = None

    # ── 静默自动 OCR（不弹对话框，仅写剪贴板）──

    def start_silent_auto_ocr(self, on_done=None) -> bool:
        """异步触发自动 OCR：识别成功后用文本覆盖剪贴板，不弹对话框、不抢焦点。

        on_done 是可选回调，在 OCR 完成（成功或失败）后调用，参数为 bool
        表示是否识别出文本。调用方可在此处再关闭窗口，避免 close 抢占剪贴板。

        返回 True 表示已启动任务；False 表示 widget 状态不允许启动。
        """
        if self.edit_pixmap.isNull() or self.ocr_running():
            return False
        self.detach_ocr_job()
        self.ocr_job = create_ocr_job(self.edit_pixmap.toImage())
        # 用 store 和 history_id 的本地引用，避免 widget 关闭后回调里访问 self.* 崩溃
        history_store = self.history_store
        history_id = self.history_item_id
        notify = self.notify if hasattr(self, "notify") else None
        show_notifications = getattr(self.config, "show_notifications", True)

        def emit_notify(msg: str) -> None:
            if notify is not None and show_notifications:
                try:
                    notify.emit(msg)
                except Exception as exc:  # noqa: BLE001
                    debug_log(f"silent OCR notify failed: {exc}")

        def on_success(result: OcrResult) -> None:
            text = (result.text or "").strip()
            success = bool(text)
            if not text:
                emit_notify("OCR：未识别到文字")
            else:
                try:
                    copy_text_to_clipboard(text)
                    engine = result.engine_label or "OCR"
                    emit_notify(f"{engine} 文本已复制")
                except Exception as exc:  # noqa: BLE001
                    debug_log(f"silent OCR clipboard write failed: {exc}")
                    success = False
                if history_id and history_store is not None:
                    try:
                        history_store.update_ocr_text(history_id, text)
                    except Exception as exc:  # noqa: BLE001
                        debug_log(f"silent OCR history update failed: {exc}")
            if on_done is not None:
                try:
                    on_done(success)
                except Exception as exc:  # noqa: BLE001
                    debug_log(f"silent OCR on_done failed: {exc}")

        def on_failure(error_text: str) -> None:
            debug_log(f"silent OCR failed: {error_text}")
            emit_notify("OCR 失败")
            if on_done is not None:
                try:
                    on_done(False)
                except Exception as exc:  # noqa: BLE001
                    debug_log(f"silent OCR on_done failed: {exc}")

        self.ocr_job.succeeded.connect(on_success)
        self.ocr_job.failed.connect(on_failure)
        self.ocr_job.finished.connect(self.on_ocr_job_finished)
        self.ocr_job.start()
        return True

    def apply_ocr_result(self, result: OcrResult) -> None:
        try:
            self._apply_ocr_result_impl(result)
        except Exception as exc:
            from ..utils import debug_log
            import traceback
            debug_log(f'apply_ocr_result CRASH: {exc}')
            debug_log(traceback.format_exc())
            self.message = f'识文失败: {exc}'
            self.update()

    def _apply_ocr_result_impl(self, result: OcrResult) -> None:
        text = result.text.strip()
        if not text:
            self.message = result.note or "未识别到文字"
            self.maybe_notify("未识别到文字")
            self.update()
            return

        QApplication.clipboard().setText(text)
        if self.history_item_id:
            self.history_store.update_ocr_text(self.history_item_id, text) if self.history_store else None
        else:
            item = self.record_capture_history("ocr", text)
            if item:
                self.history_item_id = str(item.get("id", ""))

        if result.note:
            self.message = f"{result.note}，并已复制识别结果"
        else:
            self.message = f"{result.engine_label} 识别完成，已复制到剪贴板"
        self.maybe_notify(f"{result.engine_label} 识别完成")
        self.update()

        dialog = OcrResultDialog(
            text,
            None,
            engine_label=result.engine_label,
            elapsed_seconds=result.elapsed_seconds,
            note=result.note,
        )
        dialog.setWindowTitle(f"{result.engine_label} 识别结果")
        dialog.title_label.setText(f"{result.engine_label} 识别结果已复制，可校对后再复制")
        # 非模态：允许用户继续操作截图，对话框关闭时自动释放引用
        self._ocr_dialog = dialog
        dialog.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose, True)
        dialog.destroyed.connect(lambda: self._clear_ocr_dialog_ref())
        dialog.show()
        self.close()
