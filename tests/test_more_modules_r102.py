"""
更多模块剩余边界测试（RalphLoop 原子任务 GZ）
覆盖：incentive_contract 结算排名、world_state 摘要/系统状态（此前未单点覆盖）
通过标准：新增 ≥6 项测试全过
"""
import logging

import pytest

from blockchain.ledger.world_state import WorldState, AgentStatus
from blockchain.contracts.incentive_contract import IncentiveContract, ContributionScore

logging.basicConfig(level=logging.CRITICAL)


class TestSettleRank:
    def test_rank_bonus_top(self):
        """排名1 获得加成 ≥ 排名2"""
        ws = WorldState()
        for i in range(4):
            ws.register_agent(f"agent_{i}", f"0x{'ab' * 32}")
        contract = IncentiveContract(ws)
        scores = [
            ContributionScore("agent_0", 1.0, 1.0, 1.0),
            ContributionScore("agent_1", 0.8, 1.0, 1.0),
            ContributionScore("agent_2", 0.5, 1.0, 1.0),
            ContributionScore("agent_3", 0.2, 1.0, 1.0),
        ]
        deltas = contract.settle_rewards(1, scores)
        assert deltas["agent_0"] >= deltas["agent_1"]
        assert deltas["agent_0"] >= 10.0

    def test_settle_empty(self):
        """空评分空增量"""
        ws = WorldState()
        contract = IncentiveContract(ws)
        assert contract.settle_rewards(1, []) == {}

    def test_settle_betrayal(self):
        """背叛惩罚 -20"""
        ws = WorldState()
        ws.register_agent("agent_0", "0x" + "ab" * 32)
        contract = IncentiveContract(ws)
        cs = ContributionScore("agent_0", 0.5, 0.0, 0.0)
        deltas = contract.settle_rewards(1, [cs])
        assert deltas["agent_0"] == -20.0

    def test_history_recorded(self):
        """结算历史查询"""
        ws = WorldState()
        ws.register_agent("agent_0", "0x" + "ab" * 32)
        contract = IncentiveContract(ws)
        cs = ContributionScore("agent_0", 0.5, 1.0, 1.0)
        contract.settle_rewards(5, [cs])
        history = contract.get_settlement_history(5)
        assert len(history) == 1
        assert history[0]["agent_id"] == "agent_0"


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

    def test_summary_unregistered_empty(self):
        """未注册摘要空 dict"""
        ws = WorldState()
        assert ws.get_agent_summary("ghost") == {}

    def test_all_agents_summary(self):
        """全部摘要"""
        ws = WorldState()
        ws.register_agent("a0", "0x" + "ab" * 32)
        ws.register_agent("a1", "0x" + "cd" * 32)
        summaries = ws.get_all_agents_summary()
        assert len(summaries) == 2
        assert {s["agent_id"] for s in summaries} == {"a0", "a1"}


class TestSystemState:
    def test_update_and_get(self):
        """系统状态更新/获取"""
        ws = WorldState()
        ws.update_system_state(height=2, tx_count=10, online_count=2)
        state = ws.get_system_state()
        assert state["block_height"] == 2
        assert state["total_transactions"] == 10
        assert state["online_agents"] == 2

    def test_system_state_initial(self):
        """初始状态"""
        ws = WorldState()
        state = ws.get_system_state()
        assert state["block_height"] == 0
        assert state["total_transactions"] == 0
        assert state["registered_agents"] == 0


class TestStatusFlow:
    def test_status_set_get(self):
        """状态设置/查询"""
        ws = WorldState()
        ws.register_agent("a0", "0x" + "ab" * 32)
        ws.set_agent_status("a0", AgentStatus.DEMOTED)
        assert ws.get_agent_status("a0") == AgentStatus.DEMOTED

    def test_weight_update(self):
        """权重更新/查询"""
        ws = WorldState()
        ws.register_agent("a0", "0x" + "ab" * 32)
        ws.update_consensus_weight("a0", 0.6)
        assert ws.get_consensus_weight("a0") == 0.6
