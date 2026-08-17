"""
更多模块剩余边界测试（RalphLoop 原子任务 EP）
覆盖：cw_pbft 权重边界、world_state 背叛分级（此前未单点覆盖）
通过标准：新增 ≥6 项测试全过
"""
import logging

import pytest

from blockchain.consensus.cw_pbft import CWPBFTConsensus
from blockchain.ledger.world_state import WorldState, AgentStatus
from blockchain.ledger.world_state import _PENALTY_THRESHOLDS

logging.basicConfig(level=logging.CRITICAL)

NODES = ['node_0', 'node_1', 'node_2']


@pytest.fixture
def pbft():
    return CWPBFTConsensus('node_0', NODES)


class TestWeightUpdate:
    def test_normal_update(self, pbft):
        """正常权重更新"""
        pbft.update_weight('node_1', 0.8)
        assert pbft.get_weights()['node_1'] == 0.8

    def test_min_protected(self, pbft):
        """低于 MIN_WEIGHT 被下界保护"""
        pbft.update_weight('node_1', 0.01)
        assert pbft.get_weights()['node_1'] == pbft.MIN_WEIGHT == 0.1

    def test_zero_ban(self, pbft):
        """封禁节点权重置 0"""
        pbft.update_weight('node_1', 0.0)
        assert pbft.get_weights()['node_1'] == 0.0

    def test_unregistered_ignored(self, pbft):
        """未注册节点更新忽略"""
        before = dict(pbft.get_weights())
        pbft.update_weight('ghost', 0.9)
        assert pbft.get_weights() == before


class TestBetrayalGrades:
    def test_warning_threshold(self):
        """达到警告阈值 → WARNING 状态"""
        ws = WorldState()
        ws.register_agent("a0", "0x" + "ab" * 32)
        for _ in range(_PENALTY_THRESHOLDS["warning"]):
            ws.record_betrayal("a0", 1)
        assert ws.get_agent_status("a0") == AgentStatus.WARNING

    def test_demotion_threshold(self):
        """达到降级阈值 → DEMOTED + 权重 0.3"""
        ws = WorldState()
        ws.register_agent("a0", "0x" + "ab" * 32)
        for _ in range(_PENALTY_THRESHOLDS["demotion"]):
            ws.record_betrayal("a0", 1)
        assert ws.get_agent_status("a0") == AgentStatus.DEMOTED
        assert ws.get_consensus_weight("a0") == 0.3

    def test_ban_threshold(self):
        """达到封禁阈值 → BANNED + 权重 0"""
        ws = WorldState()
        ws.register_agent("a0", "0x" + "ab" * 32)
        for _ in range(_PENALTY_THRESHOLDS["ban"]):
            ws.record_betrayal("a0", 1)
        assert ws.get_agent_status("a0") == AgentStatus.BANNED
        assert ws.get_consensus_weight("a0") == 0.0
        assert ws.is_active("a0") is False


class TestBetrayalQueries:
    def test_count_increments(self):
        """背叛计数累积"""
        ws = WorldState()
        ws.register_agent("a0", "0x" + "ab" * 32)
        ws.record_betrayal("a0", 1)
        ws.record_betrayal("a0", 2)
        assert ws.get_betrayal_count("a0") == 2

    def test_rounds_recorded(self):
        """背叛轮次记录"""
        ws = WorldState()
        ws.register_agent("a0", "0x" + "ab" * 32)
        ws.record_betrayal("a0", 7)
        assert ws._behaviors["a0"].betrayal_rounds == [7]

    def test_unregistered_noop(self):
        """未注册背叛 noop"""
        ws = WorldState()
        ws.record_betrayal("ghost", 1)  # 不崩溃
        assert ws.get_betrayal_count("ghost") == 0


class TestSummaryFlow:
    def test_summary_after_penalty(self):
        """惩罚后摘要一致"""
        ws = WorldState()
        ws.register_agent("a0", "0x" + "ab" * 32)
        for _ in range(_PENALTY_THRESHOLDS["demotion"]):
            ws.record_betrayal("a0", 1)
        summary = ws.get_agent_summary("a0")
        assert summary["betrayal_count"] == _PENALTY_THRESHOLDS["demotion"]
        assert summary["status"] == AgentStatus.DEMOTED
        assert summary["consensus_weight"] == 0.3
