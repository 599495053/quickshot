"""manager facade —— 保留对外稳定 API：HistoryWindow / PinManagerWindow。

实际实现拆分在：
- `_manager_delegates.py`: HistoryItemDelegate / PinItemDelegate / build_header_card
- `_manager_history.py`: HistoryWindow（历史库窗口）
- `_manager_pin.py`: PinManagerWindow（贴图管理窗口）
"""

from ._manager_delegates import HistoryItemDelegate, PinItemDelegate, build_header_card
from ._manager_history import HistoryWindow
from ._manager_pin import PinManagerWindow

__all__ = [
    "HistoryItemDelegate",
    "PinItemDelegate",
    "build_header_card",
    "HistoryWindow",
    "PinManagerWindow",
]
