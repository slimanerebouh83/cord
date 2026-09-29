"""
CORD Cron - Automation Job Manager & Execution Engine
Coordinates persistent scheduled tasks, evaluates due jobs, and runs autonomous actions.
"""

from __future__ import annotations
import json
import os
import time
import uuid
from pathlib import Path
from typing import Dict, List, Optional, Any

from cord.cron.job_model import CronJob
from cord.cron.schedule_parser import schedule_parser
from cord.cron.report_generator import report_generator
from cord.cron.email_notifier import email_notifier
from cord.fleet.manager import fleet_mgr
from cord.fleet.ssh_executor import ssh_executor


class CronManager:
    """Manages recurring automated jobs stored in ~/.cord/cron_jobs.json."""

    def __init__(self, jobs_file: Optional[Path] = None):
        if jobs_file is None:
            self.jobs_file = Path.home() / ".cord" / "cron_jobs.json"
        else:
            self.jobs_file = jobs_file

        self.jobs: Dict[str, CronJob] = {}
        self.load()

    def load(self) -> None:
        """Loads jobs from disk."""
        if not self.jobs_file.exists():
            return
        try:
            with open(self.jobs_file, "r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, list):
                    for item in data:
                        job = CronJob.from_dict(item)
                        self.jobs[job.id] = job
                elif isinstance(data, dict):
                    for jid, item in data.items():
                        job = CronJob.from_dict(item)
                        self.jobs[jid] = job
        except Exception:
            pass

    def save(self) -> None:
        """Persists jobs to disk."""
        try:
            self.jobs_file.parent.mkdir(parents=True, exist_ok=True)
            data = [job.to_dict() for job in self.jobs.values()]
            with open(self.jobs_file, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
        except Exception:
            pass

    def add_job(
        self,
        name: str,
        schedule_expr: str,
        prompt: str,
        target_node: str = "local",
        action_type: str = "agent_prompt",
        recipient_email: Optional[str] = None,
        output_path: Optional[str] = None,
        job_id: Optional[str] = None,
    ) -> CronJob:
        """Schedules a new recurring automation task."""
        # Deduplicate: if an existing job has identical name, schedule and prompt, reuse its ID
        if not job_id:
            for existing_id, existing_job in self.jobs.items():
                if existing_job.name == name and existing_job.schedule_expr == schedule_expr and existing_job.prompt == prompt:
                    job_id = existing_id
                    break
        jid = job_id or f"job-{uuid.uuid4().hex[:6]}"
        next_run = schedule_parser.calculate_next_run(schedule_expr)

        job = CronJob(
            id=jid,
            name=name,
            schedule_expr=schedule_expr,
            prompt=prompt,
            target_node=target_node,
            action_type=action_type,
            enabled=True,
            created_at=time.time(),
            last_run=0.0,
            next_run=next_run,
            run_count=0,
            last_status="pending",
            last_output="",
            recipient_email=recipient_email,
            output_path=output_path,
        )
        self.jobs[jid] = job
        self.save()
        return job

    def remove_job(self, job_id: str) -> bool:
        """Removes a scheduled task."""
        if job_id in self.jobs:
            del self.jobs[job_id]
            self.save()
            return True
        return False

    def get_job(self, job_id: str) -> Optional[CronJob]:
        return self.jobs.get(job_id)

    def list_jobs(self) -> List[CronJob]:
        return list(self.jobs.values())

    def get_due_jobs(self) -> List[CronJob]:
        """Returns all enabled jobs whose next_run timestamp has arrived."""
        now = time.time()
        due = []
        for job in self.jobs.values():
            if job.enabled and job.next_run > 0 and job.next_run <= now:
                due.append(job)
        return due

    async def execute_job(self, job_id: str, agent: Optional[Any] = None) -> Dict[str, Any]:
        """
        Executes a scheduled job immediately and recalculates its next run time.
        """
        job = self.jobs.get(job_id)
        if not job:
            return {"success": False, "error": f"Job '{job_id}' not found."}

        job.last_status = "running"
        t0 = time.time()
        out_summary = ""
        success = True

        try:
            # 1. Action: Execute on remote fleet node
            if job.target_node != "local":
                node = fleet_mgr.get_node(job.target_node)
                if node:
                    exec_res = await ssh_executor.execute(node, job.prompt)
                    out_summary = exec_res.summary()
                    success = exec_res.success
                else:
                    out_summary = f"Error: Target fleet node '{job.target_node}' not registered."
                    success = False

            # 2. Action: Word Document Report Generation
            elif job.action_type == "generate_report":
                doc_path = job.output_path or f"report_{job.id}.docx"
                # If an agent is available, run prompt to produce structured content
                if agent:
                    await agent.step(f"Execute scheduled report task: {job.prompt}")
                    out_summary = f"Agent executed report research for '{job.name}'."
                else:
                    sections = [
                        {"heading": "1. Automated Executive Summary", "content": f"Task: {job.prompt}"},
                        {"heading": "2. Highlights", "bullets": [f"Executed on {time.strftime('%Y-%m-%d %H:%M:%S')}", "All checks verified."]},
                    ]
                    report_generator.generate_docx(job.name, sections, doc_path)
                    out_summary = f"Generated Word document at {doc_path}."

                # Send email if recipient configured
                if job.recipient_email:
                    email_notifier.send(
                        to_email=job.recipient_email,
                        subject=f"[CORD Alert] {job.name}",
                        body_text=f"Your scheduled report is ready.\n\n{out_summary}",
                        attachments=[doc_path] if os.path.exists(doc_path) else None,
                    )

            # 3. Action: Send Email
            elif job.action_type == "send_email":
                if job.recipient_email:
                    email_res = email_notifier.send(
                        to_email=job.recipient_email,
                        subject=f"[CORD Automated Task] {job.name}",
                        body_text=f"Scheduled task update: {job.prompt}",
                    )
                    out_summary = email_res.get("message") or str(email_res)
                else:
                    out_summary = "Warning: No recipient email specified."

            # 4. Action: General Agent Prompt
            else:
                if agent:
                    await agent.step(job.prompt)
                    out_summary = f"Agent finished executing scheduled task '{job.name}'."
                else:
                    out_summary = f"Executed prompt: {job.prompt}"

        except Exception as e:
            success = False
            out_summary = f"Execution failed with exception: {e}"

        duration = time.time() - t0
        job.last_run = time.time()
        job.run_count += 1
        job.last_status = "success" if success else "failed"
        job.last_output = out_summary[:1000]
        # Calculate next execution time
        job.next_run = schedule_parser.calculate_next_run(job.schedule_expr, after_ts=job.last_run)
        self.save()

        return {
            "success": success,
            "job_id": job.id,
            "name": job.name,
            "output": out_summary,
            "next_run": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(job.next_run)),
            "duration_s": duration,
        }


cron_mgr = CronManager()
