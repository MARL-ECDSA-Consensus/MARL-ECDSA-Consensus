"""
更多模块剩余边界测试（RalphLoop 原子任务 HB）
覆盖：cw_pbft 权重边界/共识统计、signing_service 统计（此前未单点覆盖）
通过标准：新增 ≥6 项测试全过
"""
import logging
import shutil
import tempfile
import time

import pytest

from blockchain.consensus.cw_pbft import CWPBFTConsensus, ConsensusState
from marl.integration.signing_service import SigningService
from blockchain.crypto.key_manager import KeyManager
from blockchain.crypto.security_guard import SecurityGuard

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


class TestSigningStats:
    def test_stats_structure(self):
        """统计字段完整"""
        key_dir = tempfile.mkdtemp(prefix="test_hb_")
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
        key_dir = tempfile.mkdtemp(prefix="test_hb2_")
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
        key_dir = tempfile.mkdtemp(prefix="test_hb3_")
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
