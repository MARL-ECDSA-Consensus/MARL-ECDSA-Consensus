"""
更多模块剩余边界测试（RalphLoop 原子任务 FD）
覆盖：world_state 摘要/系统状态、action_recorder flush（此前未单点覆盖）
通过标准：新增 ≥6 项测试全过
"""
import logging

import pytest

from blockchain.ledger.world_state import WorldState, AgentStatus
from marl.integration.action_recorder import ActionRecorder

logging.basicConfig(level=logging.CRITICAL)


def _pkg(verified=True):
    pkg = {
        'signature_hex': '0x' + 'ab' * 32,
        'message_hex': '0x' + 'cd' * 16,
        'r': 12345,
        's': 67890,
    }
    if verified is not None:
        pkg['verified'] = verified
    return pkg


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

    def test_system_state_accumulate(self):
        """多次更新累计"""
        ws = WorldState()
        ws.update_system_state(1, 10, 1)
        ws.update_system_state(2, 5, 2)
        state = ws.get_system_state()
        assert state["total_transactions"] == 15
        assert state["block_height"] == 2


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


class TestFlushPending:
    def test_flush_no_bc(self):
        """无 bc_node → flush noop"""
        ar = ActionRecorder(n_agents=3)
        ar.record_action("a0", 1, [0.1], 1.0, 1000, 1, _pkg())
        ar.flush_pending()
        assert ar._tx_count == 0

    def test_flush_with_bc(self):
        """有 bc_node → flush 添加交易"""
        class _BC:
            def __init__(self):
                self.txs = []
            def add_transaction(self, tx):
                self.txs.append(tx)
        bc = _BC()
        ar = ActionRecorder(bc_node=bc, n_agents=3)
        ar.record_action("a0", 1, [0.1], 1.0, 1000, 1, _pkg())
        ar.flush_pending()
        assert len(bc.txs) == 1
        assert ar._tx_count == 1
        assert len(ar._pending_actions) == 0

    def test_flush_filters_unverified(self):
        """flush 过滤未验证"""
        class _BC:
            def __init__(self):
                self.txs = []
            def add_transaction(self, tx):
                self.txs.append(tx)
        bc = _BC()
        ar = ActionRecorder(bc_node=bc, n_agents=3)
        ar.record_action("a0", 1, [0.1], 1.0, 1000, 1, _pkg(verified=True))
        ar.record_action("a1", 2, [0.2], 1.0, 1001, 2, _pkg(verified=False))
        ar.flush_pending()
        assert len(bc.txs) == 1  # 仅可信
