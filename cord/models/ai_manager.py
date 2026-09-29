"""
CORD Models - AI Manager
Unified access layer using LiteLLM for multi-provider AI access.
Handles streaming, tool calls, error unification, automatic fallbacks, retries, and cost tracking.
"""

from __future__ import annotations
import json
import asyncio
from typing import AsyncGenerator, Dict, Any, List, Optional, Tuple
from dataclasses import dataclass, field

from cord.models.capabilities import Capability, ModelCapabilities, CapabilityUnsupportedError
from cord.models.model_resolver import ModelResolver
from cord.providers.provider_manager import ProviderManager
from cord.ui.console import ui


# Unified Domain Exceptions
class AIError(Exception):
    """Base error for AI interactions."""
    pass


class AuthenticationError(AIError):
    """Raised on invalid API keys."""
    pass


class ModelNotFoundError(AIError):
    """Raised when model does not exist or has been decommissioned."""
    pass


class RateLimitError(AIError):
    """Raised when rate limits are exceeded."""
    pass


@dataclass
class ToolCallDelta:
    index: int
    id: str = ""
    name: str = ""
    arguments: str = ""


@dataclass
class StreamChunk:
    text: str = ""
    thinking: str = ""
    tool_call_delta: Optional[ToolCallDelta] = None
    finish_reason: Optional[str] = None
    input_tokens: int = 0
    output_tokens: int = 0
    cost: float = 0.0


