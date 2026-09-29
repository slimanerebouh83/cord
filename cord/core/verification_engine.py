"""CORD Core - Automated Verification Engine"""
from __future__ import annotations
import ast
import subprocess
from pathlib import Path
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, field

@dataclass
class VerificationResult:
    passed: bool
    issues: List[str] = field(default_factory=list)
    test_output: Optional[str] = None
    diagnostics: Dict[str, Any] = field(default_factory=dict)

class VerificationEngine:
    """Verifies file changes, code correctness, syntax, and test suites automatically."""

    def __init__(self, workspace_root: Optional[Path] = None):
        self.workspace_root = workspace_root or Path.cwd()

    def check_file_syntax(self, file_path: str | Path) -> tuple[bool, Optional[str]]:
        """Validates code syntax without executing."""
        path = Path(file_path).resolve()
        if not path.exists():
            return False, f"File {file_path} not found"

        # Python syntax check via ast.parse
        if path.suffix == ".py":
            try:
                code = path.read_text(encoding="utf-8", errors="replace")
                ast.parse(code, filename=str(path))
                return True, None
            except SyntaxError as e:
                return False, f"Python SyntaxError at {path.name}:{e.lineno}:{e.offset}: {e.msg}"
            except Exception as e:
                return False, f"Error validating {path.name}: {e}"

        # JSON syntax check
        elif path.suffix == ".json":
            try:
                import json
                json.loads(path.read_text(encoding="utf-8", errors="replace"))
                return True, None
            except Exception as e:
                return False, f"JSON Syntax error in {path.name}: {e}"

        # JS / TS syntax check if node is available
        elif path.suffix in [".js", ".mjs"]:
            try:
                res = subprocess.run(["node", "--check", str(path)], capture_output=True, text=True, timeout=5)
                if res.returncode != 0:
                    return False, f"Node syntax error in {path.name}: {res.stderr.strip()}"
                return True, None
            except Exception:
                pass

        return True, None

    def run_tests_verification(self, timeout: int = 60) -> tuple[bool, str]:
        """Runs the workspace test suite if tests exist."""
        cwd = self.workspace_root
        # Detect pytest
        if (cwd / "pytest.ini").exists() or (cwd / "tests").exists() or (cwd / "conftest.py").exists():
            try:
                res = subprocess.run(["pytest", "-q"], capture_output=True, text=True, timeout=timeout, cwd=str(cwd))
                passed = (res.returncode == 0)
                out = res.stdout[-2000:] + ("\n" + res.stderr[-1000:] if res.stderr else "")
                return passed, out.strip()
            except Exception as e:
                return False, f"Test runner execution error: {e}"

        return True, "No test suite configured; skipped."

    def verify_change(self, modified_files: List[str], run_tests: bool = True) -> VerificationResult:
        """Run complete verification cycle over touched files."""
        issues: List[str] = []

        # 1. Syntax Check each modified file
        for f in modified_files:
            valid, err = self.check_file_syntax(f)
            if not valid and err:
                issues.append(err)

        if issues:
            return VerificationResult(passed=False, issues=issues)

        # 2. Automated Test Run if syntax is sound
        test_out = None
        if run_tests:
            tests_passed, test_out = self.run_tests_verification()
            if not tests_passed:
                issues.append("Automated test suite failed after changes.")
                return VerificationResult(passed=False, issues=issues, test_output=test_out)

        return VerificationResult(passed=True, test_output=test_out)

verification_engine = VerificationEngine()
