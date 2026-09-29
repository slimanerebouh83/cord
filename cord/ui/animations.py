"""
CORD UI - Terminal Animations & Live Visual Effects
Provides pulsing spinners, thinking phase visualizers, and live-updating execution clocks.
"""

from __future__ import annotations
import time
import asyncio
from typing import Optional, List
from contextlib import asynccontextmanager
from rich.live import Live
from rich.text import Text
from rich.panel import Panel

from cord.ui.console import ui

# Braille spinner frames
SPINNER_FRAMES = ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"]

# Rotating thinking phrases with distinct visual color accents
THINKING_PHASES = [
    ("🧠", "Deep Reasoning & Planning...", "bold magenta"),
    ("✨", "Synthesizing optimal architecture...", "bold cyan"),
    ("⚡", "Analyzing codebase patterns & dependencies...", "bold yellow"),
    ("🔍", "Formulating precise surgical solution...", "bold green"),
    ("💡", "Validating edge cases & syntax...", "bold #a855f7"),
]


class ThinkingAnimation:
    """Live updating thinking animation with Braille spinner and cycling thoughts."""

    def __init__(self, model_name: str = ""):
        self.model_name = model_name.split("/")[-1] if model_name else "Agent"
        self._running = False
        self._task: Optional[asyncio.Task] = None
        self._live: Optional[Live] = None
        self._start_time = 0.0

    def _render_frame(self, frame_idx: int, phase_idx: int) -> Text:
        elapsed = time.time() - self._start_time
        icon, phrase, style = THINKING_PHASES[phase_idx % len(THINKING_PHASES)]
        spinner = SPINNER_FRAMES[frame_idx % len(SPINNER_FRAMES)]

        text = Text()
        text.append(f" {spinner} ", style="bold bright_cyan")
        text.append(f"{icon} ", style="bold")
        text.append(phrase, style=style)
        text.append(f"  ⏱️ {elapsed:.1f}s", style="dim white")
        text.append(f" │ 🤖 {self.model_name}", style="dim")
        return text

    async def _animate(self) -> None:
        frame_idx = 0
        phase_idx = 0
        phase_timer = 0

        while self._running:
            if self._live:
                self._live.update(self._render_frame(frame_idx, phase_idx))
            
            frame_idx += 1
            phase_timer += 1
            # Change phase every ~2.5 seconds (25 ticks of 100ms)
            if phase_timer >= 25:
                phase_timer = 0
                phase_idx += 1

            await asyncio.sleep(0.08)

    async def start(self) -> None:
        self._running = True
        self._start_time = time.time()
        self._live = Live(
            self._render_frame(0, 0),
            console=ui.console,
            refresh_per_second=15,
            transient=True,
        )
        self._live.start()
        self._task = asyncio.create_task(self._animate())

    async def stop(self) -> None:
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None
        if self._live:
            self._live.stop()
            self._live = None


@asynccontextmanager
async def animate_thinking(model_name: str = ""):
    """Async context manager wrapper for thinking animation."""
    anim = ThinkingAnimation(model_name=model_name)
    await anim.start()
    try:
        yield anim
    finally:
        await anim.stop()


class ToolAnimation:
    """Live updating animation for executing tools."""

    def __init__(self, tool_name: str, args_summary: str = ""):
        self.tool_name = tool_name
        self.args_summary = args_summary
        self._running = False
        self._task: Optional[asyncio.Task] = None
        self._live: Optional[Live] = None
        self._start_time = 0.0

    def _render(self, frame_idx: int) -> Text:
        elapsed = time.time() - self._start_time
        spinner = SPINNER_FRAMES[frame_idx % len(SPINNER_FRAMES)]

        t_lower = self.tool_name.lower()
        if "grep" in t_lower or "search" in t_lower:
            verb = "Searching"
        elif "read" in t_lower or "view" in t_lower:
            verb = "Reading"
        elif "write" in t_lower or "edit" in t_lower or "replace" in t_lower:
            verb = "Editing"
        elif "command" in t_lower or "shell" in t_lower:
            verb = "Running"
        elif "nitee" in t_lower or "computer" in t_lower:
            verb = "Automating"
        else:
            verb = self.tool_name

        text = Text()
        text.append(f" ~ ", style="bold #38bdf8")
        text.append(f"{verb} ", style="bold white")
        if self.args_summary:
            summary = self.args_summary
            if len(summary) > 40:
                summary = summary[:37] + "..."
            text.append(f"{summary} ", style="dim")
        text.append(f"{spinner}", style="bold cyan")
        return text

    async def _animate(self) -> None:
        frame_idx = 0
        while self._running:
            if self._live:
                self._live.update(self._render(frame_idx))
            frame_idx += 1
            await asyncio.sleep(0.08)

    async def start(self) -> None:
        self._running = True
        self._start_time = time.time()
        self._live = Live(
            self._render(0),
            console=ui.console,
            refresh_per_second=15,
            transient=True,
        )
        self._live.start()
        self._task = asyncio.create_task(self._animate())

    async def stop(self) -> None:
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None
        if self._live:
            self._live.stop()
            self._live = None


@asynccontextmanager
async def animate_tool(tool_name: str, args_summary: str = ""):
    """Async context manager wrapper for tool execution animation."""
    anim = ToolAnimation(tool_name=tool_name, args_summary=args_summary)
    await anim.start()
    try:
        yield anim
    finally:
        await anim.stop()
