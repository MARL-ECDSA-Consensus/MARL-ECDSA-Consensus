"""
更多模块剩余边界测试（RalphLoop 原子任务 DX）
覆盖：signing_service 签名流程、action_recorder 转换/统计（此前未单点覆盖）
通过标准：新增 ≥6 项测试全过
"""
import logging
import shutil
import tempfile
import time

import pytest

from marl.integration.signing_service import SigningService
from marl.integration.action_recorder import ActionRecorder
from blockchain.crypto.key_manager import KeyManager
from blockchain.crypto.security_guard import SecurityGuard

logging.basicConfig(level=logging.CRITICAL)


@pytest.fixture
def keyed():
    key_dir = tempfile.mkdtemp(prefix="test_dx_")
    km = KeyManager(key_dir=key_dir)
    guard = SecurityGuard()
    for i in range(3):
        km.generate_or_load(f"agent_{i}")
    svc = SigningService(key_manager=km, security_guard=guard, n_agents=3)
    yield svc, km
    shutil.rmtree(key_dir, ignore_errors=True)


class TestSigningFlow:
    def test_sign_verify_success(self, keyed):
        """正常签名+校验 → verified True"""
        svc, _ = keyed
        pkg = svc.sign_and_verify("agent_0", [0.1], 1, int(time.time() * 1000))
        assert pkg is not None
        assert pkg.get('verified') is True

    def test_sign_missing_key_returns_none(self, keyed):
        """缺失密钥 → 签名失败返回 None"""
        svc, _ = keyed
        pkg = svc.sign_and_verify("ghost", [0.1], 1, int(time.time() * 1000))
        assert pkg is None  # get_private_key 返回 None → 不签名

    def test_sign_count_increments(self, keyed):
        """签名计数增长"""
        svc, _ = keyed
        for nonce in range(1, 4):
            svc.sign_and_verify("agent_0", [0.1], nonce, int(time.time() * 1000))
        assert svc.get_stats()['ecdsa_sign_count'] == 3

    def test_replay_nonce_intercepted(self, keyed):
        """重复 nonce → verified False"""
        svc, _ = keyed
        ts = int(time.time() * 1000)
        svc.sign_and_verify("agent_0", [0.1], 1, ts)
        pkg2 = svc.sign_and_verify("agent_0", [0.2], 1, ts)
        assert pkg2.get('verified') is False


class TestRecorderConversion:
    def test_pending_to_transaction_full(self):
        """完整 pending → Transaction 映射"""
        ar = ActionRecorder(n_agents=3)
        pending = {
            'agent_id': 'a0', 'step': 3, 'action': [0.5],
            'action_hash': 'hash1', 'env_reward': 1.0,
            'timestamp': 1000, 'nonce': 2, 'signature_hex': '0x' + 'ab' * 32,
            'message_hex': '00', 'r': 1, 's': 2, 'verified': True,
        }
        tx = ar.pending_to_transaction(pending)
        assert tx is not None
        assert tx.agent_id == 'a0'
        assert tx.action_hash == 'hash1'
        assert tx.tx_id == tx.compute_hash()

    def test_pending_to_transaction_minimal(self):
        """最小字段 pending → Transaction"""
        ar = ActionRecorder(n_agents=3)
        pending = {'agent_id': 'a0', 'action_hash': 'h1', 'timestamp': 1000}
        tx = ar.pending_to_transaction(pending)
        assert tx is not None
        assert tx.nonce == 0  # 默认
        assert tx.signature_hex == ''  # 默认

    def test_pending_to_transaction_bad(self):
        """缺必填字段 → None 降级"""
        ar = ActionRecorder(n_agents=3)
        assert ar.pending_to_transaction({}) is None


class TestRecorderStats:
    def test_stats_after_record(self):
        """记录后 pending 统计"""
        ar = ActionRecorder(n_agents=3)
        ar.record_action("a0", 1, [0.1], 1.0, 1000, 1,
                         {'signature_hex': '0x' + 'ab' * 32,
                          'message_hex': '00', 'r': 1, 's': 2, 'verified': True})
        stats = ar.get_stats()
        assert stats['pending_actions'] == 1
        assert stats['tx_count'] == 0

    def test_stats_after_batch(self):
        """批量上链后 tx_count 增长"""
        class _BC:
            def __init__(self):
                self.txs = []
            def add_transaction(self, tx):
                self.txs.append(tx)
        bc = _BC()
        ar = ActionRecorder(bc_node=bc, n_agents=3)
        ar.record_action("a0", 1, [0.1], 1.0, 1000, 1,
                         {'signature_hex': '0x' + 'ab' * 32,
                          'message_hex': '00', 'r': 1, 's': 2, 'verified': True})
        ar.batch_upload()
        stats = ar.get_stats()
        assert stats['pending_actions'] == 0
        assert stats['tx_count'] == 1
