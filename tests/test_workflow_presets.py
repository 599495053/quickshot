from __future__ import annotations

import os
import tempfile
import unittest

from quickshot.config import Config
from quickshot.workflow_presets import (
    WORKFLOW_PRESET_DEFAULT,
    apply_workflow_preset,
    normalize_workflow_preset,
    workflow_preset_values,
)


class WorkflowPresetTest(unittest.TestCase):

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self._prev_appdata = os.environ.get("APPDATA")
        os.environ["APPDATA"] = self._tmp.name

    def tearDown(self) -> None:
        if self._prev_appdata is None:
            os.environ.pop("APPDATA", None)
        else:
            os.environ["APPDATA"] = self._prev_appdata
        self._tmp.cleanup()

    def test_invalid_preset_normalizes_to_custom(self) -> None:
        self.assertEqual(normalize_workflow_preset("missing"), WORKFLOW_PRESET_DEFAULT)

    def test_publish_preset_enables_save_upload_and_markdown(self) -> None:
        cfg = Config()
        changed = apply_workflow_preset(cfg, "publish")

        self.assertTrue(changed)
        self.assertEqual(cfg.workflow_preset, "publish")
        self.assertFalse(cfg.auto_copy)
        self.assertTrue(cfg.workflow_auto_save)
        self.assertTrue(cfg.workflow_auto_upload)
        self.assertTrue(cfg.workflow_copy_markdown)
        self.assertFalse(cfg.workflow_auto_ocr)

    def test_custom_preset_keeps_existing_values(self) -> None:
        cfg = Config()
        cfg.workflow_auto_upload = True

        changed = apply_workflow_preset(cfg, "custom")

        self.assertFalse(changed)
        self.assertTrue(cfg.workflow_auto_upload)

    def test_preset_values_returns_copy(self) -> None:
        values = workflow_preset_values("privacy")
        values["workflow_privacy_first"] = False

        self.assertTrue(workflow_preset_values("privacy")["workflow_privacy_first"])


if __name__ == "__main__":
    unittest.main()
