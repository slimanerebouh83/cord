---
name: code-refactor
description: Codebase refactoring, architectural modularization, backward compatibility maintenance, and dead-code elimination.
category: Engineering
---

# Code Refactoring & Quality Enhancement Skill

Guidelines for modifying and modernizing code cleanly.

## Key Rules
1. **Preserve Compatibility**: Keep existing public APIs, function signatures, and return structures backward-compatible unless a breaking change is explicitly requested.
2. **Modular Architecture**: Separate concerns cleanly (UI in `ui/`, tools in `tools/`, core logic in `core/`).
3. **Robust Error Handling**: Always catch specific exceptions, provide explanatory error messages, and prevent silent failures.
4. **Test Verification**: Verify with automated test suites (`pytest`) before declaring any refactor complete.
