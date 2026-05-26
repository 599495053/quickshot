"""HistoryMixin — facade，re-export 三个职责 Mixin。

为保持向后兼容（外部 import HistoryMixin 不受影响），此文件保留
HistoryMixin 类名，它继承自三个拆分后的 Mixin。
"""

from ._undo import UndoMixin
from ._export import ExportMixin
from ._postprocess import PostProcessMixin


class HistoryMixin(UndoMixin, ExportMixin, PostProcessMixin):
    """撤销栈 + 导出操作 + 后处理变换（组合 facade）。"""
    pass


__all__ = ["HistoryMixin"]
