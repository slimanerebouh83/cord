"""CORD Tools Package - Comprehensive Native and Modular Tool Suite"""
from __future__ import annotations
from typing import List
from cord.tools.base import BaseTool

# Filesystem Tools
from cord.tools.filesystem.list_directory import ListDirectoryTool
from cord.tools.filesystem.read_file import ReadFileTool
from cord.tools.filesystem.write_file import WriteFileTool
from cord.tools.filesystem.edit_file import EditFileTool
from cord.tools.filesystem.move_file import MoveFileTool
from cord.tools.filesystem.copy_file import CopyFileTool
from cord.tools.filesystem.delete_file import DeleteFileTool
from cord.tools.filesystem.create_directory import CreateDirectoryTool
from cord.tools.filesystem.search_files import SearchFilesTool

# Shell Tools
from cord.tools.shell.execute_command import ExecuteCommandTool

# Process Tools
from cord.tools.process.start_process import StartProcessTool
from cord.tools.process.stop_process import StopProcessTool
from cord.tools.process.get_processes import GetProcessesTool
from cord.tools.process.manage_process import ManageProcessTool

# System Tools
from cord.tools.system.system_info import GetSystemInfoTool
from cord.tools.system.cpu_usage import GetCpuUsageTool
from cord.tools.system.memory_usage import GetMemoryUsageTool
from cord.tools.system.disk_usage import GetDiskUsageTool
from cord.tools.system.environment import GetEnvironmentTool

# Network Tools
from cord.tools.network.http_request import HttpRequestTool
from cord.tools.network.download_file import DownloadFileTool
from cord.tools.network.inspect_url import InspectUrlTool
from cord.tools.network.duckduckgo_search import DuckDuckGoSearchTool

