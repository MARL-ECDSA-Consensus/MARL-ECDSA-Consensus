"""
更多模块剩余边界测试（RalphLoop 原子任务 GP）
覆盖：cw_pbft 投票路径/状态、incentive 奖励计算（此前未单点覆盖）
通过标准：新增 ≥6 项测试全过
"""
import logging

import pytest

from blockchain.consensus.cw_pbft import CWPBFTConsensus, ConsensusVote, ConsensusState
from blockchain.ledger.world_state import WorldState
from blockchain.contracts.incentive_contract import IncentiveContract

logging.basicConfig(level=logging.CRITICAL)

NODES = ['node_0', 'node_1', 'node_2']


@pytest.fixture
def pbft():
    return CWPBFTConsensus('node_0', NODES)


class TestPrePrepare:
    def test_receive_returns_prepare(self, pbft):
        """收到 pre-prepare → 返回 prepare 投票"""
        vote = pbft.receive_pre_prepare('hash_pp', 'node_0')
        assert vote is not None
        assert vote.phase == 'prepare'
        assert pbft.get_state() == ConsensusState.PREPARE

    def test_receive_sets_hash(self, pbft):
        """pre-prepare 设置当前区块哈希"""
        pbft.receive_pre_prepare('hash_pp2', 'node_1')
        assert pbft._current_block_hash == 'hash_pp2'


class TestReceiveVote:
    def test_wrong_hash_ignored(self, pbft):
        """错误哈希投票忽略"""
        pbft.start_consensus('hash_target')
        vote = ConsensusVote(voter_id='node_1', block_hash='hash_other',
                             phase='prepare', weight=1.0)
        pbft.receive_vote(vote)
        assert 'node_1' not in pbft._votes['prepare']

    def test_records_vote(self, pbft):
        """投票记录"""
        pbft.start_consensus('hash_v')
        vote = ConsensusVote(voter_id='node_1', block_hash='hash_v',
                             phase='prepare', weight=1.0)
        pbft.receive_vote(vote)
        assert 'node_1' in pbft._votes['prepare']

    def test_duplicate_ignored(self, pbft):
        """重复投票忽略"""
        pbft.start_consensus('hash_d')
        vote = ConsensusVote(voter_id='node_1', block_hash='hash_d',
                             phase='prepare', weight=1.0)
        pbft.receive_vote(vote)
        pbft.receive_vote(vote)
        assert len(pbft._votes['prepare']) == 1


class TestVotePath:
    def test_all_votes_threshold(self, pbft):
        """全节点投票达阈值"""
        pbft.start_consensus('hash_t')
        for nid in NODES:
            pbft._votes['prepare'][nid] = ConsensusVote(
                voter_id=nid, block_hash='hash_t', phase='prepare',
                weight=pbft._weights[nid])
        assert pbft._check_weight_threshold('prepare') is True

    def test_partial_votes_below(self, pbft):
        """部分投票未达阈值"""
        pbft.start_consensus('hash_p')
        pbft._votes['prepare']['node_0'] = ConsensusVote(
            voter_id='node_0', block_hash='hash_p', phase='prepare',
            weight=pbft._weights['node_0'])
        assert pbft._check_weight_threshold('prepare') is False

    def test_state_after_start(self, pbft):
        """start_consensus 后 PRE_PREPARE"""
        pbft.start_consensus('hash_s')
        assert pbft.get_state() == ConsensusState.PRE_PREPARE


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
