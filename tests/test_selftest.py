from __future__ import annotations

import unittest
from unittest.mock import patch

from PyQt6.QtGui import QImage

import launcher
from quickshot import selftest


class PackagedSelfTestTest(unittest.TestCase):
    def test_privacy_ocr_fallback_self_test_passes_when_rects_are_found(self) -> None:
        image = QImage(10, 10, QImage.Format.Format_RGB32)

        with patch("quickshot.selftest.ocr.is_rapidocr_available", return_value=False):
            with patch("quickshot.selftest._make_privacy_sample_qimage", return_value=image):
                with patch("quickshot.selftest.ocr.detect_privacy_info", return_value=[(1, 2, 3, 4)]):
                    selftest.run_privacy_ocr_fallback_self_test()

    def test_privacy_ocr_fallback_self_test_requires_lightweight_build(self) -> None:
        with patch("quickshot.selftest.ocr.is_rapidocr_available", return_value=True):
            with self.assertRaisesRegex(RuntimeError, "RapidOCR is available"):
                selftest.run_privacy_ocr_fallback_self_test()

    def test_privacy_ocr_fallback_self_test_fails_without_rects(self) -> None:
        image = QImage(10, 10, QImage.Format.Format_RGB32)

        with patch("quickshot.selftest.ocr.is_rapidocr_available", return_value=False):
            with patch("quickshot.selftest._make_privacy_sample_qimage", return_value=image):
                with patch("quickshot.selftest.ocr.detect_privacy_info", return_value=[]):
                    with self.assertRaisesRegex(RuntimeError, "did not detect privacy text"):
                        selftest.run_privacy_ocr_fallback_self_test()

    def test_run_self_test_returns_success_status(self) -> None:
        with patch("quickshot.selftest.run_privacy_ocr_fallback_self_test"):
            self.assertEqual(selftest.run_self_test(selftest.PRIVACY_OCR_FALLBACK_TEST), 0)

    def test_run_self_test_dispatches_overlay_edit_smoke(self) -> None:
        with patch("quickshot.selftest.run_overlay_edit_smoke_self_test") as run_overlay:
            self.assertEqual(selftest.run_self_test(selftest.OVERLAY_EDIT_SMOKE_TEST), 0)

        run_overlay.assert_called_once_with()

    def test_run_self_test_dispatches_capture_backend_smoke(self) -> None:
        with patch("quickshot.selftest.run_capture_backend_smoke_self_test") as run_capture:
            self.assertEqual(selftest.run_self_test(selftest.CAPTURE_BACKEND_SMOKE_TEST), 0)

        run_capture.assert_called_once_with()

    def test_run_self_test_returns_failure_status(self) -> None:
        self.assertEqual(selftest.run_self_test("missing-test"), 1)

    def test_launcher_dispatches_self_test_argument(self) -> None:
        with patch("sys.argv", ["QuickShot.exe", selftest.SELF_TEST_ARG, selftest.PRIVACY_OCR_FALLBACK_TEST]):
            with patch("quickshot.selftest.run_self_test", return_value=7) as run_self_test:
                with self.assertRaises(SystemExit) as raised:
                    launcher.run()

        run_self_test.assert_called_once_with(selftest.PRIVACY_OCR_FALLBACK_TEST)
        self.assertEqual(raised.exception.code, 7)


if __name__ == "__main__":
    unittest.main()
