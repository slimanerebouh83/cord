"""
Unit tests for ComputerControlArbiter, Subagent Consensus/Negotiation,
Frontier Models (Claude Opus 5.5, Fable 5.1, GPT Astra 6), and Fleet Enhancements.
"""

import pytest
import asyncio
from unittest.mock import AsyncMock, patch, MagicMock

from cord.subagents.computer_arbiter import (
    computer_arbiter,
    ComputerControlArbiter,
    ComputerControlLease,
)
from cord.tools.computer.computer_negotiation_tools import (
    RequestComputerControlTool,
    ReleaseComputerControlTool,
    ProposeComputerPlanTool,
    GetComputerArbiterStatusTool,
)
from cord.subagents.roles import ROLE_CONFIGS, COMPUTER_CONTROL_TOOLS
from cord.subagents.model_scout import LATEST_MODELS_CATALOG
from cord.core.config import PROVIDER_PRESETS
from cord.fleet.manager import FleetManager, FleetNode
from cord.tools.fleet.fleet_nodes_tool import FleetNodesTool


@pytest.fixture(autouse=True)
def reset_arbiter():
    """Ensure arbiter is clean before each test."""
    computer_arbiter.active_lease = None
    computer_arbiter.waiting_queue.clear()
    yield
    computer_arbiter.active_lease = None
    computer_arbiter.waiting_queue.clear()


@pytest.mark.asyncio
async def test_computer_arbiter_lease_lifecycle():
    arbiter = ComputerControlArbiter()

    # 1. Main agent and supervisor always allowed
    can_sup, _ = arbiter.can_execute("supervisor")
    assert can_sup is True
    can_main, _ = arbiter.can_execute(None)
    assert can_main is True

    # 2. Acquire lease for agent-alpha
    res = arbiter.request_lease(
        agent_id="agent-alpha",
        purpose="Automating Chrome forms",
        planned_steps=["click button", "type credentials"],
        target_app="chrome.exe",
        duration_sec=30,
    )
    assert res["granted"] is True
    assert arbiter.active_lease is not None
    assert arbiter.active_lease.holder_id == "agent-alpha"

    # 3. Agent-alpha can execute
    can_alpha, _ = arbiter.can_execute("agent-alpha")
    assert can_alpha is True

    # 4. Agent-beta tries to execute without acquiring -> blocked
    can_beta, reason = arbiter.can_execute("agent-beta")
    assert can_beta is False
    assert "agent-alpha" in reason

    # 5. Agent-beta requests lease while busy -> enqueued and rejected immediately
    res_beta = arbiter.request_lease(
        agent_id="agent-beta",
        purpose="Opening terminal",
        planned_steps=["press Win+R", "type cmd"],
    )
    assert res_beta["granted"] is False
    assert "busy" in res_beta["status"]
    assert len(arbiter.waiting_queue) == 1

    # 6. Release by agent-alpha -> automatically hands over to agent-beta in queue
    rel_res = arbiter.release_lease("agent-alpha")
    assert rel_res["success"] is True
    assert rel_res["handed_over_to"] == "agent-beta"
    assert arbiter.active_lease.holder_id == "agent-beta"

    # Now agent-beta can execute
    can_beta_now, _ = arbiter.can_execute("agent-beta")
    assert can_beta_now is True

    # 7. Release by agent-beta -> arbiter is now idle
    rel_beta = arbiter.release_lease("agent-beta")
    assert rel_beta["success"] is True
    assert rel_beta["handed_over_to"] is None
    assert arbiter.active_lease is None


@pytest.mark.asyncio
async def test_computer_arbiter_plan_consensus():
    arbiter = ComputerControlArbiter()

    res = arbiter.propose_plan_for_consensus(
        agent_id="agent-gamma",
        title="Automate bulk database purge on GUI client",
        planned_steps=[
            "Launch admin console",
            "Select cluster DB",
            "Click Purge and Confirm",
        ],
        explanation="Testing data reset procedure across subagents",
    )
    assert res["success"] is True
    assert "topic_id" in res
    assert res["status"] == "deliberation_opened"


