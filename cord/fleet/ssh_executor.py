"""
CORD Fleet - Native OpenSSH Remote Command & File Transfer Engine
Provides async execution, SCP file synchronization, OS fingerprinting, and service management.
"""

from __future__ import annotations
import asyncio
import os
import shutil
import time
from typing import Dict, Any, List, Optional
from dataclasses import dataclass

from cord.fleet.models import FleetNode


@dataclass
class SSHCommandResult:
    node_name: str
    command: str
    exit_code: int
    stdout: str
    stderr: str
    duration_ms: float
    success: bool

    def summary(self) -> str:
        status = "SUCCESS" if self.success else f"FAILED (code {self.exit_code})"
        res = f"[{self.node_name}] {self.command} -> {status} in {self.duration_ms:.1f}ms\n"
        if self.stdout.strip():
            res += f"STDOUT:\n{self.stdout.strip()}\n"
        if self.stderr.strip():
            res += f"STDERR:\n{self.stderr.strip()}\n"
        return res


class SSHExecutor:
    """Executes remote commands and transfers files via native OpenSSH CLI."""

    def __init__(self):
        self.ssh_bin = shutil.which("ssh") or "ssh"
        self.scp_bin = shutil.which("scp") or "scp"

    def _build_ssh_args(self, node: FleetNode, extra_opts: Optional[List[str]] = None) -> List[str]:
        args = [
            self.ssh_bin,
            "-p", str(node.port),
            "-o", "StrictHostKeyChecking=accept-new",
            "-o", "ConnectTimeout=10",
            "-o", "ServerAliveInterval=15",
        ]
        if node.key_path:
            expanded = os.path.expanduser(node.key_path)
            args.extend(["-i", expanded])
        if extra_opts:
            args.extend(extra_opts)
        target = f"{node.user}@{node.host}" if node.user else node.host
        args.append(target)
        return args

    def _build_scp_args(self, node: FleetNode, recursive: bool = True) -> List[str]:
        args = [
            self.scp_bin,
            "-P", str(node.port),
            "-o", "StrictHostKeyChecking=accept-new",
            "-o", "ConnectTimeout=10",
        ]
        if recursive:
            args.append("-r")
        if node.key_path:
            expanded = os.path.expanduser(node.key_path)
            args.extend(["-i", expanded])
        return args

    async def execute(
        self,
        node: FleetNode,
        command: str,
        timeout: float = 60.0,
        env: Optional[Dict[str, str]] = None,
    ) -> SSHCommandResult:
        """Executes a command on the remote node via OpenSSH."""
        t0 = time.time()
        ssh_cmd = self._build_ssh_args(node)
        ssh_cmd.append(command)

        merged_env = os.environ.copy()
        if env:
            merged_env.update(env)

        try:
            proc = await asyncio.create_subprocess_exec(
                *ssh_cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                env=merged_env,
            )
            try:
                stdout_b, stderr_b = await asyncio.wait_for(proc.communicate(), timeout=timeout)
                duration = (time.time() - t0) * 1000.0
                stdout = stdout_b.decode("utf-8", errors="replace")
                stderr = stderr_b.decode("utf-8", errors="replace")
                code = proc.returncode if proc.returncode is not None else -1
                return SSHCommandResult(
                    node_name=node.name,
                    command=command,
                    exit_code=code,
                    stdout=stdout,
                    stderr=stderr,
                    duration_ms=duration,
                    success=(code == 0),
                )
            except asyncio.TimeoutError:
                try:
                    proc.kill()
                    await proc.communicate()  # Drain streams to prevent zombie processes
                except Exception:
                    pass
                duration = (time.time() - t0) * 1000.0
                return SSHCommandResult(
                    node_name=node.name,
                    command=command,
                    exit_code=-1,
                    stdout="",
                    stderr=f"SSH execution timed out after {timeout}s",
                    duration_ms=duration,
                    success=False,
                )
        except Exception as ex:
            duration = (time.time() - t0) * 1000.0
            return SSHCommandResult(
                node_name=node.name,
                command=command,
                exit_code=-1,
                stdout="",
                stderr=f"SSH process failed: {ex}",
                duration_ms=duration,
                success=False,
            )

    async def upload(
        self,
        node: FleetNode,
        local_path: str,
        remote_path: str,
        timeout: float = 120.0,
    ) -> Dict[str, Any]:
        """Uploads a local file or directory to the remote node via SCP."""
        t0 = time.time()
        local_p = os.path.expanduser(local_path)
        if not os.path.exists(local_p):
            return {
                "success": False,
                "error": f"Local path not found: {local_p}",
                "node": node.name,
            }

        scp_args = self._build_scp_args(node, recursive=os.path.isdir(local_p))
        scp_args.append(local_p)
        remote_target = f"{node.user}@{node.host}:{remote_path}"
        scp_args.append(remote_target)

        try:
            proc = await asyncio.create_subprocess_exec(
                *scp_args,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout_b, stderr_b = await asyncio.wait_for(proc.communicate(), timeout=timeout)
            duration = (time.time() - t0) * 1000.0
            stdout = stdout_b.decode("utf-8", errors="replace")
            stderr = stderr_b.decode("utf-8", errors="replace")
            success = (proc.returncode == 0)
            return {
                "success": success,
                "node": node.name,
                "local_path": local_p,
                "remote_path": remote_path,
                "duration_ms": duration,
                "error": stderr if not success else None,
                "stdout": stdout,
            }
        except Exception as ex:
            return {
                "success": False,
                "node": node.name,
                "error": f"Upload failed: {ex}",
            }

    async def download(
        self,
        node: FleetNode,
        remote_path: str,
        local_path: str,
        timeout: float = 120.0,
    ) -> Dict[str, Any]:
        """Downloads a remote file or directory to the local system via SCP."""
        t0 = time.time()
        local_p = os.path.expanduser(local_path)
        os.makedirs(os.path.dirname(os.path.abspath(local_p)), exist_ok=True)

        scp_args = self._build_scp_args(node, recursive=True)
        remote_source = f"{node.user}@{node.host}:{remote_path}"
        scp_args.append(remote_source)
        scp_args.append(local_p)

        try:
            proc = await asyncio.create_subprocess_exec(
                *scp_args,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout_b, stderr_b = await asyncio.wait_for(proc.communicate(), timeout=timeout)
            duration = (time.time() - t0) * 1000.0
            stdout = stdout_b.decode("utf-8", errors="replace")
            stderr = stderr_b.decode("utf-8", errors="replace")
            success = (proc.returncode == 0)
            return {
                "success": success,
                "node": node.name,
                "remote_path": remote_path,
                "local_path": local_p,
                "duration_ms": duration,
                "error": stderr if not success else None,
                "stdout": stdout,
            }
        except Exception as ex:
            return {
                "success": False,
                "node": node.name,
                "error": f"Download failed: {ex}",
            }

    async def test_connection(self, node: FleetNode) -> Dict[str, Any]:
        """Tests SSH reachability and fingerprints the remote operating system."""
        # Check OS via uname or cmd
        cmd = "uname -sm || ver"
        res = await self.execute(node, cmd, timeout=10.0)
        if not res.success:
            return {
                "reachable": False,
                "error": res.stderr or "Connection failed",
                "node": node.name,
            }

        raw_os = res.stdout.strip()
        os_type = "linux"
        if "Darwin" in raw_os:
            os_type = "darwin"
        elif "Windows" in raw_os or "Microsoft" in raw_os:
            os_type = "windows"
        elif "Linux" in raw_os:
            os_type = "linux"

        # Fetch detailed specs
        specs = await self.get_system_specs(node, os_type)
        return {
            "reachable": True,
            "os_type": os_type,
            "raw_os": raw_os,
            "specs": specs,
            "latency_ms": res.duration_ms,
        }

    async def get_system_specs(self, node: FleetNode, os_type: str = "linux") -> Dict[str, Any]:
        """Fetches CPU, RAM, disk, and hostname specs from the remote machine."""
        specs: Dict[str, Any] = {"os_type": os_type}
        if os_type in ("linux", "darwin"):
            info_cmd = "hostname && uname -r && nproc 2>/dev/null || sysctl -n hw.ncpu 2>/dev/null && free -m 2>/dev/null || vm_stat 2>/dev/null"
            res = await self.execute(node, info_cmd, timeout=10.0)
            if res.success:
                lines = [l.strip() for l in res.stdout.splitlines() if l.strip()]
                if lines:
                    specs["hostname"] = lines[0]
                if len(lines) > 1:
                    specs["kernel"] = lines[1]
                if len(lines) > 2 and lines[2].isdigit():
                    specs["cpu_cores"] = int(lines[2])
                specs["raw_telemetry"] = res.stdout[:500]

            # Disk usage
            df_res = await self.execute(node, "df -h / 2>/dev/null || df -h", timeout=10.0)
            if df_res.success:
                specs["disk_root"] = df_res.stdout.splitlines()[-1] if df_res.stdout.splitlines() else ""

        elif os_type == "windows":
            win_cmd = "hostname && wmic cpu get NumberOfCores /value 2>nul"
            res = await self.execute(node, win_cmd, timeout=10.0)
            if res.success:
                specs["raw_telemetry"] = res.stdout[:500]

        return specs


ssh_executor = SSHExecutor()
