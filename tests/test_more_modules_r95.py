"""
更多模块剩余边界测试（RalphLoop 原子任务 GL）
覆盖：security_guard check_package 综合、world_state 积分（此前未单点覆盖）
通过标准：新增 ≥6 项测试全过
"""
import logging
import time

import pytest

from blockchain.crypto.security_guard import SecurityGuard
from blockchain.ledger.world_state import WorldState, AgentStatus

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

    def test_fail_alert_recorded(self):
        """拦截后告警/风险"""
        guard = SecurityGuard()
        guard.check_package(_pkg(ts=int(time.time() * 1000) - 60000))
        assert len(guard.get_alerts("agent_0")) == 1
        assert guard.get_fail_count("agent_0") == 1
        assert guard.get_risk_level("agent_0") == "WARNING"


class TestScore:
    def test_add_score_positive(self):
        """正增量计入累计贡献"""
        ws = WorldState()
        ws.register_agent("a0", "0x" + "ab" * 32)
        ws.add_score("a0", 10.0)
        assert ws.get_score("a0") == 10.0
        assert ws.get_contribution("a0") == 10.0

    def test_add_score_negative(self):
        """负增量不计入累计贡献"""
        ws = WorldState()
        ws.register_agent("a0", "0x" + "ab" * 32)
        ws.add_score("a0", -5.0)
        assert ws.get_score("a0") == -5.0
        assert ws.get_contribution("a0") == 0.0

    def test_add_score_unregistered_noop(self):
        """未注册 add_score noop"""
        ws = WorldState()
        ws.add_score("ghost", 5.0)  # 不崩溃
        assert "ghost" not in ws.get_all_scores()

    def test_get_score_unregistered_raises(self):
        """未注册 get_score KeyError（P2-13 契约）"""
        ws = WorldState()
        with pytest.raises(KeyError):
            ws.get_score("ghost")


class TestStatusWeight:
    def test_set_status(self):
        """状态设置/查询"""
        ws = WorldState()
        ws.register_agent("a0", "0x" + "ab" * 32)
        ws.set_agent_status("a0", AgentStatus.BANNED)
        assert ws.get_agent_status("a0") == AgentStatus.BANNED
        assert ws.is_active("a0") is False

    def test_update_weight(self):
        """权重更新/查询"""
        ws = WorldState()
        ws.register_agent("a0", "0x" + "ab" * 32)
        ws.update_consensus_weight("a0", 0.7)
        assert ws.get_consensus_weight("a0") == 0.7

    def test_update_weight_unregistered(self):
        """未注册权重更新 noop"""
        ws = WorldState()
        ws.update_consensus_weight("ghost", 0.5)  # 不崩溃
        assert ws.get_consensus_weight("ghost") == 0.0
