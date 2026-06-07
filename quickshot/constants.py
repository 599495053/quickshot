"""QuickShot 全局常量定义。

集中管理所有魔法数字和配置常量，便于维护和调整。
"""

# ── 热键相关 ──
HOTKEY_DEBOUNCE_SECONDS = 0.35
"""热键防抖时间（秒），防止快速重复触发"""

HOTKEY_POLL_INTERVAL_MS = 45
"""备用热键轮询间隔（毫秒）"""

WINDOW_CAPTURE_DELAY_MS = 350
"""窗口截图延迟（毫秒），等待窗口激活"""

# ── UI 显示相关 ──
TRAY_MESSAGE_DURATION_MS = 1800
"""托盘消息显示时长（毫秒）"""

DOUBLE_CLICK_GUARD_MS = 400
"""双击保护时间（毫秒），防止误触"""

# ── Overlay 标注相关 ──
HANDLE_MARGIN = 9
"""选区调整把手边距（像素）"""

TEXT_FONT_SIZE_DEFAULT = 28
"""默认文本标注字号"""

MOSAIC_BLOCK_SIZE = 14
"""马赛克块大小（像素）"""

HIGHLIGHT_ALPHA = 96
"""高亮工具透明度（0-255）"""

HIGHLIGHT_WIDTH_MULTIPLIER = 2.0
"""高亮工具线宽倍数"""

# ── OCR 相关 ──
OCR_IMAGE_MAX_SCALE = 2.0
"""OCR 图像预处理最大缩放倍数"""

OCR_IMAGE_SMOOTH_THRESHOLD = 900
"""使用平滑缩放的尺寸阈值（像素）"""

OCR_PRIVACY_CHECK_INTERVAL = 50
"""隐私检测扫描间隔（字符数）"""

# ── 历史记录相关 ──
HISTORY_SAVE_DEBOUNCE_MS = 500
"""历史保存 debounce 延迟（毫秒）"""

HISTORY_DEFAULT_LIMIT = 200
"""默认历史记录保留数量"""

HISTORY_MIN_LIMIT = 20
"""最小历史记录保留数量"""

HISTORY_THUMBNAIL_BATCH_SIZE = 20
"""历史缩略图批量加载数量"""

# ── 网络相关 ──
UPLOAD_TIMEOUT_SECONDS = 30
"""上传请求超时时间（秒）"""

UPLOAD_MAX_RETRIES = 3
"""上传最大重试次数"""

TRANSLATE_TIMEOUT_SECONDS = 10
"""翻译请求超时时间（秒）"""

# ── 性能相关 ──
PREVIEW_SCALER_MAX_THREADS = 2
"""预览缩放最大并发线程数"""

WINDOW_ENUM_REFRESH_INTERVAL = 2.0
"""窗口列表刷新间隔（秒）"""

# ── 文件路径相关 ──
CACHE_DIR_NAME = "quickshot_cache"
"""缓存目录名称"""

HISTORY_DIR_NAME = "history"
"""历史存储目录名称"""

CONFIG_FILE_NAME = "config.json"
"""配置文件名称"""
