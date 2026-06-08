from __future__ import annotations

import os
import sys
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtWidgets import QApplication

from quickshot.dialogs import OcrResultDialog


_app: QApplication | None = None


def _ensure_app() -> QApplication:
    global _app
    if _app is None:
        _app = QApplication.instance() or QApplication(sys.argv)
    return _app


class OcrResultDialogTest(unittest.TestCase):

    def test_can_toggle_between_cleaned_and_raw_text(self) -> None:
        app = _ensure_app()
        dialog = OcrResultDialog("Settings", raw_text="□ Settings")
        try:
            self.assertFalse(dialog.raw_toggle_btn.isHidden())
            self.assertEqual(dialog.current_text(), "Settings")

            dialog.toggle_raw_text()
            self.assertEqual(dialog.current_text(), "□ Settings")
            self.assertEqual(dialog.raw_toggle_btn.text(), "使用清理结果")

            dialog.copy_raw_text()
            self.assertEqual(app.clipboard().text(), "□ Settings")

            dialog.toggle_raw_text()
            self.assertEqual(dialog.current_text(), "Settings")
            self.assertEqual(dialog.raw_toggle_btn.text(), "查看原始结果")
        finally:
            dialog.close()

    def test_raw_toggle_hidden_when_text_is_unchanged(self) -> None:
        _ensure_app()
        dialog = OcrResultDialog("Settings", raw_text="Settings")
        try:
            self.assertTrue(dialog.raw_toggle_btn.isHidden())
        finally:
            dialog.close()


if __name__ == "__main__":
    unittest.main()
