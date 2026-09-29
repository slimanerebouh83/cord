"""
Tests for CORD Core Fallback Tool Parser
"""

import pytest
import json
from cord.core.tool_parser import parse_fallback_tool_calls, strip_tool_xml_from_text


def test_parse_xml_tool_calls_user_scenario():
    sample = """
<create_plan>
goal: Build a Python calculator application and open it for the user
steps:
  - Create a Python script `calculator.py` using Tkinter with a modern, clean UI supporting all standard arithmetic operations, clear button, and error handling.
  - Execute and launch `calculator.py` in the background so the GUI calculator window opens on the user's desktop.
  - Verify success and inform the user.
</create_plan>

<write_file>
content: |
    import tkinter as tk
    from tkinter import messagebox
path: calculator.py
</write_file>

<execute_command>
command: python calculator.py
</execute_command>
"""
    known = {"create_plan", "write_file", "execute_command", "read_file"}
    calls = parse_fallback_tool_calls(sample, known)

    assert len(calls) == 3

    # 1. create_plan
    assert calls[0]["function"]["name"] == "create_plan"
    args0 = json.loads(calls[0]["function"]["arguments"])
    assert "calculator" in args0["goal"]
    assert len(args0["steps"]) == 3

    # 2. write_file
    assert calls[1]["function"]["name"] == "write_file"
    args1 = json.loads(calls[1]["function"]["arguments"])
    assert args1["path"] == "calculator.py"
    assert "import tkinter" in args1["content"]

    # 3. execute_command
    assert calls[2]["function"]["name"] == "execute_command"
    args2 = json.loads(calls[2]["function"]["arguments"])
    assert args2["command"] == "python calculator.py"


def test_ignored_tags():
    sample = """
<thought>
I should write the file now.
</thought>
<write_file>
path: test.txt
content: hello
</write_file>
"""
    calls = parse_fallback_tool_calls(sample, {"write_file"})
    assert len(calls) == 1
    assert calls[0]["function"]["name"] == "write_file"


def test_generic_tool_call():
    sample = """
<tool_call>
{"name": "read_file", "arguments": {"path": "main.py"}}
</tool_call>
"""
    calls = parse_fallback_tool_calls(sample, {"read_file"})
    assert len(calls) == 1
    assert calls[0]["function"]["name"] == "read_file"
    args = json.loads(calls[0]["function"]["arguments"])
    assert args["path"] == "main.py"


def test_strip_tool_xml():
    sample = "Hello!\n<write_file>\npath: test.txt\n</write_file>\nDone!"
    cleaned = strip_tool_xml_from_text(sample, [{"function": {"name": "write_file"}}])
    assert "Hello!" in cleaned
    assert "Done!" in cleaned
    assert "<write_file>" not in cleaned
