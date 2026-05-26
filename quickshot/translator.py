"""翻译模块 - 使用 deep-translator 提供本地翻译功能"""

from __future__ import annotations

import logging
from typing import Optional

from PyQt6.QtCore import QThread, pyqtSignal

logger = logging.getLogger(__name__)


class TranslateJob(QThread):
    """异步翻译任务，参考 OcrJob 的信号模式"""

    succeeded = pyqtSignal(str)
    failed = pyqtSignal(str)
    finished = pyqtSignal()

    def __init__(
        self,
        text: str,
        target_lang: str = "zh-CN",
        parent=None,
    ) -> None:
        super().__init__(parent)
        self._text = text
        self._target_lang = target_lang
        self._cancelled = False

    def cancel(self) -> None:
        self._cancelled = True

    def run(self) -> None:
        if self._cancelled:
            self.finished.emit()
            return

        try:
            result = translate_text(self._text, self._target_lang)
            if self._cancelled:
                self.finished.emit()
                return
            if result:
                self.succeeded.emit(result)
            else:
                self.failed.emit("翻译结果为空")
        except Exception as exc:
            if not self._cancelled:
                logger.exception("翻译失败")
                self.failed.emit(f"翻译失败：{exc}")
        finally:
            self.finished.emit()


def translate_text(text: str, target_lang: str = "zh-CN") -> Optional[str]:
    """同步翻译文本，返回翻译结果。

    Args:
        text: 要翻译的文本。
        target_lang: 目标语言代码，默认 zh-CN。

    Returns:
        翻译后的文本，失败时返回 None。
    """
    if not text or not text.strip():
        return None

    try:
        from deep_translator import GoogleTranslator

        translator = GoogleTranslator(source="auto", target=target_lang)
        result = translator.translate(text.strip())
        return result
    except Exception:
        logger.exception("翻译异常")
        return None
