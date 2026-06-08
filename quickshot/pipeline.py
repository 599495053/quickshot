"""截图后工作流引擎。

将截图后的一系列动作（保存、上传、复制、OCR、Pin 等）抽象为可插拔的 Step。
Pipeline 按配置顺序执行各 Step，并通过 PipelineContext 在 Step 间传递数据。

设计目标：
- Step 之间松耦合，单 Step 失败不应阻塞后续 Step（除非显式声明 critical）
- 通过 Config 控制启用项
- 易于测试：所有 Step 都可独立单元测试
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, List, Optional

from .config import Config
from .uploader import (
    UploaderRegistry,
    UploadError,
    UploadResult,
    format_markdown_link,
)
from .utils import copy_text_to_clipboard, debug_log


@dataclass
class PipelineContext:
    """在 Step 之间传递的运行时上下文。"""

    image_path: Optional[str] = None
    upload_result: Optional[UploadResult] = None
    markdown_link: Optional[str] = None
    ocr_text: Optional[str] = None
    errors: List[str] = field(default_factory=list)
    messages: List[str] = field(default_factory=list)

    def log_error(self, msg: str) -> None:
        self.errors.append(msg)
        debug_log(f"pipeline error: {msg}")

    def log_message(self, msg: str) -> None:
        self.messages.append(msg)


class PipelineStep:
    """单个工作流步骤的抽象。"""

    name: str = "step"

    def is_enabled(self, config: Config) -> bool:  # noqa: ARG002
        return True

    def run(self, ctx: PipelineContext, config: Config) -> None:  # pragma: no cover
        raise NotImplementedError


class OcrStep(PipelineStep):
    """OCR 步骤：对 image_path 跑识别，结果写入 ctx.ocr_text 并复制到剪贴板。

    注意：识别会用文本**覆盖**剪贴板，原本的图片剪贴板会被替换。
    用户在设置中显式开启 workflow_auto_ocr 才会执行。
    """

    name = "ocr"

    def __init__(
        self,
        recognize_fn=None,
        clipboard_writer: Callable[[str], None] = copy_text_to_clipboard,
    ) -> None:
        self._recognize_fn = recognize_fn
        self.clipboard_writer = clipboard_writer

    def is_enabled(self, config: Config) -> bool:
        return bool(getattr(config, "workflow_auto_ocr", False))

    def _recognize(self, image_path: str):
        if self._recognize_fn is not None:
            return self._recognize_fn(image_path)
        # 延迟导入：Pipeline 在不需要时不应付出 OCR 模块加载代价
        from PyQt6.QtGui import QImage
        from .ocr import recognize_text
        image = QImage(image_path)
        if image.isNull():
            return None
        return recognize_text(image)

    def run(self, ctx: PipelineContext, config: Config) -> None:  # noqa: ARG002
        if not ctx.image_path:
            ctx.log_error("OCR 跳过：缺少 image_path")
            return
        try:
            result = self._recognize(ctx.image_path)
        except Exception as exc:  # noqa: BLE001
            ctx.log_error(f"OCR 失败：{exc}")
            return
        if result is None:
            ctx.log_error("OCR 失败：无法读取图片")
            return
        text = (getattr(result, "text", "") or "").strip()
        if not text:
            note = getattr(result, "note", "") or "未识别到文字"
            ctx.log_message(f"OCR：{note}")
            return
        ctx.ocr_text = text
        try:
            self.clipboard_writer(text)
            engine = getattr(result, "engine_label", "OCR")
            ctx.log_message(f"{engine} 已复制识别文本")
        except Exception as exc:  # noqa: BLE001
            ctx.log_error(f"复制 OCR 文本失败：{exc}")


class UploadStep(PipelineStep):
    """上传步骤：使用配置中的上传器把 image_path 上传，得到 url。"""

    name = "upload"

    def __init__(self, registry: UploaderRegistry) -> None:
        self.registry = registry

    def is_enabled(self, config: Config) -> bool:
        return bool(getattr(config, "workflow_auto_upload", False))

    def run(self, ctx: PipelineContext, config: Config) -> None:
        if not ctx.image_path:
            ctx.log_error("上传跳过：缺少 image_path")
            return
        identifier = getattr(config, "workflow_uploader", "local")
        uploader = self.registry.get(identifier)
        if uploader is None:
            ctx.log_error(f"上传跳过：找不到上传器 {identifier}，请在设置页重新选择上传器。")
            return
        if not uploader.is_configured():
            ctx.log_error(f"上传跳过：{uploader.configuration_hint()}")
            return
        try:
            ctx.upload_result = uploader.upload(ctx.image_path)
            ctx.log_message(f"已上传到 {uploader.display_name()}")
        except UploadError as exc:
            ctx.log_error(f"上传失败：{exc}")


class CopyMarkdownStep(PipelineStep):
    """复制 Markdown 链接到剪贴板（需要 UploadStep 已成功）。"""

    name = "copy_markdown"

    def __init__(self, clipboard_writer: Callable[[str], None] = copy_text_to_clipboard) -> None:
        self.clipboard_writer = clipboard_writer

    def is_enabled(self, config: Config) -> bool:
        return bool(getattr(config, "workflow_copy_markdown", False))

    def run(self, ctx: PipelineContext, config: Config) -> None:  # noqa: ARG002
        if ctx.upload_result is None:
            ctx.log_error("Markdown 复制跳过：尚未上传")
            return
        link = format_markdown_link(ctx.upload_result)
        ctx.markdown_link = link
        try:
            self.clipboard_writer(link)
            ctx.log_message("已复制 Markdown 链接")
        except Exception as exc:  # noqa: BLE001
            ctx.log_error(f"复制 Markdown 失败：{exc}")


class Pipeline:
    """按顺序执行启用的 Step。"""

    def __init__(self, steps: Optional[List[PipelineStep]] = None) -> None:
        self.steps: List[PipelineStep] = list(steps) if steps else []

    def add(self, step: PipelineStep) -> None:
        self.steps.append(step)

    def run(self, ctx: PipelineContext, config: Config) -> PipelineContext:
        for step in self.steps:
            try:
                if step.is_enabled(config):
                    step.run(ctx, config)
            except Exception as exc:  # noqa: BLE001
                ctx.log_error(f"步骤 {step.name} 异常：{exc}")
        return ctx


def build_default_pipeline(
    registry: UploaderRegistry,
    clipboard_writer: Callable[[str], None] = copy_text_to_clipboard,
) -> Pipeline:
    """构建默认工作流：上传 → 复制 Markdown。

    注意：OCR 不在这里。OCR 是慢操作，会阻塞主线程几百毫秒到几秒，必须异步执行。
    自动 OCR 在 overlay/_history.py 中通过 OcrJob 异步触发，不进入同步 Pipeline。
    """
    return Pipeline([
        UploadStep(registry),
        CopyMarkdownStep(clipboard_writer=clipboard_writer),
    ])


def should_run_post_capture(config: Config) -> bool:
    """快速判断是否需要在截图后运行 Pipeline，避免无谓的对象创建。

    OCR 走单独的异步路径，不在这里判断。
    """
    return bool(
        getattr(config, "workflow_auto_upload", False)
        or getattr(config, "workflow_copy_markdown", False)
    )


def run_post_capture_pipeline(
    image_path: str,
    config: Config,
    clipboard_writer: Callable[[str], None] = copy_text_to_clipboard,
) -> PipelineContext:
    """便利入口：用默认注册表和默认 Pipeline 处理一次截图后流程。

    若 workflow_* 全部关闭，则直接返回空 Context 不构造 Pipeline。
    """
    ctx = PipelineContext(image_path=image_path)
    if not should_run_post_capture(config):
        return ctx
    # 延迟导入：避免主路径在不需要时引入注册表构造开销
    from .uploader import build_default_registry
    registry = build_default_registry(config=config)
    pipeline = build_default_pipeline(registry, clipboard_writer=clipboard_writer)
    pipeline.run(ctx, config)
    return ctx
