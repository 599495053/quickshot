"""Settings 扩展测试：配置字段、保存格式、导入导出。"""

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


class ConfigSaveFormatTest(unittest.TestCase):
    """保存格式配置测试。"""

    def setUp(self):
        _ensure_app()
        self._tmp = tempfile.TemporaryDirectory()
        self._prev = os.environ.get("APPDATA")
        os.environ["APPDATA"] = self._tmp.name

    def tearDown(self):
        if self._prev is None:
            os.environ.pop("APPDATA", None)
        else:
            os.environ["APPDATA"] = self._prev
        self._tmp.cleanup()

    def test_default_save_format(self):
        cfg = Config()
        self.assertEqual(cfg.save_format, "png")

    def test_save_format_roundtrip(self):
        cfg = Config()
        cfg.save_format = "jpg"
        cfg.save()
        cfg2 = Config()
        self.assertEqual(cfg2.save_format, "jpg")

    def test_default_jpeg_quality(self):
        cfg = Config()
        self.assertEqual(cfg.jpeg_quality, 90)

    def test_jpeg_quality_clamped(self):
        cfg = Config()
        cfg.jpeg_quality = 150
        cfg.save()
        cfg2 = Config()
        self.assertEqual(cfg2.jpeg_quality, 100)

    def test_jpeg_quality_roundtrip(self):
        cfg = Config()
        cfg.jpeg_quality = 75
        cfg.save()
        cfg2 = Config()
        self.assertEqual(cfg2.jpeg_quality, 75)


class ConfigImportExportTest(unittest.TestCase):
    """配置导入导出测试。"""

    def setUp(self):
        _ensure_app()
        self._tmp = tempfile.TemporaryDirectory()
        self._prev = os.environ.get("APPDATA")
        os.environ["APPDATA"] = self._tmp.name

    def tearDown(self):
        if self._prev is None:
            os.environ.pop("APPDATA", None)
        else:
            os.environ["APPDATA"] = self._prev
        self._tmp.cleanup()

    def test_export_contains_save_format(self):
        cfg = Config()
        cfg.save_format = "webp"
        data = cfg.to_dict()
        self.assertEqual(data["save_format"], "webp")

    def test_export_contains_jpeg_quality(self):
        cfg = Config()
        cfg.jpeg_quality = 80
        data = cfg.to_dict()
        self.assertEqual(data["jpeg_quality"], 80)

    def test_import_save_format(self):
        cfg = Config()
        cfg.import_from_dict({"save_format": "bmp"})
        self.assertEqual(cfg.save_format, "bmp")

    def test_import_jpeg_quality(self):
        cfg = Config()
        cfg.import_from_dict({"jpeg_quality": 60})
        self.assertEqual(cfg.jpeg_quality, 60)


class ConfigHistoryLimitTest(unittest.TestCase):
    """历史限制配置测试。"""

    def setUp(self):
        _ensure_app()
        self._tmp = tempfile.TemporaryDirectory()
        self._prev = os.environ.get("APPDATA")
        os.environ["APPDATA"] = self._tmp.name

    def tearDown(self):
        if self._prev is None:
            os.environ.pop("APPDATA", None)
        else:
            os.environ["APPDATA"] = self._prev
        self._tmp.cleanup()

    def test_default_history_limit(self):
        cfg = Config()
        self.assertEqual(cfg.history_limit, 200)

    def test_history_limit_clamped_min(self):
        cfg = Config()
        cfg.history_limit = 5
        cfg.save()
        cfg2 = Config()
        self.assertEqual(cfg2.history_limit, 20)

    def test_history_limit_clamped_max(self):
        cfg = Config()
        cfg.history_limit = 5000
        cfg.save()
        cfg2 = Config()
        self.assertEqual(cfg2.history_limit, 1000)


class ConfigWorkflowTest(unittest.TestCase):
    """工作流配置测试。"""

    def setUp(self):
        _ensure_app()
        self._tmp = tempfile.TemporaryDirectory()
        self._prev = os.environ.get("APPDATA")
        os.environ["APPDATA"] = self._tmp.name

    def tearDown(self):
        if self._prev is None:
            os.environ.pop("APPDATA", None)
        else:
            os.environ["APPDATA"] = self._prev
        self._tmp.cleanup()

    def test_workflow_defaults(self):
        cfg = Config()
        self.assertEqual(cfg.workflow_preset, "custom")
        self.assertFalse(cfg.workflow_auto_save)
        self.assertFalse(cfg.workflow_auto_ocr)
        self.assertFalse(cfg.workflow_auto_upload)
        self.assertFalse(cfg.workflow_copy_markdown)
        self.assertFalse(cfg.workflow_privacy_first)
        self.assertEqual(cfg.workflow_uploader, "local")

    def test_workflow_roundtrip(self):
        cfg = Config()
        cfg.workflow_auto_save = True
        cfg.workflow_auto_ocr = True
        cfg.workflow_auto_upload = True
        cfg.workflow_privacy_first = True
        cfg.workflow_uploader = "github"
        cfg.save()
        cfg2 = Config()
        self.assertTrue(cfg2.workflow_auto_save)
        self.assertTrue(cfg2.workflow_auto_ocr)
        self.assertTrue(cfg2.workflow_auto_upload)
        self.assertTrue(cfg2.workflow_privacy_first)
        self.assertEqual(cfg2.workflow_uploader, "github")


if __name__ == "__main__":
    unittest.main()