@pytest.mark.asyncio
async def test_negotiation_tools_execution():
    req_tool = RequestComputerControlTool()
    status_tool = GetComputerArbiterStatusTool()
    prop_tool = ProposeComputerPlanTool()
    rel_tool = ReleaseComputerControlTool()

    # Get status when idle
    s_res = await status_tool.execute()
    assert s_res.success is True
    assert "UNLOCKED" in s_res.output

    # Request lease
    req_res = await req_tool.execute(
        agent_id="tester-agent",
        purpose="Testing desktop login window",
        planned_steps=["click login", "type admin"],
        duration_sec=15,
    )
    assert req_res.success is True
    assert "GRANTED" in req_res.output

    # Status shows active
    s_res2 = await status_tool.execute()
    assert s_res2.success is True
    assert "LOCKED" in s_res2.output
    assert "tester-agent" in s_res2.output

    # Propose plan
    p_res = await prop_tool.execute(
        agent_id="tester-agent",
        title="Form fill test",
        planned_steps=["step 1", "step 2"],
    )
    assert p_res.success is True
    assert "Proposal" in p_res.output

    # Release lease
    r_res = await rel_tool.execute(agent_id="tester-agent")
    assert r_res.success is True
    assert "released" in r_res.output.lower()


def test_operator_role_configuration():
    assert "operator" in ROLE_CONFIGS
    operator_cfg = ROLE_CONFIGS["operator"]
    assert "computer_act" in operator_cfg["allowed_tools"]
    assert "request_computer_control" in operator_cfg["allowed_tools"]
    assert "release_computer_control" in operator_cfg["allowed_tools"]
    assert "propose_computer_plan" in operator_cfg["allowed_tools"]
    assert "get_computer_arbiter_status" in operator_cfg["allowed_tools"]
    assert "subagent_deliberate" in operator_cfg["allowed_tools"]

    # Coder & Tester also have arbiter negotiation tools
    coder_tools = ROLE_CONFIGS["coder"]["allowed_tools"]
    assert "request_computer_control" in coder_tools
    assert "release_computer_control" in coder_tools

    tester_tools = ROLE_CONFIGS["tester"]["allowed_tools"]
    assert "request_computer_control" in tester_tools
    assert "computer_act" in tester_tools


def test_frontier_models_registered():
    # 1. Check LATEST_MODELS_CATALOG
    assert "claude-opus-5-5" in LATEST_MODELS_CATALOG
    opus = LATEST_MODELS_CATALOG["claude-opus-5-5"]
    assert opus["id"] == "anthropic/claude-opus-5.5"
    assert "2026" in opus["release"]

    assert "fable-5-1" in LATEST_MODELS_CATALOG
    fable = LATEST_MODELS_CATALOG["fable-5-1"]
    assert fable["id"] == "fable/fable-5.1-instruct"

    assert "gpt-astra-6" in LATEST_MODELS_CATALOG
    astra = LATEST_MODELS_CATALOG["gpt-astra-6"]
    assert astra["id"] == "openai/gpt-astra-6"

    # 2. Check PROVIDER_PRESETS
    openrouter_models = PROVIDER_PRESETS["openrouter"]["models"]
    assert "anthropic/claude-opus-5.5" in openrouter_models
    assert "fable/fable-5.1-instruct" in openrouter_models
    assert "openai/gpt-astra-6" in openrouter_models

    assert "claude-opus-5.5" in PROVIDER_PRESETS["anthropic"]["models"]
    assert "gpt-astra-6" in PROVIDER_PRESETS["openai"]["models"]
    assert "fable" in PROVIDER_PRESETS
    assert "fable-5.1" in PROVIDER_PRESETS["fable"]["models"]


