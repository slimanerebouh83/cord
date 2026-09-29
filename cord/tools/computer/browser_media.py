"""
CORD Tool - browser_media
Direct YouTube searching, video launching, web search, and media playback control.
"""

from __future__ import annotations
import os
import sys
import time
import urllib.parse
import webbrowser
import ctypes
from typing import Optional

from cord.tools.base import BaseTool, ToolResult
from cord.permissions.levels import PermissionLevel, RiskLevel
from cord.vision.safety import computer_safety

# Windows Virtual Key Codes for Media and Control
VK_VOLUME_MUTE = 0xAD
VK_VOLUME_DOWN = 0xAE
VK_VOLUME_UP = 0xAF
VK_MEDIA_NEXT_TRACK = 0xB0
VK_MEDIA_PREV_TRACK = 0xB1
VK_MEDIA_PLAY_PAUSE = 0xB3

KEY_MAP = {
    "play_pause": VK_MEDIA_PLAY_PAUSE,
    "pause": VK_MEDIA_PLAY_PAUSE,
    "play": VK_MEDIA_PLAY_PAUSE,
    "mute": VK_VOLUME_MUTE,
    "volume_up": VK_VOLUME_UP,
    "volume_down": VK_VOLUME_DOWN,
    "next": VK_MEDIA_NEXT_TRACK,
    "prev": VK_MEDIA_PREV_TRACK,
    "fullscreen": 0x46,   # 'F' key
    "seek_fwd": 0x4C,     # 'L' key (YouTube 10s forward)
    "seek_back": 0x4A,    # 'J' key (YouTube 10s backward)
    "toggle_subtitles": 0x43, # 'C' key (YouTube subtitles)
}


class BrowserMediaTool(BaseTool):
    name = "browser_media"
    description = (
        "Search and open YouTube videos, launch web searches, open URLs in the default browser, "
        "and control media playback (Play/Pause, Mute, Volume Up/Down, Fullscreen) on Windows."
    )
    required_permission = PermissionLevel.EXECUTE
    risk_level = RiskLevel.MEDIUM
    parameters = {
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "enum": ["search_youtube", "open_video", "web_search", "media_key", "open_url"],
                "description": "Action to perform: 'search_youtube', 'open_video', 'web_search', 'media_key', or 'open_url'."
            },
            "query": {
                "type": "string",
                "description": "Search query for YouTube or web search (e.g. 'Sankara YouTube', 'Python tutorial')."
            },
            "url": {
                "type": "string",
                "description": "Direct URL or video link to open (e.g. 'https://www.youtube.com/watch?v=...')."
            },
            "key": {
                "type": "string",
                "enum": [
                    "play_pause", "pause", "play", "mute", "volume_up", "volume_down",
                    "next", "prev", "fullscreen", "seek_fwd", "seek_back", "toggle_subtitles"
                ],
                "description": "Media command key to simulate (e.g. 'play_pause', 'fullscreen', 'volume_up', 'mute')."
            },
            "engine": {
                "type": "string",
                "enum": ["google", "youtube", "bing", "duckduckgo"],
                "description": "Search engine to use for web_search (defaults to 'google')."
            }
        },
        "required": ["action"]
    }

    async def execute(
        self,
        action: str,
        query: Optional[str] = None,
        url: Optional[str] = None,
        key: Optional[str] = None,
        engine: Optional[str] = "google",
        **kwargs
    ) -> ToolResult:
        allowed, reason = computer_safety.validate_action(action)
        if not allowed:
            return ToolResult(success=False, output="", error=f"Media action blocked: {reason}")

        try:
            if action == "search_youtube":
                q = (query or "").strip()
                if not q:
                    return ToolResult(success=False, output="", error="Query parameter is required for search_youtube.")
                
                encoded = urllib.parse.quote_plus(q)
                yt_url = f"https://www.youtube.com/results?search_query={encoded}"
                self._open_url_native(yt_url)
                return ToolResult(
                    success=True,
                    output=f"Opened YouTube search for '{q}' in default browser.\nURL: {yt_url}"
                )

            elif action in ("open_video", "open_url"):
                target = (url or query or "").strip()
                if not target:
                    return ToolResult(success=False, output="", error="URL is required for open_video/open_url.")
                if not (target.startswith("http://") or target.startswith("https://")):
                    target = f"https://{target}"
                self._open_url_native(target)
                return ToolResult(success=True, output=f"Launched URL in default browser: {target}")

            elif action == "web_search":
                q = (query or "").strip()
                if not q:
                    return ToolResult(success=False, output="", error="Query parameter is required for web_search.")
                
                encoded = urllib.parse.quote_plus(q)
                eng = (engine or "google").lower()
                if eng == "youtube":
                    search_url = f"https://www.youtube.com/results?search_query={encoded}"
                elif eng == "bing":
                    search_url = f"https://www.bing.com/search?q={encoded}"
                elif eng == "duckduckgo":
                    search_url = f"https://duckduckgo.com/?q={encoded}"
                else:
                    search_url = f"https://www.google.com/search?q={encoded}"

                self._open_url_native(search_url)
                return ToolResult(
                    success=True,
                    output=f"Opened {eng.capitalize()} search for '{q}' in default browser.\nURL: {search_url}"
                )

            elif action == "media_key":
                cmd = (key or "").strip().lower()
                if not cmd:
                    return ToolResult(success=False, output="", error="key parameter is required for media_key action.")
                
                vk_code = KEY_MAP.get(cmd)
                if vk_code is None:
                    return ToolResult(
                        success=False,
                        output="",
                        error=f"Unsupported media key '{cmd}'. Supported: {list(KEY_MAP.keys())}"
                    )

                if sys.platform != "win32":
                    return ToolResult(
                        success=False,
                        output="",
                        error="Hardware media keys simulation is only supported on Windows."
                    )

                # Send key down and key up via Windows user32
                ctypes.windll.user32.keybd_event(vk_code, 0, 0, 0)
                time.sleep(0.05)
                ctypes.windll.user32.keybd_event(vk_code, 0, 2, 0)

                return ToolResult(
                    success=True,
                    output=f"Simulated Windows media action: '{cmd}' (VK 0x{vk_code:02X})."
                )

            return ToolResult(success=False, output="", error=f"Unknown browser_media action: '{action}'")

        except Exception as e:
            return ToolResult(success=False, output="", error=f"Browser/Media action failed: {e}")

    def _open_url_native(self, url: str):
        """Opens URL via Windows ShellExecute (os.startfile) or fallback to webbrowser."""
        if sys.platform == "win32":
            try:
                os.startfile(url)
                return
            except Exception:
                pass
        webbrowser.open(url)
