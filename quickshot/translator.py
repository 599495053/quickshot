"""翻译模块 - 使用 deep-translator 提供本地翻译功能"""

from __future__ import annotations

import logging
import socket
from typing import Optional

from PyQt6.QtCore import QThread, pyqtSignal

from .constants import TRANSLATE_TIMEOUT_SECONDS

logger = logging.getLogger(__name__)

# 网络请求超时（秒）
TRANSLATE_TIMEOUT = TRANSLATE_TIMEOUT_SECONDS


def _translate_with_timeout(func, *args, timeout=TRANSLATE_TIMEOUT, **kwargs):
    """为翻译函数添加超时保护。

    通过设置 socket 默认超时来防止网络请求无限阻塞。
    """
    old_timeout = socket.getdefaulttimeout()
    try:
        socket.setdefaulttimeout(timeout)
        return func(*args, **kwargs)
    finally:
        socket.setdefaulttimeout(old_timeout)


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
                self.failed.emit("翻译结果为空，请检查网络连接")
        except Exception as exc:
            if not self._cancelled:
                logger.exception("翻译失败")
                error_msg = str(exc)
                if "Network" in error_msg or "timeout" in error_msg.lower():
                    self.failed.emit("翻译失败：网络连接超时，请检查网络")
                elif "quota" in error_msg.lower() or "limit" in error_msg.lower():
                    self.failed.emit("翻译失败：API 调用频率限制，请稍后再试")
                else:
                    self.failed.emit(f"翻译失败：{error_msg[:100]}")
        finally:
            self.finished.emit()


def _mymemory_source_for_target(target_lang: str) -> str:
    target = target_lang.lower()
    if target.startswith("zh"):
        return "en-US"
    return "zh-CN"


def translate_text(text: str, target_lang: str = "zh-CN") -> Optional[str]:
    """同步翻译文本，返回翻译结果。

    依次尝试：Google Translator 自动识别 → MyMemory 双语兜底。

    Args:
        text: 要翻译的文本。
        target_lang: 目标语言代码，默认 zh-CN。

    Returns:
        翻译后的文本，失败时返回 None。
    """
    if not text or not text.strip():
        return None

    stripped = text.strip()

    # 优先使用支持源语言自动识别的服务，避免把中文、日文等误当英文。
    try:
        from deep_translator import GoogleTranslator
        result = _translate_with_timeout(
            lambda: GoogleTranslator(source="auto", target=target_lang).translate(stripped)
        )
        if result:
            return result
    except ImportError:
        logger.debug("deep_translator 未安装，跳过 Google 翻译")
    except socket.timeout:
        logger.debug("Google 翻译超时")
    except Exception as exc:
        logger.debug("Google 翻译失败: %s", exc)

    # MyMemory 不支持 auto source，用常见中英互译方向做兜底。
    try:
        from deep_translator import MyMemoryTranslator
        result = _translate_with_timeout(
            lambda: MyMemoryTranslator(
                source=_mymemory_source_for_target(target_lang),
                target=target_lang,
            ).translate(stripped)
        )
        if result:
            return result
    except ImportError:
        logger.debug("deep_translator 未安装，跳过 MyMemory 翻译")
    except socket.timeout:
        logger.debug("MyMemory 翻译超时")
    except Exception as exc:
        logger.debug("MyMemory 翻译失败: %s", exc)

    # 第三兜底：尝试 Linguee（deep_translator 内置）
    try:
        from deep_translator import LingueeTranslator
        source_lang = _mymemory_source_for_target(target_lang)
        result = _translate_with_timeout(
            lambda: LingueeTranslator(
                source=source_lang.lower().split("-")[0],
                target=target_lang.lower().split("-")[0]
            ).translate(stripped)
        )
        if result:
            return result
    except ImportError:
        pass
    except socket.timeout:
        logger.debug("Linguee 翻译超时")
    except Exception as exc:
        logger.debug("Linguee 翻译失败: %s", exc)

    logger.warning("所有翻译服务均失败")
    return None
