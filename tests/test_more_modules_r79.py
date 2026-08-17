"""
更多模块剩余边界测试（RalphLoop 原子任务 FF）
覆盖：cw_pbft 权重边界、signing_service 统计（此前未单点覆盖）
通过标准：新增 ≥6 项测试全过
"""
import logging
import shutil
import tempfile
import time

import pytest

from blockchain.consensus.cw_pbft import CWPBFTConsensus
from marl.integration.signing_service import SigningService
from blockchain.crypto.key_manager import KeyManager
from blockchain.crypto.security_guard import SecurityGuard

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

    def test_weights_copy(self, pbft):
        """get_weights 返回副本"""
        weights = pbft.get_weights()
        weights['node_1'] = 99.0
        assert pbft.get_weights()['node_1'] != 99.0


class TestSigningStats:
    def test_stats_structure(self):
        """统计字段完整"""
        key_dir = tempfile.mkdtemp(prefix="test_ff_")
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

    def test_stats_initial_zero(self):
        """初始统计为零"""
        key_dir = tempfile.mkdtemp(prefix="test_ff2_")
        try:
            km = KeyManager(key_dir=key_dir)
            guard = SecurityGuard()
            km.generate_or_load("agent_0")
            svc = SigningService(key_manager=km, security_guard=guard, n_agents=1)
            stats = svc.get_stats()
            assert stats['ecdsa_sign_count'] == 0
            assert stats['security_pass_count'] == 0
            assert stats['security_fail_count'] == 0
        finally:
            shutil.rmtree(key_dir, ignore_errors=True)

    def test_stats_after_sign(self):
        """签名后计数增长"""
        key_dir = tempfile.mkdtemp(prefix="test_ff3_")
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
        key_dir = tempfile.mkdtemp(prefix="test_ff4_")
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
