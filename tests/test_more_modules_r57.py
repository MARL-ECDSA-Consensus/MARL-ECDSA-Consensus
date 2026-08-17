"""
更多模块剩余边界测试（RalphLoop 原子任务 DN）
覆盖：cw_pbft 主节点轮换/投票接收/预准备（此前未单点覆盖）
通过标准：新增 ≥6 项测试全过
"""
import logging

import pytest

from blockchain.consensus.cw_pbft import CWPBFTConsensus, ConsensusVote, ConsensusState

logging.basicConfig(level=logging.CRITICAL)

NODES = ['node_0', 'node_1', 'node_2']


@pytest.fixture
def pbft():
    return CWPBFTConsensus('node_0', NODES)


class TestPrimaryRotation:
    def test_get_primary_rotation(self, pbft):
        """主节点每 BLOCKS_PER_ROTATION=10 区块轮换"""
        assert pbft.get_primary(0) == 'node_0'
        assert pbft.get_primary(9) == 'node_0'   # 0-9 区间
        assert pbft.get_primary(10) == 'node_1'  # 10-19 区间
        assert pbft.get_primary(20) == 'node_2'  # 20-29 区间

    def test_is_primary(self, pbft):
        """主节点判定（node_0 是 0-9 区块的主节点）"""
        assert pbft.is_primary(0) is True
        assert pbft.is_primary(9) is True
        assert pbft.is_primary(10) is False  # 10-19 主节点是 node_1


class TestReceivePrePrepare:
    def test_receive_pre_prepare_returns_vote(self, pbft):
        """收到 pre-prepare 后返回 prepare 投票"""
        vote = pbft.receive_pre_prepare('hash_pp', 'node_0')
        assert vote is not None
        assert vote.phase == 'prepare'
        assert vote.block_hash == 'hash_pp'

    def test_receive_pre_prepare_sets_state(self, pbft):
        """收到 pre-prepare 后状态进入 PREPARE"""
        pbft.receive_pre_prepare('hash_pp2', 'node_0')
        assert pbft.get_state() == ConsensusState.PREPARE


class TestReceiveVote:
    def test_receive_vote_records(self, pbft):
        """接收投票记录到对应阶段（单票未达阈值 → 返回 None 为正常契约）"""
        pbft.start_consensus('hash_v')
        vote = ConsensusVote(voter_id='node_1', block_hash='hash_v',
                             phase='prepare', weight=1.0)
        result = pbft.receive_vote(vote)
        assert 'node_1' in pbft._votes['prepare']  # 投票已记录
        assert result is None  # 单票未达 2/3 阈值，不生成 commit

    def test_receive_vote_wrong_hash_ignored(self, pbft):
        """错误区块哈希投票被忽略"""
        pbft.start_consensus('hash_target')
        vote = ConsensusVote(voter_id='node_1', block_hash='hash_other',
                             phase='prepare', weight=1.0)
        pbft.receive_vote(vote)
        assert 'node_1' not in pbft._votes['prepare']  # 未记录

    def test_receive_vote_duplicate_ignored(self, pbft):
        """重复投票被忽略"""
        pbft.start_consensus('hash_dup')
        vote = ConsensusVote(voter_id='node_1', block_hash='hash_dup',
                             phase='prepare', weight=1.0)
        pbft.receive_vote(vote)
        pbft.receive_vote(vote)  # 重复
        assert len(pbft._votes['prepare']) == 1  # 仅记录一次


class TestStateTransitions:
    def test_state_after_start(self, pbft):
        """start_consensus 后状态为 PRE_PREPARE（主节点发起阶段）"""
        pbft.start_consensus('hash_s')
        assert pbft.get_state() == ConsensusState.PRE_PREPARE

    def test_reset_after_receive(self, pbft):
        """reset 清空投票与状态"""
        pbft.receive_pre_prepare('hash_r', 'node_0')
        pbft.reset()
        assert pbft.get_state() == ConsensusState.IDLE
        assert pbft._votes == {'prepare': {}, 'commit': {}}

    def test_fast_consensus_committed_state(self, pbft):
        """快速共识后达成共识"""
        pbft.fast_consensus('hash_fc', 'node_0')
        assert pbft.is_consensus_reached() is True
