---
name: swarm-mesh
description: Autonomous peer-to-peer agent swarm coordination, distributed plan publishing, peer consensus, and 10,000+ virtual agent scaling.
category: Multi-Agent & Swarm
---

# Multi-Agent Swarm Mesh Skill

Guidelines for orchestrating collaborative autonomous subagents where all agents are treated as equal peers ("كلهم سواسية").

## Swarm Principles
1. **Peer Equality**:
   - The Main Agent and Subagents interact as equal collaborative peers on the unified Swarm Message Bus (`swarm_bus`).
   - Any agent can publish plans, broadcast findings, request peer reviews, and propose solutions.

2. **Distributed Plan Sharing**:
   - Use `swarm_bus.publish_plan(author_id, plan_title, steps)` to broadcast action plans to all active peers.
   - Peers can inspect plans, vote or suggest improvements, and divide subtasks autonomously.

3. **High-Density Scaling**:
   - The swarm architecture supports scaling up to 10,000+ virtual agents using lightweight in-memory agent state tracking.
   - Broadcast messages use ring-buffer retention to keep memory overhead minimal while allowing arbitrary peer discovery.
