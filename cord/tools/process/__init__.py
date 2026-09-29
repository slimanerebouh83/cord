"""CORD Process Tools Package"""
from cord.tools.process.start_process import StartProcessTool
from cord.tools.process.stop_process import StopProcessTool
from cord.tools.process.get_processes import GetProcessesTool

PROCESS_TOOLS = [
    StartProcessTool(),
    StopProcessTool(),
    GetProcessesTool(),
]
