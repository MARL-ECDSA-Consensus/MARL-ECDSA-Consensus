"""
更多模块剩余边界测试（RalphLoop 原子任务 DZ）
覆盖：incentive_contract 贡献度/结算、penalty_contract 分级（此前未单点覆盖）
通过标准：新增 ≥6 项测试全过
"""
import logging

import pytest

from blockchain.ledger.world_state import WorldState, AgentStatus
from blockchain.contracts.incentive_contract import IncentiveContract, ContributionScore
from blockchain.contracts.penalty_contract import PenaltyContract

logging.basicConfig(level=logging.CRITICAL)


@pytest.fixture
def ws():
    state = WorldState()
    for i in range(3):
        state.register_agent(f"agent_{i}", f"0x{'ab' * 32}")
    return state


class TestComputeContribution:
    def test_cooperate_scores(self, ws):
        """合作 → 合作分 1"""
        contract = IncentiveContract(ws)
        cs = contract.compute_contribution("agent_0", 0.8, True, False)
        assert cs.cooperation_score == 1.0
        assert cs.compliance_score == 1.0

    def test_betray_scores(self, ws):
        """背叛 → 合作分 0、合规分 0"""
        contract = IncentiveContract(ws)
        cs = contract.compute_contribution("agent_0", 0.8, False, True)
        assert cs.cooperation_score == 0.0
        assert cs.compliance_score == 0.0

    def test_neutral_score(self, ws):
        """中性 → 合作分 0.5"""
        contract = IncentiveContract(ws)
        cs = contract.compute_contribution("agent_0", 0.5, False, False)
        assert cs.cooperation_score == 0.5

    def test_env_reward_clamped(self, ws):
        """环境奖励截断 [0,1]"""
        contract = IncentiveContract(ws)
        high = contract.compute_contribution("agent_0", 5.0, False, False)
        low = contract.compute_contribution("agent_0", -5.0, False, False)
        assert high.task_score == 1.0
        assert low.task_score == 0.0


class TestSettleRewards:
    def test_empty_scores(self, ws):
        """空评分 → 空增量"""
        contract = IncentiveContract(ws)
        assert contract.settle_rewards(1, []) == {}

    def test_betrayal_penalty(self, ws):
        """背叛惩罚 -20"""
        contract = IncentiveContract(ws)
        cs = ContributionScore("agent_0", 0.5, 0.0, 0.0)
        deltas = contract.settle_rewards(1, [cs])
        assert deltas["agent_0"] == -20.0

    def test_honest_base_reward(self, ws):
        """诚实基础奖励 ≥10"""
        contract = IncentiveContract(ws)
        cs = ContributionScore("agent_0", 0.5, 1.0, 1.0)
        deltas = contract.settle_rewards(2, [cs])
        assert deltas["agent_0"] >= 10.0

    def test_history_recorded(self, ws):
        """结算历史按区块查询"""
        contract = IncentiveContract(ws)
        cs = ContributionScore("agent_0", 0.5, 1.0, 1.0)
        contract.settle_rewards(5, [cs])
        history = contract.get_settlement_history(5)
        assert len(history) == 1
        assert history[0]["agent_id"] == "agent_0"


class TestPenaltyGrades:
    def test_unregistered(self, ws):
        """未注册 → 失败"""
        penalty = PenaltyContract(ws)
        result = penalty.apply_penalty("ghost")
        assert result["success"] is False
        assert "未注册" in result["error"]

    def test_warning_grade(self, ws):
        """警告级扣 20 分"""
        penalty = PenaltyContract(ws)
        result = penalty.apply_penalty("agent_0", severity="mild")
        assert result["level"] == "WARNING"
        assert ws.get_score("agent_0") == -20.0

    def test_demotion_grade(self, ws):
        """降级级权重 0.3"""
        penalty = PenaltyContract(ws)
        result = penalty.apply_penalty("agent_0", severity="moderate")
        assert result["level"] == "DEMOTED"
        assert ws.get_consensus_weight("agent_0") == 0.3

    def test_ban_grade(self, ws):
        """封禁级状态 BANNED"""
        penalty = PenaltyContract(ws)
        result = penalty.apply_penalty("agent_0", severity="severe")
        assert result["level"] == "BANNED"
        assert ws.get_agent_status("agent_0") == AgentStatus.BANNED
