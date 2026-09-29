"""
CORD Cron - Natural Language & Cron Schedule Parser
Parses expressions like 'every morning at 8:00', 'every 24h', 'every 30m', or '0 8 * * *'.
"""

from __future__ import annotations
import re
import time
from datetime import datetime, timedelta
from typing import Optional


class ScheduleParser:
    """Computes next execution timestamps for natural language and cron schedules."""

    @staticmethod
    def calculate_next_run(schedule_expr: str, after_ts: Optional[float] = None) -> float:
        """
        Calculates the epoch timestamp of the next run based on the schedule expression.
        """
        base_ts = after_ts if after_ts is not None else time.time()
        base_dt = datetime.fromtimestamp(base_ts)
        expr = schedule_expr.strip().lower()

        # 1. Simple relative intervals: "every Nh", "every Nm", "every Ns", "every N days"
        # e.g. "every 24h", "every 24 hours", "every 1 hour", "every 30m", "every 15 minutes"
        m_interval = re.search(r"every\s+(\d+)\s*(s|sec|seconds?|m|min|minutes?|h|hr|hours?|d|days?)", expr)
        if m_interval:
            val = int(m_interval.group(1))
            unit = m_interval.group(2)
            if unit.startswith("s"):
                delta = timedelta(seconds=val)
            elif unit.startswith("m"):
                delta = timedelta(minutes=val)
            elif unit.startswith("h"):
                delta = timedelta(hours=val)
            elif unit.startswith("d"):
                delta = timedelta(days=val)
            else:
                delta = timedelta(hours=val)
            return (base_dt + delta).timestamp()

        # 2. Specific time of day: "every morning at 8:00", "every day at 08:00", "daily at 8:00 am"
        m_tod = re.search(r"(?:every\s+(?:day|morning|evening|night)?\s*at|daily\s+at)\s+(\d{1,2})(?::(\d{2}))?\s*(am|pm)?", expr)
        if m_tod:
            hour = int(m_tod.group(1))
            minute = int(m_tod.group(2)) if m_tod.group(2) else 0
            ampm = m_tod.group(3)
            if ampm == "pm" and hour < 12:
                hour += 12
            elif ampm == "am" and hour == 12:
                hour = 0

            target = base_dt.replace(hour=hour, minute=minute, second=0, microsecond=0)
            if target <= base_dt:
                target += timedelta(days=1)
            return target.timestamp()

        # 3. Keyword presets
        if "hourly" in expr:
            return (base_dt + timedelta(hours=1)).timestamp()
        if "daily" in expr:
            return (base_dt + timedelta(days=1)).timestamp()
        if "weekly" in expr:
            return (base_dt + timedelta(weeks=1)).timestamp()

        # 4. Standard 5-field cron expression (minute hour day_of_month month day_of_week)
        parts = schedule_expr.strip().split()
        if len(parts) == 5:
            min_p, hour_p, dom_p, mon_p, dow_p = parts

            # Handle simple minute step: */N * * * *
            if min_p.startswith("*/") and hour_p == "*":
                step = int(min_p[2:])
                next_min = (base_dt.minute // step + 1) * step
                if next_min >= 60:
                    target = base_dt.replace(minute=0, second=0, microsecond=0) + timedelta(hours=1)
                else:
                    target = base_dt.replace(minute=next_min, second=0, microsecond=0)
                return target.timestamp()

            # Handle exact minute & hour: e.g. "0 8 * * *" (8:00 AM daily)
            if min_p.isdigit() and hour_p.isdigit():
                h = int(hour_p)
                m = int(min_p)
                target = base_dt.replace(hour=h, minute=m, second=0, microsecond=0)
                if target <= base_dt:
                    target += timedelta(days=1)
                return target.timestamp()

        # Default fallback: 24 hours from now
        return (base_dt + timedelta(hours=24)).timestamp()


schedule_parser = ScheduleParser()
