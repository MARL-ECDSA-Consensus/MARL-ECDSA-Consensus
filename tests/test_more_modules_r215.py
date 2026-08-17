"""
更多模块剩余边界测试（RalphLoop 原子任务 PR）
覆盖：cw_pbft 权重边界/共识统计、incentive 结算排名（此前未单点覆盖）
通过标准：新增 ≥6 项测试全过
"""
import logging

import pytest

from blockchain.consensus.cw_pbft import CWPBFTConsensus, ConsensusState
from blockchain.ledger.world_state import WorldState
from blockchain.contracts.incentive_contract import IncentiveContract, ContributionScore

logging.basicConfig(level=logging.CRITICAL)

NODES = ['node_0', 'node_1', 'node_2']


@pytest.fixture
def pbft():
    return CWPBFTConsensus('node_0', NODES)


class TestWeightEdge:
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

    def test_weights_copy(self, pbft):
        """get_weights 返回副本"""
        weights = pbft.get_weights()
        weights['node_1'] = 99.0
        assert pbft.get_weights()['node_1'] != 99.0

    def test_weight_history_recorded(self, pbft):
        """权重历史记录"""
        pbft.update_weight('node_1', 0.8)
        assert len(pbft.get_weight_history()) == 1
        assert pbft.get_weight_history()[0]['weights']['node_1'] == 0.8


class TestConsensusStats:
    def test_stats_structure(self, pbft):
        """统计结构完整"""
        stats = pbft.get_consensus_stats()
        for key in ['node_id', 'state', 'n_nodes', 'f_tolerance',
                    'prepare_votes', 'commit_votes', 'current_block_hash',
                    'weights', 'consensus_success_rate', 'weight_history',
                    'weight_derivation']:
            assert key in stats

    def test_stats_initial_zero(self, pbft):
        """初始统计零值"""
        stats = pbft.get_consensus_stats()
        assert stats['consensus_success_rate'] == 0.0
        assert stats['prepare_votes'] == 0
        assert stats['state'] == ConsensusState.IDLE

    def test_stats_after_fast(self, pbft):
        """快速共识后成功率 1"""
        pbft.fast_consensus('hash_fc', 'node_0')
        assert pbft.get_consensus_stats()['consensus_success_rate'] == 1.0


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
