"""CORD Tools - Keyless DuckDuckGo Web Search Tool"""
from __future__ import annotations
import re
import urllib.parse
from typing import Dict, Any, List
import httpx

from cord.tools.base import BaseTool, ToolResult, PermissionLevel, RiskLevel


class DuckDuckGoSearchTool(BaseTool):
    """Searches DuckDuckGo for live web information without an API key."""

    name = "duckduckgo_search"
    description = (
        "Search the web using DuckDuckGo to obtain up-to-date documentation, "
        "tutorials, software libraries, and general web information with zero API keys required."
    )
    required_permission = PermissionLevel.READ_ONLY
    risk_level = RiskLevel.LOW

    def get_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Search terms or question to look up"},
                "max_results": {"type": "integer", "description": "Maximum search results to return (default: 5)"},
            },
            "required": ["query"],
        }

    async def execute(self, query: str, max_results: int = 5, **kwargs: Any) -> ToolResult:
        if not query.strip():
            return ToolResult(output="Error: Empty search query provided.", success=False)

        max_results = min(max(max_results, 1), 15)
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Referer": "https://duckduckgo.com/",
        }

        url = "https://html.duckduckgo.com/html/"
        data = {"q": query}

        try:
            async with httpx.AsyncClient(timeout=12.0, follow_redirects=True) as client:
                resp = await client.post(url, data=data, headers=headers)
                if resp.status_code != 200:
                    return ToolResult(output=f"DuckDuckGo returned HTTP status {resp.status_code}", success=False)

                html = resp.text

            # Parse search results
            # Result blocks typically contain <a class="result__a" href="...">title</a>
            # and <a class="result__snippet" ...>snippet</a>
            raw_blocks = re.findall(
                r'<div[^>]*class="[^"]*result__body[^"]*"[^>]*>(.*?)</div>\s*</div>',
                html,
                re.DOTALL | re.IGNORECASE,
            )

            if not raw_blocks:
                # Fallback: search across all result__a tags
                raw_blocks = re.findall(
                    r'<a[^>]*class="[^"]*result__a[^"]*"[^>]*href="([^"]+)"[^>]*>(.*?)</a>',
                    html,
                    re.DOTALL | re.IGNORECASE,
                )

            results: List[Dict[str, str]] = []

            for block in raw_blocks:
                if len(results) >= max_results:
                    break

                if isinstance(block, tuple):
                    href, title_html = block
                    snippet_html = ""
                else:
                    # Extract title and href
                    a_match = re.search(r'<a[^>]*class="[^"]*result__a[^"]*"[^>]*href="([^"]+)"[^>]*>(.*?)</a>', block, re.DOTALL | re.IGNORECASE)
                    if not a_match:
                        continue
                    href = a_match.group(1)
                    title_html = a_match.group(2)

                    # Extract snippet
                    s_match = re.search(r'<a[^>]*class="[^"]*result__snippet[^"]*"[^>]*>(.*?)</a>', block, re.DOTALL | re.IGNORECASE)
                    snippet_html = s_match.group(1) if s_match else ""

                # Clean DuckDuckGo redirect URL
                clean_url = href
                if "uddg=" in href:
                    try:
                        parsed = urllib.parse.urlparse(href)
                        qs = urllib.parse.parse_qs(parsed.query)
                        if "uddg" in qs:
                            clean_url = qs["uddg"][0]
                    except Exception:
                        clean_url = href

                # Strip HTML tags
                clean_title = re.sub(r"<[^>]+>", "", title_html).strip()
                clean_snippet = re.sub(r"<[^>]+>", "", snippet_html).strip()

                if clean_title:
                    results.append({
                        "title": clean_title,
                        "url": clean_url,
                        "snippet": clean_snippet or "No snippet available",
                    })

            if not results:
                return ToolResult(
                    output=f"No results found on DuckDuckGo for query: '{query}'.",
                    success=True,
                )

            output_lines = [f"Found {len(results)} results for '{query}':\n"]
            for i, r in enumerate(results, 1):
                output_lines.append(f"{i}. {r['title']}")
                output_lines.append(f"   URL: {r['url']}")
                output_lines.append(f"   Snippet: {r['snippet']}\n")

            return ToolResult(output="\n".join(output_lines), success=True)

        except Exception as e:
            return ToolResult(output=f"DuckDuckGo search error: {e}", success=False)