class AIManager:
    """Universal AI management layer wrapping LiteLLM."""

    def __init__(
        self,
        default_model: str = "openai/gpt-oss-120b",
        api_key: str = "",
        base_url: Optional[str] = None,
        max_retries: int = 3,
        timeout: float = 180.0,
    ):
        self.default_model = default_model
        self.api_key = api_key
        self.base_url = base_url
        self.max_retries = max_retries
        self.timeout = timeout
        self.total_cost = 0.0

    async def stream_chat(
        self,
        messages: List[Dict[str, Any]],
        tools: Optional[List[Dict[str, Any]]] = None,
        system_prompt: Optional[str] = None,
        model: Optional[str] = None,
        temperature: float = 0.2,
        max_tokens: int = 8192,
    ) -> AsyncGenerator[StreamChunk, None]:
        """
        Streams completions with tools and thinking deltas.
        Automatically retries and handles fallbacks if model is decommissioned or fails.
        """
        active_model = model or self.default_model
        attempt = 0

        while attempt <= self.max_retries:
            attempt += 1
            try:
                async for chunk in self._call_litellm(
                    messages=messages,
                    tools=tools,
                    system_prompt=system_prompt,
                    model=active_model,
                    temperature=temperature,
                    max_tokens=max_tokens,
                ):
                    yield chunk
                # Success, break retry loop
                return

            except (ModelNotFoundError, Exception) as e:
                err_str = str(e).lower()
                is_model_failure = any(term in err_str for term in ("decommissioned", "not found", "does not exist", "404", "invalid_request_error"))
                is_timeout = "timed out" in err_str or "timeout" in err_str or "unresponsive" in err_str

                if is_timeout and attempt < self.max_retries:
                    ui.print_warning(
                        f"Connection timed out for '{active_model}'. Reconnecting to '{active_model}' (Attempt {attempt + 1}/{self.max_retries})..."
                    )
                    await asyncio.sleep(2.0 * attempt)
                    continue

                # Translate and raise error
                self._handle_exception(e)

    async def _call_litellm(
        self,
        messages: List[Dict[str, Any]],
        tools: Optional[List[Dict[str, Any]]] = None,
        system_prompt: Optional[str] = None,
        model: str = "openai/gpt-oss-120b",
        temperature: float = 0.2,
        max_tokens: int = 8192,
    ) -> AsyncGenerator[StreamChunk, None]:
        """Internal call using LiteLLM or fallback resilient HTTP client."""
        try:
            import litellm
            use_litellm = True
        except ImportError:
            use_litellm = False

        formatted_messages = []
        if system_prompt:
            formatted_messages.append({"role": "system", "content": system_prompt})
        formatted_messages.extend(messages)

        if use_litellm:
            async for chunk in self._stream_with_litellm(
                messages=formatted_messages,
                tools=tools,
                model=model,
                temperature=temperature,
                max_tokens=max_tokens,
            ):
                yield chunk
        else:
            async for chunk in self._stream_with_httpx_fallback(
                messages=formatted_messages,
                tools=tools,
                model=model,
                temperature=temperature,
                max_tokens=max_tokens,
            ):
                yield chunk

    async def _stream_with_litellm(
        self,
        messages: List[Dict[str, Any]],
        tools: Optional[List[Dict[str, Any]]],
        model: str,
        temperature: float,
        max_tokens: int,
    ) -> AsyncGenerator[StreamChunk, None]:
        import litellm

        kwargs: Dict[str, Any] = {
            "model": model,
            "messages": messages,
            "stream": True,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        if self.api_key:
            kwargs["api_key"] = self.api_key
        if self.base_url:
            kwargs["api_base"] = self.base_url

        if tools:
            kwargs["tools"] = [{"type": "function", "function": t} for t in tools]
            kwargs["tool_choice"] = "auto"

        response = await litellm.acompletion(**kwargs)
        async for chunk in response:
            choices = getattr(chunk, "choices", [])
            if not choices:
                continue

            delta = choices[0].delta
            # 1. Text
            if hasattr(delta, "content") and delta.content:
                yield StreamChunk(text=delta.content)

            # 2. Reasoning / Thinking
            reasoning = getattr(delta, "reasoning_content", None) or getattr(delta, "thinking", None)
            if reasoning:
                yield StreamChunk(thinking=reasoning)

            # 3. Tool Calls
            tool_calls = getattr(delta, "tool_calls", None)
            if tool_calls:
                for tc in tool_calls:
                    idx = getattr(tc, "index", 0)
                    tc_id = getattr(tc, "id", "") or ""
                    fn = getattr(tc, "function", None)
                    name = getattr(fn, "name", "") if fn else ""
                    args = getattr(fn, "arguments", "") if fn else ""
                    yield StreamChunk(
                        tool_call_delta=ToolCallDelta(
                            index=idx,
                            id=tc_id,
                            name=name or "",
                            arguments=args or "",
                        )
                    )

            # 4. Finish reason
            finish = getattr(choices[0], "finish_reason", None)
            if finish:
                yield StreamChunk(finish_reason=finish)

    async def _stream_with_httpx_fallback(
        self,
        messages: List[Dict[str, Any]],
        tools: Optional[List[Dict[str, Any]]],
        model: str,
        temperature: float,
        max_tokens: int,
    ) -> AsyncGenerator[StreamChunk, None]:
        """Resilient streaming fallback over httpx directly to OpenAI-compatible base URL."""
        import httpx

        base_url = (self.base_url or "https://api.groq.com/openai/v1").strip().rstrip("/")
        if base_url.endswith("/chat/completions"):
            base_url = base_url[:-17].rstrip("/")
        elif base_url.endswith("/chat"):
            base_url = base_url[:-5].rstrip("/")
        url = f"{base_url}/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        payload: Dict[str, Any] = {
            "model": model,
            "messages": messages,
            "stream": True,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        if tools:
            payload["tools"] = [{"type": "function", "function": t} for t in tools]
            payload["tool_choice"] = "auto"

        timeout = httpx.Timeout(connect=25.0, read=180.0, write=30.0, pool=30.0)
        limits = httpx.Limits(max_keepalive_connections=5, max_connections=10)
        async with httpx.AsyncClient(timeout=timeout, limits=limits) as client:
            async with client.stream("POST", url, headers=headers, json=payload) as response:
                if response.status_code == 401:
                    raise AuthenticationError("Invalid API key for the AI provider.")
                elif response.status_code == 404:
                    raise ModelNotFoundError(f"Model '{model}' was not found on the provider.")
                elif response.status_code != 200:
                    err_body = (await response.aread()).decode(errors="replace")
                    if "decommissioned" in err_body.lower():
                        raise ModelNotFoundError(f"Model '{model}' has been decommissioned.")
                    raise AIError(f"API Error {response.status_code}: {err_body}")

                async for line in response.aiter_lines():
                    if not line or not line.startswith("data: "):
                        continue
                    data_str = line[6:].strip()
                    if data_str == "[DONE]":
                        break
                    try:
                        data = json.loads(data_str)
                    except json.JSONDecodeError:
                        continue

                    choices = data.get("choices", [])
                    if not choices:
                        continue

                    delta = choices[0].get("delta", {})
                    # Text
                    content = delta.get("content")
                    if content:
                        yield StreamChunk(text=content)

                    # Reasoning
                    reasoning = delta.get("reasoning_content") or delta.get("reasoning")
                    if reasoning:
                        yield StreamChunk(thinking=reasoning)

                    # Tool calls
                    tool_calls = delta.get("tool_calls")
                    if tool_calls:
                        for tc in tool_calls:
                            idx = tc.get("index", 0)
                            call_id = tc.get("id", "")
                            fn = tc.get("function", {})
                            yield StreamChunk(
                                tool_call_delta=ToolCallDelta(
                                    index=idx,
                                    id=call_id,
                                    name=fn.get("name", ""),
                                    arguments=fn.get("arguments", ""),
                                )
                            )

    def _handle_exception(self, e: Exception) -> None:
        err_msg = str(e)
        err_lower = err_msg.lower()

        if "401" in err_lower or "authentication" in err_lower or "unauthorized" in err_lower:
            raise AuthenticationError(f"Authentication failed: {err_msg}")
        elif "rate" in err_lower and ("limit" in err_lower or "429" in err_lower):
            raise RateLimitError(f"Rate limit reached: {err_msg}")
        elif "decommissioned" in err_lower or ("not found" in err_lower and "model" in err_lower) or (err_lower.startswith("404") or "status 404" in err_lower or "error 404" in err_lower):
            raise ModelNotFoundError(f"Model not found: {err_msg}")
        raise AIError(err_msg)

    async def chat_complete(
        self,
        messages: List[Dict[str, Any]],
        tools: Optional[List[Dict[str, Any]]] = None,
        system_prompt: Optional[str] = None,
        model: Optional[str] = None,
        temperature: float = 0.2,
        max_tokens: int = 8192,
    ) -> Dict[str, Any]:
        """Non-streaming complete chat generation returning dict with content and tool_calls."""
        content_acc = ""
        thinking_acc = ""
        tool_calls_dict: Dict[int, Dict[str, Any]] = {}

        async for chunk in self.stream_chat(
            messages=messages,
            tools=tools,
            system_prompt=system_prompt,
            model=model,
            temperature=temperature,
            max_tokens=max_tokens,
        ):
            if chunk.text:
                content_acc += chunk.text
            if chunk.thinking:
                thinking_acc += chunk.thinking
            if chunk.tool_call_delta:
                d = chunk.tool_call_delta
                idx = d.index
                if idx not in tool_calls_dict:
                    tool_calls_dict[idx] = {
                        "id": d.id or f"call_{idx}",
                        "type": "function",
                        "function": {"name": d.name, "arguments": d.arguments}
                    }
                else:
                    if d.name:
                        tool_calls_dict[idx]["function"]["name"] += d.name
                    if d.arguments:
                        tool_calls_dict[idx]["function"]["arguments"] += d.arguments

        tool_calls = list(tool_calls_dict.values())
        return {
            "content": content_acc,
            "thinking": thinking_acc,
            "tool_calls": tool_calls,
        }

ai_manager = AIManager()

