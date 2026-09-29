"""
CORD UI - In-Terminal Multi-Window Multiplexer
Allows running 2 or more CORD instances inside the same terminal screen.
Supports side-by-side vertical splits, stacked horizontal splits, mouse-driven
divider dragging/resizing, pane switching, and independent parallel agent execution.
"""

from __future__ import annotations
import os
import shutil
import time
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field

from rich.layout import Layout
from rich.panel import Panel
from rich.text import Text
from rich.console import Console, RenderableType


@dataclass
class Pane:
    """Represents a single CORD window/pane in the terminal multiplexer."""
    id: int
    title: str
    model: str
    agent: Optional[Any] = None
    history: List[str] = field(default_factory=list)
    status: str = "idle"  # idle, running, completed, error
    active: bool = False
    created_at: float = field(default_factory=time.time)

    def add_line(self, line: str) -> None:
        self.history.append(line)
        if len(self.history) > 300:
            self.history = self.history[-300:]


class MultiPaneManager:
    """Manages multi-window splits, mouse resize events, and pane focus."""

    def __init__(self):
        self.panes: Dict[int, Pane] = {}
        self.active_id: int = 1
        self.split_type: str = "none"  # "none", "vertical", "horizontal"
        self.split_ratio: float = 0.50  # 0.15 to 0.85 (mouse resizable)
        self.next_id: int = 1
        self._init_default_pane()

    def _init_default_pane(self, model: str = "gemini-2.5-flash") -> None:
        p = Pane(
            id=1,
            title="CORD Terminal #1",
            model=model,
            active=True,
        )
        self.panes[1] = p
        self.active_id = 1
        self.next_id = 2

    @property
    def active_pane(self) -> Pane:
        return self.panes.get(self.active_id, self.panes[1])

    @property
    def is_split(self) -> bool:
        return len(self.panes) > 1 and self.split_type != "none"

    def split_vertical(self, model: Optional[str] = None, title: Optional[str] = None, agent: Optional[Any] = None) -> Pane:
        """Opens a new CORD instance side-by-side (vertical split)."""
        pid = self.next_id
        self.next_id += 1
        new_model = model or self.active_pane.model
        new_pane = Pane(
            id=pid,
            title=title or f"CORD Terminal #{pid}",
            model=new_model,
            agent=agent,
            active=True,
        )
        for p in self.panes.values():
            p.active = False

        self.panes[pid] = new_pane
        self.active_id = pid
        self.split_type = "vertical"
        return new_pane

    def split_horizontal(self, model: Optional[str] = None, title: Optional[str] = None, agent: Optional[Any] = None) -> Pane:
        """Opens a new CORD instance stacked vertically (horizontal split)."""
        pid = self.next_id
        self.next_id += 1
        new_model = model or self.active_pane.model
        new_pane = Pane(
            id=pid,
            title=title or f"CORD Terminal #{pid}",
            model=new_model,
            agent=agent,
            active=True,
        )
        for p in self.panes.values():
            p.active = False

        self.panes[pid] = new_pane
        self.active_id = pid
        self.split_type = "horizontal"
        return new_pane

    def switch_pane(self, target_id: Optional[int] = None) -> Pane:
        """Switches focus to next pane or specified pane ID."""
        if not self.panes:
            self._init_default_pane()
            return self.active_pane

        pane_ids = sorted(self.panes.keys())
        if target_id is not None and target_id in self.panes:
            new_id = target_id
        else:
            curr_idx = pane_ids.index(self.active_id) if self.active_id in pane_ids else 0
            new_idx = (curr_idx + 1) % len(pane_ids)
            new_id = pane_ids[new_idx]

        for pid, p in self.panes.items():
            p.active = (pid == new_id)

        self.active_id = new_id
        return self.panes[new_id]

    def close_pane(self, target_id: Optional[int] = None) -> bool:
        """Closes a pane. If only 1 pane remains, reverts split layout to none."""
        if len(self.panes) <= 1:
            return False

        close_id = target_id if target_id is not None else self.active_id
        if close_id in self.panes:
            del self.panes[close_id]
            remaining = sorted(self.panes.keys())
            self.active_id = remaining[0]
            self.panes[self.active_id].active = True
            if len(self.panes) <= 1:
                self.split_type = "none"
            return True
        return False

    def resize_split(self, delta: float) -> float:
        """Enlarges or shrinks pane split ratio by delta (e.g. +0.05 or -0.05)."""
        self.split_ratio = max(0.15, min(0.85, self.split_ratio + delta))
        return self.split_ratio

    def set_split_ratio_from_mouse(self, mouse_col: int, total_cols: int) -> float:
        """Calculates new split ratio directly from mouse click/drag column."""
        if total_cols <= 0:
            return self.split_ratio
        raw_ratio = mouse_col / total_cols
        self.split_ratio = max(0.15, min(0.85, raw_ratio))
        return self.split_ratio

    def handle_mouse_click(self, col: int, row: int, total_cols: int, total_rows: int) -> Optional[int]:
        """Handles mouse click inside terminal: switches pane focus or activates resize handle."""
        if not self.is_split or len(self.panes) < 2:
            return None

        pane_ids = sorted(self.panes.keys())
        p1_id, p2_id = pane_ids[0], pane_ids[1]

        if self.split_type == "vertical":
            divider_col = int(total_cols * self.split_ratio)
            # Clicking near divider (+/- 2 columns) adjusts ratio
            if abs(col - divider_col) <= 2:
                return self.active_id
            elif col < divider_col:
                self.switch_pane(p1_id)
                return p1_id
            else:
                self.switch_pane(p2_id)
                return p2_id
        else:
            divider_row = int(total_rows * self.split_ratio)
            if abs(row - divider_row) <= 1:
                return self.active_id
            elif row < divider_row:
                self.switch_pane(p1_id)
                return p1_id
            else:
                self.switch_pane(p2_id)
                return p2_id

    def render_pane_panel(self, pane: Pane, height: int = 15) -> Panel:
        """Renders the content panel for a single pane with focus styling."""
        lines = pane.history[-height:] if pane.history else [
            f"[dim]Window #{pane.id} initialized with model: [bold cyan]{pane.model}[/bold cyan][/dim]",
            "[dim]Ready for commands and autonomous tasks.[/dim]",
        ]
        content_text = Text.from_markup("\n".join(lines))

        if pane.active:
            title = f"[bold #2563eb]● Pane {pane.id} (ACTIVE)[/bold #2563eb] [bold white]│ {pane.model}[/bold white]"
            border_style = "bold #2563eb"
        else:
            title = f"[dim white]○ Pane {pane.id}[/dim white] [dim]│ {pane.model}[/dim]"
            border_style = "dim cyan"

        return Panel(
            content_text,
            title=title,
            title_align="left",
            border_style=border_style,
            padding=(0, 1),
            subtitle=f"[dim]Status: {pane.status}[/dim]",
            subtitle_align="right",
        )

    def render_multipane_layout(self, width: Optional[int] = None, height: Optional[int] = None) -> Layout:
        """Builds a rich responsive layout matching active splits and mouse dividers."""
        term_size = shutil.get_terminal_size((120, 30))
        cols = width or term_size.columns
        rows = height or (term_size.lines - 6)

        root = Layout()
        pane_ids = sorted(self.panes.keys())

        if not self.is_split or len(pane_ids) == 1:
            p = self.panes[pane_ids[0]]
            root.update(self.render_pane_panel(p, height=rows))
            return root

        p1 = self.panes[pane_ids[0]]
        p2 = self.panes[pane_ids[1]]

        if self.split_type == "vertical":
            p1_ratio = int(self.split_ratio * 100)
            p2_ratio = 100 - p1_ratio
            root.split_row(
                Layout(self.render_pane_panel(p1, height=rows), name="left", ratio=p1_ratio),
                Layout(self.render_pane_panel(p2, height=rows), name="right", ratio=p2_ratio),
            )
        else:
            p1_ratio = int(self.split_ratio * 100)
            p2_ratio = 100 - p1_ratio
            root.split_column(
                Layout(self.render_pane_panel(p1, height=max(rows // 2, 6)), name="top", ratio=p1_ratio),
                Layout(self.render_pane_panel(p2, height=max(rows // 2, 6)), name="bottom", ratio=p2_ratio),
            )

        return root


multipane_mgr = MultiPaneManager()
