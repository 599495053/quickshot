"""Windows 窗口枚举。

使用 ctypes 调用 EnumWindows 枚举所有可见顶层窗口，
返回窗口句柄、物理像素矩形和标题。
"""

from __future__ import annotations

import ctypes
import sys
from typing import List, Tuple

from PyQt6.QtCore import QRect


def _get_window_text(user32, hwnd) -> str:
    length = user32.GetWindowTextLengthW(hwnd)
    if length <= 0:
        return ""
    buf = ctypes.create_unicode_buffer(length + 1)
    user32.GetWindowTextW(hwnd, buf, length + 1)
    return buf.value or ""


def _get_class_name(user32, hwnd) -> str:
    buf = ctypes.create_unicode_buffer(256)
    try:
        if user32.GetClassNameW(hwnd, buf, len(buf)) <= 0:
            return ""
    except Exception:
        return ""
    return buf.value or ""


def _format_element_title(text: str, class_name: str) -> str:
    text = " ".join(str(text or "").split())
    class_name = " ".join(str(class_name or "").split())
    if text and class_name:
        return f"{text} · {class_name}"
    return text or class_name or "控件"


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

            title = _get_window_text(user32, hwnd)
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


def enumerate_visible_ui_elements(
    top_windows: List[Tuple[int, QRect, str]] | None = None,
    *,
    max_per_window: int = 80,
    max_total: int = 600,
) -> List[Tuple[int, QRect, str, int]]:
    """枚举顶层窗口下的可见子控件，返回 [(hwnd, rect, title, parent_hwnd), ...]。

    这是 clean-room 的第一版 UI 元素检测：只使用 Win32 可公开获取的子窗口
    矩形，后续可以在同一输出格式下接入 UI Automation。
    """
    if not sys.platform.startswith("win"):
        return []

    if top_windows is None:
        top_windows = enumerate_visible_windows()
    if not top_windows:
        return []

    user32 = ctypes.windll.user32
    from ctypes import wintypes

    results: List[Tuple[int, QRect, str, int]] = []
    WNDENUMPROC = ctypes.WINFUNCTYPE(
        ctypes.c_bool, wintypes.HWND, wintypes.LPARAM
    )

    def _child_rect(hwnd) -> QRect:
        rect = wintypes.RECT()
        try:
            if not user32.GetWindowRect(hwnd, ctypes.byref(rect)):
                return QRect()
        except Exception:
            return QRect()
        return QRect(int(rect.left), int(rect.top), int(rect.right - rect.left), int(rect.bottom - rect.top))

    for parent_hwnd, parent_rect, parent_title in top_windows:
        if len(results) >= max_total:
            break
        parent_count = 0

        def _callback(hwnd, _lparam):
            nonlocal parent_count
            if parent_count >= max_per_window or len(results) >= max_total:
                return False
            try:
                if hwnd == parent_hwnd:
                    return True
                if not user32.IsWindowVisible(hwnd):
                    return True

                rect = _child_rect(hwnd).intersected(parent_rect)
                if rect.width() < 24 or rect.height() < 16:
                    return True
                if (
                    abs(rect.left() - parent_rect.left()) <= 2
                    and abs(rect.top() - parent_rect.top()) <= 2
                    and abs(rect.width() - parent_rect.width()) <= 4
                    and abs(rect.height() - parent_rect.height()) <= 4
                ):
                    return True

                text = _get_window_text(user32, hwnd)
                class_name = _get_class_name(user32, hwnd)
                title = _format_element_title(text, class_name)
                if "QuickShot" in title or title == parent_title:
                    return True

                results.append((int(hwnd), rect, title, int(parent_hwnd)))
                parent_count += 1
            except Exception:
                pass
            return True

        callback = WNDENUMPROC(_callback)
        try:
            user32.EnumChildWindows(parent_hwnd, callback, 0)
        except Exception:
            continue

    return results
