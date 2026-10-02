"""
CORD LLM - Universal Multi-Provider Streaming Engine
Supports OpenAI-compatible endpoints (OpenRouter, DeepSeek, OpenAI, Ollama, Groq, Custom)
and Anthropic Messages API with SSE streaming, tool calls, and reasoning/thinking extraction.
"""

from __future__ import annotations
import json
import asyncio
from typing import AsyncGenerator, Dict, Any, List, Optional, Tuple, Callable
from dataclasses import dataclass, field
import httpx

from cord.core.config import CordConfig


@dataclass
class ToolCallDelta:
    index: int
    id: str = ""
    name: str = ""
    arguments: str = ""
    extra_content: Optional[Dict[str, Any]] = None


@dataclass
class StreamChunk:
    """Represents an atomic update emitted by the streaming engine."""
    text: str = ""
    thinking: str = ""
    tool_call_delta: Optional[ToolCallDelta] = None
    finish_reason: Optional[str] = None
    input_tokens: int = 0
    output_tokens: int = 0


@dataclass
class CompleteMessage:
    role: str = "assistant"
    content: str = ""
    thinking: str = ""
    tool_calls: List[Dict[str, Any]] = field(default_factory=list)
    usage: Dict[str, int] = field(default_factory=dict)


class LLMError(Exception):
    pass


class LLMAuthError(LLMError):
    pass


class ThoughtStreamFilter:
    """Filters incoming text chunks, extracting <thought> and <thinking> tags into thinking chunks."""
    def __init__(self):
        self.in_thought = False
        self.buffer = ""

    def process(self, chunk_text: str) -> List[Tuple[str, str]]:
        if not chunk_text:
            return []
        results = []
        self.buffer += chunk_text

        while self.buffer:
            if not self.in_thought:
                lower = self.buffer.lower()
                open_pos = -1
                tag_len = 0
                for tag in ("<thought>", "<thinking>", "<think>", "<reasoning>"):
                    pos = lower.find(tag)
                    if pos != -1 and (open_pos == -1 or pos < open_pos):
                        open_pos = pos
                        tag_len = len(tag)

                if open_pos != -1:
                    pre = self.buffer[:open_pos]
                    if pre:
                        results.append(("text", pre))
                    self.buffer = self.buffer[open_pos + tag_len:]
                    self.in_thought = True
                else:
                    partial = False
                    for tag in ("<thought>", "<thinking>", "<think>", "<reasoning>"):
                        for i in range(1, len(tag)):
                            if lower.endswith(tag[:i]):
                                partial = True
                                break
                        if partial:
                            break
                    if partial:
                        break
                    else:
                        results.append(("text", self.buffer))
                        self.buffer = ""
            else:
                lower = self.buffer.lower()
                close_pos = -1
                tag_len = 0
                for tag in ("</thought>", "</thinking>", "</think>", "</reasoning>"):
                    pos = lower.find(tag)
                    if pos != -1 and (close_pos == -1 or pos < close_pos):
                        close_pos = pos
                        tag_len = len(tag)

                if close_pos != -1:
                    thought_part = self.buffer[:close_pos]
                    if thought_part:
                        results.append(("thinking", thought_part))
                    self.buffer = self.buffer[close_pos + tag_len:]
                    self.in_thought = False
                else:
                    partial = False
                    for tag in ("</thought>", "</thinking>", "</think>", "</reasoning>"):
                        for i in range(1, len(tag)):
                            if lower.endswith(tag[:i]):
                                partial = True
                                break
                        if partial:
                            break
                    if partial:
                        break
                    else:
                        results.append(("thinking", self.buffer))
                        self.buffer = ""

        return results

    def flush(self) -> List[Tuple[str, str]]:
        if not self.buffer:
            return []
        kind = "thinking" if self.in_thought else "text"
        res = [(kind, self.buffer)]
        self.buffer = ""
        return res


