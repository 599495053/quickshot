import ctypes
import os
import sys
import threading
import time
import traceback as _traceback


_STDIO_SINKS = []


def prepare_standard_streams() -> None:
    """PyInstaller 无控制台模式下，sys.stdout/sys.stderr 可能为 None。"""
    for name in ("stdout", "stderr"):
        if getattr(sys, name, None) is not None:
            continue
        try:
            stream = open(os.devnull, "w", encoding="utf-8", errors="ignore")
        except OSError:
            continue
        setattr(sys, name, stream)
        _STDIO_SINKS.append(stream)


def prepare_dpi_awareness() -> None:
    """在导入 Qt 之前启用 Windows 高 DPI 感知。"""
    if not sys.platform.startswith("win"):
        return
    # 旧版 Win 没有 SetProcessDpiAwarenessContext，预期失败转下一个 API
    try:
        ctypes.windll.user32.SetProcessDpiAwarenessContext(ctypes.c_void_p(-4))
        return
    except (AttributeError, OSError):
        pass
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(2)
        return
    except (AttributeError, OSError):
        pass


# 必须在 Qt 导入之前执行
prepare_standard_streams()
prepare_dpi_awareness()

from typing import Optional

from PyQt6.QtCore import QObject, Qt, QTimer
from PyQt6.QtGui import QAction, QIcon
from PyQt6.QtWidgets import (
    QApplication,
    QMenu,
    QMessageBox,
    QSystemTrayIcon,
)

from .config import Config
from .constants import HOTKEY_DEBOUNCE_SECONDS, HOTKEY_POLL_INTERVAL_MS, TRAY_MESSAGE_DURATION_MS, WINDOW_CAPTURE_DELAY_MS
from .feedback import detailed_error_message
from .history import CaptureHistoryStore
from .hotkey import NativeHotkeyWindow
from .ocr import schedule_rapidocr_prewarm, shutdown_ocr_executor
from .overlay import FloatingSnipOverlay
from .screenshot import get_foreground_window_rect, grab_virtual_screen, schedule_capture_prewarm
from .utils import APP_NAME, copy_text_to_clipboard, debug_log, load_app_icon, safe_print
from .workflow_presets import (
    WORKFLOW_PRESET_CUSTOM,
    WORKFLOW_PRESET_LABELS,
    apply_workflow_preset,
    normalize_workflow_preset,
    workflow_capture_hint,
    workflow_preset_hint,
    workflow_preset_label,
)


def _global_exception_hook(exc_type, exc_value, exc_tb) -> None:
    """sys.excepthook — 未捕获异常弹窗提示，避免无声闪退。"""
    tb_text = "".join(_traceback.format_exception(exc_type, exc_value, exc_tb))
    debug_log(f"UNCAUGHT EXCEPTION:\n{tb_text}")
    try:
        QMessageBox.critical(
            None, f"{APP_NAME} 遇到问题",
            f"程序遇到了一个未预期的错误，部分功能可能暂时不可用。\n\n"
            f"错误类型：{exc_type.__name__}\n"
            f"错误信息：{exc_value}\n\n"
            f"详细信息已记录到日志，如持续出现请反馈。",
        )
    except Exception as exc:
        debug_log(f"global exception hook QMessageBox failed: {exc}")


def _thread_exception_hook(args) -> None:
    """threading.excepthook — 子线程未捕获异常。"""
    if args.exc_type is None:
        return
    tb_text = "".join(_traceback.format_exception(args.exc_type, args.exc_value, args.exc_traceback))
    debug_log(f"THREAD EXCEPTION ({args.thread.name}):\n{tb_text}")


def _qt_message_handler(mode, context, message) -> None:
    """qInstallMessageHandler — Qt 内部警告/致命错误。"""
    level = {0: "Debug", 1: "Warning", 2: "Critical", 3: "Fatal"}.get(mode, str(mode))
    debug_log(f"Qt {level}: {message}")


