"""
更多模块剩余边界测试（RalphLoop 原子任务 GR）
覆盖：security_guard check_package 综合、world_state 摘要/系统状态（此前未单点覆盖）
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
