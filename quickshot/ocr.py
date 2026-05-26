from dataclasses import dataclass
import threading
import time
from pathlib import Path
from typing import List, Optional, Union

from PyQt6.QtCore import QObject, QThread, Qt, pyqtSignal, pyqtSlot
from PyQt6.QtGui import QColor, QImage, QPainter, QPixmap

from .utils import debug_log, hidden_process_startupinfo


@dataclass(frozen=True)
class OcrResult:
    text: str
    engine_key: str
    engine_label: str
    elapsed_seconds: float = 0.0
    note: str = ""


WINDOWS_OCR_SCRIPT = r"""
param([Parameter(Mandatory=$true)][string]$ImagePath)

$ErrorActionPreference = "Stop"
[Console]::OutputEncoding = [System.Text.UTF8Encoding]::new($false)
$OutputEncoding = [Console]::OutputEncoding

Add-Type -AssemblyName System.Runtime.WindowsRuntime
[Windows.Media.Ocr.OcrEngine, Windows.Foundation, ContentType=WindowsRuntime] | Out-Null
[Windows.Media.Ocr.OcrResult, Windows.Foundation, ContentType=WindowsRuntime] | Out-Null
[Windows.Globalization.Language, Windows.Globalization, ContentType=WindowsRuntime] | Out-Null
[Windows.Storage.StorageFile, Windows.Storage, ContentType=WindowsRuntime] | Out-Null
[Windows.Storage.Streams.IRandomAccessStreamWithContentType, Windows.Storage.Streams, ContentType=WindowsRuntime] | Out-Null
[Windows.Graphics.Imaging.BitmapDecoder, Windows.Graphics.Imaging, ContentType=WindowsRuntime] | Out-Null
[Windows.Graphics.Imaging.SoftwareBitmap, Windows.Graphics.Imaging, ContentType=WindowsRuntime] | Out-Null

$asTaskGeneric = ([System.WindowsRuntimeSystemExtensions].GetMethods() | Where-Object {
    $_.Name -eq "AsTask" -and
    $_.IsGenericMethodDefinition -and
    $_.GetParameters().Count -eq 1 -and
    $_.GetParameters()[0].ParameterType.Name -eq 'IAsyncOperation`1'
})[0]

function Await-Operation($Operation, [Type]$ResultType) {
    $task = $asTaskGeneric.MakeGenericMethod($ResultType).Invoke($null, @($Operation))
    $task.Wait()
    return $task.Result
}

$engine = [Windows.Media.Ocr.OcrEngine]::TryCreateFromUserProfileLanguages()
if ($null -eq $engine) {
    foreach ($tag in @("zh-Hans", "en-US")) {
        $language = [Windows.Globalization.Language]::new($tag)
        if ([Windows.Media.Ocr.OcrEngine]::IsLanguageSupported($language)) {
            $engine = [Windows.Media.Ocr.OcrEngine]::TryCreateFromLanguage($language)
            if ($null -ne $engine) {
                break
            }
        }
    }
}
if ($null -eq $engine) {
    throw "当前系统没有可用的 OCR 语言包，请在 Windows 设置中添加中文或英文语言包。"
}

$stream = $null
try {
    $file = Await-Operation ([Windows.Storage.StorageFile]::GetFileFromPathAsync($ImagePath)) ([Windows.Storage.StorageFile])
    $stream = Await-Operation ($file.OpenReadAsync()) ([Windows.Storage.Streams.IRandomAccessStreamWithContentType])
    $decoder = Await-Operation ([Windows.Graphics.Imaging.BitmapDecoder]::CreateAsync($stream)) ([Windows.Graphics.Imaging.BitmapDecoder])
    $bitmap = Await-Operation ($decoder.GetSoftwareBitmapAsync()) ([Windows.Graphics.Imaging.SoftwareBitmap])
    $result = Await-Operation ($engine.RecognizeAsync($bitmap)) ([Windows.Media.Ocr.OcrResult])
    Write-Output ([Convert]::ToBase64String([System.Text.Encoding]::UTF8.GetBytes($result.Text)))
}
finally {
    if ($null -ne $stream) {
        $stream.Dispose()
    }
}
"""


