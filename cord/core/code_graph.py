"""
CORD Code Graph Engine - AST Semantic Dependency & Blast Radius Analysis
Parses repository code into an in-memory symbol graph, cross-links function calls,
identifies dependent files, and calculates blast radius before modifications.
"""

from __future__ import annotations
import ast
import os
from pathlib import Path
from typing import Dict, List, Set, Any, Optional
from dataclasses import dataclass, field
from rich.table import Table
from rich.tree import Tree
from rich.panel import Panel

from cord.ui.console import ui


@dataclass
class CodeSymbol:
    name: str
    kind: str  # "function", "class", "method"
    file_path: str
    line: int
    docstring: Optional[str] = None
    calls: List[str] = field(default_factory=list)
    callers: List[str] = field(default_factory=list)


@dataclass
class FileNode:
    file_path: str
    relative_path: str
    symbols: Dict[str, CodeSymbol] = field(default_factory=dict)
    imports: Set[str] = field(default_factory=set)
    imported_by: Set[str] = field(default_factory=set)


class CodeGraphEngine:
    """In-memory AST semantic code graph engine for impact analysis and blast radius calculation."""

    SKIP_DIRS = {
        ".git", ".venv", "venv", "__pycache__", "node_modules",
        "dist", "build", ".pytest_cache", ".ruff_cache", "site-packages",
    }

    def __init__(self, root_dir: Optional[Path] = None):
        self.root_dir = root_dir or Path.cwd()
        self.files: Dict[str, FileNode] = {}
        self.symbols: Dict[str, CodeSymbol] = {}
        self._built = False

    def build_graph(self) -> None:
        """Parses all Python source files in the project workspace."""
        self.files.clear()
        self.symbols.clear()

        py_files: List[Path] = []
        for root, dirs, filenames in os.walk(str(self.root_dir), followlinks=False):
            dirs[:] = [d for d in dirs if d.lower() not in self.SKIP_DIRS and not d.startswith(".")]
            for f in filenames:
                if f.endswith(".py"):
                    py_files.append(Path(root) / f)

        for p in py_files:
            try:
                rel = p.relative_to(self.root_dir).as_posix()
            except ValueError:
                rel = p.name

            node = FileNode(file_path=str(p), relative_path=rel)
            self._parse_file(p, node)
            self.files[rel] = node

        self._link_cross_references()
        self._built = True

    def _parse_file(self, file_path: Path, node: FileNode) -> None:
        try:
            content = file_path.read_text(encoding="utf-8", errors="replace")
            tree = ast.parse(content, filename=str(file_path))
        except Exception:
            return

        for item in tree.body:
            # Handle imports
            if isinstance(item, ast.Import):
                for alias in item.names:
                    node.imports.add(alias.name)
            elif isinstance(item, ast.ImportFrom):
                if item.module:
                    node.imports.add(item.module)

            # Handle top-level functions
            elif isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                sym = self._extract_function(item, node.relative_path)
                node.symbols[sym.name] = sym
                self.symbols[f"{node.relative_path}:{sym.name}"] = sym

            # Handle classes and their methods
            elif isinstance(item, ast.ClassDef):
                cls_sym = CodeSymbol(
                    name=item.name,
                    kind="class",
                    file_path=node.relative_path,
                    line=item.lineno,
                    docstring=ast.get_docstring(item),
                )
                node.symbols[cls_sym.name] = cls_sym
                self.symbols[f"{node.relative_path}:{cls_sym.name}"] = cls_sym

                for sub in item.body:
                    if isinstance(sub, (ast.FunctionDef, ast.AsyncFunctionDef)):
                        method_sym = self._extract_function(sub, node.relative_path, kind="method", parent=item.name)
                        full_name = f"{item.name}.{sub.name}"
                        node.symbols[full_name] = method_sym
                        self.symbols[f"{node.relative_path}:{full_name}"] = method_sym

    def _extract_function(
        self,
        fn_node: ast.FunctionDef | ast.AsyncFunctionDef,
        rel_path: str,
        kind: str = "function",
        parent: Optional[str] = None,
    ) -> CodeSymbol:
        called: List[str] = []
        for n in ast.walk(fn_node):
            if isinstance(n, ast.Call):
                if isinstance(n.func, ast.Name):
                    called.append(n.func.id)
                elif isinstance(n.func, ast.Attribute):
                    called.append(n.func.attr)

        fn_name = f"{parent}.{fn_node.name}" if parent else fn_node.name
        return CodeSymbol(
            name=fn_name,
            kind=kind,
            file_path=rel_path,
            line=fn_node.lineno,
            docstring=ast.get_docstring(fn_node),
            calls=list(set(called)),
        )

    def _link_cross_references(self) -> None:
        """Connects caller and callee references across the symbol graph."""
        # 1. Map file-to-file imports
        for src_rel, src_node in self.files.items():
            for imp in src_node.imports:
                for target_rel in self.files:
                    target_mod = target_rel.replace("/", ".").replace("\\", ".").replace(".py", "")
                    if imp in target_mod or target_mod.endswith(imp):
                        self.files[target_rel].imported_by.add(src_rel)

        # 2. Link symbol call graph
        for caller_key, caller_sym in self.symbols.items():
            for call_name in caller_sym.calls:
                for target_key, target_sym in self.symbols.items():
                    bare_name = target_sym.name.split(".")[-1]
                    if bare_name == call_name and caller_key != target_key:
                        target_sym.callers.append(f"{caller_sym.file_path}:{caller_sym.name}")

    def analyze_blast_radius(self, target: str) -> Dict[str, Any]:
        """Calculates the ripple effect and blast radius of modifying a target file or symbol."""
        if not self._built:
            self.build_graph()

        clean_target = target.strip().replace("\\", "/")
        matching_symbols: List[CodeSymbol] = []
        affected_files: Set[str] = set()
        direct_callers: List[str] = []
        relevant_tests: Set[str] = set()

        # Check if target is a file or symbol
        is_file = clean_target.endswith(".py") or clean_target in self.files
        if is_file:
            for rel, node in self.files.items():
                if rel == clean_target or rel.endswith(clean_target):
                    affected_files.update(node.imported_by)
                    for sym in node.symbols.values():
                        matching_symbols.append(sym)
                        for c in sym.callers:
                            direct_callers.append(c)
                            c_file = c.split(":")[0]
                            affected_files.add(c_file)
        else:
            for key, sym in self.symbols.items():
                if clean_target == sym.name or clean_target == sym.name.split(".")[-1] or clean_target in key:
                    matching_symbols.append(sym)
                    for c in sym.callers:
                        direct_callers.append(c)
                        c_file = c.split(":")[0]
                        affected_files.add(c_file)

        # Find associated test suites
        for f in self.files:
            if "test" in f.lower():
                # Test file imports target or tests target directly
                if any(t_sym.name.lower() in self.files[f].symbols for t_sym in matching_symbols):
                    relevant_tests.add(f)
                for caller in direct_callers:
                    if caller.startswith(f):
                        relevant_tests.add(f)
                if is_file and clean_target.replace(".py", "") in f:
                    relevant_tests.add(f)

        direct_callers_unique = sorted(list(set(direct_callers)))
        affected_files_unique = sorted(list(affected_files))
        relevant_tests_unique = sorted(list(relevant_tests))

        # Risk scoring
        caller_count = len(direct_callers_unique)
        file_count = len(affected_files_unique)
        if caller_count > 12 or file_count > 6:
            risk = "CRITICAL"
            risk_color = "bold red"
        elif caller_count > 5 or file_count > 3:
            risk = "HIGH"
            risk_color = "bold #f97316"
        elif caller_count > 1 or file_count > 1:
            risk = "MEDIUM"
            risk_color = "bold yellow"
        else:
            risk = "LOW"
            risk_color = "bold green"

        return {
            "target": target,
            "is_file": is_file,
            "risk": risk,
            "risk_color": risk_color,
            "symbols_count": len(matching_symbols),
            "direct_callers": direct_callers_unique,
            "direct_callers_count": caller_count,
            "affected_files": affected_files_unique,
            "affected_files_count": file_count,
            "relevant_tests": relevant_tests_unique,
            "relevant_tests_count": len(relevant_tests_unique),
        }

    def render_blast_radius(self, target: str) -> None:
        """Renders an aesthetic Rich dashboard of the impact analysis."""
        data = self.analyze_blast_radius(target)

        table = Table(
            title=f"⚡ CORD AST Blast Radius Analysis: '{target}'",
            show_header=True,
            header_style="bold #38bdf8",
            border_style="#6366f1",
        )
        table.add_column("Metric", style="bold white", width=24)
        table.add_column("Assessment", style="cyan")

        table.add_row("Blast Radius Risk Level", f"[{data['risk_color']}]{data['risk']}[/{data['risk_color']}]")
        table.add_row("Direct Callers", f"[bold yellow]{data['direct_callers_count']}[/bold yellow] call sites")
        table.add_row("Dependent Files", f"[bold magenta]{data['affected_files_count']}[/bold magenta] files in workspace")
        table.add_row("Associated Test Suites", f"[bold green]{data['relevant_tests_count']}[/bold green] test files")

        ui.console.print("\n")
        ui.console.print(table)

        if data["direct_callers"]:
            tree = Tree(f"[bold cyan]🔍 Direct Call Sites for '{target}':[/bold cyan]")
            for c in data["direct_callers"][:12]:
                tree.add(f"[dim white]{c}[/dim white]")
            if len(data["direct_callers"]) > 12:
                tree.add(f"[dim]... and {len(data['direct_callers']) - 12} more sites[/dim]")
            ui.console.print(tree)

        if data["relevant_tests"]:
            test_tree = Tree("[bold green]🧪 Required Regression Verification Tests:[/bold green]")
            for t in data["relevant_tests"]:
                test_tree.add(f"[green]{t}[/green]")
            ui.console.print(test_tree)

        ui.console.print("\n")

    def render_overview(self) -> None:
        """Renders an overview of the code graph size and most referenced hubs."""
        if not self._built:
            self.build_graph()

        hubs = sorted(
            self.files.values(),
            key=lambda n: len(n.imported_by),
            reverse=True,
        )[:8]

        table = Table(
            title=f"🧠 CORD Code Graph Nervous System ({len(self.files)} Modules, {len(self.symbols)} Symbols)",
            show_header=True,
            header_style="bold #38bdf8",
            border_style="#38bdf8",
        )
        table.add_column("Core Module Hub", style="bold cyan")
        table.add_column("Defined Symbols", justify="center", style="yellow")
        table.add_column("Inbound Dependents", justify="center", style="magenta")
        table.add_column("Outbound Imports", justify="center", style="green")

        for h in hubs:
            table.add_row(
                h.relative_path,
                str(len(h.symbols)),
                f"[bold magenta]{len(h.imported_by)}[/bold magenta]",
                str(len(h.imports)),
            )

        ui.console.print("\n")
        ui.console.print(table)
        ui.console.print("\n")


# Global singleton
code_graph_engine = CodeGraphEngine()
