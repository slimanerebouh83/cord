"""CORD Tool - run_tests"""
from __future__ import annotations
import subprocess
import os
from pathlib import Path
from cord.tools.base import BaseTool, ToolResult
from cord.permissions.levels import PermissionLevel, RiskLevel

class RunTestsTool(BaseTool):
    name = "run_tests"
    description = "Execute unit and integration tests across Python (pytest/unittest), Node (npm/yarn/jest), Rust (cargo test), or Go."
    required_permission = PermissionLevel.EXECUTE
    risk_level = RiskLevel.MEDIUM
    parameters = {
        "type": "object",
        "properties": {
            "framework": {
                "type": "string",
                "enum": ["auto", "pytest", "unittest", "npm", "cargo", "go"],
                "description": "Test runner to use ('auto' will detect automatically based on workspace files)",
                "default": "auto"
            },
            "path": {
                "type": "string",
                "description": "Optional specific test file or directory path (e.g. 'tests/test_basic.py')"
            },
            "args": {
                "type": "string",
                "description": "Additional CLI flags to pass to the test runner (e.g. '-v -k test_name')"
            }
        },
        "required": []
    }

    async def execute(self, framework: str = "auto", path: str | None = None, args: str | None = None, **kwargs) -> ToolResult:
        try:
            cwd = Path.cwd()

            # Auto-detection if requested
            if framework == "auto":
                if (cwd / "pytest.ini").exists() or (cwd / "conftest.py").exists() or (cwd / "tests").exists() or list(cwd.glob("test_*.py")):
                    framework = "pytest"
                elif (cwd / "package.json").exists():
                    framework = "npm"
                elif (cwd / "Cargo.toml").exists():
                    framework = "cargo"
                elif (cwd / "go.mod").exists():
                    framework = "go"
                else:
                    framework = "pytest"

            cmd: list[str] = []
            if framework == "pytest":
                cmd = ["pytest"]
                if path:
                    cmd.append(path)
                if args:
                    cmd.extend(args.split())
            elif framework == "unittest":
                cmd = ["python", "-m", "unittest"]
                if path:
                    cmd.append(path)
                else:
                    cmd.extend(["discover", "-s", "tests"])
                if args:
                    cmd.extend(args.split())
            elif framework == "npm":
                cmd = ["npm", "test"]
                if args:
                    cmd.extend(["--", *args.split()])
            elif framework == "cargo":
                cmd = ["cargo", "test"]
                if args:
                    cmd.extend(args.split())
            elif framework == "go":
                cmd = ["go", "test", "./..."]
                if args:
                    cmd.extend(args.split())
            else:
                return ToolResult(success=False, output="", error=f"Unsupported test framework: {framework}")

            res = subprocess.run(cmd, capture_output=True, text=True, timeout=120, cwd=str(cwd), shell=False)
            output = f"Command: {' '.join(cmd)}\nExit Code: {res.returncode}\n\nSTDOUT:\n{res.stdout[-3000:]}\n"
            if res.stderr:
                output += f"\nSTDERR:\n{res.stderr[-2000:]}\n"

            passed = (res.returncode == 0)
            return ToolResult(
                success=passed,
                output=output,
                error="" if passed else f"Tests failed with exit code {res.returncode}"
            )
        except subprocess.TimeoutExpired:
            return ToolResult(success=False, output="", error="Test execution timed out after 120 seconds")
        except FileNotFoundError as e:
            return ToolResult(success=False, output="", error=f"Test runner executable not found: {e}")
        except Exception as e:
            return ToolResult(success=False, output="", error=str(e))
