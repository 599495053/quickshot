from __future__ import annotations

import unittest
from unittest.mock import patch

from quickshot import screenshot


class HdrCaptureRoutingTest(unittest.TestCase):
    def test_single_output_hdr_capture_allowed_for_one_screen(self) -> None:
        with patch("quickshot.screenshot._qt_screen_count", return_value=1):
            self.assertTrue(screenshot._can_use_single_output_hdr_capture())

    def test_single_output_hdr_capture_skipped_for_multiple_screens(self) -> None:
        with patch("quickshot.screenshot._qt_screen_count", return_value=2):
            self.assertFalse(screenshot._can_use_single_output_hdr_capture())

    def test_hdr_capture_not_attempted_on_multiple_screens(self) -> None:
        with (
            patch("quickshot.screenshot._can_use_single_output_hdr_capture", return_value=False),
            patch("quickshot.screenshot._grab_virtual_screen_with_wgc_hdr") as wgc,
            patch("quickshot.screenshot._grab_virtual_screen_with_dxcam") as dxcam,
        ):
            self.assertIsNone(screenshot._grab_virtual_screen_with_hdr_if_safe(True))

        wgc.assert_not_called()
        dxcam.assert_not_called()

    def test_hdr_capture_not_attempted_when_disabled(self) -> None:
        with (
            patch("quickshot.screenshot._can_use_single_output_hdr_capture") as can_use,
            patch("quickshot.screenshot._grab_virtual_screen_with_wgc_hdr") as wgc,
            patch("quickshot.screenshot._grab_virtual_screen_with_dxcam") as dxcam,
        ):
            self.assertIsNone(screenshot._grab_virtual_screen_with_hdr_if_safe(False))

        can_use.assert_not_called()
        wgc.assert_not_called()
        dxcam.assert_not_called()


if __name__ == "__main__":
    unittest.main()