def install_exception_hooks() -> None:
    """安装全局异常钩子。"""
    sys.excepthook = _global_exception_hook
    threading.excepthook = _thread_exception_hook
    try:
        from PyQt6.QtCore import qInstallMessageHandler
        qInstallMessageHandler(_qt_message_handler)
    except Exception as exc:
        debug_log(f"qInstallMessageHandler failed: {exc}")


class QuickShotApp(QObject):
    def __init__(self, app: QApplication) -> None:
        super().__init__()
        debug_log("QuickShotApp init start")
        self.app = app
        self.app.setQuitOnLastWindowClosed(False)
        self.config = Config()
        self.history_store = CaptureHistoryStore(self.config)
        self.hotkey_window = NativeHotkeyWindow()
        self.hotkey_window.region_hotkey.connect(self.on_region_hotkey)
        self.hotkey_window.window_hotkey.connect(self.on_window_hotkey)
        self.hotkey_window.history_hotkey.connect(self.show_history)
        self.hotkey_window.pin_hotkey.connect(self.show_pin_manager)
        self.hotkey_window.ocr_hotkey.connect(self.on_ocr_hotkey)
        self.overlay: Optional[FloatingSnipOverlay] = None
        self.settings_window = None
        self.history_window = None
        self.pin_manager_window = None
        self._ocr_prewarmed = False
        self._pending_auto_ocr = False
        self._quitting = False
        self._last_hotkey_time = 0.0
        self._fallback_region_pressed = False
        self._fallback_window_pressed = False
        self._poll_region_mods: list = []
        self._poll_region_vk = 0
        self._poll_window_mods: list = []
        self._poll_window_vk = 0
        self._poll_error_count = 0
        self._update_fallback_poll_keys()
        self.hotkey_poll_timer = QTimer(self)
        self.hotkey_poll_timer.timeout.connect(self.poll_fallback_hotkeys)

        self.tray = QSystemTrayIcon(self.create_icon(), self.app)
        self.refresh_tray_tooltip()
        self.menu = self.create_tray_menu()
        self.tray.setContextMenu(self.menu)
        self.tray.activated.connect(self.on_tray_activated)
        self.tray.show()
        debug_log(f"tray visible={self.tray.isVisible()} available={QSystemTrayIcon.isSystemTrayAvailable()}")

        self.register_hotkeys()
        self.start_fallback_hotkey_polling()
        # OCR 预热延后到首次截图，省常驻内存；截图后端 DLL 在启动后空闲时后台 import，消除首次截图冷启动延迟
        QTimer.singleShot(300, self._prewarm_capture_and_ocr)
        self.tray.showMessage(
            APP_NAME,
            f"已启动：{self.config.region_hotkey} 区域截图；工作流：{workflow_preset_label(self.config.workflow_preset)}",
            QSystemTrayIcon.MessageIcon.Information,
            TRAY_MESSAGE_DURATION_MS,
        )
        debug_log("QuickShotApp init done")

    def present_window(self, window, label: str) -> None:
        def _show() -> None:
            try:
                window.setWindowState(window.windowState() & ~Qt.WindowState.WindowMinimized)
            except Exception as exc:
                debug_log(f"{label} setWindowState failed: {exc}")
            try:
                window.showNormal()
            except Exception:
                # showNormal 在某些状态下抛错，show() 是设计好的兜底
                window.show()
            window.raise_()
            window.activateWindow()
            if sys.platform.startswith("win"):
                try:
                    hwnd = int(window.winId())
                    ctypes.windll.user32.ShowWindow(hwnd, 5)
                    ctypes.windll.user32.SetForegroundWindow(hwnd)
                except Exception as exc:
                    debug_log(f"{label} force_show failed: {exc}")
            QTimer.singleShot(60, lambda: debug_log(f"{label} visible={window.isVisible()}"))

        QTimer.singleShot(0, _show)

    def create_icon(self) -> QIcon:
        return load_app_icon()

    def run_after_tray_menu(self, callback, delay_ms: int = 180) -> None:
        try:
            self.menu.hide()
        except Exception as exc:
            debug_log(f"tray menu hide failed: {exc}")
        QTimer.singleShot(delay_ms, callback)

    def create_tray_menu(self) -> QMenu:
        menu = QMenu()
        region_action = QAction(f"区域截图  {self.config.region_hotkey}", menu)
        window_action = QAction(f"当前窗口截图  {self.config.window_hotkey}", menu)
        history_action = QAction("截图历史", menu)
        pin_manager_action = QAction("贴图管理", menu)
        workflow_menu = self.create_workflow_menu(menu)
        settings_action = QAction("设置", menu)
        open_dir_action = QAction("打开保存目录", menu)
        diagnostic_action = QAction("复制诊断信息", menu)
        quit_action = QAction("退出", menu)

        region_action.triggered.connect(lambda: self.run_after_tray_menu(self.start_region_snip))
        window_action.triggered.connect(lambda: self.run_after_tray_menu(self.start_window_snip))
        history_action.triggered.connect(lambda: self.run_after_tray_menu(self.show_history))
        pin_manager_action.triggered.connect(lambda: self.run_after_tray_menu(self.show_pin_manager))
        settings_action.triggered.connect(lambda: self.run_after_tray_menu(self.show_settings))
        open_dir_action.triggered.connect(lambda: self.run_after_tray_menu(self.open_save_dir))
        diagnostic_action.triggered.connect(lambda: self.run_after_tray_menu(self.copy_diagnostic_info))
        quit_action.triggered.connect(self.quit)

        menu.addAction(region_action)
        menu.addAction(window_action)
        menu.addAction(history_action)
        menu.addAction(pin_manager_action)
        menu.addMenu(workflow_menu)
        menu.addSeparator()
        menu.addAction(settings_action)
        menu.addAction(open_dir_action)
        menu.addAction(diagnostic_action)
        menu.addSeparator()
        menu.addAction(quit_action)
        return menu

    def create_workflow_menu(self, parent: QMenu) -> QMenu:
        workflow_menu = QMenu("工作流预设", parent)
        current = normalize_workflow_preset(getattr(self.config, "workflow_preset", WORKFLOW_PRESET_CUSTOM))
        status_action = QAction(f"当前：{workflow_preset_label(current)}", workflow_menu)
        status_action.setEnabled(False)
        status_action.setToolTip(workflow_capture_hint(self.config))
        workflow_menu.addAction(status_action)
        workflow_menu.addSeparator()
        for preset, label in WORKFLOW_PRESET_LABELS:
            if preset == WORKFLOW_PRESET_CUSTOM:
                continue
            action = QAction(label, workflow_menu)
            action.setCheckable(True)
            action.setChecked(current == preset)
            action.setToolTip(workflow_preset_hint(preset))
            action.triggered.connect(
                lambda _checked=False, selected=preset: self.run_after_tray_menu(
                    lambda: self.set_workflow_preset(selected)
                )
            )
            workflow_menu.addAction(action)
        return workflow_menu

    def refresh_tray_tooltip(self) -> None:
        if not hasattr(self, "tray"):
            return
        self.tray.setToolTip(
            f"{APP_NAME} 正在后台运行\n"
            f"工作流：{workflow_preset_label(getattr(self.config, 'workflow_preset', WORKFLOW_PRESET_CUSTOM))}"
        )

    def set_workflow_preset(self, preset: str) -> None:
        changed = apply_workflow_preset(self.config, preset)
        self.config.save()
        settings_window = getattr(self, "settings_window", None)
        if settings_window is not None and hasattr(settings_window, "_refresh_workflow_controls"):
            try:
                settings_window._refresh_workflow_controls()
            except Exception as exc:
                debug_log(f"refresh settings workflow controls failed: {exc}")
        self.refresh_tray_tooltip()
        self.refresh_tray_menu()
        label = workflow_preset_label(getattr(self.config, "workflow_preset", preset))
        suffix = workflow_capture_hint(self.config)
        self.show_tip(f"工作流已切换：{label}；{suffix}" if changed else f"工作流保持：{label}")

    def _hotkey_allowed(self) -> bool:
        now = time.monotonic()
        if now - self._last_hotkey_time < HOTKEY_DEBOUNCE_SECONDS:
            return False
        self._last_hotkey_time = now
        return True

    def on_region_hotkey(self) -> None:
        if self._hotkey_allowed():
            debug_log("region hotkey triggered")
            if self.config.delay_seconds > 0:
                self.tray.showMessage(
                    APP_NAME,
                    f"将在 {self.config.delay_seconds} 秒后截图...",
                    QSystemTrayIcon.MessageIcon.Information,
                    1000,
                )
                QTimer.singleShot(self.config.delay_seconds * 1000, self.start_region_snip)
            else:
                self.start_region_snip()

    def on_window_hotkey(self) -> None:
        if self._hotkey_allowed():
            debug_log("window hotkey triggered")
            if self.config.delay_seconds > 0:
                self.tray.showMessage(
                    APP_NAME,
                    f"将在 {self.config.delay_seconds} 秒后截图...",
                    QSystemTrayIcon.MessageIcon.Information,
                    1000,
                )
                QTimer.singleShot(self.config.delay_seconds * 1000, self.start_window_snip)
            else:
                self.start_window_snip()

    def on_ocr_hotkey(self) -> None:
        if self._hotkey_allowed():
            self._pending_auto_ocr = True
            if self.config.delay_seconds > 0:
                self.tray.showMessage(
                    APP_NAME,
                    f"将在 {self.config.delay_seconds} 秒后截图并识别...",
                    QSystemTrayIcon.MessageIcon.Information,
                    1000,
                )
                QTimer.singleShot(self.config.delay_seconds * 1000, self.start_region_snip)
            else:
                self.start_region_snip()

    def start_fallback_hotkey_polling(self) -> None:
        """源码运行时的备用快捷键轮询。"""
        if not sys.platform.startswith("win"):
            return
        self.hotkey_poll_timer.start(HOTKEY_POLL_INTERVAL_MS)

    def _update_fallback_poll_keys(self) -> None:
        from .hotkey_util import get_vk_poll_codes
        region = get_vk_poll_codes(self.config.region_hotkey)
        window = get_vk_poll_codes(self.config.window_hotkey)
        self._poll_region_mods, self._poll_region_vk = region if region else ([], 0)
        self._poll_window_mods, self._poll_window_vk = window if window else ([], 0)

    @staticmethod
    def _modifier_groups_pressed(down, modifier_groups: list) -> bool:
        if not modifier_groups:
            return False
        return all(any(down(vk) for vk in group) for group in modifier_groups)

    def poll_fallback_hotkeys(self) -> None:
        if not sys.platform.startswith("win") or self._quitting:
            return

        try:
            user32 = ctypes.windll.user32
            down = lambda vk: bool(user32.GetAsyncKeyState(vk) & 0x8000)

            region_mods_ok = self._modifier_groups_pressed(down, self._poll_region_mods)
            window_mods_ok = self._modifier_groups_pressed(down, self._poll_window_mods)

            region_pressed = region_mods_ok and self._poll_region_vk > 0 and down(self._poll_region_vk)
            window_pressed = window_mods_ok and self._poll_window_vk > 0 and down(self._poll_window_vk)

            if region_pressed and not self._fallback_region_pressed:
                self.on_region_hotkey()
            if window_pressed and not self._fallback_window_pressed:
                self.on_window_hotkey()

            self._fallback_region_pressed = region_pressed
            self._fallback_window_pressed = window_pressed
            self._poll_error_count = 0
        except Exception as exc:
            self._poll_error_count += 1
            if self._poll_error_count == 1:
                debug_log(f"poll_fallback_hotkeys error (will suppress after 1st): {exc}")
            elif self._poll_error_count >= 200:
                debug_log(f"poll_fallback_hotkeys: {self._poll_error_count} consecutive errors, last: {exc}")
                self._poll_error_count = 1

    def register_hotkeys(self) -> None:
        try:
            ok = self.hotkey_window.register(
                self.config.region_hotkey, self.config.window_hotkey,
                self.config.history_hotkey, self.config.pin_hotkey,
                self.config.ocr_hotkey,
            )
            if not ok:
                raise RuntimeError(f"{self.config.region_hotkey} 或 {self.config.window_hotkey} 注册失败")
            safe_print(f"{APP_NAME} 已启动")
            safe_print(f"区域截图：{self.config.region_hotkey}")
            safe_print(f"当前窗口截图：{self.config.window_hotkey}")
            if self.config.history_hotkey:
                safe_print(f"截图历史：{self.config.history_hotkey}")
            if self.config.pin_hotkey:
                safe_print(f"贴图管理：{self.config.pin_hotkey}")
            if self.config.ocr_hotkey:
                safe_print(f"文字识别：{self.config.ocr_hotkey}")
            debug_log(
                "hotkeys registered: "
                f"region={self.config.region_hotkey}; "
                f"window={self.config.window_hotkey}; "
                f"history={self.config.history_hotkey}; "
                f"pin={self.config.pin_hotkey}; "
                f"ocr={self.config.ocr_hotkey}"
            )
        except Exception as exc:
            QMessageBox.warning(
                None,
                "快捷键注册失败",
                f"快捷键注册失败：{exc}\n\n请检查快捷键是否被其他软件占用。",
            )

    def re_register_hotkeys(self) -> None:
        try:
            self.hotkey_window.unregister()
            self.hotkey_window.register(
                self.config.region_hotkey, self.config.window_hotkey,
                self.config.history_hotkey, self.config.pin_hotkey,
                self.config.ocr_hotkey,
            )
        except Exception as exc:
            debug_log(f"re_register_hotkeys failed: {exc}")
        self._update_fallback_poll_keys()
        self.refresh_tray_menu()

    def refresh_tray_menu(self) -> None:
        try:
            old_menu = self.menu
            self.menu = self.create_tray_menu()
            self.tray.setContextMenu(self.menu)
            old_menu.deleteLater()
        except Exception as exc:
            debug_log(f"refresh_tray_menu failed: {exc}")

    def on_tray_activated(self, reason) -> None:
        if reason == QSystemTrayIcon.ActivationReason.DoubleClick:
            self.start_region_snip()

    def create_overlay(self) -> Optional[FloatingSnipOverlay]:
        if not self._ocr_prewarmed:
            self._ocr_prewarmed = True
            schedule_rapidocr_prewarm()
        try:
            raw_snapshot, display_snapshot, logical_geometry, scale_x, scale_y, physical_left, physical_top = grab_virtual_screen(self.config.hdr_color_accurate)
        except Exception as exc:
            debug_log(f"create overlay capture failed: {exc}")
            QMessageBox.warning(None, "截图失败", detailed_error_message("无法获取屏幕截图。", exc))
            return None

        if self.overlay is not None:
            try:
                self.overlay.close()
            except Exception as exc:
                debug_log(f"overlay close failed: {exc}")

        overlay = FloatingSnipOverlay(
            raw_snapshot,
            display_snapshot,
            logical_geometry,
            scale_x,
            scale_y,
            physical_left,
            physical_top,
            self.config,
            self.history_store,
        )
        overlay.closed.connect(lambda: debug_log("overlay closed"))
        overlay.closed.connect(lambda: setattr(self, "overlay", None))
        overlay.notify.connect(self.show_tip)
        overlay.history_updated.connect(self._on_history_updated)
        self.overlay = overlay
        return overlay

    def _prewarm_capture_and_ocr(self) -> None:
        """后台预热截图 + OCR 模块，消除首次截图冷启动延迟。"""
        schedule_capture_prewarm()
        if not self._ocr_prewarmed:
            self._ocr_prewarmed = True
            schedule_rapidocr_prewarm()

    def start_region_snip(self) -> None:
        QTimer.singleShot(30, self.show_region_overlay)

    def show_region_overlay(self) -> None:
        overlay = self.create_overlay()
        if overlay is None:
            return
        if getattr(self, '_pending_auto_ocr', False):
            self._pending_auto_ocr = False
            overlay.auto_ocr = True
        overlay.show()
        debug_log("region overlay shown")

    def start_window_snip(self) -> None:
        QTimer.singleShot(WINDOW_CAPTURE_DELAY_MS, self.capture_current_window)

    def capture_current_window(self) -> None:
        rect = get_foreground_window_rect()
        if rect is None:
            debug_log("window capture no foreground rect")
            self.tray.showMessage(
                APP_NAME,
                "没有找到可截图的当前窗口。建议使用 Ctrl + Shift + W 触发。",
                QSystemTrayIcon.MessageIcon.Warning,
                2000,
            )
            return

        overlay = self.create_overlay()
        if overlay is None:
            return
        overlay.set_initial_capture_from_physical_abs(rect)
        overlay.show()
        debug_log("window overlay shown")

    def show_settings(self, checked: bool = False) -> None:
        if self.settings_window is None:
            from .settings import SettingsWindow
            self.settings_window = SettingsWindow(self.config)
            self.settings_window.hotkeys_changed.connect(self.re_register_hotkeys)
            self.settings_window.destroyed.connect(lambda: setattr(self, "settings_window", None))
        self.present_window(self.settings_window, "show_settings")

    def _on_history_updated(self) -> None:
        if self.history_window is not None:
            self.history_window.reload_items()
        if self.pin_manager_window is not None:
            self.pin_manager_window.reload_items()

    def show_history(self, checked: bool = False) -> None:
        if self.history_window is None:
            from .manager import HistoryWindow
            self.history_window = HistoryWindow(self.history_store, self.config)
            self.history_window._reedit_callback = self.reedit_from_history
            self.history_window.destroyed.connect(lambda: setattr(self, "history_window", None))
        else:
            self.history_window.reload_items()
        self.present_window(self.history_window, "show_history")

    def reedit_from_history(self, pixmap) -> None:
        from PyQt6.QtCore import QRect
        if pixmap is None or pixmap.isNull():
            QMessageBox.warning(None, "编辑失败", detailed_error_message("无法加载截图，图片为空。", include_hint=False))
            return
        try:
            raw_snapshot, display_snapshot, logical_geometry, scale_x, scale_y, physical_left, physical_top = grab_virtual_screen(self.config.hdr_color_accurate)
        except Exception as exc:
            debug_log(f"reedit capture failed: {exc}")
            QMessageBox.warning(None, "编辑失败", detailed_error_message("无法获取屏幕截图，暂时不能重新编辑。", exc))
            return
        if self.overlay is not None:
            try:
                self.overlay.close()
            except Exception as exc:
                debug_log(f"overlay close failed: {exc}")
        from .overlay import FloatingSnipOverlay
        overlay = FloatingSnipOverlay(
            raw_snapshot, display_snapshot, logical_geometry,
            scale_x, scale_y, physical_left, physical_top,
            self.config, self.history_store,
        )
        overlay.closed.connect(lambda: setattr(self, "overlay", None))
        overlay.notify.connect(self.show_tip)
        overlay.history_updated.connect(self._on_history_updated)
        self.overlay = overlay
        overlay.base_edit_pixmap = pixmap.copy()
        overlay.base_edit_pixmap.setDevicePixelRatio(1.0)
        overlay.edit_pixmap = pixmap.copy()
        overlay.edit_pixmap.setDevicePixelRatio(1.0)
        screen_rect = overlay.rect()
        sel_w = min(pixmap.width(), screen_rect.width())
        sel_h = min(pixmap.height(), screen_rect.height())
        sel_x = (screen_rect.width() - sel_w) // 2
        sel_y = (screen_rect.height() - sel_h) // 2
        overlay.selection_rect = QRect(sel_x, sel_y, sel_w, sel_h)
        overlay.selection_physical_rect = QRect(
            int(sel_x * scale_x), int(sel_y * scale_y),
            int(sel_w * scale_x), int(sel_h * scale_y),
        )
        overlay.mode = "edit"
        overlay.selection_snapshot_required = True
        overlay.update_toolbar_layout()
        overlay.update_selection_display_cache()
        overlay.message = "已加载历史截图，可继续编辑或标注"
        overlay.show()

    def show_pin_manager(self, checked: bool = False) -> None:
        try:
            if self.pin_manager_window is None:
                from .manager import PinManagerWindow
                self.pin_manager_window = PinManagerWindow()
                self.pin_manager_window.destroyed.connect(lambda: setattr(self, "pin_manager_window", None))
            else:
                self.pin_manager_window.reload_items()
            self.present_window(self.pin_manager_window, "show_pin_manager")
            debug_log("show_pin_manager success")
        except Exception as exc:
            debug_log(f"show_pin_manager failed: {exc}")
            QMessageBox.warning(None, "打开失败", f"无法打开贴图管理：{exc}")

    def open_save_dir(self) -> None:
        path = self.config.ensure_save_dir()
        try:
            os.startfile(path)  # type: ignore[attr-defined]
        except Exception as exc:
            QMessageBox.warning(None, "打开失败", f"无法打开保存目录：{exc}")

    def copy_diagnostic_info(self) -> None:
        try:
            from .diagnostics import build_diagnostic_report

            copy_text_to_clipboard(build_diagnostic_report(self.config))
            self.show_tip("诊断信息已复制到剪贴板")
        except Exception as exc:
            debug_log(f"copy diagnostic info failed: {exc}")
            QMessageBox.warning(None, "复制失败", f"无法复制诊断信息：{exc}")

    def show_tip(self, text: str) -> None:
        if not text:
            return
        self.tray.showMessage(APP_NAME, text, QSystemTrayIcon.MessageIcon.Information, 1600)

    def quit(self) -> None:
        debug_log("quit requested")
        if self._quitting:
            debug_log("quit ignored because already quitting")
            return
        self._quitting = True
        try:
            self.history_store.flush()
        except Exception as exc:
            debug_log(f"history_store flush failed: {exc}")
        try:
            self.hotkey_poll_timer.stop()
        except Exception as exc:
            debug_log(f"hotkey_poll_timer stop failed: {exc}")
        try:
            self.hotkey_window.unregister()
            self.hotkey_window.close()
        except Exception as exc:
            debug_log(f"hotkey_window cleanup failed: {exc}")
        try:
            if self.overlay is not None:
                self.overlay.close()
        except Exception as exc:
            debug_log(f"quit overlay close failed: {exc}")
        try:
            shutdown_ocr_executor()
        except Exception as exc:
            debug_log(f"shutdown_ocr_executor failed: {exc}")
        self.tray.hide()
        self.app.quit()
        debug_log("app.quit called")


def main() -> None:
    debug_log("main start")
    app = QApplication(sys.argv)
    install_exception_hooks()
    app.setApplicationName(APP_NAME)
    app.aboutToQuit.connect(lambda: debug_log("aboutToQuit signal"))

    if not QSystemTrayIcon.isSystemTrayAvailable():
        QMessageBox.warning(None, APP_NAME, "系统托盘不可用，程序仍会运行。")

    quickshot = QuickShotApp(app)
    app.aboutToQuit.connect(quickshot.quit)
    exit_code = app.exec()
    debug_log(f"event loop exited code={exit_code}")
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
