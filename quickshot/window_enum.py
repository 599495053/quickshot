"""Windows 窗口枚举。

使用 ctypes 调用 EnumWindows 枚举所有可见顶层窗口，
返回窗口句柄、物理像素矩形和标题。
"""

from __future__ import annotations

import ctypes
import sys
from typing import List, Tuple

from PyQt6.QtCore import QRect


def enumerate_visible_windows() -> List[Tuple[int, QRect, str]]:
    """枚举所有可见顶层窗口，返回 [(hwnd, rect, title), ...]。

    rect 为物理像素坐标（屏幕绝对坐标）。
    过滤条件：IsWindowVisible、非最小化、宽高 > 50px、
    非 ToolWindow 类型（排除悬浮工具栏等）。
    """
    if not sys.platform.startswith("win"):
        return []

    user32 = ctypes.windll.user32
    dwmapi = ctypes.windll.dwmapi
    from ctypes import wintypes

    results: List[Tuple[int, QRect, str]] = []

    WNDENUMPROC = ctypes.WINFUNCTYPE(
        ctypes.c_bool, wintypes.HWND, wintypes.LPARAM
    )

    def _callback(hwnd, _lparam):
        try:
            if not user32.IsWindowVisible(hwnd):
                return True

            # 排除最小化窗口
            if user32.IsIconic(hwnd):
                return True

            # 获取窗口标题
            length = user32.GetWindowTextLengthW(hwnd)
            if length <= 0:
                return True
            buf = ctypes.create_unicode_buffer(length + 1)
            user32.GetWindowTextW(hwnd, buf, length + 1)
            title = buf.value
            if not title:
                return True

            # 排除 QuickShot 自身
            if "QuickShot" in title:
                return True

            # 排除 ToolWindow（悬浮工具栏等）
            GWL_EXSTYLE = -20
            WS_EX_TOOLWINDOW = 0x00000080
            try:
                style = user32.GetWindowLongW(hwnd, GWL_EXSTYLE)
                if style & WS_EX_TOOLWINDOW:
                    return True
            except Exception:
                pass

            # 获取窗口矩形（优先 DWM 扩展边框，排除阴影区域）
            rect = wintypes.RECT()
            ok = False
            try:
                result = dwmapi.DwmGetWindowAttribute(
                    hwnd, 9, ctypes.byref(rect), ctypes.sizeof(rect)
                )
                ok = result == 0
            except Exception:
                ok = False
            if not ok:
                try:
                    user32.GetWindowRect(hwnd, ctypes.byref(rect))
                    ok = True
                except Exception:
                    return True

            left = int(rect.left)
            top = int(rect.top)
            width = int(rect.right - rect.left)
            height = int(rect.bottom - rect.top)
            if width < 50 or height < 50:
                return True

            results.append((hwnd, QRect(left, top, width, height), title))
        except Exception:
            pass  # 单个窗口异常不影响整体枚举
        return True

    callback = WNDENUMPROC(_callback)
    user32.EnumWindows(callback, 0)
    return results
