"""
更多模块剩余边界测试（RalphLoop 原子任务 EF）
覆盖：settlement_coordinator 结算/奖励更新/统计（此前未单点覆盖）
通过标准：新增 ≥6 项测试全过
"""
import logging

import pytest

from marl.integration.settlement_coordinator import SettlementCoordinator

logging.basicConfig(level=logging.CRITICAL)


class TestSettle:
    def test_settle_no_contract_simulated(self):
        """无合约 → 模拟结算"""
        sc = SettlementCoordinator(n_agents=3)
        from blockchain.contracts.incentive_contract import ContributionScore
        scores = [ContributionScore("a0", 0.5, 1.0, 1.0)]
        deltas = sc.settle(1, scores)
        assert "a0" in deltas
        assert isinstance(deltas["a0"], float)

    def test_settle_with_contract(self):
        """有合约 → 委托合约结算"""
        from blockchain.ledger.world_state import WorldState
        from blockchain.contracts.incentive_contract import IncentiveContract, ContributionScore
        ws = WorldState()
        ws.register_agent("a0", "0x" + "ab" * 32)
        contract = IncentiveContract(ws)
        sc = SettlementCoordinator(incentive_contract=contract, n_agents=3)
        scores = [ContributionScore("a0", 0.5, 1.0, 1.0)]
        deltas = sc.settle(1, scores)
        assert deltas["a0"] >= 10.0  # 基础奖励

    def test_settle_empty_scores(self):
        """空评分 → 空增量"""
        sc = SettlementCoordinator(n_agents=3)
        assert sc.settle(1, []) == {}


class TestUpdateRewards:
    def test_update_ablate_mode(self):
        """无合约（ablate）→ _bc_scores 累计"""
        sc = SettlementCoordinator(n_agents=3)
        sc.update_rewards_and_scores({"a0": 2.0, "a1": -1.0})
        scores = sc.get_bc_scores()
        assert scores["a0"] == 2.0
        assert scores["a1"] == -1.0
        rewards = sc.get_bc_rewards()
        assert rewards["a0"] == 2.0

    def test_update_with_contract(self):
        """有合约 → _bc_scores 不重复累计（WorldState 为源）"""
        from blockchain.ledger.world_state import WorldState
        from blockchain.contracts.incentive_contract import IncentiveContract
        ws = WorldState()
        ws.register_agent("a0", "0x" + "ab" * 32)
        contract = IncentiveContract(ws)
        sc = SettlementCoordinator(incentive_contract=contract, n_agents=3)
        sc.update_rewards_and_scores({"a0": 5.0})
        assert sc.get_bc_rewards()["a0"] == 5.0  # 本回合增量
        assert sc.get_bc_scores()["a0"] == 0.0  # WorldState 为积分源

    def test_update_missing_agent(self):
        """更新未注册 agent → 默认处理（不崩溃）"""
        sc = SettlementCoordinator(n_agents=3)
        sc.update_rewards_and_scores({"ghost": 1.0})
        assert sc.get_bc_rewards().get("ghost", 0.0) == 1.0 or "ghost" in sc.get_bc_rewards()


class TestTotalReward:
    def test_lambda_zero_passthrough(self):
        """λ=0 → 总奖励 = 环境奖励"""
        sc = SettlementCoordinator(n_agents=3, lambda_weight=0.0)
        assert sc.compute_total_reward("a0", 5.0) == 5.0

    def test_lambda_positive_fusion(self):
        """λ>0 → 融合 BC 奖励"""
        sc = SettlementCoordinator(n_agents=3, lambda_weight=0.1)
        total = sc.compute_total_reward("a0", 5.0)
        assert isinstance(total, float)
        assert total >= 0

    def test_batch_rewards(self):
        """批量融合奖励"""
        sc = SettlementCoordinator(n_agents=3)
        rewards = sc.get_all_total_rewards([1.0, 2.0], ["a0", "a1"])
        assert len(rewards) == 2


class TestStats:
    def test_get_stats(self):
        """get_stats 返回结构"""
        sc = SettlementCoordinator(n_agents=3, lambda_weight=0.1)
        stats = sc.get_stats()
        assert isinstance(stats, dict)
        assert len(stats) >= 1
