"""
更多模块剩余边界测试（RalphLoop 原子任务 EV）
覆盖：incentive_contract 奖励计算、world_state 摘要/系统状态（此前未单点覆盖）
通过标准：新增 ≥6 项测试全过
"""
import logging

import pytest

from blockchain.ledger.world_state import WorldState, AgentStatus
from blockchain.contracts.incentive_contract import IncentiveContract

logging.basicConfig(level=logging.CRITICAL)


class TestBCReward:
    def test_lambda_scaling(self):
        """BC 奖励 = λ * 积分"""
        ws = WorldState()
        ws.register_agent("a0", "0x" + "ab" * 32)
        ws.add_score("a0", 10.0)
        contract = IncentiveContract(ws)
        assert contract.compute_bc_reward("a0", lambda_weight=0.1) == 1.0
        assert contract.compute_bc_reward("a0", lambda_weight=0.5) == 5.0

    def test_zero_score(self):
        """零积分 → 奖励 0"""
        ws = WorldState()
        ws.register_agent("a0", "0x" + "ab" * 32)
        contract = IncentiveContract(ws)
        assert contract.compute_bc_reward("a0") == 0.0

    def test_all_bc_rewards(self):
        """批量奖励"""
        ws = WorldState()
        ws.register_agent("a0", "0x" + "ab" * 32)
        ws.register_agent("a1", "0x" + "cd" * 32)
        ws.add_score("a0", 10.0)
        ws.add_score("a1", 20.0)
        contract = IncentiveContract(ws)
        rewards = contract.get_all_bc_rewards(lambda_weight=0.1)
        assert rewards["a0"] == 1.0
        assert rewards["a1"] == 2.0


class TestSummary:
    def test_summary_structure(self):
        """摘要字段完整"""
        ws = WorldState()
        ws.register_agent("a0", "0x" + "ab" * 32)
        summary = ws.get_agent_summary("a0")
        for key in ['agent_id', 'status', 'consensus_weight', 'score',
                    'cumulative_contribution', 'betrayal_count',
                    'cooperation_rounds', 'last_active_block']:
            assert key in summary

    def test_summary_unregistered(self):
        """未注册摘要 → 空 dict"""
        ws = WorldState()
        assert ws.get_agent_summary("ghost") == {}

    def test_summary_reflects_state(self):
        """摘要反映状态"""
        ws = WorldState()
        ws.register_agent("a0", "0x" + "ab" * 32)
        ws.add_score("a0", 5.0)
        ws.record_cooperation("a0")
        ws.update_consensus_weight("a0", 0.7)
        summary = ws.get_agent_summary("a0")
        assert summary["score"] == 5.0
        assert summary["cooperation_rounds"] == 1
        assert summary["consensus_weight"] == 0.7


class TestSystemState:
    def test_system_state_update(self):
        """系统状态更新"""
        ws = WorldState()
        ws.update_system_state(height=3, tx_count=15, online_count=2)
        state = ws.get_system_state()
        assert state["block_height"] == 3
        assert state["total_transactions"] == 15
        assert state["online_agents"] == 2

    def test_system_state_initial(self):
        """初始状态"""
        ws = WorldState()
        state = ws.get_system_state()
        assert state["block_height"] == 0
        assert state["total_transactions"] == 0
        assert state["online_agents"] == 0
        assert state["registered_agents"] == 0

    def test_all_agents_summary(self):
        """全部智能体摘要"""
        ws = WorldState()
        ws.register_agent("a0", "0x" + "ab" * 32)
        ws.register_agent("a1", "0x" + "cd" * 32)
        summaries = ws.get_all_agents_summary()
        assert len(summaries) == 2
        assert {s["agent_id"] for s in summaries} == {"a0", "a1"}


class TestStatusFlow:
    def test_status_after_penalty(self):
        """惩罚后状态流转"""
        ws = WorldState()
        ws.register_agent("a0", "0x" + "ab" * 32)
        ws.set_agent_status("a0", AgentStatus.BANNED)
        assert ws.get_agent_status("a0") == AgentStatus.BANNED
        assert ws.is_active("a0") is False
