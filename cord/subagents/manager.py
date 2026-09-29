"""
CORD Subagents - Subagent Orchestrator & Manager
Supports both pre-configured roles (researcher, coder, reviewer, tester)
and dynamic AI-synthesized custom subagents with tailored system prompts and tools,
strictly inheriting provider/model configuration from the spawning agent.
"""

from __future__ import annotations
import uuid
from typing import Dict, Any, List, Optional

from cord.core.config import CordConfig
from cord.subagents.base_subagent import Subagent, SubagentResult, TOOL_ALIASES
from cord.subagents.roles import ROLE_CONFIGS
from cord.subagents.message_bus import swarm_bus
from cord.tools.base import BaseTool


class SubagentManager:
    """Manages the creation and execution of specialized subagents."""

    def __init__(
        self,
        config: CordConfig,
        available_tools: Dict[str, BaseTool],
        parent_agent: Optional[Any] = None,
    ):
        self.config = config
        self.available_tools = available_tools
        self.parent_agent = parent_agent
        self.history: List[SubagentResult] = []
        self.custom_subagents: Dict[str, Dict[str, Any]] = {}
        self.agents: Dict[str, Subagent] = {}

    def update_config(self, new_config: CordConfig) -> None:
        """Dynamically updates the configuration used for subagents."""
        self.config = new_config

    def get_effective_config(self) -> CordConfig:
        """Returns the active configuration from the parent agent if available, else self.config."""
        if self.parent_agent and hasattr(self.parent_agent, "config"):
            return self.parent_agent.config
        return self.config

    def get_available_roles(self) -> Dict[str, str]:
        roles = {role: meta["description"] for role, meta in ROLE_CONFIGS.items()}
        for name, meta in self.custom_subagents.items():
            roles[f"custom:{name}"] = meta.get("description", "Custom AI-created subagent")
        return roles

    def _resolve_tools(self, requested_tool_names: List[str] | set[str]) -> List[BaseTool]:
        """Resolves requested tool names including aliases against available tools."""
        req_set = set(requested_tool_names)
        resolved: List[BaseTool] = []
        seen = set()

        for name, tool_inst in self.available_tools.items():
            if name in req_set:
                if name not in seen:
                    resolved.append(tool_inst)
                    seen.add(name)
            else:
                # Check if any requested tool is an alias for this tool
                for req in req_set:
                    if TOOL_ALIASES.get(req) == name and name not in seen:
                        resolved.append(tool_inst)
                        seen.add(name)
        return resolved

    async def spawn(
        self,
        role: str,
        task: str,
        custom_name: Optional[str] = None,
        model: Optional[str] = None,
        provider: Optional[str] = None,
        parent_config: Optional[CordConfig] = None,
    ) -> SubagentResult:
        """Instantiates and executes a standard preset subagent."""
        role_key = role.lower()
        if role_key not in ROLE_CONFIGS:
            role_key = "coder"

        meta = ROLE_CONFIGS[role_key]
        tools = self._resolve_tools(meta["allowed_tools"])

        sub_name = custom_name or f"{role_key}-{uuid.uuid4().hex[:6]}"
        effective_cfg = parent_config or self.get_effective_config()

        parent_label = "main"
        if self.parent_agent and hasattr(self.parent_agent, "config"):
            parent_label = f"agent ({self.parent_agent.config.model})"

        agent = Subagent(
            name=sub_name,
            role=role_key,
            system_prompt=meta["system_prompt"],
            config=effective_cfg,
            tools=tools,
            model=model,
            provider=provider,
            parent_name=parent_label,
        )

        self.agents[sub_name] = agent
        swarm_bus.register_agent(sub_name)

        result = await agent.run(task)
        self.history.append(result)
        return result

    async def spawn_custom(
        self,
        name: str,
        role_title: str,
        system_prompt: str,
        tool_names: List[str],
        task: str,
        model: Optional[str] = None,
        provider: Optional[str] = None,
        parent_config: Optional[CordConfig] = None,
    ) -> SubagentResult:
        """
        Dynamically synthesizes and launches an autonomous subagent defined entirely by the AI.
        Allows custom system instructions and fine-grained tool assignment.
        """
        # Save definition for inspection in /subagents
        clean_name = name.lower().replace(" ", "_")
        self.custom_subagents[clean_name] = {
            "title": role_title,
            "description": f"{role_title} (AI Custom Created)",
            "system_prompt": system_prompt,
            "tools": tool_names,
        }

        # Resolve requested tools against available registry including aliases
        assigned_tools = self._resolve_tools(tool_names)

        # If no tools matched or specified, default to safe read-only tools
        if not assigned_tools:
            assigned_tools = self._resolve_tools([
                "read_file", "list_directory", "list_dir", "search_files", "find_files"
            ])

        effective_cfg = parent_config or self.get_effective_config()
        parent_label = "main"
        if self.parent_agent and hasattr(self.parent_agent, "config"):
            parent_label = f"agent ({self.parent_agent.config.model})"

        sub_instance = Subagent(
            name=f"custom-{clean_name}",
            role=role_title,
            system_prompt=system_prompt,
            config=effective_cfg,
            tools=assigned_tools,
            model=model,
            provider=provider,
            parent_name=parent_label,
        )

        self.agents[sub_instance.name] = sub_instance
        swarm_bus.register_agent(sub_instance.name)

        result = await sub_instance.run(task)
        self.history.append(result)
        return result

    def get_agent(self, identifier: str) -> Optional[Subagent]:
        """Finds an agent by exact name, role, or partial ID match."""
        if not identifier:
            return None
        clean = identifier.strip().lower()
        if clean in self.agents:
            return self.agents[clean]
        for name, ag in self.agents.items():
            if name.lower() == clean:
                return ag
        for name, ag in self.agents.items():
            if clean in name.lower() or (hasattr(ag, "id") and clean in ag.id.lower()):
                return ag
        for ag in self.agents.values():
            if ag.role.lower() == clean:
                return ag
        return None

    def list_agents(self) -> List[Subagent]:
        """Returns all registered subagents."""
        return list(self.agents.values())

    def create_interactive_agent(
        self,
        role: str,
        custom_name: Optional[str] = None,
        model: Optional[str] = None,
        provider: Optional[str] = None,
    ) -> Subagent:
        """Creates and registers a subagent ready for interactive chat without requiring an immediate task."""
        role_key = role.lower()
        if role_key not in ROLE_CONFIGS:
            role_key = "coder"

        meta = ROLE_CONFIGS[role_key]
        tools = self._resolve_tools(meta["allowed_tools"])
        sub_name = custom_name or f"{role_key}-{uuid.uuid4().hex[:6]}"
        effective_cfg = self.get_effective_config()

        parent_label = "main"
        if self.parent_agent and hasattr(self.parent_agent, "config"):
            parent_label = f"agent ({self.parent_agent.config.model})"

        agent = Subagent(
            name=sub_name,
            role=role_key,
            system_prompt=meta["system_prompt"],
            config=effective_cfg,
            tools=tools,
            model=model,
            provider=provider,
            parent_name=parent_label,
        )
        self.agents[sub_name] = agent
        swarm_bus.register_agent(sub_name)
        return agent

    async def run_swarm(
        self,
        goal: str,
        tasks: List[Dict[str, Any]],
        max_concurrency: int = 50,
    ) -> Dict[str, Any]:
        """
        Executes a mass swarm of autonomous subagents concurrently (up to 1,000 subagent workers).
        Controls load via an async worker pool with semaphore throttling and a peer-to-peer message bus.
        """
        import asyncio
        from cord.subagents.message_bus import swarm_bus
        from cord.tools.system.swarm_tools import (
            SubagentSendMessageTool,
            SubagentBroadcastTool,
            SubagentReadInboxTool,
            SubagentShareSkillTool,
            SubagentListPeersTool,
        )
        from cord.tools.system.deliberation_tools import (
            SubagentProposeTool,
            SubagentVoteTool,
            SubagentConsensusTool,
        )
        from cord.tools.dynamic_tool import (
            CreateDynamicTool,
            ListDynamicTools,
        )
        from cord.tools.skills.create_skill import CreateSkillTool
        from cord.tools.skills.list_skills import ListSkillsTool
        from cord.ui.console import ui
        from rich.panel import Panel

        total = len(tasks)
        limit = min(max(max_concurrency, 1), 2000)
        sem = asyncio.Semaphore(limit)

        effective_cfg = self.get_effective_config()

        ui.console.print(Panel(
            f"[bold #38bdf8]⚡ CORD SWARM MESH ACTIVATED[/bold #38bdf8]\n"
            f"[white]Goal:[/white] [bold]{goal}[/bold]\n"
            f"[white]Provider:[/white] [bold cyan]{effective_cfg.provider}[/bold cyan] │ "
            f"[white]Model:[/white] [bold cyan]{effective_cfg.model}[/bold cyan]\n"
            f"[white]Total Subagent Workers:[/white] [bold cyan]{total:,}[/bold cyan]  │  "
            f"[white]Concurrency Pool:[/white] [bold green]{limit:,}[/bold green] active\n"
            f"[dim]Peer-to-peer mesh, voting deliberation, dynamic tool synthesis & skill sharing enabled.[/dim]",
            border_style="#2563eb",
            title="[bold #2563eb]● MASSIVE SWARM ENGINE[/bold #2563eb]",
            expand=False,
        ))

        completed_count = 0
        failed_count = 0
        results: List[SubagentResult] = []

        # Mesh collaboration tools available to all subagents
        mesh_tools = [
            SubagentSendMessageTool(),
            SubagentBroadcastTool(),
            SubagentReadInboxTool(),
            SubagentShareSkillTool(),
            SubagentListPeersTool(),
            SubagentProposeTool(),
            SubagentVoteTool(),
            SubagentConsensusTool(),
            CreateDynamicTool(),
            ListDynamicTools(),
            CreateSkillTool(),
            ListSkillsTool(),
        ]

        async def _execute_single(idx: int, t_info: Dict[str, Any]) -> SubagentResult:
            nonlocal completed_count, failed_count
            role = t_info.get("role", "coder").lower()
            prompt = t_info.get("prompt", "")
            agent_id = t_info.get("name") or f"{role}-{idx+1:04d}"

            swarm_bus.register_agent(agent_id)

            # Resolve allowed tools
            req_tools = t_info.get("tools")
            if req_tools:
                t_list = self._resolve_tools(req_tools)
            elif role in ROLE_CONFIGS:
                t_list = self._resolve_tools(ROLE_CONFIGS[role]["allowed_tools"])
            else:
                t_list = self._resolve_tools(["read_file", "list_directory", "list_dir", "search_files", "find_files"])

            # Equip with full peer-to-peer mesh & dynamic tools
            all_agent_tools = t_list + mesh_tools

            base_role_prompt = ROLE_CONFIGS.get(role, {}).get(
                "system_prompt",
                f"You are subagent '{agent_id}' ({role}). Collaborate with peer subagents and accomplish your assigned task cleanly."
            )
            sys_prompt = f"""{base_role_prompt}

### GOLDEN DIRECTIVE — UNLIMITED TIME & COMPLETE AUTONOMOUS FREEDOM:
You have ample time and complete autonomous authority. You are a real, capable subagent in a living swarm.
Do not rush, cut corners, or leave work incomplete. You can:
1. Communicate and deliberate with peers using `subagent_send_message`, `subagent_broadcast`, and `subagent_read_inbox`.
2. Propose architectures and vote on decisions using `subagent_propose`, `subagent_vote`, and `subagent_consensus`.
3. Discover what your peers know and do using `subagent_list_peers`.
4. Teach/share skills across the swarm with `subagent_share_skill`.
5. Dynamically write and compile custom tools using `create_dynamic_tool`.
Persist until your task is thoroughly completed, verified, and reported.
"""

            worker_model = t_info.get("model")
            worker_provider = t_info.get("provider")

            agent = Subagent(
                name=agent_id,
                role=role,
                system_prompt=sys_prompt,
                config=effective_cfg,
                tools=all_agent_tools,
                max_iterations=10,
                model=worker_model,
                provider=worker_provider,
                parent_name=f"swarm ({effective_cfg.model})",
            )
            self.agents[agent_id] = agent

            async with sem:
                try:
                    res = await agent.run(prompt)
                    if res.success:
                        completed_count += 1
                    else:
                        failed_count += 1
                    return res
                except Exception as ex:
                    failed_count += 1
                    return SubagentResult(
                        role=role,
                        task=prompt,
                        success=False,
                        summary=f"Worker crashed: {ex}",
                        model=worker_model or effective_cfg.model,
                        provider=worker_provider or effective_cfg.provider,
                    )
                finally:
                    swarm_bus.unregister_agent(agent_id)

        # Dispatch all tasks into worker pool
        worker_coroutines = [_execute_single(i, t) for i, t in enumerate(tasks)]
        results = await asyncio.gather(*worker_coroutines)
        self.history.extend(results)

        ui.console.print(Panel(
            f"[bold green]✔ Swarm Execution Completed[/bold green]\n"
            f"[bold white]Total Workers:[/bold white] {total}  │  "
            f"[bold green]Successful:[/bold green] {completed_count}  │  "
            f"[bold red]Failed:[/bold red] {failed_count}",
            border_style="green",
            expand=False,
        ))

        return {
            "goal": goal,
            "total_tasks": total,
            "completed": completed_count,
            "failed": failed_count,
            "results": [
                {
                    "worker": r.role,
                    "success": r.success,
                    "summary": r.summary,
                    "tool_calls": r.tool_calls_count,
                    "model": r.model,
                    "provider": r.provider,
                }
                for r in results
            ],
        }
