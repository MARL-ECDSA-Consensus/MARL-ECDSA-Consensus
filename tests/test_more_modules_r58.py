"""
更多模块剩余边界测试（RalphLoop 原子任务 DP）
覆盖：cw_pbft 超时/重置、incentive 排行榜/统计（此前未单点覆盖）
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


class TestTimeout:
    def test_not_started_not_timed_out(self, pbft):
        """未启动共识 → 不超时"""
        assert pbft.is_timed_out() is False

    def test_started_not_timed_out(self, pbft):
        """刚启动 → 未超时"""
        pbft.start_consensus('hash_t')
        assert pbft.is_timed_out() is False

    def test_timeout_threshold(self, pbft):
        """超过超时阈值 → 超时（_consensus_start_ms=0 是未启动哨兵，不能用来模拟）"""
        import time
        pbft.start_consensus('hash_t2')
        # 把起始时间设为很久以前（超时阈值 + 1s），elapsed 必超阈值
        pbft._consensus_start_ms = int(time.time() * 1000) - pbft.CONSENSUS_TIMEOUT_MS - 1000
        assert pbft.is_timed_out() is True


class TestReset:
    def test_reset_clears_state(self, pbft):
        """reset 清空状态/投票/哈希"""
        pbft.start_consensus('hash_r')
        pbft.reset()
        assert pbft.get_state() == ConsensusState.IDLE
        assert pbft._current_block_hash is None
        assert pbft._votes == {'prepare': {}, 'commit': {}}
        assert pbft._consensus_start_ms == 0

    def test_reset_then_restart(self, pbft):
        """reset 后可重新发起共识"""
        pbft.start_consensus('hash_a')
        pbft.reset()
        pbft.start_consensus('hash_b')
        assert pbft.get_state() == ConsensusState.PRE_PREPARE
        assert pbft._current_block_hash == 'hash_b'


class TestLeaderboard:
    def test_leaderboard_sorted_desc(self):
        """排行榜按积分降序"""
        ws = WorldState()
        for i in range(3):
            ws.register_agent(f"agent_{i}", f"0x{'ab' * 32}")
        ws.add_score("agent_0", 5.0)
        ws.add_score("agent_1", 15.0)
        ws.add_score("agent_2", 10.0)
        contract = IncentiveContract(ws)
        board = contract.get_leaderboard()
        scores = [s for _, s in board]
        assert scores == sorted(scores, reverse=True)
        assert board[0][0] == "agent_1"  # 最高分

    def test_leaderboard_empty(self):
        """空排行榜"""
        ws = WorldState()
        contract = IncentiveContract(ws)
        assert contract.get_leaderboard() == []


class TestIncentiveStats:
    def test_stats_structure(self):
        """get_stats 含全部字段"""
        ws = WorldState()
        ws.register_agent("agent_0", "0x" + "ab" * 32)
        contract = IncentiveContract(ws)
        stats = contract.get_stats()
        for key in ['total_agents', 'avg_score', 'max_score',
                    'min_score', 'settled_blocks']:
            assert key in stats

    def test_stats_empty_ws(self):
        """空 WorldState 统计（除零保护）"""
        ws = WorldState()
        contract = IncentiveContract(ws)
        stats = contract.get_stats()
        assert stats['total_agents'] == 0
        assert stats['avg_score'] == 0  # 空时不除零
        assert stats['settled_blocks'] == 0

    def test_stats_after_settlement(self):
        """结算后 settled_blocks 增长"""
        ws = WorldState()
        ws.register_agent("agent_0", "0x" + "ab" * 32)
        contract = IncentiveContract(ws)
        scores = [ContributionScore("agent_0", 0.5, 1.0, 1.0)]
        contract.settle_rewards(1, scores)
        contract.settle_rewards(2, scores)
        stats = contract.get_stats()
        assert stats['settled_blocks'] == 2
        assert stats['total_agents'] == 1
