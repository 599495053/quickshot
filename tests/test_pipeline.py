"""工作流 Pipeline 测试。

覆盖 pipeline.py：
- UploadStep 在配置开启/关闭时的行为
- CopyMarkdownStep 依赖上传结果
- Pipeline 顺序执行与错误隔离
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
from quickshot.pipeline import (  # noqa: E402
    CopyMarkdownStep,
    OcrStep,
    Pipeline,
    PipelineContext,
    PipelineStep,
    UploadStep,
    build_default_pipeline,
    run_post_capture_pipeline,
    should_run_post_capture,
)
from quickshot.uploader import (  # noqa: E402
    UploadResult,
    build_default_registry,
)

_app: QApplication | None = None


def setUpModule() -> None:
    global _app
    if QApplication.instance() is None:
        _app = QApplication([])


class _CaptureClipboard:
    """收集 clipboard 写入文本，避免依赖系统剪贴板。"""

    def __init__(self) -> None:
        self.last_text: str | None = None

    def __call__(self, text: str) -> None:
        self.last_text = text


def _make_config(tmpdir: Path) -> Config:
    os.environ["APPDATA"] = str(tmpdir)
    return Config()


class UploadStepTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.tmp_path = Path(self.tmp.name)
        self.config = _make_config(self.tmp_path)
        self.registry = build_default_registry(archive_dir=str(self.tmp_path / "uploads"))
        # 准备一张假图
        self.image = self.tmp_path / "shot.png"
        self.image.write_bytes(b"png")

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_disabled_by_default(self) -> None:
        step = UploadStep(self.registry)
        self.assertFalse(step.is_enabled(self.config))

    def test_enabled_when_config_set(self) -> None:
        self.config.workflow_auto_upload = True
        step = UploadStep(self.registry)
        self.assertTrue(step.is_enabled(self.config))

    def test_upload_writes_result_to_ctx(self) -> None:
        self.config.workflow_auto_upload = True
        step = UploadStep(self.registry)
        ctx = PipelineContext(image_path=str(self.image))
        step.run(ctx, self.config)
        self.assertIsNotNone(ctx.upload_result)
        self.assertTrue(ctx.upload_result.url.startswith("file:"))

    def test_unknown_uploader_logs_error(self) -> None:
        self.config.workflow_auto_upload = True
        self.config.workflow_uploader = "nonexistent"
        step = UploadStep(self.registry)
        ctx = PipelineContext(image_path=str(self.image))
        step.run(ctx, self.config)
        self.assertIsNone(ctx.upload_result)
        self.assertTrue(any("nonexistent" in e for e in ctx.errors))
        self.assertTrue(any("重新选择上传器" in e for e in ctx.errors))

    def test_unconfigured_github_logs_specific_missing_items(self) -> None:
        self.config.workflow_auto_upload = True
        self.config.workflow_uploader = "github"
        registry = build_default_registry(
            archive_dir=str(self.tmp_path / "uploads"),
            config=self.config,
            github_token_provider=lambda: "",
        )
        step = UploadStep(registry)
        ctx = PipelineContext(image_path=str(self.image))

        step.run(ctx, self.config)

        self.assertIsNone(ctx.upload_result)
        self.assertTrue(any("Personal Access Token" in e for e in ctx.errors))

    def test_missing_image_logs_error(self) -> None:
        self.config.workflow_auto_upload = True
        step = UploadStep(self.registry)
        ctx = PipelineContext(image_path=None)
        step.run(ctx, self.config)
        self.assertTrue(ctx.errors)


class CopyMarkdownStepTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.config = _make_config(Path(self.tmp.name))
        self.clipboard = _CaptureClipboard()

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_skipped_without_upload(self) -> None:
        self.config.workflow_copy_markdown = True
        step = CopyMarkdownStep(clipboard_writer=self.clipboard)
        ctx = PipelineContext()
        step.run(ctx, self.config)
        self.assertIsNone(self.clipboard.last_text)
        self.assertTrue(ctx.errors)

    def test_copies_markdown_when_uploaded(self) -> None:
        self.config.workflow_copy_markdown = True
        step = CopyMarkdownStep(clipboard_writer=self.clipboard)
        ctx = PipelineContext(upload_result=UploadResult(url="https://x/a.png", name="a.png"))
        step.run(ctx, self.config)
        self.assertEqual(self.clipboard.last_text, "![a.png](https://x/a.png)")
        self.assertEqual(ctx.markdown_link, "![a.png](https://x/a.png)")

    def test_disabled_by_default(self) -> None:
        step = CopyMarkdownStep(clipboard_writer=self.clipboard)
        self.assertFalse(step.is_enabled(self.config))


class PipelineTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.tmp_path = Path(self.tmp.name)
        self.config = _make_config(self.tmp_path)
        self.registry = build_default_registry(archive_dir=str(self.tmp_path / "uploads"))
        self.image = self.tmp_path / "shot.png"
        self.image.write_bytes(b"png")
        self.clipboard = _CaptureClipboard()

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_upload_then_markdown(self) -> None:
        self.config.workflow_auto_upload = True
        self.config.workflow_copy_markdown = True
        pipeline = Pipeline([
            UploadStep(self.registry),
            CopyMarkdownStep(clipboard_writer=self.clipboard),
        ])
        ctx = PipelineContext(image_path=str(self.image))
        pipeline.run(ctx, self.config)
        self.assertIsNotNone(ctx.upload_result)
        self.assertIsNotNone(self.clipboard.last_text)
        self.assertTrue(self.clipboard.last_text.startswith("!["))

    def test_step_exception_does_not_break_pipeline(self) -> None:
        class BoomStep(PipelineStep):
            name = "boom"

            def is_enabled(self, config: Config) -> bool:  # noqa: ARG002
                return True

            def run(self, ctx: PipelineContext, config: Config) -> None:  # noqa: ARG002
                raise RuntimeError("kaboom")

        called = []

        class TailStep(PipelineStep):
            name = "tail"

            def is_enabled(self, config: Config) -> bool:  # noqa: ARG002
                return True

            def run(self, ctx: PipelineContext, config: Config) -> None:  # noqa: ARG002
                called.append(True)

        pipeline = Pipeline([BoomStep(), TailStep()])
        ctx = PipelineContext()
        pipeline.run(ctx, self.config)
        self.assertEqual(called, [True])
        self.assertTrue(any("kaboom" in e for e in ctx.errors))

    def test_disabled_step_skipped(self) -> None:
        # 默认所有 workflow_* 为 False
        pipeline = build_default_pipeline(self.registry)
        ctx = PipelineContext(image_path=str(self.image))
        pipeline.run(ctx, self.config)
        self.assertIsNone(ctx.upload_result)


class _FakeOcrResult:
    def __init__(self, text: str, engine_label: str = "FakeOCR", note: str = "") -> None:
        self.text = text
        self.engine_label = engine_label
        self.note = note


class OcrStepTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.tmp_path = Path(self.tmp.name)
        self.config = _make_config(self.tmp_path)
        self.image = self.tmp_path / "shot.png"
        self.image.write_bytes(b"png")
        self.clipboard = _CaptureClipboard()

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_disabled_by_default(self) -> None:
        step = OcrStep()
        self.assertFalse(step.is_enabled(self.config))

    def test_enabled_when_config_set(self) -> None:
        self.config.workflow_auto_ocr = True
        step = OcrStep()
        self.assertTrue(step.is_enabled(self.config))

    def test_recognizes_and_writes_clipboard(self) -> None:
        self.config.workflow_auto_ocr = True
        step = OcrStep(
            recognize_fn=lambda path: _FakeOcrResult("hello world"),
            clipboard_writer=self.clipboard,
        )
        ctx = PipelineContext(image_path=str(self.image))
        step.run(ctx, self.config)
        self.assertEqual(ctx.ocr_text, "hello world")
        self.assertEqual(self.clipboard.last_text, "hello world")

    def test_empty_text_does_not_write_clipboard(self) -> None:
        self.config.workflow_auto_ocr = True
        step = OcrStep(
            recognize_fn=lambda path: _FakeOcrResult("", note="未识别"),
            clipboard_writer=self.clipboard,
        )
        ctx = PipelineContext(image_path=str(self.image))
        step.run(ctx, self.config)
        self.assertIsNone(ctx.ocr_text)
        self.assertIsNone(self.clipboard.last_text)

    def test_missing_image_path_logs_error(self) -> None:
        self.config.workflow_auto_ocr = True
        step = OcrStep(recognize_fn=lambda path: _FakeOcrResult("x"))
        ctx = PipelineContext(image_path=None)
        step.run(ctx, self.config)
        self.assertTrue(ctx.errors)

    def test_recognize_exception_logged(self) -> None:
        self.config.workflow_auto_ocr = True

        def boom(_path):
            raise RuntimeError("ocr down")
        step = OcrStep(recognize_fn=boom, clipboard_writer=self.clipboard)
        ctx = PipelineContext(image_path=str(self.image))
        step.run(ctx, self.config)
        self.assertIsNone(self.clipboard.last_text)
        self.assertTrue(any("ocr down" in e for e in ctx.errors))


class PostCaptureEntryTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.tmp_path = Path(self.tmp.name)
        self.config = _make_config(self.tmp_path)
        self.image = self.tmp_path / "shot.png"
        self.image.write_bytes(b"png")

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_should_run_post_capture_false_by_default(self) -> None:
        self.assertFalse(should_run_post_capture(self.config))

    def test_should_run_post_capture_ignores_auto_save(self) -> None:
        self.config.workflow_auto_save = True
        self.assertFalse(should_run_post_capture(self.config))

    def test_should_run_post_capture_true_when_upload_enabled(self) -> None:
        self.config.workflow_auto_upload = True
        self.assertTrue(should_run_post_capture(self.config))

    def test_should_run_post_capture_true_when_markdown_enabled(self) -> None:
        self.config.workflow_copy_markdown = True
        self.assertTrue(should_run_post_capture(self.config))

    def test_should_run_post_capture_ignores_ocr(self) -> None:
        # OCR 走异步路径，不进入同步 Pipeline，应保持 False
        self.config.workflow_auto_ocr = True
        self.assertFalse(should_run_post_capture(self.config))

    def test_run_post_capture_skipped_when_disabled(self) -> None:
        ctx = run_post_capture_pipeline(str(self.image), self.config)
        self.assertIsNone(ctx.upload_result)
        self.assertEqual(ctx.errors, [])

    def test_run_post_capture_executes_when_enabled(self) -> None:
        self.config.workflow_auto_upload = True
        # 默认 uploader 'local' 会写入 %APPDATA%/QuickShot/uploads/
        ctx = run_post_capture_pipeline(str(self.image), self.config)
        self.assertIsNotNone(ctx.upload_result)
        self.assertTrue(ctx.upload_result.url.startswith("file:"))


if __name__ == "__main__":
    unittest.main()
