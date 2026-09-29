"""
CORD Tools - Web Documentation & API Fetcher
Allows the agent to read external documentation, API references, and web resources.
"""

from __future__ import annotations
import re
from typing import Optional
import httpx

from cord.tools.base import BaseTool, ToolResult
from cord.ui.console import ui


def html_to_markdown(html_content: str) -> str:
    """Converts basic HTML into clean markdown/text."""
    # Remove script and style elements
    text = re.sub(r"<(script|style).*?>.*?</\1>", "", html_content, flags=re.DOTALL | re.IGNORECASE)
    # Headings
    text = re.sub(r"<h1.*?>(.*?)</h1>", r"\n# \1\n", text, flags=re.IGNORECASE)
    text = re.sub(r"<h2.*?>(.*?)</h2>", r"\n## \1\n", text, flags=re.IGNORECASE)
    text = re.sub(r"<h3.*?>(.*?)</h3>", r"\n### \1\n", text, flags=re.IGNORECASE)
    # Paragraphs and breaks
    text = re.sub(r"<br\s*/?>", "\n", text, flags=re.IGNORECASE)
    text = re.sub(r"</p>", "\n\n", text, flags=re.IGNORECASE)
    # Pre / Code blocks
    text = re.sub(r"<pre><code>(.*?)</code></pre>", r"\n```\n\1\n```\n", text, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r"<code>(.*?)</code>", r"`\1`", text, flags=re.IGNORECASE)
    # Links
    text = re.sub(r'<a\s+[^>]*href="([^"]+)"[^>]*>(.*?)</a>', r"[\2](\1)", text, flags=re.IGNORECASE)
    # Strip remaining tags
    text = re.sub(r"<[^>]+>", " ", text)
    # Normalize excessive whitespaces
    text = re.sub(r"\n\s*\n\s*\n+", "\n\n", text)
    return text.strip()


class FetchWebPageTool(BaseTool):
    name = "fetch_web_page"
    description = "Fetch and read the content of a web page or documentation URL as clean markdown."
    parameters = {
        "type": "object",
        "properties": {
            "url": {
                "type": "string",
                "description": "Full HTTP or HTTPS URL to fetch.",
            },
            "max_length": {
                "type": "integer",
                "description": "Maximum characters to return (default: 8000).",
            },
        },
        "required": ["url"],
    }

    async def execute(self, url: str, max_length: int = 8000, **kwargs) -> ToolResult:
        if not url.startswith(("http://", "https://")):
            url = "https://" + url

        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36 CORD-CLI/1.0",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        }

        try:
            async with httpx.AsyncClient(timeout=15.0, follow_redirects=True) as client:
                resp = await client.get(url, headers=headers)
                if resp.status_code != 200:
                    return ToolResult(
                        success=False,
                        output="",
                        error=f"Failed to fetch {url}: HTTP status {resp.status_code}",
                    )

                raw_text = resp.text
                clean_text = html_to_markdown(raw_text)

                if len(clean_text) > max_length:
                    clean_text = clean_text[:max_length] + f"\n\n... [Truncated {len(clean_text) - max_length} characters]"

                header = f"--- Content of {url} ---\n\n"
                return ToolResult(success=True, output=header + clean_text)

        except Exception as e:
            return ToolResult(success=False, output="", error=f"Error fetching URL {url}: {e}")
