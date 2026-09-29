"""
CORD Tools - System Information Tool
Gathers system information: CPU, RAM, disk, OS, network, and running processes.
"""
from __future__ import annotations
import json
import platform
import os
import subprocess
from typing import Any, Dict

from cord.tools.base import BaseTool, ToolResult


class SystemInfoTool(BaseTool):
    """Gathers system information for the autonomous agent."""
    name = "system_info"
    description = "Get system information. Query types: 'overview' (OS/CPU/RAM), 'disk' (disk usage), 'processes' (top running processes), 'network' (network interfaces)."
    parameters = {
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "enum": ["overview", "disk", "processes", "network", "all"],
                "description": "Type of system information to retrieve."
            }
        },
        "required": ["query"]
    }

    async def execute(self, **kwargs) -> ToolResult:
        query = kwargs.get("query", "overview")
        info = {}

        if query in ("overview", "all"):
            info["os"] = f"{platform.system()} {platform.release()} ({platform.version()})"
            info["machine"] = platform.machine()
            info["processor"] = platform.processor()
            info["python"] = platform.python_version()
            info["hostname"] = platform.node()
            info["cpu_count"] = os.cpu_count()
            # RAM via PowerShell
            try:
                ram = subprocess.run(
                    ["powershell", "-Command",
                     "[math]::Round((Get-CimInstance Win32_ComputerSystem).TotalPhysicalMemory/1GB, 2)"],
                    capture_output=True, text=True, timeout=5
                )
                info["total_ram_gb"] = ram.stdout.strip()
            except Exception:
                info["total_ram_gb"] = "unknown"

        if query in ("disk", "all"):
            try:
                disk = subprocess.run(
                    ["powershell", "-Command",
                     "Get-PSDrive -PSProvider FileSystem | Select-Object Name, @{N='Used_GB';E={[math]::Round($_.Used/1GB,2)}}, @{N='Free_GB';E={[math]::Round($_.Free/1GB,2)}} | ConvertTo-Json"],
                    capture_output=True, text=True, timeout=5
                )
                info["disks"] = disk.stdout.strip()
            except Exception as e:
                info["disks"] = f"Error: {e}"

        if query in ("processes", "all"):
            try:
                procs = subprocess.run(
                    ["powershell", "-Command",
                     "Get-Process | Sort-Object -Property WorkingSet64 -Descending | Select-Object -First 15 Name, Id, @{N='RAM_MB';E={[math]::Round($_.WorkingSet64/1MB,1)}}, CPU | ConvertTo-Json"],
                    capture_output=True, text=True, timeout=10
                )
                info["top_processes"] = procs.stdout.strip()
            except Exception as e:
                info["top_processes"] = f"Error: {e}"

        if query in ("network", "all"):
            try:
                net = subprocess.run(
                    ["powershell", "-Command",
                     "Get-NetIPAddress -AddressFamily IPv4 | Where-Object {$_.IPAddress -ne '127.0.0.1'} | Select-Object InterfaceAlias, IPAddress | ConvertTo-Json"],
                    capture_output=True, text=True, timeout=5
                )
                info["network"] = net.stdout.strip()
            except Exception as e:
                info["network"] = f"Error: {e}"

        output = json.dumps(info, indent=2, ensure_ascii=False)
        return ToolResult(success=True, output=output, metadata={"query": query})