# Swarm Mesh Tools
from cord.tools.system.swarm_tools import (
    SwarmDispatchTool,
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

# Dynamic Runtime Tool Synthesis & Self-Repair
from cord.tools.dynamic_tool import (
    CreateDynamicTool,
    RepairDynamicTool,
    ListDynamicTools,
    DeleteDynamicTool,
)

# AST Code Graph & Impact Analysis
from cord.tools.code_graph_tool import CodeImpactAnalysisTool

# Community Sentinel & Council Triage
from cord.tools.sentinel_tool import SentinelTriageTool

# Internet Tech Radar & MCP Marketplace
from cord.tools.tech_radar_tool import TechRadarTool

# Git Tools
from cord.tools.git.git_status import GitStatusTool
from cord.tools.git.git_diff import GitDiffTool
from cord.tools.git.git_log import GitLogTool
from cord.tools.git.git_branch import GitBranchTool
from cord.tools.git.git_checkout import GitCheckoutTool
from cord.tools.git.git_commit import GitCommitTool
from cord.tools.git.git_merge import GitMergeTool

# Developer Tools
from cord.tools.developer.run_tests import RunTestsTool
from cord.tools.developer.run_formatter import RunFormatterTool
from cord.tools.developer.run_linter import RunLinterTool
from cord.tools.developer.install_dependencies import InstallDependenciesTool

# Project Tools
from cord.tools.project.inspect_project import InspectProjectTool
from cord.tools.project.detect_language import DetectLanguageTool
from cord.tools.project.detect_package_manager import DetectPackageManagerTool
from cord.tools.project.detect_framework import DetectFrameworkTool
from cord.tools.project.run_project import RunProjectTool
from cord.tools.project.build_project import BuildProjectTool

# Computer Use Tools
from cord.tools.computer.computer_screenshot import ComputerScreenshotTool
from cord.tools.computer.computer_mouse import ComputerMouseTool
from cord.tools.computer.computer_keyboard import ComputerKeyboardTool
from cord.tools.computer.computer_window import ComputerWindowTool
from cord.tools.computer.windows_apps import WindowsAppTool
from cord.tools.computer.browser_media import BrowserMediaTool
from cord.tools.computer.computer_act import ComputerActTool
from cord.tools.computer.nitee_tool import NiteePlannerTool
from cord.tools.computer.kinetic_tool import KineticActTool
from cord.tools.computer.clipboard_tool import ClipboardTool
from cord.tools.computer.system_info_tool import SystemInfoTool

# Skills Tools
from cord.tools.skills.create_skill import CreateSkillTool
from cord.tools.skills.improve_skill import ImproveSkillTool
from cord.tools.skills.list_skills import ListSkillsTool

# Interactive & Planning Tools
from cord.tools.interactive_tools import AskUserTool, CreatePlanTool, UpdatePlanStepTool, ThinkTool

# Fleet Tools
from cord.tools.fleet import (
    FleetNodesTool,
    FleetExecTool,
    FleetTransferTool,
    FleetDeployTool,
    FleetSpawnAgentTool,
    FleetMeshTool,
)

# Cron & Automation Tools
from cord.tools.cron import (
    ScheduleCronJobTool,
    ListCronJobsTool,
    DeleteCronJobTool,
    RunCronJobNowTool,
    GenerateReportTool,
    SendEmailTool,
)

# Voice & Audio Models Tools
from cord.tools.voice import ManageVoiceModelsTool

# Ollama & Custom Models Tools
from cord.tools.models import OllamaModelTool, ManageProvidersTool

def get_default_tools() -> List[BaseTool]:
    """Returns an instantiated list of all standard tools across all domains."""
    return [
        # Filesystem
        ListDirectoryTool(),
        ReadFileTool(),
        WriteFileTool(),
        EditFileTool(),
        MoveFileTool(),
        CopyFileTool(),
        DeleteFileTool(),
        CreateDirectoryTool(),
        SearchFilesTool(),
        # Shell
        ExecuteCommandTool(),
        # Process
        StartProcessTool(),
        StopProcessTool(),
        GetProcessesTool(),
        ManageProcessTool(),
        # System
        GetSystemInfoTool(),
        GetCpuUsageTool(),
        GetMemoryUsageTool(),
        GetDiskUsageTool(),
        GetEnvironmentTool(),
        # Network
        HttpRequestTool(),
        DownloadFileTool(),
        InspectUrlTool(),
        DuckDuckGoSearchTool(),
        # Swarm Mesh & Deliberation
        SwarmDispatchTool(),
        SubagentSendMessageTool(),
        SubagentBroadcastTool(),
        SubagentReadInboxTool(),
        SubagentShareSkillTool(),
        SubagentListPeersTool(),
        SubagentProposeTool(),
        SubagentVoteTool(),
        SubagentConsensusTool(),
        # Dynamic Tool Synthesis & Self-Repair
        CreateDynamicTool(),
        RepairDynamicTool(),
        ListDynamicTools(),
        DeleteDynamicTool(),
        # Git
        GitStatusTool(),
        GitDiffTool(),
        GitLogTool(),
        GitBranchTool(),
        GitCheckoutTool(),
        GitCommitTool(),
        GitMergeTool(),
        # Developer
        RunTestsTool(),
        RunFormatterTool(),
        RunLinterTool(),
        InstallDependenciesTool(),
        # Project
        InspectProjectTool(),
        DetectLanguageTool(),
        DetectPackageManagerTool(),
        DetectFrameworkTool(),
        RunProjectTool(),
        BuildProjectTool(),
        # Computer Use
        ComputerScreenshotTool(),
        ComputerMouseTool(),
        ComputerKeyboardTool(),
        ComputerWindowTool(),
        WindowsAppTool(),
        BrowserMediaTool(),
        ComputerActTool(),
        NiteePlannerTool(),
        KineticActTool(),
        ClipboardTool(),
        SystemInfoTool(),
        # Skills
        CreateSkillTool(),
        ImproveSkillTool(),
        ListSkillsTool(),
        # Interactive
        AskUserTool(),
        CreatePlanTool(),
        UpdatePlanStepTool(),
        # Fleet & SSH
        FleetNodesTool(),
        FleetExecTool(),
        FleetTransferTool(),
        FleetDeployTool(),
        FleetSpawnAgentTool(),
        FleetMeshTool(),
        # Cron & Automation
        ScheduleCronJobTool(),
        ListCronJobsTool(),
        DeleteCronJobTool(),
        RunCronJobNowTool(),
        GenerateReportTool(),
        SendEmailTool(),
        # Voice & Ollama & Model Providers
        ManageVoiceModelsTool(),
        OllamaModelTool(),
        ManageProvidersTool(),
        # Code Graph & Frontier Tools
        CodeImpactAnalysisTool(),
        SentinelTriageTool(),
        TechRadarTool(),
    ]

