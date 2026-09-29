"""
CORD Cron - Autonomous Background Daemon Runner
Continuously monitors scheduled tasks, evaluates due triggers, and executes jobs autonomously.
"""

from __future__ import annotations
import asyncio
import time
from typing import Optional, Any
from cord.cron.cron_manager import cron_mgr
from cord.ui.console import ui
from rich.panel import Panel


class CronDaemon:
    """Runs a continuous polling loop to trigger scheduled tasks at their appointed times."""

    def __init__(self, check_interval_sec: float = 30.0, agent: Optional[Any] = None):
        self.check_interval = check_interval_sec
        self.agent = agent
        self._running = False

    async def start(self) -> None:
        """Starts the persistent background daemon loop."""
        self._running = True
        ui.console.print(Panel(
            f"[bold cyan]⏰ CORD CRON DAEMON ACTIVATED[/bold cyan]\n"
            f"[white]Active Scheduled Jobs:[/white] [bold green]{len(cron_mgr.jobs)}[/bold green]\n"
            f"[dim]Polling for due tasks every {self.check_interval:.0f}s. Press Ctrl+C to terminate.[/dim]",
            border_style="cyan",
            title="[bold #38bdf8]● AUTONOMOUS SCHEDULER[/bold #38bdf8]",
            expand=False,
        ))

        try:
            while self._running:
                due_jobs = cron_mgr.get_due_jobs()
                for job in due_jobs:
                    ui.console.print(
                        f"\n[bold yellow]⚡ [CRON TRIGGER][/bold yellow] Executing scheduled task: "
                        f"[bold white]{job.name}[/bold white] (ID: {job.id})"
                    )
                    res = await cron_mgr.execute_job(job.id, agent=self.agent)
                    status_color = "green" if res["success"] else "red"
                    ui.console.print(
                        f"[{status_color}]✔ Job '{job.name}' finished.[/{status_color}] "
                        f"Next execution: [cyan]{res['next_run']}[/cyan]"
                    )

                await asyncio.sleep(self.check_interval)
        except (KeyboardInterrupt, asyncio.CancelledError):
            pass
        finally:
            self._running = False
            ui.print_info("CORD Cron Daemon stopped.")

    def stop(self) -> None:
        self._running = False


async def run_cron_daemon(agent: Optional[Any] = None) -> None:
    daemon = CronDaemon(check_interval_sec=30.0, agent=agent)
    await daemon.start()
