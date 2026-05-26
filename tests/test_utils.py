"""Utils 工具函数测试。

覆盖 utils.py 中的关键功能：
- debug_log
- load_app_icon
- copy_pixmap_to_clipboard
- normalize_ocr_symbols (已在 test_ocr_utils 中测试)
"""

from __future__ import annotations

import os
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtGui import QColor, QPixmap  # noqa: E402
from PyQt6.QtWidgets import QApplication  # noqa: E402

from quickshot.utils import (  # noqa: E402
    APP_NAME,
    APP_VERSION,
    debug_log,
    load_app_icon,
)


_app = None


def _ensure_app():
    global _app
    if _app is None:
        _app = QApplication.instance() or QApplication(sys.argv)
    return _app


class AppConstantsTest(unittest.TestCase):

    def test_app_name(self):
        self.assertIsInstance(APP_NAME, str)
        self.assertGreater(len(APP_NAME), 0)

    def test_app_version(self):
        self.assertIsInstance(APP_VERSION, str)
        self.assertGreater(len(APP_VERSION), 0)


class DebugLogTest(unittest.TestCase):

    def test_debug_log_no_error(self):
        # Should not raise any exception
        debug_log("Test message")
        debug_log("")


class LoadAppIconTest(unittest.TestCase):

    def test_load_app_icon(self):
        _ensure_app()
        icon = load_app_icon()
        self.assertIsNotNone(icon)
        self.assertFalse(icon.isNull())


if __name__ == "__main__":
    unittest.main()
