"""
更多模块剩余边界测试（RalphLoop 原子任务 GB）
覆盖：incentive_contract 结算排名、world_state 背叛分级（此前未单点覆盖）
通过标准：新增 ≥6 项测试全过
"""
import logging

import pytest

from blockchain.ledger.world_state import WorldState, AgentStatus
from blockchain.ledger.world_state import _PENALTY_THRESHOLDS
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


class TestBetrayalGrades:
    def test_warning_threshold(self):
        """警告阈值 → WARNING"""
        ws = WorldState()
        ws.register_agent("a0", "0x" + "ab" * 32)
        for _ in range(_PENALTY_THRESHOLDS["warning"]):
            ws.record_betrayal("a0", 1)
        assert ws.get_agent_status("a0") == AgentStatus.WARNING

    def test_demotion_threshold(self):
        """降级阈值 → DEMOTED + 权重 0.3"""
        ws = WorldState()
        ws.register_agent("a0", "0x" + "ab" * 32)
        for _ in range(_PENALTY_THRESHOLDS["demotion"]):
            ws.record_betrayal("a0", 1)
        assert ws.get_agent_status("a0") == AgentStatus.DEMOTED
        assert ws.get_consensus_weight("a0") == 0.3

    def test_ban_threshold(self):
        """封禁阈值 → BANNED + 权重 0"""
        ws = WorldState()
        ws.register_agent("a0", "0x" + "ab" * 32)
        for _ in range(_PENALTY_THRESHOLDS["ban"]):
            ws.record_betrayal("a0", 1)
        assert ws.get_agent_status("a0") == AgentStatus.BANNED
        assert ws.get_consensus_weight("a0") == 0.0
        assert ws.is_active("a0") is False

    def test_betrayal_count(self):
        """背叛计数累积"""
        ws = WorldState()
        ws.register_agent("a0", "0x" + "ab" * 32)
        ws.record_betrayal("a0", 1)
        ws.record_betrayal("a0", 2)
        assert ws.get_betrayal_count("a0") == 2
        assert ws._behaviors["a0"].betrayal_rounds == [1, 2]

    def test_betrayal_unregistered(self):
        """未注册背叛 noop"""
        ws = WorldState()
        ws.record_betrayal("ghost", 1)  # 不崩溃
        assert ws.get_betrayal_count("ghost") == 0


class TestScoreFlow:
    def test_score_contribution(self):
        """积分/贡献联动"""
        ws = WorldState()
        ws.register_agent("a0", "0x" + "ab" * 32)
        ws.add_score("a0", 10.0)
        ws.add_score("a0", -3.0)
        assert ws.get_score("a0") == 7.0
        assert ws.get_contribution("a0") == 10.0

    def test_score_unregistered(self):
        """未注册积分 KeyError（P2-13 契约）"""
        ws = WorldState()
        with pytest.raises(KeyError):
            ws.get_score("ghost")

    def test_leaderboard_desc(self):
        """排行榜降序"""
        ws = WorldState()
        for i in range(3):
            ws.register_agent(f"agent_{i}", f"0x{'ab' * 32}")
        ws.add_score("agent_0", 5.0)
        ws.add_score("agent_1", 15.0)
        contract = IncentiveContract(ws)
        board = contract.get_leaderboard()
        assert board[0][0] == "agent_1"
        assert board[1][0] == "agent_0"
