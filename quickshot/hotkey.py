import ctypes
from ctypes import wintypes
import sys

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import QWidget

from .utils import APP_NAME, debug_log


class NativeHotkeyWindow(QWidget):
    """使用 Windows RegisterHotKey 注册真正全局快捷键。"""

    region_hotkey = pyqtSignal()
    window_hotkey = pyqtSignal()
    history_hotkey = pyqtSignal()
    pin_hotkey = pyqtSignal()
    ocr_hotkey = pyqtSignal()

    WM_HOTKEY = 0x0312
    MOD_ALT = 0x0001
    MOD_CONTROL = 0x0002
    MOD_SHIFT = 0x0004
    MOD_WIN = 0x0008
    HOTKEY_REGION_ID = 1001
    HOTKEY_WINDOW_ID = 1002
    HOTKEY_HISTORY_ID = 1003
    HOTKEY_PIN_ID = 1004
    HOTKEY_OCR_ID = 1005

    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle(f"{APP_NAME} Hotkey Receiver")
        self.setAttribute(Qt.WidgetAttribute.WA_DontShowOnScreen, True)
        self._registered = False
        self._hwnd = int(self.winId())
        self.show()
        self.hide()

    def register(self, region_hotkey: str = "Ctrl+Shift+A", window_hotkey: str = "Ctrl+Shift+W",
                 history_hotkey: str = "", pin_hotkey: str = "", ocr_hotkey: str = "") -> bool:
        """注册全局热键。

        Returns:
            bool: 注册成功返回 True，失败返回 False（可能已被其他程序占用）
        """
        if not sys.platform.startswith("win"):
            return False
        from .hotkey_util import parse_hotkey_string
        region_parsed = parse_hotkey_string(region_hotkey)
        window_parsed = parse_hotkey_string(window_hotkey)
        if region_parsed is None or window_parsed is None:
            return False
        user32 = ctypes.windll.user32
        self.unregister()
        r_mod, r_vk = region_parsed
        w_mod, w_vk = window_parsed

        # 尝试注册核心热键
        ok_region = user32.RegisterHotKey(self._hwnd, self.HOTKEY_REGION_ID, r_mod, r_vk)
        ok_window = user32.RegisterHotKey(self._hwnd, self.HOTKEY_WINDOW_ID, w_mod, w_vk)

        if not ok_region or not ok_window:
            # 注册失败，清理并返回
            self.unregister()

            # 构建友好的错误提示
            failed_keys = []
            if not ok_region:
                failed_keys.append(f"区域截图: {region_hotkey}")
            if not ok_window:
                failed_keys.append(f"窗口截图: {window_hotkey}")

            error_msg = (
                f"快捷键注册失败：\n\n"
                f"{', '.join(failed_keys)}\n\n"
                f"可能已被其他程序占用。\n"
                f"建议在设置中更换为其他组合键。"
            )

            # 显示警告对话框
            from PyQt6.QtWidgets import QMessageBox
            QMessageBox.warning(
                None,
                "热键注册失败",
                error_msg
            )
            return False

        # 可选快捷键：历史记录、贴图、OCR（失败不影响主功能）
        history_parsed = parse_hotkey_string(history_hotkey) if history_hotkey else None
        pin_parsed = parse_hotkey_string(pin_hotkey) if pin_hotkey else None
        ocr_parsed = parse_hotkey_string(ocr_hotkey) if ocr_hotkey else None
        if history_parsed is not None:
            h_mod, h_vk = history_parsed
            user32.RegisterHotKey(self._hwnd, self.HOTKEY_HISTORY_ID, h_mod, h_vk)
        if pin_parsed is not None:
            p_mod, p_vk = pin_parsed
            user32.RegisterHotKey(self._hwnd, self.HOTKEY_PIN_ID, p_mod, p_vk)
        if ocr_parsed is not None:
            o_mod, o_vk = ocr_parsed
            user32.RegisterHotKey(self._hwnd, self.HOTKEY_OCR_ID, o_mod, o_vk)

        self._registered = True
        return True

    def unregister(self) -> None:
        if not sys.platform.startswith("win"):
            return
        user32 = ctypes.windll.user32
        for hk_id in (self.HOTKEY_REGION_ID, self.HOTKEY_WINDOW_ID, self.HOTKEY_HISTORY_ID, self.HOTKEY_PIN_ID, self.HOTKEY_OCR_ID):
            try:
                user32.UnregisterHotKey(self._hwnd, hk_id)
            except Exception as exc:
                debug_log(f"unregister hotkey {hk_id} failed: {exc}")
        self._registered = False

    def nativeEvent(self, event_type, message):
        try:
            msg = wintypes.MSG.from_address(int(message))
            if msg.message == self.WM_HOTKEY:
                hotkey_id = int(msg.wParam)
                if hotkey_id == self.HOTKEY_REGION_ID:
                    self.region_hotkey.emit()
                    return True, 0
                if hotkey_id == self.HOTKEY_WINDOW_ID:
                    self.window_hotkey.emit()
                    return True, 0
                if hotkey_id == self.HOTKEY_HISTORY_ID:
                    self.history_hotkey.emit()
                    return True, 0
                if hotkey_id == self.HOTKEY_PIN_ID:
                    self.pin_hotkey.emit()
                    return True, 0
                if hotkey_id == self.HOTKEY_OCR_ID:
                    self.ocr_hotkey.emit()
                    return True, 0
        except Exception as exc:
            debug_log(f"nativeEvent error: {exc}")
        return False, 0

    def closeEvent(self, event) -> None:
        self.unregister()
        super().closeEvent(event)
