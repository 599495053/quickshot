"""PinWindow 测试。

覆盖 pin.py 中：
- 缩放控制（set_scale_keep_center / zoom_in / zoom_out / reset_scale）
- 翻转（flip_horizontal / flip_vertical）
- 锁定与置顶切换
- 透明度控制
- 位置微调（nudge_position）
- 匹配关键字
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

from PyQt6.QtGui import QImage, QPixmap  # noqa: E402
from PyQt6.QtWidgets import QApplication  # noqa: E402

from quickshot.config import Config  # noqa: E402
from quickshot.pin import PinWindow  # noqa: E402

_app: QApplication | None = None


def setUpModule() -> None:
    global _app
    if QApplication.instance() is None:
        _app = QApplication([])


def _make_pixmap(width: int = 200, height: int = 120, color: int = 0xFF0000FF) -> QPixmap:
    image = QImage(width, height, QImage.Format.Format_ARGB32)
    image.fill(color)
    pixmap = QPixmap.fromImage(image)
    pixmap.setDevicePixelRatio(1.0)
    return pixmap


def _isolated_config(tmp_path: Path) -> Config:
    os.environ["APPDATA"] = str(tmp_path)
    return Config()


class PinScaleTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.config = _isolated_config(Path(self.tmp.name))
        self.pin = PinWindow(_make_pixmap(), self.config)

    def tearDown(self) -> None:
        self.pin.close()
        self.tmp.cleanup()

    def test_set_scale_clamped_to_min(self) -> None:
        self.pin.set_scale_keep_center(0.01)
        self.assertGreaterEqual(self.pin.scale, 0.12)

    def test_set_scale_clamped_to_max(self) -> None:
        self.pin.set_scale_keep_center(10.0)
        self.assertLessEqual(self.pin.scale, 4.0)

    def test_zoom_in_increases_scale(self) -> None:
        before = self.pin.scale
        self.pin.zoom_in()
        self.assertGreater(self.pin.scale, before)

    def test_zoom_out_decreases_scale(self) -> None:
        before = self.pin.scale
        self.pin.zoom_out()
        self.assertLess(self.pin.scale, before)

    def test_reset_scale_to_one(self) -> None:
        self.pin.set_scale_keep_center(0.5)
        self.pin.reset_scale()
        self.assertAlmostEqual(self.pin.scale, 1.0, places=3)

    def test_set_scale_keeps_center(self) -> None:
        before_center = self.pin.geometry().center()
        self.pin.set_scale_keep_center(0.5)
        after_center = self.pin.geometry().center()
        # 中心点应基本不变（允许 1px 误差）
        self.assertLessEqual(abs(after_center.x() - before_center.x()), 1)
        self.assertLessEqual(abs(after_center.y() - before_center.y()), 1)


class PinFlipTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.config = _isolated_config(Path(self.tmp.name))
        self.pin = PinWindow(_make_pixmap(40, 20), self.config)

    def tearDown(self) -> None:
        self.pin.close()
        self.tmp.cleanup()

    def test_flip_horizontal_preserves_size(self) -> None:
        before = (self.pin.pixmap.width(), self.pin.pixmap.height())
        self.pin.flip_horizontal()
        after = (self.pin.pixmap.width(), self.pin.pixmap.height())
        self.assertEqual(before, after)

    def test_flip_vertical_preserves_size(self) -> None:
        before = (self.pin.pixmap.width(), self.pin.pixmap.height())
        self.pin.flip_vertical()
        after = (self.pin.pixmap.width(), self.pin.pixmap.height())
        self.assertEqual(before, after)

    def test_double_flip_horizontal_is_identity_size(self) -> None:
        original = (self.pin.pixmap.width(), self.pin.pixmap.height())
        self.pin.flip_horizontal()
        self.pin.flip_horizontal()
        self.assertEqual((self.pin.pixmap.width(), self.pin.pixmap.height()), original)


class PinStateTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.config = _isolated_config(Path(self.tmp.name))
        self.pin = PinWindow(_make_pixmap(), self.config)

    def tearDown(self) -> None:
        self.pin.close()
        self.tmp.cleanup()

    def test_default_state(self) -> None:
        self.assertTrue(self.pin.always_on_top)
        self.assertFalse(self.pin.locked)
        self.assertEqual(self.pin.opacity_percent, 100)

    def test_toggle_locked(self) -> None:
        self.assertFalse(self.pin.locked)
        self.pin.toggle_locked()
        self.assertTrue(self.pin.locked)
        self.pin.toggle_locked()
        self.assertFalse(self.pin.locked)

    def test_toggle_always_on_top(self) -> None:
        before = self.pin.always_on_top
        self.pin.toggle_always_on_top()
        self.assertNotEqual(self.pin.always_on_top, before)

    def test_opacity_clamped(self) -> None:
        self.pin.set_opacity_percent(5)
        self.assertGreaterEqual(self.pin.opacity_percent, 35)
        self.pin.set_opacity_percent(200)
        self.assertLessEqual(self.pin.opacity_percent, 100)

    def test_set_display_name_strips(self) -> None:
        self.pin.set_display_name("  自定义名  ")
        self.assertEqual(self.pin.name, "自定义名")

    def test_empty_name_keeps_original(self) -> None:
        before = self.pin.name
        self.pin.set_display_name("   ")
        self.assertEqual(self.pin.name, before)


class PinPositionTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.config = _isolated_config(Path(self.tmp.name))
        self.pin = PinWindow(_make_pixmap(), self.config)

    def tearDown(self) -> None:
        self.pin.close()
        self.tmp.cleanup()

    def test_nudge_moves_when_unlocked(self) -> None:
        before = self.pin.pos()
        self.pin.nudge_position(10, 5)
        after = self.pin.pos()
        self.assertEqual(after.x() - before.x(), 10)
        self.assertEqual(after.y() - before.y(), 5)

    def test_nudge_ignored_when_locked(self) -> None:
        self.pin.set_locked(True)
        before = self.pin.pos()
        self.pin.nudge_position(10, 5)
        after = self.pin.pos()
        self.assertEqual(before, after)


class PinMatchKeywordTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.config = _isolated_config(Path(self.tmp.name))
        self.pin = PinWindow(_make_pixmap(), self.config)
        self.pin.set_display_name("项目截图")

    def tearDown(self) -> None:
        self.pin.close()
        self.tmp.cleanup()

    def test_empty_keyword_matches_all(self) -> None:
        self.assertTrue(self.pin.match_keyword(""))

    def test_keyword_matches_name(self) -> None:
        self.assertTrue(self.pin.match_keyword("项目"))

    def test_keyword_no_match(self) -> None:
        self.assertFalse(self.pin.match_keyword("不存在的内容"))

    def test_keyword_matches_status(self) -> None:
        # 默认置顶，可拖动
        self.assertTrue(self.pin.match_keyword("置顶"))
        self.pin.set_locked(True)
        self.assertTrue(self.pin.match_keyword("锁定"))


if __name__ == "__main__":
    unittest.main()
