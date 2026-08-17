"""
更多模块剩余边界测试（RalphLoop 原子任务 FL）
覆盖：cw_pbft 投票路径、incentive 结算排名（此前未单点覆盖）
通过标准：新增 ≥6 项测试全过
"""
import logging

import pytest

from blockchain.consensus.cw_pbft import CWPBFTConsensus, ConsensusVote, ConsensusState
from blockchain.ledger.world_state import WorldState
from blockchain.contracts.incentive_contract import IncentiveContract, ContributionScore

logging.basicConfig(level=logging.CRITICAL)

NODES = ['node_0', 'node_1', 'node_2']


@pytest.fixture
def pbft():
    return CWPBFTConsensus('node_0', NODES)


class TestPrePrepare:
    def test_receive_pre_prepare_returns_prepare(self, pbft):
        """收到 pre-prepare → 返回 prepare 投票"""
        vote = pbft.receive_pre_prepare('hash_pp', 'node_0')
        assert vote is not None
        assert vote.phase == 'prepare'
        assert pbft.get_state() == ConsensusState.PREPARE

    def test_receive_pre_prepare_sets_hash(self, pbft):
        """pre-prepare 设置当前区块哈希"""
        pbft.receive_pre_prepare('hash_pp2', 'node_1')
        assert pbft._current_block_hash == 'hash_pp2'


class TestReceiveVote:
    def test_receive_wrong_hash_ignored(self, pbft):
        """错误哈希投票忽略"""
        pbft.start_consensus('hash_target')
        vote = ConsensusVote(voter_id='node_1', block_hash='hash_other',
                             phase='prepare', weight=1.0)
        pbft.receive_vote(vote)
        assert 'node_1' not in pbft._votes['prepare']

    def test_receive_records(self, pbft):
        """投票记录"""
        pbft.start_consensus('hash_v')
        vote = ConsensusVote(voter_id='node_1', block_hash='hash_v',
                             phase='prepare', weight=1.0)
        pbft.receive_vote(vote)
        assert 'node_1' in pbft._votes['prepare']

    def test_receive_duplicate_ignored(self, pbft):
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
        assert deltas["agent_0"] >= 10.0

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

    def test_history_query(self):
        """结算历史查询"""
        ws = WorldState()
        ws.register_agent("agent_0", "0x" + "ab" * 32)
        contract = IncentiveContract(ws)
        cs = ContributionScore("agent_0", 0.5, 1.0, 1.0)
        contract.settle_rewards(5, [cs])
        history = contract.get_settlement_history(5)
        assert len(history) == 1
        assert history[0]["agent_id"] == "agent_0"
