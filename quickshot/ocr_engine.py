"""OCR 引擎抽象层 — 统一接口 + 注册表模式。

新增 OCR 引擎只需：
1. 创建 OcrEngine 子类
2. 在 build_default_registry() 中注册
"""

from __future__ import annotations

import time
from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, List, Optional

from PyQt6.QtGui import QImage

if TYPE_CHECKING:
    from .ocr import OcrResult


class OcrEngine(ABC):
    """OCR 引擎抽象基类。"""

    @abstractmethod
    def identifier(self) -> str:
        """唯一标识，如 'rapidocr', 'windows_ocr'。"""

    @abstractmethod
    def display_name(self) -> str:
        """界面展示名称，如 'RapidOCR', '系统 OCR'。"""

    @abstractmethod
    def is_available(self) -> bool:
        """引擎是否可用（依赖已安装等）。"""

    @abstractmethod
    def recognize(self, prepared_image: QImage) -> str:
        """对预处理后的 QImage 执行 OCR，返回纯文本。

        prepared_image 已经过 prepare_ocr_image() 处理。
        抛异常表示引擎失败，空字符串表示未识别到文字。
        """


class RapidOcrEngine(OcrEngine):
    """RapidOCR 引擎（进程内 ONNX 推理）。"""

    def identifier(self) -> str:
        return "rapidocr"

    def display_name(self) -> str:
        return "RapidOCR"

    def is_available(self) -> bool:
        from .ocr import is_rapidocr_available
        return is_rapidocr_available()

    def recognize(self, prepared_image: QImage) -> str:
        from .ocr import _qimage_to_numpy, rapidocr_engine
        from .ocr_utils import clean_ocr_text, format_rapidocr_result
        result, _elapsed = rapidocr_engine()(_qimage_to_numpy(prepared_image))
        return clean_ocr_text(format_rapidocr_result(result))


class WindowsOcrEngine(OcrEngine):
    """Windows 系统 OCR 引擎（PowerShell + WinRT API）。"""

    def identifier(self) -> str:
        return "windows_ocr"

    def display_name(self) -> str:
        return "系统 OCR"

    def is_available(self) -> bool:
        import shutil
        return bool(shutil.which("powershell") or shutil.which("pwsh"))

    def recognize(self, prepared_image: QImage) -> str:
        from .ocr import recognize_text_with_windows_ocr
        return recognize_text_with_windows_ocr(prepared_image)


class OcrEngineRegistry:
    """OCR 引擎注册表，按注册顺序（优先级）尝试。"""

    def __init__(self) -> None:
        self._engines: List[OcrEngine] = []

    def register(self, engine: OcrEngine) -> None:
        """注册引擎（后注册的优先级更低）。"""
        self._engines.append(engine)

    def recognize(self, prepared_image: QImage) -> OcrResult:
        """按优先级尝试各引擎，返回统一的 OcrResult。"""
        from .ocr import OcrResult
        started = time.perf_counter()
        errors: List[str] = []

        for engine in self._engines:
            if not engine.is_available():
                continue
            try:
                text = engine.recognize(prepared_image)
                if text.strip():
                    return OcrResult(
                        text=text,
                        engine_key=engine.identifier(),
                        engine_label=engine.display_name(),
                        elapsed_seconds=time.perf_counter() - started,
                    )
                errors.append(f"{engine.display_name()} 未识别到文字")
            except Exception as exc:
                errors.append(f"{engine.display_name()} 失败：{exc}")

        note = "；".join(errors) if errors else "未识别到文字"
        return OcrResult(
            text="",
            engine_key="none",
            engine_label="OCR",
            elapsed_seconds=time.perf_counter() - started,
            note=note,
        )


# 全局默认注册表（惰性初始化）
_DEFAULT_REGISTRY: Optional[OcrEngineRegistry] = None


def get_default_registry() -> OcrEngineRegistry:
    """获取默认的 OCR 引擎注册表（单例）。"""
    global _DEFAULT_REGISTRY
    if _DEFAULT_REGISTRY is None:
        _DEFAULT_REGISTRY = OcrEngineRegistry()
        _DEFAULT_REGISTRY.register(RapidOcrEngine())
        _DEFAULT_REGISTRY.register(WindowsOcrEngine())
    return _DEFAULT_REGISTRY
