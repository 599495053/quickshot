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
