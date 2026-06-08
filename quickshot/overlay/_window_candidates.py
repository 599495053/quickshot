"""Window candidate normalization for the screenshot selection overlay."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Iterable, Optional, Tuple

from PyQt6.QtCore import QPoint, QRect


PhysicalToLogical = Callable[[Tuple[int, int, int, int]], Tuple[QRect, QRect]]


@dataclass(frozen=True)
class WindowCandidate:
    hwnd: int
    logical_rect: QRect
    physical_rect: QRect
    title: str
    z_order: int

    def __post_init__(self) -> None:
        object.__setattr__(self, "logical_rect", QRect(self.logical_rect))
        object.__setattr__(self, "physical_rect", QRect(self.physical_rect))
        object.__setattr__(self, "title", normalize_window_title(self.title))

    @property
    def area(self) -> int:
        return max(0, self.logical_rect.width()) * max(0, self.logical_rect.height())

    def contains(self, pos: QPoint) -> bool:
        return self.logical_rect.contains(pos)


def normalize_window_title(title: object) -> str:
    return " ".join(str(title or "").split())


def _valid_rect(rect: QRect, min_size: int) -> bool:
    return not rect.isNull() and rect.width() >= min_size and rect.height() >= min_size


def build_window_candidates(
    raw_windows: Iterable[tuple[int, QRect, str]],
    physical_to_logical: PhysicalToLogical,
    bounds: QRect,
    *,
    min_size: int = 8,
) -> list[WindowCandidate]:
    """Convert enumerated physical windows into clipped logical candidates.

    EnumWindows already reports top-level windows in z-order, so this function
    preserves input order and only normalizes coordinates once per refresh.
    """
    candidates: list[WindowCandidate] = []
    logical_bounds = QRect(bounds)
    for z_order, (hwnd, physical_source, title) in enumerate(raw_windows):
        clean_title = normalize_window_title(title)
        if not clean_title:
            continue

        physical = QRect(physical_source)
        if not _valid_rect(physical, min_size):
            continue

        try:
            logical, clipped_physical = physical_to_logical(
                (physical.x(), physical.y(), physical.width(), physical.height())
            )
        except Exception:
            continue
        logical = QRect(logical).intersected(logical_bounds)
        clipped_physical = QRect(clipped_physical)
        if not _valid_rect(logical, min_size) or not _valid_rect(clipped_physical, min_size):
            continue

        candidates.append(
            WindowCandidate(
                hwnd=int(hwnd),
                logical_rect=logical,
                physical_rect=clipped_physical,
                title=clean_title,
                z_order=z_order,
            )
        )
    return candidates


def candidate_at(candidates: Iterable[WindowCandidate], pos: QPoint) -> Optional[WindowCandidate]:
    for candidate in candidates:
        if candidate.contains(pos):
            return candidate
    return None


def legacy_logical_rects(candidates: Iterable[WindowCandidate]) -> list[tuple[int, QRect, str]]:
    return [(candidate.hwnd, QRect(candidate.logical_rect), candidate.title) for candidate in candidates]
