"""CORD Network Tools Package"""
from cord.tools.network.http_request import HttpRequestTool
from cord.tools.network.download_file import DownloadFileTool
from cord.tools.network.inspect_url import InspectUrlTool
from cord.tools.network.duckduckgo_search import DuckDuckGoSearchTool

NETWORK_TOOLS = [
    HttpRequestTool(),
    DownloadFileTool(),
    InspectUrlTool(),
    DuckDuckGoSearchTool(),
]
