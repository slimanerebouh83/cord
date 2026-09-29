"""
Tests - CORD Multi-Machine SSH Fleet Orchestration & Encrypted Mesh Communication
"""

import os
import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from cord.fleet.models import FleetNode
from cord.fleet.manager import FleetManager
from cord.fleet.ssh_executor import SSHExecutor, SSHCommandResult
from cord.fleet.mesh_bus import EncryptedMeshBus, MeshSecurityError
from cord.fleet.node_agent import FleetNodeAgent
from cord.tools.fleet.fleet_nodes_tool import FleetNodesTool
from cord.tools.fleet.fleet_exec_tool import FleetExecTool
from cord.tools.fleet.fleet_mesh_tool import FleetMeshTool
from cord.core.config import CordConfig


def test_fleet_node_model_and_tags():
    node = FleetNode(
        name="web-01",
        host="192.168.1.100",
        port=2222,
        user="ubuntu",
        tags=["web", "production", "nginx"],
        description="Frontend load balancer",
    )
    assert node.matches_tag("web")
    assert node.matches_tag("NGINX")
    assert node.matches_tag("web-01")
    assert not node.matches_tag("database")

    data = node.to_dict()
    assert data["port"] == 2222
    restored = FleetNode.from_dict(data)
    assert restored.name == "web-01"
    assert restored.host == "192.168.1.100"


def test_fleet_manager_persistence(tmp_path):
    f_file = tmp_path / "fleet.json"
    mgr = FleetManager(fleet_file=f_file)
    n1 = FleetNode(name="db-01", host="10.0.0.5", tags=["db", "postgres"])
    n2 = FleetNode(name="nas-01", host="10.0.0.6", tags=["storage", "media"])

    mgr.add_node(n1)
    mgr.add_node(n2)

    assert len(mgr.list_nodes()) == 2
    assert len(mgr.list_nodes(tag="db")) == 1
    assert mgr.get_node("db-01").host == "10.0.0.5"

    # Reload from disk
    mgr2 = FleetManager(fleet_file=f_file)
    assert len(mgr2.list_nodes()) == 2
    assert mgr2.get_node("nas-01").tags == ["storage", "media"]

    mgr2.remove_node("db-01")
    assert len(mgr2.list_nodes()) == 1


def test_ssh_executor_args_builder():
    executor = SSHExecutor()
    node = FleetNode(
        name="test-box",
        host="172.16.0.10",
        port=2200,
        user="admin",
        key_path="~/.ssh/custom_key",
    )
    args = executor._build_ssh_args(node)
    assert "-p" in args
    assert "2200" in args
    assert "-i" in args
    assert "admin@172.16.0.10" in args


def test_encrypted_mesh_bus_tamper_detection(tmp_path):
    k_file = tmp_path / "mesh.key"
    bus = EncryptedMeshBus(key_path=k_file)

    bus.register_agent("agent-alpha")
    bus.register_agent("agent-beta")

    # Send encrypted message
    msg = bus.send_encrypted(
        sender_agent="agent-alpha",
        sender_node="master",
        recipient_agent="agent-beta",
        recipient_node="web-server",
        payload="Deploy build #42 to /var/www",
    )

    assert msg.ciphertext != "Deploy build #42 to /var/www"
    assert msg.signature is not None

    # Normal decryption
    inbox = bus.read_inbox("agent-beta")
    assert len(inbox) == 1
    assert inbox[0]["content"] == "Deploy build #42 to /var/www"
    assert inbox[0]["verified"] is True

    # Tampering test
    tampered_msg = bus.send_encrypted(
        sender_agent="agent-alpha",
        sender_node="master",
        recipient_agent="agent-beta",
        recipient_node="web-server",
        payload="Original clean command",
    )
    # Corrupt the signature
    tampered_msg.signature = "0" * 64

    # Inbox reading catches security alert
    inbox2 = bus.read_inbox("agent-beta")
    assert len(inbox2) == 1
    assert inbox2[0]["verified"] is False
    assert "SECURITY ALERT" in inbox2[0]["error"]


@pytest.mark.asyncio
async def test_fleet_nodes_tool_workflow(tmp_path):
    with patch("cord.tools.fleet.fleet_nodes_tool.fleet_mgr", FleetManager(fleet_file=tmp_path / "f.json")):
        tool = FleetNodesTool()

        # 1. Add node
        add_res = await tool.execute(
            action="add",
            name="cloud-vm",
            host="54.210.10.20",
            port=22,
            user="ubuntu",
            tags=["aws", "web"],
        )
        assert add_res.success
        assert "cloud-vm" in add_res.output

        # 2. List nodes
        list_res = await tool.execute(action="list")
        assert list_res.success
        assert "cloud-vm" in list_res.output
        assert "54.210.10.20" in list_res.output

        # 3. Remove node
        rm_res = await tool.execute(action="remove", name="cloud-vm")
        assert rm_res.success


@pytest.mark.asyncio
async def test_fleet_node_agent_and_recursive_subagents():
    node = FleetNode(name="test-server", host="127.0.0.1", user="root")
    cfg = CordConfig()

    parent_agent = FleetNodeAgent(
        node=node,
        mission="Master server orchestration",
        config=cfg,
    )

    with patch("cord.subagents.base_subagent.Subagent.run", new_callable=AsyncMock) as mock_run:
        from cord.subagents.base_subagent import SubagentResult
        mock_run.return_value = SubagentResult(
            role="node-controller:test-server",
            task="sub-task",
            success=True,
            summary="Worker finished successfully",
        )

        child_res = await parent_agent.spawn_child_subagent("Setup nginx reverse proxy", child_role="proxy")
        assert child_res.success
        assert len(parent_agent.child_agents) == 1
        assert "proxy" in child_res.agent_id
