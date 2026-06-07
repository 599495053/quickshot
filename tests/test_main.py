"""main.py 非 GUI 逻辑测试。

覆盖 QuickShotApp 中可独立测试的纯逻辑函数。
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


class HotkeyAllowedTest(unittest.TestCase):
    """测试 _hotkey_allowed 防抖逻辑。"""

    def _make_app_stub(self):
        """创建 QuickShotApp 的最小 stub，仅包含 _hotkey_allowed 所需状态。"""
        from types import SimpleNamespace
        return SimpleNamespace(_last_hotkey_time=0.0)

    def test_first_call_allowed(self) -> None:
        from quickshot.main import QuickShotApp
        app = self._make_app_stub()
        self.assertTrue(QuickShotApp._hotkey_allowed(app))

    def test_rapid_second_call_blocked(self) -> None:
        from quickshot.main import QuickShotApp
        app = self._make_app_stub()
        QuickShotApp._hotkey_allowed(app)
        # 立即再调用应被阻止
        self.assertFalse(QuickShotApp._hotkey_allowed(app))

    def test_delayed_call_allowed(self) -> None:
        import time
        from quickshot.main import QuickShotApp
        app = self._make_app_stub()
        QuickShotApp._hotkey_allowed(app)
        time.sleep(0.4)
        self.assertTrue(QuickShotApp._hotkey_allowed(app))


class FallbackModifierPollingTest(unittest.TestCase):

    def test_accepts_one_key_from_each_modifier_group(self) -> None:
        from quickshot.main import QuickShotApp

        pressed = {0xA2, 0xA0}  # Left Ctrl + Left Shift
        groups = [[0x11, 0xA2, 0xA3], [0x10, 0xA0, 0xA1]]
        self.assertTrue(QuickShotApp._modifier_groups_pressed(lambda vk: vk in pressed, groups))

    def test_requires_every_modifier_group(self) -> None:
        from quickshot.main import QuickShotApp

        pressed = {0xA2}  # Ctrl only
        groups = [[0x11, 0xA2, 0xA3], [0x10, 0xA0, 0xA1]]
        self.assertFalse(QuickShotApp._modifier_groups_pressed(lambda vk: vk in pressed, groups))


class ExceptionHooksTest(unittest.TestCase):
    """测试异常钩子安装。"""

    def test_install_exception_hooks_sets_excepthook(self) -> None:
        import sys
        import threading
        from quickshot.main import install_exception_hooks
        old_sys = sys.excepthook
        old_thread = threading.excepthook
        try:
            install_exception_hooks()
            self.assertIsNotNone(sys.excepthook)
            self.assertIsNotNone(threading.excepthook)
        finally:
            sys.excepthook = old_sys
            threading.excepthook = old_thread


if __name__ == "__main__":
    unittest.main()
