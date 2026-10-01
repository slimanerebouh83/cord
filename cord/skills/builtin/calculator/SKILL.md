---
name: calculator
description: Precision arithmetic, scientific calculations, financial formulas, and desktop/GUI calculator application building & launching.
category: Productivity & Math
---

# Calculator & Mathematical Computations Skill

This skill guides the CORD agent on performing mathematical operations and creating or launching calculator applications.

## Capabilities & Workflows

### 1. Launching Native Windows Calculator
When the user asks to "open the calculator" or "افتح الة حاسبة":
- Use `execute_command` with:
  ```powershell
  Start-Process calc.exe
  ```
- Do NOT block waiting for the process to exit (use async or background start).
- Report clearly to the user that Windows Calculator has been launched.

### 2. Creating Custom Calculator Applications
When the user asks to "create a calculator" or "اصنع الة حاسبة":
- Choose modern, clean Tkinter, PyQt, or HTML/JS/CSS depending on user intent.
- Ensure the calculator has:
  - Responsive keyboard and mouse click support.
  - Standard arithmetic (+, -, *, /) and clear/backspace.
  - Safe expression evaluation (never use raw insecure `eval` without restrictions).
  - Modern aesthetic (dark mode, rounded buttons, crisp display).
- Save to the workspace (e.g., `calculator.py` or `index.html`) and launch it using `execute_command` (e.g. `python calculator.py`).

### 3. Precision Scientific & Financial Calculations
When computing complex numbers, statistics, or currency:
- Utilize Python `math`, `decimal.Decimal`, or `numpy` for exact precision.
- Format large numbers with commas and appropriate decimal places.
