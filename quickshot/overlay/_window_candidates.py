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
    kind: str = "window"
    parent_hwnd: int = 0

    def __post_init__(self) -> None:
        object.__setattr__(self, "logical_rect", QRect(self.logical_rect))
        object.__setattr__(self, "physical_rect", QRect(self.physical_rect))
        object.__setattr__(self, "title", normalize_window_title(self.title))
        object.__setattr__(self, "kind", str(self.kind or "window"))
        object.__setattr__(self, "parent_hwnd", int(self.parent_hwnd or 0))

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
    kind: str = "window",
    parent_hwnd: int = 0,
    z_order_offset: int = 0,
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
                z_order=z_order + z_order_offset,
                kind=kind,
                parent_hwnd=parent_hwnd,
            )
        )
    return candidates


def sort_candidates_for_hit_testing(candidates: Iterable[WindowCandidate]) -> list[WindowCandidate]:
    """Return candidates ordered for hover hit-testing.

    UI elements sit above their parent window; within the same layer, smaller
    rects win because they represent more specific capture targets.
    """
    return sorted(
        candidates,
        key=lambda item: (
            item.z_order,
            0 if item.kind != "window" else 1,
            item.area,
            item.logical_rect.top(),
            item.logical_rect.left(),
            item.hwnd,
        ),
    )


def build_combined_candidates(
    raw_windows: Iterable[tuple[int, QRect, str]],
    raw_elements: Iterable[tuple[int, QRect, str, int]],
    physical_to_logical: PhysicalToLogical,
    bounds: QRect,
    *,
    min_window_size: int = 8,
    min_element_size: int = 8,
) -> list[WindowCandidate]:
    windows = build_window_candidates(
        raw_windows,
        physical_to_logical,
        bounds,
        min_size=min_window_size,
        kind="window",
    )
    window_order = {candidate.hwnd: candidate.z_order for candidate in windows}
    elements: list[WindowCandidate] = []
    for hwnd, rect, title, parent_hwnd in raw_elements:
        parent_order = window_order.get(int(parent_hwnd))
        if parent_order is None:
            continue
        element = build_window_candidates(
            [(hwnd, rect, title)],
            physical_to_logical,
            bounds,
            min_size=min_element_size,
            kind="element",
            parent_hwnd=int(parent_hwnd),
            z_order_offset=parent_order,
        )
        if element:
            elements.append(element[0])
    return sort_candidates_for_hit_testing(elements + windows)


def candidate_at(candidates: Iterable[WindowCandidate], pos: QPoint) -> Optional[WindowCandidate]:
    for candidate in candidates:
        if candidate.contains(pos):
            return candidate
    return None


def legacy_logical_rects(candidates: Iterable[WindowCandidate]) -> list[tuple[int, QRect, str]]:
    return [(candidate.hwnd, QRect(candidate.logical_rect), candidate.title) for candidate in candidates]
