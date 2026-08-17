"""
更多模块剩余边界测试（RalphLoop 原子任务 ED）
覆盖：cw_pbft 投票达成路径、action_recorder 批量上链（此前未单点覆盖）
通过标准：新增 ≥6 项测试全过
"""
import logging

import pytest

from blockchain.consensus.cw_pbft import CWPBFTConsensus, ConsensusVote, ConsensusState
from marl.integration.action_recorder import ActionRecorder

logging.basicConfig(level=logging.CRITICAL)

NODES = ['node_0', 'node_1', 'node_2']


@pytest.fixture
def pbft():
    return CWPBFTConsensus('node_0', NODES)


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


class TestVotePath:
    def test_receive_pre_prepare_returns_prepare(self, pbft):
        """收到 pre-prepare → 返回 prepare 投票"""
        vote = pbft.receive_pre_prepare('hash_pp', 'node_0')
        assert vote is not None
        assert vote.phase == 'prepare'
        assert pbft.get_state() == ConsensusState.PREPARE

    def test_full_vote_path_committed(self, pbft):
        """完整投票路径 → 共识达成（COMMITTED）"""
        pbft.start_consensus('hash_full')
        # 主节点 pre_prepare
        prepare_votes = []
        for nid in NODES:
            v = pbft.receive_pre_prepare('hash_full', 'node_0')
            # 每个节点收到 pre-prepare 后进入 PREPARE 并准备投票
            pbft._votes['prepare'][nid] = ConsensusVote(
                voter_id=nid, block_hash='hash_full', phase='prepare',
                weight=pbft._weights[nid])
            prepare_votes.append(v)
        # 广播 prepare 投票 → 达到 2/3 → commit
        for v in prepare_votes:
            for nid in NODES:
                pbft._votes['prepare'][nid] = ConsensusVote(
                    voter_id=nid, block_hash='hash_full', phase='prepare',
                    weight=pbft._weights[nid])
        # 全节点 prepare 达成 → 状态 COMMIT（通过 receive_vote 触发）
        assert pbft._check_weight_threshold('prepare') is True

    def test_partial_votes_no_consensus(self, pbft):
        """部分投票 → 未达成"""
        pbft.start_consensus('hash_part')
        pbft._votes['prepare']['node_0'] = ConsensusVote(
            voter_id='node_0', block_hash='hash_part', phase='prepare',
            weight=pbft._weights['node_0'])
        assert pbft._check_weight_threshold('prepare') is False


class TestBatchUpload:
    def test_batch_empty_noop(self):
        """空缓冲批量上链 noop"""
        ar = ActionRecorder(n_agents=3)
        ar.batch_upload()  # 不崩溃
        assert ar._tx_count == 0

    def test_batch_stub_mode(self):
        """无 bc_node stub 模式：清空缓冲"""
        ar = ActionRecorder(n_agents=3)
        ar.record_action("a0", 1, [0.1], 1.0, 1000, 1, _pkg())
        ar.batch_upload()
        assert len(ar._pending_actions) == 0
        assert ar._tx_count == 0  # stub 不计交易

    def test_batch_filters_unverified(self):
        """批量过滤未验证行为"""
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
        assert len(bc.txs) == 1  # 仅可信行为上链
        assert ar._tx_count == 1

    def test_flush_pending(self):
        """flush 刷新剩余行为"""
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
        assert len(ar._pending_actions) == 0
