"""
更多模块剩余边界测试（RalphLoop 原子任务 DR）
覆盖：cw_pbft 权重阈值/加权投票、world_state 行为记录/系统状态（此前未单点覆盖）
通过标准：新增 ≥6 项测试全过
"""
import logging

import pytest

from blockchain.consensus.cw_pbft import CWPBFTConsensus, ConsensusVote
from blockchain.ledger.world_state import WorldState

logging.basicConfig(level=logging.CRITICAL)

NODES = ['node_0', 'node_1', 'node_2']


@pytest.fixture
def pbft():
    return CWPBFTConsensus('node_0', NODES)


class TestWeightThreshold:
    def test_no_votes_false(self, pbft):
        """无投票 → 未达阈值"""
        assert pbft._check_weight_threshold('prepare') is False

    def test_all_votes_true(self, pbft):
        """全节点投票 → 达 2/3 阈值"""
        pbft.start_consensus('hash_t')
        for nid in NODES:
            pbft._votes['prepare'][nid] = ConsensusVote(
                voter_id=nid, block_hash='hash_t', phase='prepare',
                weight=pbft._weights[nid])
        assert pbft._check_weight_threshold('prepare') is True

    def test_partial_votes_false(self, pbft):
        """部分投票 → 未达阈值"""
        pbft.start_consensus('hash_p')
        pbft._votes['prepare']['node_0'] = ConsensusVote(
            voter_id='node_0', block_hash='hash_p', phase='prepare',
            weight=pbft._weights['node_0'])
        assert pbft._check_weight_threshold('prepare') is False


class TestWeightedVoting:
    def test_high_weight_dominates(self, pbft):
        """高权重节点主导：少数高权重可达阈值"""
        pbft.update_weight('node_1', 2.0)
        pbft.update_weight('node_2', 0.1)
        total = sum(pbft.get_weights().values())
        pbft.start_consensus('hash_w')
        # node_0 + node_1（权重 1.0+2.0=3.0）> 2/3 total
        pbft._votes['prepare']['node_0'] = ConsensusVote(
            voter_id='node_0', block_hash='hash_w', phase='prepare',
            weight=pbft._weights['node_0'])
        pbft._votes['prepare']['node_1'] = ConsensusVote(
            voter_id='node_1', block_hash='hash_w', phase='prepare', weight=2.0)
        voted = sum(v.weight for v in pbft._votes['prepare'].values())
        assert voted >= (2 / 3) * total

    def test_weight_history_recorded(self, pbft):
        """权重历史记录更新"""
        pbft.update_weight('node_1', 0.8)
        pbft.update_weight('node_2', 0.5)
        assert len(pbft.get_weight_history()) == 2
        assert pbft.get_weight_history()[-1]['weights']['node_2'] == 0.5


class TestWorldBehavior:
    def test_record_action_appends(self):
        """行为哈希累积"""
        ws = WorldState()
        ws.register_agent("agent_0", "0x" + "ab" * 32)
        ws.record_action("agent_0", "h1", 3)
        ws.record_action("agent_0", "h2", 5)
        assert ws._behaviors["agent_0"].action_hashes == ["h1", "h2"]
        assert ws._behaviors["agent_0"].last_active_block == 5

    def test_record_action_unregistered_noop(self):
        """未注册行为记录 noop"""
        ws = WorldState()
        ws.record_action("ghost", "h1", 1)  # 不崩溃

    def test_record_betrayal_rounds(self):
        """背叛轮次记录"""
        ws = WorldState()
        ws.register_agent("agent_0", "0x" + "ab" * 32)
        ws.record_betrayal("agent_0", 7)
        assert ws._behaviors["agent_0"].betrayal_rounds == [7]
        assert ws.get_betrayal_count("agent_0") == 1


class TestSystemState:
    def test_system_state_updates(self):
        """系统状态更新"""
        ws = WorldState()
        ws.update_system_state(height=5, tx_count=10, online_count=3)
        state = ws.get_system_state()
        assert state["block_height"] == 5
        assert state["total_transactions"] == 10
        assert state["online_agents"] == 3

    def test_system_state_accumulates(self):
        """多次更新累计"""
        ws = WorldState()
        ws.update_system_state(1, 10, 1)
        ws.update_system_state(2, 5, 2)
        state = ws.get_system_state()
        assert state["total_transactions"] == 15  # 10+5 累计
        assert state["block_height"] == 2  # 最新高度
