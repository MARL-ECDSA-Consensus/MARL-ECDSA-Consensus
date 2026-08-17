"""
更多模块剩余边界测试（RalphLoop 原子任务 FN）
覆盖：world_state 摘要/系统状态、action_recorder 转换/批量（此前未单点覆盖）
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

    def test_system_state_initial(self):
        """初始状态"""
        ws = WorldState()
        state = ws.get_system_state()
        assert state["block_height"] == 0
        assert state["total_transactions"] == 0


class TestRecorderConvert:
    def test_pending_full(self):
        """完整 pending → Transaction"""
        ar = ActionRecorder(n_agents=3)
        pending = {
            'agent_id': 'a0', 'step': 3, 'action': [0.5],
            'action_hash': 'hash1', 'env_reward': 1.0,
            'timestamp': 1000, 'nonce': 2, 'signature_hex': '0x' + 'ab' * 32,
            'message_hex': '00', 'r': 1, 's': 2, 'verified': True,
        }
        tx = ar.pending_to_transaction(pending)
        assert tx is not None
        assert tx.agent_id == 'a0'
        assert tx.action_hash == 'hash1'
        assert tx.tx_id == tx.compute_hash()

    def test_pending_minimal(self):
        """最小字段 pending → Transaction"""
        ar = ActionRecorder(n_agents=3)
        pending = {'agent_id': 'a0', 'action_hash': 'h1', 'timestamp': 1000}
        tx = ar.pending_to_transaction(pending)
        assert tx is not None
        assert tx.nonce == 0  # 默认
        assert tx.signature_hex == ''  # 默认

    def test_pending_bad(self):
        """缺必填字段 → None 降级"""
        ar = ActionRecorder(n_agents=3)
        assert ar.pending_to_transaction({}) is None


class TestBatchStats:
    def test_batch_with_bc(self):
        """批量上链统计"""
        class _BC:
            def __init__(self):
                self.txs = []
            def add_transaction(self, tx):
                self.txs.append(tx)
        bc = _BC()
        ar = ActionRecorder(bc_node=bc, n_agents=3)
        ar.record_action("a0", 1, [0.1], 1.0, 1000, 1, _pkg(verified=True))
        ar.record_action("a1", 2, [0.2], 1.0, 1001, 2, _pkg(verified=False))
        ar.batch_upload()
        assert len(bc.txs) == 1  # 仅可信
        stats = ar.get_stats()
        assert stats['tx_count'] == 1
        assert stats['pending_actions'] == 0

    def test_batch_no_sig_allowed(self):
        """无签名包默认可信（向后兼容）"""
        class _BC:
            def __init__(self):
                self.txs = []
            def add_transaction(self, tx):
                self.txs.append(tx)
        bc = _BC()
        ar = ActionRecorder(bc_node=bc, n_agents=3)
        ar.record_action("a0", 1, [0.1], 1.0, 1000, 1, None)
        ar.batch_upload()
        assert len(bc.txs) == 1
