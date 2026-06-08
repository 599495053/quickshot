"""main.py 非 GUI 逻辑测试。

覆盖 QuickShotApp 中可独立测试的纯逻辑函数。
"""

from __future__ import annotations

import os
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


_app = None


def _ensure_app():
    global _app
    if _app is None:
        from PyQt6.QtWidgets import QApplication

        _app = QApplication.instance() or QApplication(sys.argv)
    return _app


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


class WorkflowPresetTrayTest(unittest.TestCase):

    def test_refresh_workflow_tray_state_refreshes_tooltip_and_menu(self) -> None:
        from quickshot.main import QuickShotApp

        events: list[str] = []
        app = SimpleNamespace(
            refresh_tray_tooltip=lambda: events.append("tooltip"),
            refresh_tray_menu=lambda: events.append("menu"),
        )

        QuickShotApp.refresh_workflow_tray_state(app)

        self.assertEqual(events, ["tooltip", "menu"])

    def test_set_workflow_preset_applies_saves_and_refreshes(self) -> None:
        from quickshot.main import QuickShotApp

        class FakeConfig:
            workflow_preset = "custom"
            auto_copy = True
            workflow_auto_save = False
            workflow_auto_ocr = False
            workflow_auto_upload = False
            workflow_copy_markdown = False
            workflow_privacy_first = False
            saved = False

            def save(self) -> None:
                self.saved = True

        events: list[str] = []
        settings_window = SimpleNamespace(_refresh_workflow_controls=lambda: events.append("settings"))
        app = SimpleNamespace(
            config=FakeConfig(),
            settings_window=settings_window,
            refresh_tray_tooltip=lambda: events.append("tooltip"),
            refresh_tray_menu=lambda: events.append("menu"),
            show_tip=lambda text: events.append(text),
        )

        QuickShotApp.set_workflow_preset(app, "publish")

        self.assertEqual(app.config.workflow_preset, "publish")
        self.assertTrue(app.config.workflow_auto_save)
        self.assertTrue(app.config.workflow_auto_upload)
        self.assertTrue(app.config.workflow_copy_markdown)
        self.assertTrue(app.config.saved)
        self.assertIn("settings", events)
        self.assertIn("tooltip", events)
        self.assertIn("menu", events)
        self.assertTrue(any("发布模式" in event for event in events))

    def test_create_workflow_menu_lists_switchable_presets(self) -> None:
        from PyQt6.QtWidgets import QMenu

        from quickshot.main import QuickShotApp

        _ensure_app()
        config = SimpleNamespace(workflow_preset="privacy")
        app = SimpleNamespace(
            config=config,
            run_after_tray_menu=lambda callback: None,
        )

        parent_menu = QMenu()
        menu = QuickShotApp.create_workflow_menu(app, parent_menu)
        action_texts = [action.text() for action in menu.actions()]

        self.assertIn("当前：隐私模式", action_texts)
        self.assertIn("快速复制", action_texts)
        self.assertIn("自动保存", action_texts)
        self.assertIn("发布模式", action_texts)
        privacy_actions = [action for action in menu.actions() if action.text() == "隐私模式"]
        self.assertEqual(len(privacy_actions), 1)
        self.assertTrue(privacy_actions[0].isChecked())


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
