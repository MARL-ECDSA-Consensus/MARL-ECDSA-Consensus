"""
更多模块剩余边界测试（RalphLoop 原子任务 FP）
覆盖：security_guard check_package 综合校验、incentive 奖励计算（此前未单点覆盖）
通过标准：新增 ≥6 项测试全过
"""
import logging
import time

import pytest

from blockchain.crypto.security_guard import SecurityGuard
from blockchain.ledger.world_state import WorldState
from blockchain.contracts.incentive_contract import IncentiveContract

logging.basicConfig(level=logging.CRITICAL)


def _pkg(agent_id="agent_0", ts=None, nonce=1, r=0x1000):
    return {
        "agent_id": agent_id,
        "timestamp": ts if ts is not None else int(time.time() * 1000),
        "nonce": nonce,
        "r": r,
    }


class TestCheckPackage:
    def test_valid_ok(self):
        """合法包 OK"""
        guard = SecurityGuard()
        ok, reason = guard.check_package(_pkg())
        assert ok is True
        assert reason == 'OK'

    def test_expired_fails(self):
        """过期时间戳拦截"""
        guard = SecurityGuard()
        ok, _ = guard.check_package(_pkg(ts=int(time.time() * 1000) - 60000))
        assert ok is False

    def test_nonce_replay_fails(self):
        """nonce 重放拦截"""
        guard = SecurityGuard()
        guard.check_package(_pkg(nonce=1))
        ok, _ = guard.check_package(_pkg(nonce=1, r=0x2000))
        assert ok is False

    def test_r_reuse_fails(self):
        """k 重用拦截"""
        guard = SecurityGuard()
        guard.check_package(_pkg(nonce=1, r=0x3333))
        ok, _ = guard.check_package(_pkg(nonce=2, r=0x3333))
        assert ok is False

    def test_fail_records_alert(self):
        """拦截后告警记录"""
        guard = SecurityGuard()
        guard.check_package(_pkg(ts=int(time.time() * 1000) - 60000))
        assert len(guard.get_alerts("agent_0")) == 1
        assert guard.get_fail_count("agent_0") == 1
        assert guard.get_risk_level("agent_0") == "WARNING"


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
        """零积分 → 0"""
        ws = WorldState()
        ws.register_agent("a0", "0x" + "ab" * 32)
        contract = IncentiveContract(ws)
        assert contract.compute_bc_reward("a0") == 0.0

    def test_all_rewards(self):
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


class TestStatsAndBoard:
    def test_get_stats_fields(self):
        """统计字段完整"""
        ws = WorldState()
        ws.register_agent("a0", "0x" + "ab" * 32)
        contract = IncentiveContract(ws)
        stats = contract.get_stats()
        for key in ['total_agents', 'avg_score', 'max_score',
                    'min_score', 'settled_blocks']:
            assert key in stats

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