def _format_http_error(status_code: int, url: str, raw_body: bytes) -> str:
    """Extracts a concise, human-readable error message without HTML tags."""
    decoded = raw_body.decode(errors="replace").strip()
    if not decoded:
        return f"HTTP Error {status_code} from {url}"

    # If response is HTML, do not dump raw HTML markup
    if "<!DOCTYPE" in decoded or "<html" in decoded.lower() or "404." in decoded:
        if status_code == 404:
            return (
                f"Endpoint Not Found (404) at {url}.\n"
                f"   The endpoint path '/chat/completions' does not exist on this host.\n"
                f"   Please verify your base_url configuration in /settings."
            )
        return f"HTTP {status_code} Error: Received HTML error page from {url}. Check endpoint in /settings."

    # Try parsing JSON error
    try:
        data = json.loads(decoded)
        if isinstance(data, dict):
            err = data.get("error")
            if isinstance(err, dict):
                msg = err.get("message") or err.get("code") or str(err)
                return f"API Error {status_code}: {msg}"
            elif err:
                return f"API Error {status_code}: {err}"
            elif "message" in data:
                return f"API Error {status_code}: {data['message']}"
    except Exception:
        pass

    if len(decoded) > 200:
        decoded = decoded[:200] + "..."
    return f"API Error {status_code}: {decoded}"