def test_fleet_manager_uri_parsing(tmp_path):
    mgr = FleetManager(fleet_file=tmp_path / "fleet_test.json")

    # Full URI
    p1 = mgr.parse_connection_uri("ssh://ubuntu:secret@192.168.1.120:2222")
    assert p1["user"] == "ubuntu"
    assert p1["password"] == "secret"
    assert p1["host"] == "192.168.1.120"
    assert p1["port"] == 2222

    # Short format
    p2 = mgr.parse_connection_uri("pi@raspberrypi.local:22")
    assert p2["user"] == "pi"
    assert p2["host"] == "raspberrypi.local"
    assert p2["port"] == 22

    # Quick URI connect
    node = mgr.connect_quick_uri(
        uri="dev@10.0.0.55:2200",
        name="build-worker",
        tags=["ci", "worker"],
    )
    assert node.name == "build-worker"
    assert node.host == "10.0.0.55"
    assert node.port == 2200
    assert node.user == "dev"
    assert "ci" in node.tags

    found = mgr.get_node("build-worker")
    assert found is not None
    assert found.host == "10.0.0.55"


@pytest.mark.asyncio
async def test_fleet_manager_ping_and_broadcast(tmp_path):
    mgr = FleetManager(fleet_file=tmp_path / "fleet_test.json")
    node = FleetNode(name="srv1", host="192.168.1.10", user="admin")
    mgr.add_node(node)

    with patch("cord.fleet.ssh_executor.ssh_executor.test_connection", new_callable=AsyncMock) as mock_test:
        mock_test.return_value = {
            "reachable": True,
            "latency_ms": 12.4,
            "os_type": "linux",
            "raw_os": "Ubuntu 24.04",
            "specs": {"cores": 8},
        }
        res = await mgr.ping_all_nodes()
        assert len(res) == 1
        assert res[0]["reachable"] is True
        assert res[0]["latency_ms"] == 12.4
        assert mgr.get_node("srv1").status == "online"

    with patch("cord.fleet.ssh_executor.ssh_executor.execute", new_callable=AsyncMock) as mock_run:
        mock_result = MagicMock()
        mock_result.summary.return_value = "[srv1] uname -a -> SUCCESS"
        mock_run.return_value = mock_result

        b_res = await mgr.broadcast_command("uname -a")
        assert len(b_res) == 1
        assert mock_run.await_count == 1


@pytest.mark.asyncio
async def test_fleet_nodes_tool_new_actions(tmp_path):
    tool = FleetNodesTool()
    
    # Test quick connect action
    with patch("cord.tools.fleet.fleet_nodes_tool.fleet_mgr.connect_quick_uri") as mock_connect:
        mock_connect.return_value = FleetNode(name="my-pi", host="192.168.1.88", user="pi", port=22)
        res = await tool.execute(action="connect", uri="pi@192.168.1.88:22", name="my-pi")
        assert res.success is True
        assert "my-pi" in res.output

    # Test ping_all action
    with patch("cord.tools.fleet.fleet_nodes_tool.fleet_mgr.ping_all_nodes", new_callable=AsyncMock) as mock_ping:
        mock_ping.return_value = [
            {"name": "my-pi", "host": "192.168.1.88", "port": 22, "user": "pi", "reachable": True, "latency_ms": 5.2, "os_type": "linux"}
        ]
        res_ping = await tool.execute(action="ping_all")
        assert res_ping.success is True
        assert "ONLINE" in res_ping.output

    # Test scan action
    with patch("cord.tools.fleet.fleet_nodes_tool.fleet_mgr.scan_local_subnet", new_callable=AsyncMock) as mock_scan:
        mock_scan.return_value = [{"host": "192.168.1.50", "port": 22, "status": "open"}]
        res_scan = await tool.execute(action="scan", subnet="192.168.1.")
        assert res_scan.success is True
        assert "192.168.1.50:22" in res_scan.output
