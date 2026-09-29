"""CORD Voice - Live Hands-Free Voice Agent Session Loop"""
from __future__ import annotations
import asyncio
import re
from typing import TYPE_CHECKING, Optional

from rich.panel import Panel
from rich.prompt import Prompt
from cord.ui.console import ui
from cord.voice.audio_recorder import audio_recorder
from cord.voice.stt import stt
from cord.voice.tts import tts
from cord.utils.window_manager import window_manager

if TYPE_CHECKING:
    from cord.core.agent import CordAgent
    from cord.core.config import CordConfig


class LiveVoiceSession:
    """Orchestrates hands-free voice interaction: voice input -> autonomous agent -> TTS speech."""

    def __init__(self, agent: CordAgent, config: CordConfig) -> None:
        self.agent = agent
        self.config = config
        self._running = False

    def is_hide_command(self, text: str) -> bool:
        norm = text.lower().strip()
        triggers = ["hide terminal", "hide window", "hide console", "minimize terminal"]
        return any(t in norm for t in triggers)

    def is_show_command(self, text: str) -> bool:
        norm = text.lower().strip()
        triggers = ["show terminal", "show window", "show console", "restore terminal"]
        return any(t in norm for t in triggers)

    def is_exit_command(self, text: str) -> bool:
        norm = text.lower().strip()
        triggers = ["stop", "exit", "quit", "bye", "cancel"]
        return any(norm == t or norm.startswith(t + " ") for t in triggers)

    async def run(self) -> None:
        """Runs the interactive live voice loop."""
        self._running = True

        ui.console.print(Panel(
            "[bold #38bdf8]🎙️ CORD LIVE VOICE MODE (PUSH-TO-TALK)[/bold #38bdf8]\n\n"
            "[white]Hands-free voice operation is now active:[/white]\n"
            "• [bold green]Hold SPACEBAR[/bold green] to speak into microphone.\n"
            "• [bold green]Release SPACEBAR[/bold green] to transcribe & execute immediately.\n"
            "• [bold yellow]Say 'hide terminal'[/bold yellow] to minimize to desktop.\n"
            "• [bold yellow]Say 'show terminal'[/bold yellow] to restore the window.\n"
            "• [bold red]Press ESC or say 'exit' / 'stop'[/bold red] to return to normal chat.\n"
            "• [bold magenta]Neural Voice:[/bold magenta] CORD speaks back with human studio voice.",
            border_style="magenta",
            title="[bold green]● LIVE PUSH-TO-TALK ACTIVE[/bold green]",
            expand=False,
        ))

        tts.speak("Live Voice Mode activated. Hold Space to speak.")

        import ctypes
        VK_SPACE = 0x20
        VK_ESCAPE = 0x1B

        def _is_key_pressed(vk: int) -> bool:
            try:
                return bool(ctypes.windll.user32.GetAsyncKeyState(vk) & 0x8000)
            except Exception:
                return False

        while self._running:
            try:
                ui.console.print("\n[bold cyan]🎙️ [Ready] Hold SPACEBAR to speak, or type a message (ESC to exit)...[/bold cyan]")

                # Loop waiting for Spacebar or Esc or console input
                speech_detected = False
                typed_text = ""

                # Flush any stale space key state
                ctypes.windll.user32.GetAsyncKeyState(VK_SPACE)

                while not speech_detected and self._running:
                    if _is_key_pressed(VK_ESCAPE):
                        ui.print_info("Exiting Live Mode.")
                        self._running = False
                        break

                    if _is_key_pressed(VK_SPACE):
                        # Spacebar held down! Start recording
                        started = audio_recorder.start()
                        if not started:
                            ui.print_warning("Could not access microphone device.")
                            break

                        ui.console.print("[bold red]🔴 RECORDING... Speak now (Keep holding SPACE)[/bold red]", end="\r")
                        speech_detected = True

                        # Wait until user releases Spacebar
                        await asyncio.sleep(0.15)
                        while _is_key_pressed(VK_SPACE) and self._running:
                            await asyncio.sleep(0.05)

                        ui.console.print("\n[bold green]✔ Space released! Processing speech...[/bold green]")
                        wav_file = audio_recorder.stop()
                        if wav_file:
                            ui.print_info("Transcribing speech with neural STT...")
                            transcribed = stt.transcribe(wav_file, self.config)
                            text = (transcribed or "").strip()
                        else:
                            text = ""
                        break

                    await asyncio.sleep(0.05)

                if not self._running:
                    break

                if not speech_detected:
                    continue

                if not text:
                    ui.print_warning("No speech detected. Hold SPACE and speak clearly.")
                    continue

                ui.console.print(f"[bold cyan]🗣️ You said:[/bold cyan] [white]{text}[/white]")

                # 3. Handle Voice Triggers
                if self.is_exit_command(text):
                    tts.speak("Exiting Live Mode. Goodbye.")
                    ui.print_info("Live Voice Mode stopped.")
                    self._running = False
                    break

                if self.is_hide_command(text):
                    window_manager.hide_terminal()
                    tts.speak("Terminal hidden. Running in stealth mode.")
                    ui.print_info("Terminal hidden (Stealth mode active).")
                    continue

                if self.is_show_command(text):
                    window_manager.show_terminal()
                    tts.speak("Terminal restored.")
                    ui.print_info("Terminal visible.")
                    continue

                # 4. Dispatch turn to agent
                ui.console.print()
                response = await self.agent.step(text)
                ui.console.print()

                # 5. Speak back aloud via TTS
                if response and isinstance(response, str):
                    tts.speak(response)

            except (KeyboardInterrupt, asyncio.CancelledError):
                audio_recorder.stop()
                self._running = False
                break
            except Exception as e:
                audio_recorder.stop()
                ui.print_error(f"Live voice error: {e}")
                await asyncio.sleep(1.0)

        tts.speak("Live Mode ended.")
