"""
更多模块剩余边界测试（RalphLoop 原子任务 FB）
覆盖：security_guard nonce/r 检查、incentive 结算排名（此前未单点覆盖）
通过标准：新增 ≥6 项测试全过
"""
import logging
import time

import pytest

from blockchain.crypto.security_guard import SecurityGuard
from blockchain.ledger.world_state import WorldState
from blockchain.contracts.incentive_contract import IncentiveContract, ContributionScore

logging.basicConfig(level=logging.CRITICAL)


def _pkg(agent_id="agent_0", ts=None, nonce=1, r=0x1000):
    return {
        "agent_id": agent_id,
        "timestamp": ts if ts is not None else int(time.time() * 1000),
        "nonce": nonce,
        "r": r,
    }


class TestNonceCheck:
    def test_nonce_monotonic(self):
        """nonce 严格递增通过"""
        guard = SecurityGuard()
        ok, _ = guard._check_nonce(_pkg(nonce=1))
        assert ok is True
        ok, _ = guard._check_nonce(_pkg(nonce=2))
        assert ok is True

    def test_nonce_replay(self):
        """重复 nonce 拒绝"""
        guard = SecurityGuard()
        guard._check_nonce(_pkg(nonce=5))
        ok, reason = guard._check_nonce(_pkg(nonce=5))
        assert ok is False
        assert "重放" in reason

    def test_nonce_missing(self):
        """缺 nonce 拒绝"""
        guard = SecurityGuard()
        ok, reason = guard._check_nonce({"agent_id": "a0"})
        assert ok is False
        assert "缺少" in reason


class TestRCheck:
    def test_r_unique_passes(self):
        """不同 r 值通过"""
        guard = SecurityGuard()
        assert guard._check_r_reuse(_pkg(r=0x1111))[0] is True
        assert guard._check_r_reuse(_pkg(r=0x2222))[0] is True

    def test_r_reuse_rejected(self):
        """重复 r 拒绝（k 重用检测）"""
        guard = SecurityGuard()
        guard._check_r_reuse(_pkg(r=0x3333))
        ok, reason = guard._check_r_reuse(_pkg(r=0x3333))
        assert ok is False
        assert "重用" in reason

    def test_r_missing_ok(self):
        """缺 r 通过（跳过检测）"""
        guard = SecurityGuard()
        assert guard._check_r_reuse({"agent_id": "a0"})[0] is True


class TestCheckPackage:
    def test_valid_package_ok(self):
        """合法包通过"""
        guard = SecurityGuard()
        ok, reason = guard.check_package(_pkg())
        assert ok is True
        assert reason == 'OK'

    def test_expired_timestamp(self):
        """过期时间戳拦截"""
        guard = SecurityGuard()
        ok, _ = guard.check_package(_pkg(ts=int(time.time() * 1000) - 60000))
        assert ok is False

    def test_fail_records_alert(self):
        """拦截记录告警"""
        guard = SecurityGuard()
        guard.check_package(_pkg(ts=int(time.time() * 1000) - 60000))
        assert len(guard.get_alerts("agent_0")) == 1
        assert guard.get_fail_count("agent_0") == 1


class TestSettleRank:
    def test_rank_bonus(self):
        """排名加成：排名1 ≥ 排名2"""
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
