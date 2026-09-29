"""CORD System Tools Package"""
from cord.tools.system.system_info import GetSystemInfoTool
from cord.tools.system.cpu_usage import GetCpuUsageTool
from cord.tools.system.memory_usage import GetMemoryUsageTool
from cord.tools.system.disk_usage import GetDiskUsageTool
from cord.tools.system.environment import GetEnvironmentTool

SYSTEM_TOOLS = [
    GetSystemInfoTool(),
    GetCpuUsageTool(),
    GetMemoryUsageTool(),
    GetDiskUsageTool(),
    GetEnvironmentTool(),
]
