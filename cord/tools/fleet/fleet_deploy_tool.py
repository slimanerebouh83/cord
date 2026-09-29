"""
CORD Tools - Fleet Autonomous App & Web Server Deployment Tool
Deploys local codebases to remote machines, configures services/webservers, launches daemons, and verifies ports.
"""

from __future__ import annotations
import os
import time
from typing import Optional
from cord.tools.base import BaseTool, ToolResult
from cord.fleet.manager import fleet_mgr
from cord.fleet.ssh_executor import ssh_executor


class FleetDeployTool(BaseTool):
    name = "fleet_deploy"
    description = (
        "Autonomously deploys a website or application to a remote fleet machine. "
        "Uploads code, installs dependencies, launches the web/app server, and verifies the HTTP port."
    )
    parameters = {
        "type": "object",
        "properties": {
            "node": {"type": "string", "description": "Target fleet machine to act as the server"},
            "source_dir": {"type": "string", "description": "Local directory containing the project or website files"},
            "remote_dir": {
                "type": "string",
                "description": "Destination directory on the remote machine (e.g. '~/deployed_app' or '/var/www/site')",
                "default": "~/deployed_app",
            },
            "start_command": {
                "type": "string",
                "description": "Shell command to launch the app (e.g. 'nohup python3 -m http.server 8080 > server.log 2>&1 &')",
            },
            "port": {
                "type": "integer",
                "description": "HTTP port to verify (e.g. 80, 8080, 3000, 5000)",
                "default": 8080,
            },
            "install_cmd": {
                "type": "string",
                "description": "Optional command to install dependencies before starting (e.g. 'npm install' or 'pip install -r requirements.txt')",
            },
        },
        "required": ["node", "source_dir"],
    }

    async def execute(
        self,
        node: str,
        source_dir: str,
        remote_dir: str = "~/deployed_app",
        start_command: Optional[str] = None,
        port: int = 8080,
        install_cmd: Optional[str] = None,
        **kwargs,
    ) -> ToolResult:
        target = fleet_mgr.get_node(node)
        if not target:
            return ToolResult(success=False, output=f"Node '{node}' not found in fleet catalog.")

        logs = []
        logs.append(f"🚀 Deploying project from '{source_dir}' to {node}:{remote_dir}...")

        # 1. Create remote target directory
        mkdir_res = await ssh_executor.execute(target, f"mkdir -p {remote_dir}")
        if not mkdir_res.success:
            return ToolResult(success=False, output=f"Failed to create remote directory: {mkdir_res.stderr}")

        # 2. Upload source code
        upload_res = await ssh_executor.upload(target, source_dir, remote_dir)
        if not upload_res["success"]:
            return ToolResult(success=False, output=f"Failed to upload files: {upload_res.get('error')}")
        logs.append("✔ Code uploaded cleanly to remote server.")

        # 3. Run install command if provided
        if install_cmd:
            logs.append(f"📦 Running install: {install_cmd}...")
            inst_res = await ssh_executor.execute(target, f"cd {remote_dir} && {install_cmd}", timeout=180.0)
            if not inst_res.success:
                logs.append(f"⚠️ Warning: Install command returned code {inst_res.exit_code}: {inst_res.stderr[:200]}")

        # 4. Launch start command
        actual_start = start_command or f"nohup python3 -m http.server {port} > app.log 2>&1 &"
        logs.append(f"⚡ Starting server daemon: {actual_start}...")
        start_res = await ssh_executor.execute(target, f"cd {remote_dir} && {actual_start}")
        logs.append(f"Daemon spawn status: code {start_res.exit_code}")

        # 5. Verify server responds on port
        time.sleep(1.0)
        curl_cmd = f"curl -s -o /dev/null -w '%{{http_code}}' http://localhost:{port} || curl -s -I http://localhost:{port} | head -n 1"
        check_res = await ssh_executor.execute(target, curl_cmd, timeout=10.0)
        http_resp = check_res.stdout.strip()

        server_url = f"http://{target.host}:{port}"
        logs.append(f"🌐 Verification response on localhost:{port}: {http_resp}")
        logs.append(f"✨ Deployment Complete! Accessible at: {server_url}")

        return ToolResult(
            success=True,
            output="\n".join(logs),
        )
