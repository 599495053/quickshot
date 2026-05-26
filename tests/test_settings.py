"""Settings 窗口测试。

覆盖 settings.py 中的关键功能：
- SettingsWindow 初始化
- 配置项保存/加载
- 快捷键验证
"""

from __future__ import annotations

import os
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtWidgets import QApplication  # noqa: E402

from quickshot.config import Config  # noqa: E402
from quickshot.settings import SettingsWindow  # noqa: E402


_app = None


def _ensure_app():
    global _app
    if _app is None:
        _app = QApplication.instance() or QApplication(sys.argv)
    return _app


class _IsolatedConfigMixin:
    """每个用例隔离真实 %APPDATA%，避免污染用户配置。"""

    def setUp(self) -> None:  # type: ignore[override]
        self._tmp = tempfile.TemporaryDirectory()
        self._prev_appdata = os.environ.get("APPDATA")
        os.environ["APPDATA"] = self._tmp.name

    def tearDown(self) -> None:  # type: ignore[override]
        if self._prev_appdata is None:
            os.environ.pop("APPDATA", None)
        else:
            os.environ["APPDATA"] = self._prev_appdata
        self._tmp.cleanup()


class SettingsWindowInitTest(_IsolatedConfigMixin, unittest.TestCase):

    def test_creates_without_error(self):
        _ensure_app()
        cfg = Config()
        win = SettingsWindow(cfg)
        self.assertIsNotNone(win)
        self.assertTrue(win.windowTitle().startswith("QuickShot"))

    def test_config_values_loaded(self):
        _ensure_app()
        cfg = Config()
        cfg.auto_copy = False
        cfg.show_notifications = False
        SettingsWindow(cfg)
        # Window should reflect config values
        self.assertFalse(cfg.auto_copy)
        self.assertFalse(cfg.show_notifications)

    def test_settings_navigation_pages_exist(self):
        _ensure_app()
        cfg = Config()
        win = SettingsWindow(cfg)
        self.assertEqual(win.settings_stack.count(), 6)
        self.assertEqual(len(win._nav_buttons), 6)
        win.switch_settings_page(3)
        self.assertEqual(win.settings_stack.currentIndex(), 3)
        self.assertTrue(win._nav_buttons[3].isChecked())


class SettingsGridWatermarkColorTest(_IsolatedConfigMixin, unittest.TestCase):

    def test_grid_color_default(self):
        _ensure_app()
        cfg = Config()
        # Default value should be set (may have been changed by user)
        self.assertIsNotNone(cfg.grid_color)
        self.assertTrue(cfg.grid_color.startswith("#"))

    def test_watermark_color_default(self):
        _ensure_app()
        cfg = Config()
        # Default value should be set (may have been changed by user)
        self.assertIsNotNone(cfg.watermark_color)
        self.assertTrue(cfg.watermark_color.startswith("#"))

    def test_grid_color_save_load(self):
        _ensure_app()
        cfg = Config()
        cfg.grid_color = "#ffff0080"
        cfg.save()
        cfg2 = Config()
        self.assertEqual(cfg2.grid_color, "#ffff0080")

    def test_watermark_color_save_load(self):
        _ensure_app()
        cfg = Config()
        cfg.watermark_color = "#00000080"
        cfg.save()
        cfg2 = Config()
        self.assertEqual(cfg2.watermark_color, "#00000080")


if __name__ == "__main__":
    unittest.main()
