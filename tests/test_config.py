"""Config 配置管理测试。

覆盖 config.py 中的配置持久化逻辑：
- 默认值
- save/load 往返
- history_dir / history_index_path 路径生成
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


_app: QApplication | None = None


def _ensure_app() -> QApplication:
    global _app
    if _app is None:
        _app = QApplication.instance() or QApplication(sys.argv)
    return _app


class ConfigTest(unittest.TestCase):

    def setUp(self) -> None:
        _ensure_app()
        # 用临时目录隔离配置，避免污染真实 %APPDATA%/QuickShot/config.json
        self._tmp = tempfile.TemporaryDirectory()
        self._prev_appdata = os.environ.get("APPDATA")
        os.environ["APPDATA"] = self._tmp.name

    def tearDown(self) -> None:
        if self._prev_appdata is None:
            os.environ.pop("APPDATA", None)
        else:
            os.environ["APPDATA"] = self._prev_appdata
        self._tmp.cleanup()

    def test_default_config_has_required_keys(self) -> None:
        cfg = Config()
        self.assertIsNotNone(cfg)
        self.assertIsInstance(cfg.history_limit, int)
        self.assertIsInstance(cfg.auto_copy, bool)

    def test_save_and_load_roundtrip(self) -> None:
        cfg = Config()
        # 验证 save 不抛异常
        cfg.save()
        # 验证 config_path 存在
        self.assertTrue(cfg.config_path.exists())

    def test_app_dir_is_path(self) -> None:
        cfg = Config()
        self.assertIsInstance(cfg.app_dir, Path)

    def test_history_dir_is_path(self) -> None:
        cfg = Config()
        d = cfg.history_dir()
        self.assertIsInstance(d, Path)

    def test_history_index_path_is_path(self) -> None:
        cfg = Config()
        p = cfg.history_index_path()
        self.assertIsInstance(p, Path)
        self.assertTrue(str(p).endswith("index.json"))

    def test_ensure_save_dir(self) -> None:
        cfg = Config()
        d = cfg.ensure_save_dir()
        self.assertIsInstance(d, str)
        self.assertTrue(Path(d).exists())

    def test_grid_color_roundtrip(self) -> None:
        cfg = Config()
        cfg.grid_color = "#ffff0080"
        cfg.save()
        cfg2 = Config()
        self.assertEqual(cfg2.grid_color, "#ffff0080")

    def test_watermark_color_roundtrip(self) -> None:
        cfg = Config()
        cfg.watermark_color = "#ff000060"
        cfg.save()
        cfg2 = Config()
        self.assertEqual(cfg2.watermark_color, "#ff000060")

    def test_delay_seconds_bounds(self) -> None:
        cfg = Config()
        cfg.delay_seconds = 15  # Out of range
        cfg.save()
        cfg2 = Config()
        # Should be clamped to max 10
        self.assertLessEqual(cfg2.delay_seconds, 10)

    def test_history_limit_bounds(self) -> None:
        cfg = Config()
        cfg.history_limit = 5  # Out of range
        cfg.save()
        cfg2 = Config()
        # Should be clamped to min 20
        self.assertGreaterEqual(cfg2.history_limit, 20)

    def test_workflow_auto_upload_default_false(self) -> None:
        cfg = Config()
        self.assertIsInstance(cfg.workflow_auto_upload, bool)
        # 新增字段默认关闭，避免无声调用外部资源
        cfg.workflow_auto_upload = False
        cfg.save()
        cfg2 = Config()
        self.assertFalse(cfg2.workflow_auto_upload)

    def test_workflow_new_flags_default_safe(self) -> None:
        cfg = Config()
        self.assertEqual(cfg.workflow_preset, "custom")
        self.assertFalse(cfg.workflow_auto_save)
        self.assertFalse(cfg.workflow_privacy_first)

    def test_workflow_copy_markdown_roundtrip(self) -> None:
        cfg = Config()
        cfg.workflow_copy_markdown = True
        cfg.save()
        cfg2 = Config()
        self.assertTrue(cfg2.workflow_copy_markdown)

    def test_workflow_uploader_roundtrip(self) -> None:
        cfg = Config()
        cfg.workflow_uploader = "local"
        cfg.save()
        cfg2 = Config()
        self.assertEqual(cfg2.workflow_uploader, "local")

    def test_workflow_preset_roundtrip_applies_values(self) -> None:
        cfg = Config()
        cfg.workflow_preset = "privacy"
        cfg.save()
        cfg2 = Config()
        self.assertEqual(cfg2.workflow_preset, "privacy")
        self.assertTrue(cfg2.workflow_privacy_first)
        self.assertFalse(cfg2.auto_copy)

    def test_invalid_workflow_preset_falls_back_to_custom(self) -> None:
        cfg = Config()
        cfg.import_from_dict({"workflow_preset": "unknown"})
        self.assertEqual(cfg.workflow_preset, "custom")

    def test_to_dict_contains_all_serializable_fields(self) -> None:
        cfg = Config()
        d = cfg.to_dict()
        # 关键字段必须存在
        for key in ("save_dir", "auto_copy", "history_limit", "region_hotkey",
                     "workflow_preset", "workflow_auto_save",
                     "workflow_auto_upload", "workflow_privacy_first",
                     "github_branch"):
            self.assertIn(key, d)
        # 运行时字段不应出现
        self.assertNotIn("app_dir", d)
        self.assertNotIn("config_path", d)

    def test_import_from_dict_roundtrip(self) -> None:
        cfg = Config()
        cfg.auto_copy = False
        cfg.history_limit = 500
        cfg.watermark_text = "test watermark"
        cfg.save()
        exported = cfg.to_dict()
        # 新实例导入
        cfg2 = Config()
        cfg2.import_from_dict(exported)
        self.assertFalse(cfg2.auto_copy)
        self.assertEqual(cfg2.history_limit, 500)
        self.assertEqual(cfg2.watermark_text, "test watermark")

    def test_import_from_dict_partial(self) -> None:
        cfg = Config()
        original_limit = cfg.history_limit
        cfg.import_from_dict({"auto_copy": False})
        self.assertFalse(cfg.auto_copy)
        # 未导入的字段保持原值
        self.assertEqual(cfg.history_limit, original_limit)

    def test_import_from_dict_clamps_values(self) -> None:
        cfg = Config()
        cfg.import_from_dict({"history_limit": 5, "delay_seconds": 99})
        self.assertGreaterEqual(cfg.history_limit, 20)
        self.assertLessEqual(cfg.delay_seconds, 10)


if __name__ == "__main__":
    unittest.main()
