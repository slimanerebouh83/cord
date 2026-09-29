"""
CORD Core - Fallback Tool Call Parser
Recovers and parses tool invocations embedded as XML tags or JSON blocks in model text responses.
Ensures models that output XML tool calls (e.g. gemini-flash-lite, deepseek, qwen, or claude-style outputs)
execute their tools seamlessly instead of stalling or dumping raw XML text to the terminal.
"""

from __future__ import annotations
import re
import json
from typing import List, Dict, Any, Set, Union
import yaml


# Tags that are definitely reasoning or text, never actionable system tools
IGNORED_TAGS = {
    "thought", "thinking", "reasoning", "reflection", "analysis",
    "internal_thought", "observation", "plan_step", "thought_process"
}


def parse_fallback_tool_calls(
    text: str,
    known_tools: Union[Set[str], List[str], Dict[str, Any]]
) -> List[Dict[str, Any]]:
    """
    Parses tool calls from raw assistant text when native tool_calls are empty.
    
    Supports:
    1. Direct XML tags:
       <write_file>
       path: calculator.py
       content: |
           import tkinter as tk
       </write_file>

    2. Generic <tool_call> or <function_call> blocks with JSON/YAML inside.
    3. Markdown code blocks tagged with ```tool_call or ```function_call.
    """
    if not text:
        return []

    tool_names = set(known_tools.keys()) if isinstance(known_tools, dict) else set(known_tools)
    tool_calls: List[Dict[str, Any]] = []

    # 1. Match generic <tool_call>...</tool_call> or <function_call>...</function_call>
    generic_pattern = re.compile(
        r"<(?:tool_call|function_call|tool)>([\s\S]*?)<\/(?:tool_call|function_call|tool)>",
        re.IGNORECASE
    )
    for match in generic_pattern.finditer(text):
        raw_body = match.group(1).strip()
        data = None
        try:
            data = json.loads(raw_body)
        except Exception:
            try:
                data = yaml.safe_load(raw_body)
            except Exception:
                pass

        if isinstance(data, dict):
            fn_name = data.get("name") or data.get("tool") or data.get("function")
            raw_args = data.get("arguments") or data.get("args") or data.get("parameters") or {}
            if fn_name and fn_name in tool_names:
                args_str = json.dumps(raw_args, ensure_ascii=False) if isinstance(raw_args, dict) else str(raw_args)
                tool_calls.append({
                    "id": f"call_gen_{len(tool_calls)}",
                    "type": "function",
                    "function": {
                        "name": fn_name,
                        "arguments": args_str,
                    },
                })

    # 2. Match direct XML tags: <tool_name (attrs)?>body</tool_name>
    xml_pattern = re.compile(
        r"<([a-zA-Z0-9_-]+)(?:\s+([^>]*))?>([\s\S]*?)<\/\1>",
        re.IGNORECASE
    )
    for match in xml_pattern.finditer(text):
        tag_name = match.group(1).strip()
        attrs_str = match.group(2) or ""
        body = match.group(3).strip()

        tag_lower = tag_name.lower()
        if tag_lower in IGNORED_TAGS or tag_lower in ("tool_call", "function_call", "tool"):
            continue

        # Check if tag corresponds to a known registered tool
        matched_tool = None
        if tag_name in tool_names:
            matched_tool = tag_name
        elif tag_lower in tool_names:
            matched_tool = tag_lower
        else:
            # Check lowercase without underscores or hyphens
            for t in tool_names:
                if t.lower() == tag_lower or t.replace("_", "") == tag_lower.replace("_", ""):
                    matched_tool = t
                    break

        if not matched_tool:
            continue

        args: Dict[str, Any] = {}

        # Parse inline attributes like <write_file path="foo.py">
        if attrs_str:
            attr_matches = re.findall(r'([a-zA-Z0-9_-]+)=["\']([^"\']*)["\']', attrs_str)
            for k, v in attr_matches:
                args[k] = v

        # Parse body using PyYAML safe_load (handles both YAML and JSON)
        if body:
            parsed = None
            try:
                parsed = yaml.safe_load(body)
            except Exception:
                pass

            if isinstance(parsed, dict):
                args.update(parsed)
            elif isinstance(parsed, str) and parsed and not args:
                # Heuristic mapping for tools taking a single dominant string parameter
                if matched_tool in ("execute_command", "run_shell"):
                    args["command"] = parsed
                elif matched_tool in ("read_file", "find_file"):
                    args["path"] = parsed
                elif matched_tool in ("search_files", "grep_search"):
                    args["query"] = parsed
                elif matched_tool in ("list_directory", "list_dir"):
                    args["path"] = parsed
                else:
                    args["input"] = parsed
            elif not parsed:
                # Key: value line fallback
                for line in body.split("\n"):
                    if ":" in line:
                        k, v = line.split(":", 1)
                        clean_k = k.strip()
                        if clean_k and clean_k.isidentifier():
                            args[clean_k] = v.strip().strip("\"'")

        # Validate step list for create_plan
        if matched_tool == "create_plan" and "steps" in args:
            steps_val = args["steps"]
            if isinstance(steps_val, list):
                args["steps"] = [str(s) for s in steps_val]
            elif isinstance(steps_val, str):
                args["steps"] = [s.strip().lstrip("-•* ") for s in steps_val.split("\n") if s.strip()]

        tool_calls.append({
            "id": f"call_fallback_{len(tool_calls)}",
            "type": "function",
            "function": {
                "name": matched_tool,
                "arguments": json.dumps(args, ensure_ascii=False),
            },
        })

    # 3. Match Gemini internal call format: <call:(?:default_api:)?([a-zA-Z0-9_-]+)\{([\s\S]*?)\}(?:>)?
    gemini_pattern = re.compile(
        r"<call:(?:[a-zA-Z0-9_-]+:)?([a-zA-Z0-9_-]+)\{([\s\S]*?)(?:\}(?:>)?|$)",
        re.DOTALL
    )
    for match in gemini_pattern.finditer(text):
        tag_name = match.group(1).strip()
        tag_lower = tag_name.lower()
        body = match.group(2).strip()

        matched_tool = None
        if tag_name in tool_names:
            matched_tool = tag_name
        elif tag_lower in tool_names:
            matched_tool = tag_lower
        else:
            for t in tool_names:
                if t.lower() == tag_name.lower() or t.replace("_", "") == tag_name.lower().replace("_", ""):
                    matched_tool = t
                    break

        if not matched_tool:
            continue

        args: Dict[str, Any] = {}
        # Parse Gemini arguments: keys separated by comma or newline followed by identifier and colon
        arg_pattern = re.compile(r"(?:^|[\n,])\s*([a-zA-Z_][a-zA-Z0-9_]*)\s*[:=]\s*", re.MULTILINE)
        arg_matches = list(arg_pattern.finditer(body))
        if arg_matches:
            for i, am in enumerate(arg_matches):
                k = am.group(1).strip()
                v_start = am.end()
                v_end = arg_matches[i + 1].start() if i + 1 < len(arg_matches) else len(body)
                val = body[v_start:v_end].strip()
                val = re.sub(r"[\s,}]+$", "", val)
                if (val.startswith('"') and val.endswith('"')) or (val.startswith("'") and val.endswith("'")):
                    val = val[1:-1]
                args[k] = val
        else:
            try:
                parsed = yaml.safe_load(body)
                if isinstance(parsed, dict):
                    args.update(parsed)
            except Exception:
                pass

        tool_calls.append({
            "id": f"call_gemini_{len(tool_calls)}",
            "type": "function",
            "function": {
                "name": matched_tool,
                "arguments": json.dumps(args, ensure_ascii=False),
            },
        })

    return tool_calls