class LLMClient:
    """Universal async streaming LLM client."""

    def __init__(self, config: CordConfig):
        self.config = config

    async def stream_chat(
        self,
        messages: List[Dict[str, Any]],
        tools: Optional[List[Dict[str, Any]]] = None,
        system_prompt: Optional[str] = None,
    ) -> AsyncGenerator[StreamChunk, None]:
        """Streams chat completion tokens and tool calls from configured provider."""
        if self.config.api_format == "anthropic":
            async for chunk in self._stream_anthropic(messages, tools, system_prompt):
                yield chunk
        else:
            async for chunk in self._stream_openai_compatible(messages, tools, system_prompt):
                yield chunk

    async def _stream_openai_compatible(
        self,
        messages: List[Dict[str, Any]],
        tools: Optional[List[Dict[str, Any]]] = None,
        system_prompt: Optional[str] = None,
    ) -> AsyncGenerator[StreamChunk, None]:
        """Handles OpenAI / OpenRouter / DeepSeek / Gemini / Ollama SSE streaming."""
        base_url = self.config.base_url.strip().rstrip("/")
        # Auto-correct common Google/Gemini URL typos
        if "googleapis.com" in base_url and "generativelanguage" not in base_url:
            base_url = "https://generativelanguage.googleapis.com/v1beta/openai"

        # Robustly strip redundant trailing path segments if user entered them in base_url
        if base_url.endswith("/chat/completions"):
            base_url = base_url[:-17].rstrip("/")
        elif base_url.endswith("/chat"):
            base_url = base_url[:-5].rstrip("/")

        url = f"{base_url}/chat/completions"

        api_key = self.config.api_key or ("ollama" if ("11434" in base_url or self.config.provider == "ollama") else "")
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}",
        }
        # Extra headers (e.g. OpenRouter site info)
        if "openrouter" in self.config.base_url:
            headers["HTTP-Referer"] = "https://github.com/cord-cli"
            headers["X-Title"] = "CORD Autonomous Coding Agent"
        if self.config.extra_headers:
            headers.update(self.config.extra_headers)

        formatted_messages: List[Dict[str, Any]] = []
        if system_prompt:
            formatted_messages.append({"role": "system", "content": system_prompt})
        formatted_messages.extend(messages)

        model_name = self.config.model.lower()
        is_reasoning_model = any(k in model_name for k in ("o1", "o3", "r1", "thinking", "qwq", "reasoner"))
        is_vision_model = any(v in model_name for v in ("vision", "4o", "gemini", "claude-3"))

        # Sanitize messages for text-only models that reject multimodal image_url (e.g. Nemotron on NVIDIA)
        if not is_vision_model:
            cleaned_messages = []
            for m in formatted_messages:
                content = m.get("content")
                if isinstance(content, list):
                    text_parts = [p.get("text", "") for p in content if isinstance(p, dict) and p.get("type") == "text"]
                    cleaned_m = dict(m)
                    cleaned_m["content"] = " ".join(text_parts) if text_parts else "[Screenshot omitted for text model]"
                    cleaned_messages.append(cleaned_m)
                else:
                    cleaned_messages.append(m)
            formatted_messages = cleaned_messages

        target_model = self.config.model
        if "nvidia" in base_url or getattr(self.config, "provider", "") == "nvidia":
            if "glm-5-3" in target_model:
                target_model = target_model.replace("glm-5-3", "glm-5.3")

        payload: Dict[str, Any] = {
            "model": target_model,
            "messages": formatted_messages,
            "stream": True,
        }

        # Temperature handling: OpenAI o1/o3-mini do not allow custom temperature
        if not ("o1" in model_name or "o3" in model_name):
            payload["temperature"] = self.config.temperature

        # Max tokens allocation: support max_completion_tokens for o1/o3
        if "o1" in model_name or "o3" in model_name:
            payload["max_completion_tokens"] = self.config.max_tokens
        else:
            payload["max_tokens"] = self.config.max_tokens

        # Deep thinking & reasoning effort parameters
        if getattr(self.config, "always_think", True):
            effort = getattr(self.config, "reasoning_effort", "high")
            if is_reasoning_model or "openrouter" in self.config.base_url:
                payload["reasoning_effort"] = effort
                if "openrouter" in self.config.base_url:
                    payload["include_reasoning"] = True
                    payload["reasoning"] = {"effort": effort}

        # Include tools if provided
        if tools:
            payload["tools"] = [
                {"type": "function", "function": t} for t in tools
            ]
            payload["tool_choice"] = "auto"

        # Responsive timeout: fast connect and 25s read limit to avoid multi-minute freezes
        timeout = httpx.Timeout(connect=10.0, read=25.0, write=20.0, pool=15.0)
        limits = httpx.Limits(max_keepalive_connections=10, max_connections=20, keepalive_expiry=30.0)
        max_retries = 4

        for attempt in range(max_retries + 1):
            yielded_any = False
            thought_filter = ThoughtStreamFilter()
            tool_id_to_idx: Dict[str, int] = {}
            try:
                async with httpx.AsyncClient(timeout=timeout, limits=limits) as client:
                    async with client.stream("POST", url, headers=headers, json=payload) as response:
                        if response.status_code == 401:
                            raise LLMAuthError("Invalid API Key! Please verify your key in /settings.")
                        elif response.status_code in (429, 500, 502, 503, 504) and attempt < max_retries:
                            # Reconnection retry on the SAME MODEL with backoff
                            backoff = min(2.5 * (attempt + 1), 15.0)
                            from cord.ui.console import ui
                            if response.status_code == 429:
                                ui.print_warning(
                                    f"\n⚠️  Rate limit (HTTP 429) on '{target_model}'.\n"
                                    f"🔄 Reconnecting to '{target_model}' in {backoff:.1f}s (Attempt {attempt + 1}/{max_retries})...\n"
                                )
                            else:
                                ui.print_warning(
                                    f"\n⚠️  Server hiccup (HTTP {response.status_code}) on '{target_model}'.\n"
                                    f"🔄 Reconnecting to '{target_model}' in {backoff:.1f}s (Attempt {attempt + 1}/{max_retries})...\n"
                                )
                            await asyncio.sleep(backoff)
                            continue
                        elif response.status_code == 429:
                            error_body = await response.aread()
                            err_msg = _format_http_error(response.status_code, url, error_body)
                            raise LLMError(
                                f"API Rate Limit or Quota Exceeded (HTTP 429):\n{err_msg}\n"
                                f"💡 Tip: If using free models on OpenRouter, wait a few moments or upgrade tier."
                            )
                        elif response.status_code == 404:
                            error_body = await response.aread()
                            err_msg = _format_http_error(response.status_code, url, error_body)
                            raise LLMError(
                                f"Model Not Found (HTTP 404):\n{err_msg}\n"
                                f"💡 Tip: The model '{self.config.model}' may not exist on this endpoint. Switch using /model."
                            )
                        elif response.status_code != 200:
                            error_body = await response.aread()
                            err_msg = _format_http_error(response.status_code, url, error_body)
                            raise LLMError(err_msg)

                        async for line in response.aiter_lines():
                            if not line:
                                continue
                            line = line.strip()
                            if line.startswith("data: "):
                                data_str = line[6:].strip()
                                if data_str == "[DONE]":
                                    for kind, val in thought_filter.flush():
                                        if kind == "thinking":
                                            yield StreamChunk(thinking=val)
                                        else:
                                            yield StreamChunk(text=val)
                                    return
                                try:
                                    data = json.loads(data_str)
                                except json.JSONDecodeError:
                                    continue

                                choices = data.get("choices", [])
                                if not choices:
                                    # Check for usage info in last chunk
                                    usage = data.get("usage")
                                    if usage:
                                        yield StreamChunk(
                                            input_tokens=usage.get("prompt_tokens", 0),
                                            output_tokens=usage.get("completion_tokens", 0),
                                        )
                                    continue

                                delta = choices[0].get("delta", {})
                                finish_reason = choices[0].get("finish_reason")

                                # 1. Native Reasoning content (DeepSeek R1 / OpenAI reasoning deltas)
                                reasoning = delta.get("reasoning_content") or delta.get("reasoning")
                                if reasoning:
                                    yield StreamChunk(thinking=reasoning)
                                    yielded_any = True

                                # 2. Text content filtered through ThoughtStreamFilter
                                content = delta.get("content")
                                if not content and "text" in delta:
                                    content = delta.get("text")
                                if not content and "text" in choices[0]:
                                    content = choices[0].get("text")
                                if not content and "message" in choices[0]:
                                    content = choices[0]["message"].get("content")

                                if isinstance(content, list):
                                    text_parts = [
                                        p.get("text", "") if isinstance(p, dict) else str(p)
                                        for p in content
                                    ]
                                    content = "".join(text_parts)
                                elif isinstance(content, dict):
                                    content = content.get("text", "")

                                if content:
                                    for kind, val in thought_filter.process(str(content)):
                                        if kind == "thinking":
                                            yield StreamChunk(thinking=val)
                                        else:
                                            yield StreamChunk(text=val)
                                    yielded_any = True

                                # 3. Tool call deltas
                                tool_calls = delta.get("tool_calls")
                                if tool_calls:
                                    for tc in tool_calls:
                                        raw_idx = tc.get("index")
                                        call_id = tc.get("id", "") or ""
                                        fn = tc.get("function", {})
                                        name = fn.get("name", "")
                                        args = fn.get("arguments", "")
                                        extra_cnt = tc.get("extra_content")

                                        # Map call_id to a stable unique index across chunks
                                        if call_id:
                                            if call_id not in tool_id_to_idx:
                                                if raw_idx is not None and raw_idx not in tool_id_to_idx.values():
                                                    tool_id_to_idx[call_id] = raw_idx
                                                else:
                                                    tool_id_to_idx[call_id] = len(tool_id_to_idx)
                                            idx = tool_id_to_idx[call_id]
                                        elif raw_idx is not None:
                                            idx = raw_idx
                                        else:
                                            idx = 0

                                        yield StreamChunk(
                                            tool_call_delta=ToolCallDelta(
                                                index=idx,
                                                id=call_id,
                                                name=name,
                                                arguments=args,
                                                extra_content=extra_cnt,
                                            )
                                        )
                                        yielded_any = True

                                if finish_reason:
                                    yield StreamChunk(finish_reason=finish_reason)

                        # Guarantee flush of any buffered thought or text when connection ends
                        for kind, val in thought_filter.flush():
                            if kind == "thinking":
                                yield StreamChunk(thinking=val)
                            else:
                                yield StreamChunk(text=val)
                        return
            except (LLMAuthError, LLMError):
                raise
            except httpx.TimeoutException:
                if attempt < max_retries and not yielded_any:
                    backoff = min(2.0 * (attempt + 1), 10.0)
                    from cord.ui.console import ui
                    ui.print_warning(
                        f"\n⚠️  Request timed out connecting to {url} ({self.config.model}).\n"
                        f"🔄 Reconnecting to '{self.config.model}' in {backoff:.1f}s (Attempt {attempt + 1}/{max_retries})...\n"
                    )
                    await asyncio.sleep(backoff)
                    continue
                raise LLMError(
                    f"Request timed out connecting to {url} ({self.config.model})."
                )
            except (httpx.RequestError, httpx.RemoteProtocolError, Exception) as e:
                if yielded_any:
                    from cord.ui.console import ui
                    ui.print_warning(f"Connection stream closed: {e}")
                    return
                if attempt < max_retries:
                    backoff = min(2.0 * (attempt + 1), 10.0)
                    from cord.ui.console import ui
                    ui.print_warning(
                        f"\n⚠️  Network glitch connecting to {url} ({self.config.model}): {e}\n"
                        f"🔄 Reconnecting in {backoff:.1f}s (Attempt {attempt + 1}/{max_retries})...\n"
                    )
                    await asyncio.sleep(backoff)
                    continue
                raise LLMError(f"Network error connecting to {url}: {e}")

    async def _stream_anthropic(
        self,
        messages: List[Dict[str, Any]],
        tools: Optional[List[Dict[str, Any]]] = None,
        system_prompt: Optional[str] = None,
    ) -> AsyncGenerator[StreamChunk, None]:
        """Handles Anthropic native /v1/messages SSE streaming."""
        base_url = self.config.base_url.rstrip("/")
        # Strip redundant trailing /messages if user entered the full endpoint URL
        if base_url.endswith("/messages"):
            base_url = base_url[:-9].rstrip("/")
        url = f"{base_url}/messages"

        headers = {
            "Content-Type": "application/json",
            "x-api-key": self.config.api_key,
            "anthropic-version": "2023-06-01",
        }
        if self.config.extra_headers:
            headers.update(self.config.extra_headers)

        payload: Dict[str, Any] = {
            "model": self.config.model,
            "messages": messages,
            "max_tokens": self.config.max_tokens,
            "stream": True,
        }

        # Anthropic Claude 3.7 Sonnet thinking configuration
        if getattr(self.config, "always_think", True) and ("claude-3-7" in self.config.model.lower() or "thinking" in self.config.model.lower()):
            budget = min(getattr(self.config, "thinking_budget", 16000), self.config.max_tokens - 1000)
            if budget >= 1024:
                payload["thinking"] = {
                    "type": "enabled",
                    "budget_tokens": budget,
                }
                payload["temperature"] = 1.0
            else:
                payload["temperature"] = self.config.temperature
        else:
            payload["temperature"] = self.config.temperature

        if system_prompt:
            payload["system"] = system_prompt

        if tools:
            payload["tools"] = [
                {
                    "name": t["name"],
                    "description": t.get("description", ""),
                    "input_schema": t.get("parameters", {"type": "object", "properties": {}}),
                }
                for t in tools
            ]

        timeout = httpx.Timeout(connect=25.0, read=180.0, write=30.0, pool=30.0)
        limits = httpx.Limits(max_keepalive_connections=5, max_connections=10, keepalive_expiry=30.0)

        max_retries = 3
        attempt = 0
        yielded_any = False

        while attempt < max_retries:
            attempt += 1
            thought_filter = ThoughtStreamFilter()
            try:
                async with httpx.AsyncClient(timeout=timeout, limits=limits) as client:
                    async with client.stream("POST", url, headers=headers, json=payload) as response:
                        if response.status_code == 401:
                            raise LLMAuthError("Invalid Anthropic API Key! Check /settings.")
                        elif response.status_code in (429, 500, 502, 503, 504):
                            err = await response.aread()
                            if attempt < max_retries:
                                delay = 1.5 * (2 ** (attempt - 1))
                                from cord.ui.console import ui
                                ui.print_warning(
                                    f"Anthropic API busy/error ({response.status_code}). Retrying in {delay:.1f}s (Attempt {attempt}/{max_retries})..."
                                )
                                await asyncio.sleep(delay)
                                continue
                            raise LLMError(f"Anthropic API Error {response.status_code}: {err.decode(errors='replace')}")
                        elif response.status_code != 200:
                            err = await response.aread()
                            raise LLMError(f"Anthropic API Error {response.status_code}: {err.decode(errors='replace')}")

                        current_tool_index = 0
                        async for line in response.aiter_lines():
                            if not line or not line.startswith("data: "):
                                continue
                            data_str = line[6:].strip()
                            try:
                                event = json.loads(data_str)
                            except json.JSONDecodeError:
                                continue

                            event_type = event.get("type")
                            if event_type == "content_block_start":
                                cb = event.get("content_block", {})
                                if cb.get("type") == "tool_use":
                                    current_tool_index = event.get("index", 0)
                                    yield StreamChunk(
                                        tool_call_delta=ToolCallDelta(
                                            index=current_tool_index,
                                            id=cb.get("id", ""),
                                            name=cb.get("name", ""),
                                            arguments="",
                                        )
                                    )
                                    yielded_any = True
                            elif event_type == "content_block_delta":
                                delta = event.get("delta", {})
                                dtype = delta.get("type")
                                if dtype == "text_delta":
                                    raw_txt = delta.get("text", "")
                                    for kind, val in thought_filter.process(raw_txt):
                                        if kind == "thinking":
                                            yield StreamChunk(thinking=val)
                                        else:
                                            yield StreamChunk(text=val)
                                    yielded_any = True
                                elif dtype == "thinking_delta":
                                    yield StreamChunk(thinking=delta.get("thinking", ""))
                                    yielded_any = True
                                elif dtype == "input_json_delta":
                                    yield StreamChunk(
                                        tool_call_delta=ToolCallDelta(
                                            index=current_tool_index,
                                            arguments=delta.get("partial_json", ""),
                                        )
                                    )
                                    yielded_any = True
                            elif event_type == "message_stop":
                                for kind, val in thought_filter.flush():
                                    if kind == "thinking":
                                        yield StreamChunk(thinking=val)
                                    else:
                                        yield StreamChunk(text=val)
                            elif event_type == "message_delta":
                                usage = event.get("usage", {})
                                if usage:
                                    yield StreamChunk(output_tokens=usage.get("output_tokens", 0))
                            elif event_type == "message_start":
                                usage = event.get("message", {}).get("usage", {})
                                if usage:
                                    yield StreamChunk(input_tokens=usage.get("input_tokens", 0))
                return
            except LLMAuthError:
                raise
            except (httpx.RequestError, httpx.RemoteProtocolError, Exception) as e:
                if yielded_any:
                    from cord.ui.console import ui
                    ui.print_warning(f"Connection stream closed: {e}")
                    return
                if attempt < max_retries:
                    delay = 1.5 * (2 ** (attempt - 1))
                    from cord.ui.console import ui
                    ui.print_warning(
                        f"Network hiccup with Anthropic. Retrying in {delay:.1f}s (Attempt {attempt}/{max_retries})..."
                    )
                    await asyncio.sleep(delay)
                else:
                    raise LLMError(f"Network error communicating with Anthropic API: {e}")

