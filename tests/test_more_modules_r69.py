"""
更多模块剩余边界测试（RalphLoop 原子任务 EL）
覆盖：cw_pbft 统计结构、ecdsa sign/verify 边界（此前未单点覆盖）
通过标准：新增 ≥6 项测试全过
"""
import logging

import pytest

from blockchain.consensus.cw_pbft import CWPBFTConsensus
from blockchain.crypto.ecdsa_utils import ECDSAUtils

logging.basicConfig(level=logging.CRITICAL)

NODES = ['node_0', 'node_1', 'node_2']


@pytest.fixture
def pbft():
    return CWPBFTConsensus('node_0', NODES)


class TestConsensusStats:
    def test_stats_structure(self, pbft):
        """统计结构完整"""
        stats = pbft.get_consensus_stats()
        for key in ['node_id', 'state', 'n_nodes', 'f_tolerance',
                    'prepare_votes', 'commit_votes', 'current_block_hash',
                    'weights', 'consensus_success_rate', 'weight_history',
                    'weight_derivation']:
            assert key in stats

    def test_stats_initial(self, pbft):
        """初始统计：成功率 0、无投票"""
        stats = pbft.get_consensus_stats()
        assert stats['consensus_success_rate'] == 0.0
        assert stats['prepare_votes'] == 0
        assert stats['commit_votes'] == 0
        assert stats['f_tolerance'] == 0  # floor((3-1)/3)

    def test_stats_after_fast_consensus(self, pbft):
        """快速共识后成功率 1"""
        pbft.fast_consensus('hash_fc', 'node_0')
        stats = pbft.get_consensus_stats()
        assert stats['consensus_success_rate'] == 1.0

    def test_stats_weights(self, pbft):
        """权重含全部节点"""
        stats = pbft.get_consensus_stats()
        assert set(stats['weights'].keys()) == set(NODES)


class TestECDSASignVerify:
    def test_sign_verify_roundtrip(self):
        """签名验签往返"""
        priv, pub = ECDSAUtils.generate_key_pair()
        sig = ECDSAUtils.sign(priv, b"message")
        assert ECDSAUtils.verify(pub, b"message", sig) is True

    def test_verify_wrong_message_fails(self):
        """错误消息验签失败"""
        priv, pub = ECDSAUtils.generate_key_pair()
        sig = ECDSAUtils.sign(priv, b"msg_a")
        assert ECDSAUtils.verify(pub, b"msg_b", sig) is False

    def test_verify_wrong_key_fails(self):
        """错误公钥验签失败"""
        priv, _ = ECDSAUtils.generate_key_pair()
        _, other_pub = ECDSAUtils.generate_key_pair()
        sig = ECDSAUtils.sign(priv, b"msg")
        assert ECDSAUtils.verify(other_pub, b"msg", sig) is False

    def test_signature_deterministic(self):
        """同消息同密钥签名确定（RFC6979）"""
        priv, _ = ECDSAUtils.generate_key_pair()
        s1 = ECDSAUtils.sign(priv, b"msg")
        s2 = ECDSAUtils.sign(priv, b"msg")
        assert s1 == s2

    def test_signature_differs_by_message(self):
        """不同消息签名不同"""
        priv, _ = ECDSAUtils.generate_key_pair()
        s1 = ECDSAUtils.sign(priv, b"msg1")
        s2 = ECDSAUtils.sign(priv, b"msg2")
        assert s1 != s2