OCR_SYMBOL_TRANSLATION = str.maketrans({
    "，": ",", "。": ".", "：": ":", "；": ";",
    "（": "(", "）": ")", "［": "[", "］": "]",
    "【": "[", "】": "]", "｛": "{", "｝": "}",
    "《": "<", "》": ">", "〈": "<", "〉": ">",
    "“": '"', "”": '"', "„": '"', "＂": '"',
    "‘": "'", "’": "'", "‚": "'", "＇": "'",
    "－": "-", "–": "-", "—": "-", "―": "-",
    "〜": "~", "～": "~", "＋": "+", "＝": "=",
    "／": "/", "＼": "\\", "｜": "|", "＊": "*",
    "＆": "&", "％": "%", "＃": "#", "＠": "@",
    "！": "!", "？": "?",
})


def normalize_ocr_symbols(text: str) -> str:
    return text.translate(OCR_SYMBOL_TRANSLATION).replace(" ", " ")


def prepare_ocr_image(source_image: Union[QPixmap, QImage]) -> QImage:
    if isinstance(source_image, QPixmap):
        source = source_image.toImage().convertToFormat(QImage.Format.Format_ARGB32)
    else:
        source = source_image.copy().convertToFormat(QImage.Format.Format_ARGB32)
    source.setDevicePixelRatio(1.0)
    image = QImage(source.size(), QImage.Format.Format_RGB32)
    image.fill(QColor(255, 255, 255))
    painter = QPainter(image)
    painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceOver)
    painter.drawImage(0, 0, source)
    painter.end()

    max_dim = max(1, max(image.width(), image.height()))
    if max_dim < 900:
        scale = 3.0
    elif max_dim < 1600:
        scale = 2.0
    elif max_dim < 2600:
        scale = 1.5
    else:
        scale = 1.0
    scale = min(scale, 3200 / max_dim)

    if scale > 1.05:
        image = image.scaled(
            max(1, int(round(image.width() * scale))),
            max(1, int(round(image.height() * scale))),
            Qt.AspectRatioMode.IgnoreAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
    return image.convertToFormat(QImage.Format.Format_RGB888)


_RAPID_OCR_ENGINE = None
_RAPID_OCR_LOCK = threading.Lock()
_OCR_EXECUTOR = None
_OCR_EXECUTOR_LOCK = threading.Lock()
_PREWARM_FUTURE = None
_PREWARM_LOCK = threading.Lock()
_ACTIVE_OCR_JOBS = set()


def _get_ocr_executor():
    global _OCR_EXECUTOR
    if _OCR_EXECUTOR is None:
        with _OCR_EXECUTOR_LOCK:
            if _OCR_EXECUTOR is None:
                from concurrent.futures import ThreadPoolExecutor
                _OCR_EXECUTOR = ThreadPoolExecutor(max_workers=2, thread_name_prefix="quickshot-ocr")
    return _OCR_EXECUTOR


class _OcrWorker(QObject):
    succeeded = pyqtSignal(object)
    failed = pyqtSignal(str)
    finished = pyqtSignal()

    def __init__(self, source_image: QImage) -> None:
        super().__init__()
        self._source_image = source_image.copy()

    @pyqtSlot()
    def run(self) -> None:
        try:
            self.succeeded.emit(recognize_text(self._source_image))
        except Exception as exc:
            debug_log(f"OCR worker failed: {exc}")
            self.failed.emit(str(exc))
        finally:
            self.finished.emit()


class OcrJob(QObject):
    succeeded = pyqtSignal(object)
    failed = pyqtSignal(str)
    finished = pyqtSignal()

    def __init__(self, source_image: QImage) -> None:
        super().__init__()
        self._thread = QThread()
        self._worker = _OcrWorker(source_image)
        self._running = False

        self._worker.moveToThread(self._thread)
        self._thread.started.connect(self._worker.run)
        self._worker.succeeded.connect(self.succeeded)
        self._worker.failed.connect(self.failed)
        self._worker.finished.connect(self._handle_worker_finished)
        self._worker.finished.connect(self._thread.quit)
        self._thread.finished.connect(self._worker.deleteLater)
        self._thread.finished.connect(self._thread.deleteLater)
        self._thread.finished.connect(self._handle_thread_finished)

    def start(self) -> None:
        if self._running:
            return
        self._running = True
        _ACTIVE_OCR_JOBS.add(self)
        self._thread.start()

    def is_running(self) -> bool:
        return self._running

    @pyqtSlot()
    def _handle_worker_finished(self) -> None:
        self._running = False
        self.finished.emit()

    @pyqtSlot()
    def _handle_thread_finished(self) -> None:
        _ACTIVE_OCR_JOBS.discard(self)
        self.deleteLater()


def rapidocr_engine():
    global _RAPID_OCR_ENGINE
    if _RAPID_OCR_ENGINE is None:
        with _RAPID_OCR_LOCK:
            if _RAPID_OCR_ENGINE is None:
                from rapidocr_onnxruntime import RapidOCR
                _RAPID_OCR_ENGINE = RapidOCR()
    return _RAPID_OCR_ENGINE


def prewarm_rapidocr() -> bool:
    try:
        rapidocr_engine()
        debug_log("RapidOCR prewarm completed")
        return True
    except Exception as exc:
        debug_log(f"RapidOCR prewarm failed: {exc}")
        return False


def schedule_rapidocr_prewarm() -> None:
    global _PREWARM_FUTURE
    with _PREWARM_LOCK:
        if _PREWARM_FUTURE is not None and not _PREWARM_FUTURE.done():
            return
        _PREWARM_FUTURE = _get_ocr_executor().submit(prewarm_rapidocr)


def create_ocr_job(source_image: QImage) -> OcrJob:
    return OcrJob(source_image)


def shutdown_ocr_executor() -> None:
    for job in list(_ACTIVE_OCR_JOBS):
        # PyQt 在 signal 无接收者时 disconnect 抛 TypeError；逐个静默是预期行为
        for signal in (job.succeeded, job.failed, job.finished):
            try:
                signal.disconnect()
            except TypeError:
                pass
    if _OCR_EXECUTOR is not None:
        _OCR_EXECUTOR.shutdown(wait=False, cancel_futures=True)


def has_cjk(text: str) -> bool:
    return any("一" <= ch <= "鿿" for ch in text)


def should_join_with_space(previous: str, current: str, gap: float, avg_height: float) -> bool:
    if not previous or not current:
        return False
    if gap <= max(3.0, avg_height * 0.18):
        return False
    if has_cjk(previous[-1]) and has_cjk(current[0]):
        return False
    if current[0] in ",.;:!?)]}>" or previous[-1] in "([{<":
        return False
    return True


def format_rapidocr_result(result) -> str:
    if not result:
        return ""

    blocks = []
    for item in result:
        if len(item) < 2:
            continue
        box = item[0]
        text = str(item[1]).strip()
        if not text:
            continue
        try:
            xs = [float(point[0]) for point in box]
            ys = [float(point[1]) for point in box]
            if not xs or not ys:
                continue
        except (TypeError, ValueError, IndexError):
            # 上游 OCR 偶发返回畸形 box，跳过单条即可
            continue
        top = min(ys)
        bottom = max(ys)
        blocks.append({
            "text": text,
            "left": min(xs),
            "right": max(xs),
            "center_y": (top + bottom) / 2.0,
            "height": max(1.0, bottom - top),
        })

    if not blocks:
        return ""

    blocks.sort(key=lambda item: (item["center_y"], item["left"]))
    avg_height = sum(item["height"] for item in blocks) / max(1, len(blocks))
    line_threshold = max(10.0, avg_height * 0.65)

    lines = []
    for block in blocks:
        if not lines or abs(block["center_y"] - lines[-1]["center_y"]) > line_threshold:
            lines.append({
                "center_y": block["center_y"],
                "height": block["height"],
                "blocks": [block],
            })
            continue
        line = lines[-1]
        line["blocks"].append(block)
        count = len(line["blocks"])
        line["center_y"] = (line["center_y"] * (count - 1) + block["center_y"]) / count
        line["height"] = max(line["height"], block["height"])

    text_lines = []
    for line in lines:
        line_blocks = sorted(line["blocks"], key=lambda item: item["left"])
        parts: List[str] = []
        previous = None
        for block in line_blocks:
            text = block["text"]
            if previous is not None and should_join_with_space(
                parts[-1], text, block["left"] - previous["right"], line["height"],
            ):
                parts.append(" ")
            parts.append(text)
            previous = block
        text_lines.append("".join(parts).strip())

    return normalize_ocr_symbols("\n".join(line for line in text_lines if line)).strip()


def clean_ocr_text(text: str) -> str:
    """对 OCR 结果做轻量自动清洗：去首尾空格、合并连续空行、规范内部空格。"""
    if not text:
        return ""
    lines = []
    prev_empty = False
    for raw_line in text.splitlines():
        line = " ".join(raw_line.split())
        if not line:
            if prev_empty:
                continue
            prev_empty = True
            lines.append("")
        else:
            prev_empty = False
            lines.append(line)
    return "\n".join(lines).strip()


def deep_clean_ocr_text(text: str) -> str:
    """深度清洗 OCR 文本：移除多余空行、规范标点、修复常见 OCR 错误。"""
    if not text:
        return ""
    import re
    # 先做基础清洗
    text = clean_ocr_text(text)
    # 移除所有空行，合并为单行
    text = re.sub(r'\n+', '\n', text)
    # 修复常见 OCR 错误
    replacements = {
        '，，': '，',
        '。。': '。',
        '：：': '：',
        '；；': '；',
        '（（': '（',
        '））': '）',
        '  ': ' ',
    }
    for old, new in replacements.items():
        text = text.replace(old, new)
    # 规范中英文混合的空格（循环应用直到没有变化）
    prev = None
    while prev != text:
        prev = text
        text = re.sub(r'([\u4e00-\u9fff])\s+([\u4e00-\u9fff])', r'\1\2', text)
    return text.strip()


def extract_numbers(text: str) -> list:
    """从文本中提取所有数字。"""
    import re
    return re.findall(r'\d+\.?\d*', text)


def extract_chinese(text: str) -> str:
    """提取中文文本。"""
    import re
    return ''.join(re.findall(r'[\u4e00-\u9fff]+', text))


# ── 共享文本清洗工具 ──
# HistoryWindow 和 OcrResultDialog 共用，消除重复实现。

def clean_lines_text(text: str) -> str:
    """整理空行和首尾空格。"""
    lines = [line.strip() for line in text.splitlines()]
    return "\n".join(line for line in lines if line)


def clean_soft_text(text: str) -> str:
    """轻清洗：整理空行 + 合并行内多余空格。"""
    lines = [line.strip() for line in text.splitlines()]
    normalized = []
    for line in lines:
        if not line:
            continue
        normalized.append(" ".join(line.split()))
    return "\n".join(normalized)


def clean_hard_text(text: str) -> str:
    """强清洗：制表符替换 + 合并行内空格 + 所有行合并为一行。"""
    text = text.replace("\t", " ")
    lines = []
    for line in text.splitlines():
        compact = " ".join(line.split())
        if compact:
            lines.append(compact)
    return " ".join(lines)


def _qimage_to_numpy(image: QImage):
    import numpy as np
    if image.format() != QImage.Format.Format_RGB888:
        image = image.convertToFormat(QImage.Format.Format_RGB888)
    width = image.width()
    height = image.height()
    bpl = image.bytesPerLine()
    ptr = image.bits()
    ptr.setsize(height * bpl)
    arr = np.frombuffer(ptr, dtype=np.uint8).reshape(height, bpl)
    # 去掉每行末尾的 padding 字节，只保留 width*3 的有效像素数据
    return arr[:, :width * 3].reshape(height, width, 3).copy()


def recognize_text_with_rapidocr(source_image: Union[QPixmap, QImage]) -> str:
    if isinstance(source_image, QPixmap) and source_image.isNull():
        return ""
    if isinstance(source_image, QImage) and source_image.isNull():
        return ""
    image = prepare_ocr_image(source_image)
    result, _elapsed = rapidocr_engine()(_qimage_to_numpy(image))
    return clean_ocr_text(format_rapidocr_result(result))


# 隐私信息匹配模式（延迟编译，仅在首次 detect_privacy_info 时加载）
_PRIVACY_PATTERNS = None


def _get_privacy_patterns():
    global _PRIVACY_PATTERNS
    if _PRIVACY_PATTERNS is None:
        import re
        _PRIVACY_PATTERNS = [
            # 手机号（中国大陆，支持空格/横线分隔）
            re.compile(r'1[3-9]\d[\s\-]?\d{4}[\s\-]?\d{4}'),
            # 身份证号（18位）
            re.compile(r'[1-9]\d{5}(?:19|20)\d{2}(?:0[1-9]|1[0-2])(?:0[1-9]|[12]\d|3[01])\d{3}[\dXx]'),
            # 邮箱
            re.compile(r'[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}'),
            # 银行卡号（16-19位数字，支持空格/横线分隔）
            re.compile(r'\d{4}[\s\-]?\d{4}[\s\-]?\d{4}[\s\-]?\d{4}(?:[\s\-]?\d{1,3})?'),
        ]
    return _PRIVACY_PATTERNS


def detect_privacy_info(image: Union[QPixmap, QImage]) -> list:
    """检测图片中的隐私信息，返回需要打码的区域列表 [(x, y, w, h), ...]。"""
    if isinstance(image, QPixmap) and image.isNull():
        return []
    if isinstance(image, QImage) and image.isNull():
        return []

    # 计算缩放比例
    if isinstance(image, QPixmap):
        orig_w, orig_h = image.width(), image.height()
    else:
        orig_w, orig_h = image.width(), image.height()
    max_dim = max(1, max(orig_w, orig_h))
    if max_dim < 900:
        scale = 3.0
    elif max_dim < 1600:
        scale = 2.0
    elif max_dim < 2600:
        scale = 1.5
    else:
        scale = 1.0
    scale = min(scale, 3200 / max_dim)

    prepared = prepare_ocr_image(image)
    result, _elapsed = rapidocr_engine()(_qimage_to_numpy(prepared))
    if not result:
        return []

    # 将坐标从缩放后的空间转换回原始图像空间
    rects = _match_privacy_rects(result)
    debug_log(f"Privacy: orig={orig_w}x{orig_h}, scale={scale:.2f}, raw_rects={rects}")
    if scale > 1.05 and rects:
        inv_scale = 1.0 / scale
        rects = [(int(x * inv_scale), int(y * inv_scale), int(w * inv_scale), int(h * inv_scale)) for x, y, w, h in rects]
        debug_log(f"Privacy: scaled_rects={rects}")
    return rects


def _match_privacy_rects(ocr_result) -> list:
    """从 OCR 原始结果中匹配隐私信息区域。"""
    blur_rects = []
    debug_log(f"Privacy scan: {len(ocr_result)} text blocks")
    for item in ocr_result:
        if len(item) < 2:
            continue
        box = item[0]
        text = str(item[1]).strip()
        if not text:
            continue

        is_private = False
        for pattern in _get_privacy_patterns():
            if pattern.search(text):
                is_private = True
                debug_log(f"  MATCH [{pattern.pattern}]: {text}")
                break

        if not is_private:
            continue

        try:
            xs = [float(point[0]) for point in box]
            ys = [float(point[1]) for point in box]
            if not xs or not ys:
                continue
        except (TypeError, ValueError, IndexError):
            continue

        x = int(min(xs))
        y = int(min(ys))
        w = int(max(xs) - min(xs))
        h = int(max(ys) - min(ys))
        if w > 0 and h > 0:
            blur_rects.append((x, y, w, h))

    return blur_rects


class PrivacyBlurJob(QObject):
    """异步隐私信息检测任务。"""
    succeeded = pyqtSignal(object)  # list of (x, y, w, h)
    failed = pyqtSignal(str)
    finished = pyqtSignal()

    def __init__(self, source_image: QImage) -> None:
        super().__init__()
        self._thread = QThread()
        self._worker = _PrivacyBlurWorker(source_image)
        self._running = False

        self._worker.moveToThread(self._thread)
        self._thread.started.connect(self._worker.run)
        self._worker.succeeded.connect(self.succeeded)
        self._worker.failed.connect(self.failed)
        self._worker.finished.connect(self._handle_worker_finished)
        self._worker.finished.connect(self._thread.quit)

    def start(self) -> None:
        if self._running:
            return
        self._running = True
        self._thread.start()

    def is_running(self) -> bool:
        return self._running

    def cleanup(self) -> None:
        """安全清理线程和 worker。"""
        if self._thread.isRunning():
            self._thread.quit()
            self._thread.wait(3000)
        self._worker.deleteLater()
        self._thread.deleteLater()

    @pyqtSlot()
    def _handle_worker_finished(self) -> None:
        self._running = False
        self.finished.emit()


class _PrivacyBlurWorker(QObject):
    succeeded = pyqtSignal(object)
    failed = pyqtSignal(str)
    finished = pyqtSignal()

    def __init__(self, source_image: QImage) -> None:
        super().__init__()
        self._source_image = source_image.copy()

    @pyqtSlot()
    def run(self) -> None:
        try:
            result = detect_privacy_info(self._source_image)
            self.succeeded.emit(result)
        except Exception as exc:
            debug_log(f"Privacy blur worker failed: {exc}")
            self.failed.emit(str(exc))
        finally:
            self.finished.emit()


def create_privacy_blur_job(source_image: QImage) -> PrivacyBlurJob:
    return PrivacyBlurJob(source_image)


_CACHED_SCRIPT_PATH: Optional[Path] = None


def _get_windows_ocr_script_path() -> Path:
    import tempfile
    global _CACHED_SCRIPT_PATH
    if _CACHED_SCRIPT_PATH is not None and _CACHED_SCRIPT_PATH.exists():
        return _CACHED_SCRIPT_PATH
    script_dir = Path(tempfile.gettempdir()) / "quickshot_cache"
    script_dir.mkdir(parents=True, exist_ok=True)
    script_path = script_dir / "ocr.ps1"
    script_path.write_text(WINDOWS_OCR_SCRIPT, encoding="utf-8-sig")
    _CACHED_SCRIPT_PATH = script_path
    return script_path


def recognize_text_with_windows_ocr(source_image: Union[QPixmap, QImage]) -> str:
    import base64
    import shutil
    import subprocess
    import tempfile

    if isinstance(source_image, QPixmap) and source_image.isNull():
        return ""
    if isinstance(source_image, QImage) and source_image.isNull():
        return ""

    powershell = shutil.which("powershell") or shutil.which("pwsh")
    if not powershell:
        raise RuntimeError("未找到 PowerShell，无法调用 Windows 文字识别。")

    with tempfile.TemporaryDirectory(prefix="quickshot_ocr_") as tmp_dir:
        temp_dir = Path(tmp_dir)
        image_path = temp_dir / "capture.png"

        image = prepare_ocr_image(source_image)
        if not image.save(str(image_path), "PNG"):
            raise RuntimeError("无法准备文字识别图片。")
        script_path = _get_windows_ocr_script_path()

        creationflags = 0
        if hasattr(subprocess, "CREATE_NO_WINDOW"):
            creationflags = subprocess.CREATE_NO_WINDOW

        try:
            completed = subprocess.run(
                [
                    powershell,
                    "-NoProfile",
                    "-ExecutionPolicy",
                    "Bypass",
                    "-File",
                    str(script_path),
                    "-ImagePath",
                    str(image_path),
                ],
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=30,
                startupinfo=hidden_process_startupinfo(),
                creationflags=creationflags,
            )
        except subprocess.TimeoutExpired as exc:
            raise RuntimeError("文字识别超时，请缩小识别区域后重试。") from exc

    if completed.returncode != 0:
        detail = (completed.stderr or completed.stdout or "").strip()
        raise RuntimeError(detail or "文字识别失败。")

    encoded_text = completed.stdout.strip()
    if not encoded_text:
        return ""
    try:
        return normalize_ocr_symbols(base64.b64decode(encoded_text).decode("utf-8")).strip()
    except Exception as exc:
        raise RuntimeError("文字识别结果解析失败。") from exc


def recognize_text(source_image: Union[QPixmap, QImage]) -> OcrResult:
    """识别图片中的文字，按优先级尝试各引擎。"""
    if isinstance(source_image, QPixmap) and source_image.isNull():
        return OcrResult(text="", engine_key="none", engine_label="OCR", note="空图片")
    if isinstance(source_image, QImage) and source_image.isNull():
        return OcrResult(text="", engine_key="none", engine_label="OCR", note="空图片")
    prepared = prepare_ocr_image(source_image)
    from .ocr_engine import get_default_registry
    return get_default_registry().recognize(prepared)