def strip_tool_xml_from_text(text: str, executed_tools: List[Dict[str, Any]]) -> str:
    """Removes executed XML tool blocks from assistant text so chat history stays clean."""
    if not text or not executed_tools:
        return text

    clean = text
    for tc in executed_tools:
        name = tc.get("function", {}).get("name", "")
        if name:
            clean = re.sub(rf"<{name}(?:\s+[^>]*)?>[\s\S]*?<\/{name}>", "", clean, flags=re.IGNORECASE)
    
    clean = re.sub(r"<(?:tool_call|function_call)>[\s\S]*?<\/(?:tool_call|function_call)>", "", clean, flags=re.IGNORECASE)
    clean = re.sub(r"<call:(?:[a-zA-Z0-9_-]+:)?([a-zA-Z0-9_-]+)\{[\s\S]*?(?:\}(?:>)?|$)", "", clean)
    return clean.strip()


class ToolTextFilter:
    """
    Filters raw tool call markup (<call:...> or <tool_name>...) out of streaming terminal output
    so that users never see raw tool syntax dumped onto their screen.
    """
    def __init__(self, known_tools: Union[Set[str], List[str], Dict[str, Any]]):
        self.known_tools = set(known_tools.keys()) if isinstance(known_tools, dict) else set(known_tools)
        self.buffer = ""
        self.suppressing = False

    def feed(self, chunk: str) -> str:
        if not chunk:
            return ""
        self.buffer += chunk
        output = ""

        while self.buffer:
            if not self.suppressing:
                lower = self.buffer.lower()
                call_pos = lower.find("<call:")
                tag_pos = -1
                for t in self.known_tools:
                    p = lower.find(f"<{t.lower()}")
                    if p != -1 and (tag_pos == -1 or p < tag_pos):
                        tag_pos = p

                for gen in ("<tool_call>", "<function_call>"):
                    p = lower.find(gen)
                    if p != -1 and (tag_pos == -1 or p < tag_pos):
                        tag_pos = p

                earliest = -1
                if call_pos != -1 and tag_pos != -1:
                    earliest = min(call_pos, tag_pos)
                elif call_pos != -1:
                    earliest = call_pos
                elif tag_pos != -1:
                    earliest = tag_pos

                if earliest != -1:
                    output += self.buffer[:earliest]
                    self.buffer = self.buffer[earliest:]
                    self.suppressing = True
                else:
                    if "<" in self.buffer:
                        last_lt = self.buffer.rfind("<")
                        if len(self.buffer) - last_lt < 25:
                            output += self.buffer[:last_lt]
                            self.buffer = self.buffer[last_lt:]
                            break
                    output += self.buffer
                    self.buffer = ""
            else:
                end_pos = -1
                if self.buffer.startswith("<call:"):
                    close_brace = self.buffer.find("}")
                    if close_brace != -1:
                        end_pos = close_brace + 1
                        if end_pos < len(self.buffer) and self.buffer[end_pos] == ">":
                            end_pos += 1
                else:
                    if "</" in self.buffer:
                        close_tag_end = self.buffer.find(">", self.buffer.find("</"))
                        if close_tag_end != -1:
                            end_pos = close_tag_end + 1

                if end_pos != -1:
                    self.buffer = self.buffer[end_pos:]
                    self.suppressing = False
                else:
                    break

        return output

    def flush(self) -> str:
        if self.suppressing:
            self.buffer = ""
            return ""
        res = self.buffer
        self.buffer = ""
        return res
