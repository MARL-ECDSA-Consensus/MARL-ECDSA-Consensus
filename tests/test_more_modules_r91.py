"""
更多模块剩余边界测试（RalphLoop 原子任务 GD）
覆盖：cw_pbft 投票路径/状态、signing_service 统计（此前未单点覆盖）
通过标准：新增 ≥6 项测试全过
"""
import logging
import shutil
import tempfile
import time

import pytest

from blockchain.consensus.cw_pbft import CWPBFTConsensus, ConsensusVote, ConsensusState
from marl.integration.signing_service import SigningService
from blockchain.crypto.key_manager import KeyManager
from blockchain.crypto.security_guard import SecurityGuard

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


class TestSigningStats:
    def test_stats_structure(self):
        """统计字段完整"""
        key_dir = tempfile.mkdtemp(prefix="test_gd_")
        try:
            km = KeyManager(key_dir=key_dir)
            guard = SecurityGuard()
            km.generate_or_load("agent_0")
            svc = SigningService(key_manager=km, security_guard=guard, n_agents=1)
            stats = svc.get_stats()
            for key in ['ecdsa_sign_count', 'ecdsa_verify_count',
                        'security_pass_count', 'security_fail_count']:
                assert key in stats
        finally:
            shutil.rmtree(key_dir, ignore_errors=True)

    def test_stats_after_sign(self):
        """签名后计数增长"""
        key_dir = tempfile.mkdtemp(prefix="test_gd2_")
        try:
            km = KeyManager(key_dir=key_dir)
            guard = SecurityGuard()
            km.generate_or_load("agent_0")
            svc = SigningService(key_manager=km, security_guard=guard, n_agents=1)
            svc.sign_and_verify("agent_0", [0.1], 1, int(time.time() * 1000))
            stats = svc.get_stats()
            assert stats['ecdsa_sign_count'] == 1
            assert stats['security_pass_count'] == 1
        finally:
            shutil.rmtree(key_dir, ignore_errors=True)

    def test_stats_after_replay(self):
        """重放拦截后 fail 计数"""
        key_dir = tempfile.mkdtemp(prefix="test_gd3_")
        try:
            km = KeyManager(key_dir=key_dir)
            guard = SecurityGuard()
            km.generate_or_load("agent_0")
            svc = SigningService(key_manager=km, security_guard=guard, n_agents=1)
            ts = int(time.time() * 1000)
            svc.sign_and_verify("agent_0", [0.1], 1, ts)
            svc.sign_and_verify("agent_0", [0.2], 1, ts)  # 重复 nonce
            assert svc.get_stats()['security_fail_count'] == 1
        finally:
            shutil.rmtree(key_dir, ignore_errors=True)
