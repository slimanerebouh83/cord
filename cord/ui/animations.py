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
        if any(k in t_lower for k in ("grep", "search", "find_in_files")):
            icon, verb, style = "🔍", "Searching Codebase", "bold #0ea5e9"
        elif any(k in t_lower for k in ("read", "view", "inspect")):
            icon, verb, style = "📄", "Reading File", "bold #10b981"
        elif any(k in t_lower for k in ("write", "edit", "replace", "patch")):
            icon, verb, style = "✏️", "Applying Surgical Edit", "bold #10b981"
        elif any(k in t_lower for k in ("command", "shell", "bash", "powershell")):
            icon, verb, style = "⚡", "Executing Command", "bold #f59e0b"
        elif any(k in t_lower for k in ("computer", "mouse", "keyboard", "window", "act", "nitee")):
            icon, verb, style = "🖥️", "Automating Desktop", "bold #6366f1"
        elif any(k in t_lower for k in ("screenshot", "vision")):
            icon, verb, style = "👁️", "Capturing Screen", "bold #ec4899"
        elif any(k in t_lower for k in ("subagent", "swarm", "agent", "fleet")):
            icon, verb, style = "🐝", "Dispatching Swarm Peer", "bold #a855f7"
        else:
            icon, verb, style = "⚙️", f"Executing {self.tool_name}", "bold #38bdf8"

        text = Text()
        text.append(f" {spinner} ", style="bold bright_cyan")
        text.append(f"{icon} ", style="bold")
        text.append(f"{verb} ", style=style)
        if self.args_summary:
            summary = self.args_summary
            if len(summary) > 42:
                summary = summary[:39] + "..."
            text.append(f"\"{summary}\" ", style="dim white")
        text.append(f"│ ⏱️ {elapsed:.1f}s", style="dim")
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
