---
name: desktop-assistant
description: Autonomous Windows desktop control, window management, screen capture inspection, keyboard/mouse interaction, and system tasks.
category: System & Automation
---

# Desktop Assistant & GUI Control Skill

This skill equips CORD with advanced instructions for reliable, error-free Windows desktop automation.

## Core Directives

1. **Screen Inspection First**:
   - Before clicking or typing into unfamiliar GUI elements, take a screenshot using `computer_screenshot`.
   - Analyze coordinate locations accurately. Coordinates are (x, y) pixels relative to the primary display.

2. **Window Management**:
   - Use `computer_window` with `action="list"` to inspect all running applications and titles.
   - Use `computer_window` with `action="focus"` or `action="minimize"`/`"maximize"` to bring the target app to foreground before interacting.

3. **Stable Mouse & Keyboard Interaction**:
   - Use `computer_mouse` with `action="click"` and explicit `x`, `y` coordinates. CORD automatically applies human-like mouse movement and a 40ms button hold time for reliable OS message dispatch.
   - For text entry into active focus, use `computer_keyboard` with `action="type"` and `text="desired text"`.
   - For hotkeys (like opening start menu, saving, copying), use `computer_keyboard` with `action="hotkey"`, e.g. `key=["ctrl", "s"]` or `key=["win"]`.

4. **Clipboard Integration**:
   - Use `clipboard` tool with `action="read"` or `action="write"` to quickly transfer large text chunks without slow key strokes.

5. **Safety & Fallback**:
   - If an application is unresponsive, verify window focus with `computer_window` before retrying mouse clicks.
