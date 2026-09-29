"""
Tests for Dynamic Runtime Tool Creation, Swarm Deliberation, Voting Consensus, and 1,000,000 Agent Scaling.
"""

import pytest
from pathlib import Path

from cord.tools.dynamic_tool import (
    dynamic_tool_manager,
    CreateDynamicTool,
    ListDynamicTools,
    DeleteDynamicTool,
)
from cord.subagents.deliberation import swarm_deliberation
from cord.tools.system.deliberation_tools import (
    SubagentProposeTool,
    SubagentVoteTool,
    SubagentConsensusTool,
)
from cord.tools.system.swarm_tools import SubagentListPeersTool
from cord.subagents.message_bus import swarm_bus
from cord.subagents.fiber import fiber_scheduler


@pytest.mark.asyncio
async def test_create_and_execute_dynamic_tool(tmp_path, monkeypatch):
    """Verifies that agents can dynamically write, compile, execute, and persist new tools."""
    fake_storage = tmp_path / "dynamic_tools"
    fake_storage.mkdir()
    monkeypatch.setattr(dynamic_tool_manager, "storage_dir", fake_storage)
    dynamic_tool_manager.tools.clear()

    create_tool = CreateDynamicTool()

    code = """
async def run(num1: int, num2: int):
    return {"sum": num1 + num2, "product": num1 * num2}
"""
    res = await create_tool.execute(
        name="math_calculator",
        description="Calculates sum and product of two numbers",
        parameters={
            "type": "object",
            "properties": {
                "num1": {"type": "integer"},
                "num2": {"type": "integer"},
            },
            "required": ["num1", "num2"],
        },
        python_code=code,
        author="coder_subagent",
    )
    assert res.success is True
    assert "successfully compiled, registered, and persisted" in res.output

    # Verify tool is registered in manager
    assert "math_calculator" in dynamic_tool_manager.tools
    dyn_tool = dynamic_tool_manager.tools["math_calculator"]

    # Execute dynamic tool
    exec_res = await dyn_tool.execute(num1=7, num2=6)
    assert exec_res.success is True
    assert '"sum": 13' in exec_res.output
    assert '"product": 42' in exec_res.output

    # List dynamic tools
    list_tool = ListDynamicTools()
    list_res = await list_tool.execute()
    assert list_res.success is True
    assert "math_calculator" in list_res.output

    # Delete dynamic tool
    del_tool = DeleteDynamicTool()
    del_res = await del_tool.execute(name="math_calculator")
    assert del_res.success is True
    assert "math_calculator" not in dynamic_tool_manager.tools


@pytest.mark.asyncio
async def test_swarm_deliberation_and_voting_consensus():
    """Verifies that subagents can propose strategies, debate, cast reasoned votes, and reach consensus."""
    propose_tool = SubagentProposeTool()
    vote_tool = SubagentVoteTool()
    consensus_tool = SubagentConsensusTool()

    # 1. Propose
    p_res = await propose_tool.execute(
        title="Architecture Decision: Database Engine",
        description="Choose between SQLite, PostgreSQL, or DuckDB for the analytics module.",
        options=["SQLite", "PostgreSQL", "DuckDB"],
        creator_id="architect_agent",
    )
    assert p_res.success is True
    pid = p_res.metadata["proposal_id"]

    # 2. Subagents Vote
    v1 = await vote_tool.execute(
        proposal_id=pid,
        choice="DuckDB",
        rationale="DuckDB is in-process, zero-setup, and handles columnar OLAP queries 50x faster.",
        voter_id="analytics_coder",
    )
    assert v1.success is True

    v2 = await vote_tool.execute(
        proposal_id=pid,
        choice="DuckDB",
        rationale="Agreed with analytics_coder. Zero external service dependencies is critical for local CLI.",
        voter_id="reviewer_agent",
    )
    assert v2.success is True

    v3 = await vote_tool.execute(
        proposal_id=pid,
        choice="PostgreSQL",
        rationale="Postgres supports traditional relational transactions better, but requires docker.",
        voter_id="db_admin_agent",
    )
    assert v3.success is True

    # 3. Consensus Evaluation
    c_res = await consensus_tool.execute(proposal_id=pid, conclude=True)
    assert c_res.success is True
    assert c_res.metadata["winning_choice"] == "DuckDB"
    assert c_res.metadata["consensus_reached"] is True
    assert "66.7%" in c_res.output
    assert "zero external service dependencies" in c_res.output.lower()


@pytest.mark.asyncio
async def test_swarm_scaling_and_peer_roster():
    """Verifies that swarm_bus scales to 1,000,000 agents and subagent_list_peers reports active roster."""
    # Verify 1,000,000 agent capacity
    assert swarm_bus.agent_count >= 1_000_000

    # Register virtual fibers
    fiber_scheduler.provision_batch(count=100, role="tester", squad="qa_squad")
    assert len(fiber_scheduler.squads["qa_squad"]) == 100

    # Test peer roster tool
    peers_tool = SubagentListPeersTool()
    res = await peers_tool.execute()
    assert res.success is True
    assert "Swarm Peer Roster" in res.output
    assert "1,000,000" in res.output
