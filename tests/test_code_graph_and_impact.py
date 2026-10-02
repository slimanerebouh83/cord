"""
Tests for AST Semantic Code Graph Engine and Blast Radius Impact Analysis Tool.
"""

import pytest
from pathlib import Path
from cord.core.code_graph import CodeGraphEngine
from cord.tools.code_graph_tool import CodeImpactAnalysisTool


@pytest.mark.asyncio
async def test_code_graph_ast_parsing_and_blast_radius(tmp_path):
    """Verifies that CodeGraphEngine accurately maps symbols, call sites, and calculates risk scores."""
    # Create sample codebase
    file_a = tmp_path / "math_utils.py"
    file_a.write_text(
        "def compute_total(a, b):\n"
        "    return a + b\n\n"
        "class Calculator:\n"
        "    def multiply(self, x, y):\n"
        "        return x * y\n",
        encoding="utf-8",
    )

    file_b = tmp_path / "service.py"
    file_b.write_text(
        "from math_utils import compute_total\n\n"
        "def process_order(items):\n"
        "    return compute_total(10, 20)\n",
        encoding="utf-8",
    )

    test_file = tmp_path / "test_service.py"
    test_file.write_text(
        "from service import process_order\n\n"
        "def test_process():\n"
        "    assert process_order([]) == 30\n",
        encoding="utf-8",
    )

    engine = CodeGraphEngine(root_dir=tmp_path)
    engine.build_graph()

    # Check discovered symbols
    assert "math_utils.py" in engine.files
    assert "service.py" in engine.files
    assert "compute_total" in engine.files["math_utils.py"].symbols
    assert "Calculator" in engine.files["math_utils.py"].symbols

    # Test blast radius on compute_total
    impact = engine.analyze_blast_radius("compute_total")
    assert impact["target"] == "compute_total"
    assert impact["direct_callers_count"] >= 1
    assert any("service.py" in c for c in impact["direct_callers"])
    assert impact["risk"] in ("LOW", "MEDIUM", "HIGH")


@pytest.mark.asyncio
async def test_code_impact_tool_execution(tmp_path, monkeypatch):
    """Verifies that CodeImpactAnalysisTool executes cleanly and returns JSON metadata."""
    sample_file = tmp_path / "core.py"
    sample_file.write_text("def run():\n    pass\n", encoding="utf-8")

    from cord.core.code_graph import code_graph_engine
    monkeypatch.setattr(code_graph_engine, "root_dir", tmp_path)
    code_graph_engine._built = False

    tool = CodeImpactAnalysisTool()
    res = await tool.execute(target="core.py")

    assert res.success is True
    assert "target" in res.metadata
    assert res.metadata["target"] == "core.py"
    assert "risk" in res.metadata
