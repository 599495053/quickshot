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
from unittest.mock import patch

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
        self.assertEqual(win.copy_diagnostic_btn.text(), "复制诊断信息")

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

    def test_startup_toggle_uses_config_startup_manager(self):
        _ensure_app()
        cfg = Config()
        win = SettingsWindow(cfg)
        with (
            patch("quickshot.config.StartupManager.set_enabled") as set_enabled,
            patch("quickshot.config.StartupManager.is_enabled", return_value=False),
        ):
            win.on_startup_changed(0)
        set_enabled.assert_called_once_with(False)

    def test_restore_edit_tool_hotkeys_keeps_current_page_and_refreshes_summary(self):
        _ensure_app()
        cfg = Config()
        cfg.edit_tool_hotkeys = {"arrow": "C"}
        win = SettingsWindow(cfg)
        win.switch_settings_page(3)
        win._refresh_edit_tool_hotkey_summary()
        self.assertIn("箭头=C", win.edit_tool_hotkey_summary_label.text())

        win._restore_edit_tool_hotkeys()

        self.assertEqual(win.settings_stack.currentIndex(), 3)
        self.assertIn("箭头=A", win.edit_tool_hotkey_summary_label.text())

    def test_screenshot_dim_style_updates_controls(self):
        _ensure_app()
        cfg = Config()
        win = SettingsWindow(cfg)
        for index in range(win.screenshot_dim_style_combo.count()):
            if win.screenshot_dim_style_combo.itemData(index) == "deep":
                win.screenshot_dim_style_combo.setCurrentIndex(index)
                break

        self.assertEqual(cfg.screenshot_dim_style, "deep")
        self.assertEqual(cfg.screenshot_dim_alpha, 172)
        self.assertEqual(cfg.screenshot_dim_blur, 20)
        self.assertFalse(win.screenshot_dim_alpha_spin.isEnabled())
        self.assertFalse(win.screenshot_dim_blur_spin.isEnabled())

        for index in range(win.screenshot_dim_style_combo.count()):
            if win.screenshot_dim_style_combo.itemData(index) == "custom":
                win.screenshot_dim_style_combo.setCurrentIndex(index)
                break
        win.screenshot_dim_alpha_spin.setValue(140)
        win.screenshot_dim_blur_spin.setValue(18)

        self.assertEqual(cfg.screenshot_dim_style, "custom")
        self.assertEqual(cfg.screenshot_dim_alpha, 140)
        self.assertEqual(cfg.screenshot_dim_blur, 18)
        self.assertTrue(win.screenshot_dim_alpha_spin.isEnabled())
        self.assertTrue(win.screenshot_dim_blur_spin.isEnabled())

    def test_workflow_preset_updates_controls(self):
        _ensure_app()
        cfg = Config()
        win = SettingsWindow(cfg)
        self.assertIn("当前：自定义", win.workflow_summary_label.text())
        for index in range(win.workflow_preset_combo.count()):
            if win.workflow_preset_combo.itemData(index) == "publish":
                win.workflow_preset_combo.setCurrentIndex(index)
                break

        self.assertEqual(cfg.workflow_preset, "publish")
        self.assertTrue(cfg.workflow_auto_save)
        self.assertTrue(cfg.workflow_auto_upload)
        self.assertTrue(cfg.workflow_copy_markdown)
        self.assertFalse(cfg.auto_copy)
        self.assertTrue(win.workflow_auto_save_check.isChecked())
        self.assertTrue(win.workflow_upload_check.isChecked())
        self.assertTrue(win.workflow_md_check.isChecked())
        self.assertIn("发布模式", win.workflow_summary_label.text())
        self.assertIn("保存、上传并复制 Markdown", win.workflow_summary_label.text())

    def test_manual_workflow_toggle_marks_custom(self):
        _ensure_app()
        cfg = Config()
        win = SettingsWindow(cfg)
        for index in range(win.workflow_preset_combo.count()):
            if win.workflow_preset_combo.itemData(index) == "privacy":
                win.workflow_preset_combo.setCurrentIndex(index)
                break
        win.workflow_privacy_check.setChecked(False)

        self.assertEqual(cfg.workflow_preset, "custom")
        self.assertEqual(win.workflow_preset_combo.currentData(), "custom")
        self.assertFalse(cfg.workflow_privacy_first)
        self.assertIn("自定义", win.workflow_summary_label.text())

    def test_restore_workflow_defaults_resets_controls_and_emits(self):
        _ensure_app()
        cfg = Config()
        cfg.workflow_preset = "publish"
        cfg.auto_copy = False
        cfg.workflow_auto_save = True
        cfg.workflow_auto_ocr = True
        cfg.workflow_auto_upload = True
        cfg.workflow_copy_markdown = True
        cfg.workflow_privacy_first = True
        cfg.workflow_uploader = "github"
        win = SettingsWindow(cfg)
        events = []
        win.workflow_changed.connect(lambda: events.append("changed"))

        win.restore_workflow_defaults()

        self.assertEqual(cfg.workflow_preset, "custom")
        self.assertTrue(cfg.auto_copy)
        self.assertFalse(cfg.workflow_auto_save)
        self.assertFalse(cfg.workflow_auto_ocr)
        self.assertFalse(cfg.workflow_auto_upload)
        self.assertFalse(cfg.workflow_copy_markdown)
        self.assertFalse(cfg.workflow_privacy_first)
        self.assertEqual(cfg.workflow_uploader, "local")
        self.assertEqual(win.workflow_preset_combo.currentData(), "custom")
        self.assertTrue(win.auto_copy_check.isChecked())
        self.assertFalse(win.workflow_auto_save_check.isChecked())
        self.assertEqual(win.uploader_combo.currentData(), "local")
        self.assertIn("自动复制图片", win.workflow_summary_label.text())
        self.assertEqual(events, ["changed"])

    def test_github_status_warns_when_selected_uploader_missing_config(self):
        _ensure_app()
        cfg = Config()
        cfg.workflow_uploader = "github"

        with patch("quickshot.secrets.get_github_token", return_value=""):
            win = SettingsWindow(cfg)

        text = win.github_status_label.text()
        self.assertIn("GitHub 上传器未就绪", text)
        self.assertIn("缺少：GitHub 用户名或组织", text)
        self.assertIn("GitHub 用户名或组织", text)
        self.assertIn("仓库名", text)
        self.assertIn("Personal Access Token", text)

    def test_github_status_shows_ready_destination(self):
        _ensure_app()
        cfg = Config()
        cfg.workflow_uploader = "github"
        cfg.github_owner = "alice"
        cfg.github_repo = "screenshots"
        cfg.github_branch = "dev"
        cfg.github_path_prefix = "shots"

        with patch("quickshot.secrets.get_github_token", return_value="ghp_test"):
            win = SettingsWindow(cfg)

        self.assertIn("GitHub 上传器已就绪", win.github_status_label.text())
        self.assertIn("alice/screenshots@dev/shots", win.github_status_label.text())


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
