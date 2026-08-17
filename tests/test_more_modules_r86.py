"""
更多模块剩余边界测试（RalphLoop 原子任务 FT）
覆盖：world_state 积分/状态、signing_service 验签（此前未单点覆盖）
通过标准：新增 ≥6 项测试全过
"""
import logging
import shutil
import tempfile
import time

import pytest

from blockchain.ledger.world_state import WorldState, AgentStatus
from marl.integration.signing_service import SigningService
from blockchain.crypto.key_manager import KeyManager
from blockchain.crypto.security_guard import SecurityGuard

logging.basicConfig(level=logging.CRITICAL)


class TestScore:
    def test_add_score_positive(self):
        """正增量计入累计贡献"""
        ws = WorldState()
        ws.register_agent("a0", "0x" + "ab" * 32)
        ws.add_score("a0", 10.0)
        assert ws.get_score("a0") == 10.0
        assert ws.get_contribution("a0") == 10.0

    def test_add_score_negative(self):
        """负增量不计入累计贡献"""
        ws = WorldState()
        ws.register_agent("a0", "0x" + "ab" * 32)
        ws.add_score("a0", -5.0)
        assert ws.get_score("a0") == -5.0
        assert ws.get_contribution("a0") == 0.0

    def test_add_score_unregistered_noop(self):
        """未注册 add_score noop"""
        ws = WorldState()
        ws.add_score("ghost", 5.0)  # 不崩溃
        assert "ghost" not in ws.get_all_scores()

    def test_get_score_unregistered_raises(self):
        """未注册 get_score KeyError（P2-13 契约）"""
        ws = WorldState()
        with pytest.raises(KeyError):
            ws.get_score("ghost")


class TestStatusWeight:
    def test_set_status(self):
        """状态设置/查询"""
        ws = WorldState()
        ws.register_agent("a0", "0x" + "ab" * 32)
        ws.set_agent_status("a0", AgentStatus.BANNED)
        assert ws.get_agent_status("a0") == AgentStatus.BANNED
        assert ws.is_active("a0") is False

    def test_update_weight(self):
        """权重更新/查询"""
        ws = WorldState()
        ws.register_agent("a0", "0x" + "ab" * 32)
        ws.update_consensus_weight("a0", 0.7)
        assert ws.get_consensus_weight("a0") == 0.7

    def test_update_weight_unregistered(self):
        """未注册权重更新 noop"""
        ws = WorldState()
        ws.update_consensus_weight("ghost", 0.5)  # 不崩溃
        assert ws.get_consensus_weight("ghost") == 0.0


class TestSigningVerify:
    def test_verify_no_bc(self):
        """无 bc_node → 直接返回"""
        key_dir = tempfile.mkdtemp(prefix="test_ft_")
        try:
            km = KeyManager(key_dir=key_dir)
            km.generate_or_load("a0")
            svc = SigningService(key_manager=km, n_agents=1)
            svc.verify_episode_transactions(None)  # 不崩溃
        finally:
            shutil.rmtree(key_dir, ignore_errors=True)

    def test_verify_empty_pool(self):
        """空交易池 → 验签数不增长"""
        key_dir = tempfile.mkdtemp(prefix="test_ft2_")
        try:
            km = KeyManager(key_dir=key_dir)
            km.generate_or_load("a0")
            svc = SigningService(key_manager=km, n_agents=1)
            class _BC:
                def get_pending_transactions(self):
                    return []
            svc.verify_episode_transactions(_BC())
            assert svc.get_stats()["ecdsa_verify_count"] == 0
        finally:
            shutil.rmtree(key_dir, ignore_errors=True)

    def test_verify_no_sig_skipped(self):
        """无签名交易跳过"""
        key_dir = tempfile.mkdtemp(prefix="test_ft3_")
        try:
            km = KeyManager(key_dir=key_dir)
            km.generate_or_load("a0")
            svc = SigningService(key_manager=km, n_agents=1)
            tx = type("Tx", (), {
                "agent_id": "a0", "action": [0.1], "timestamp": 1000,
                "nonce": 1, "signature_hex": "", "extra": {},
                "tx_id": "tx1",
            })()
            class _BC:
                def get_pending_transactions(self):
                    return [tx]
            svc.verify_episode_transactions(_BC())
            assert svc.get_stats()["ecdsa_verify_count"] == 0
        finally:
            shutil.rmtree(key_dir, ignore_errors=True)

    def test_verify_unknown_agent_skipped(self):
        """未知 agent 交易跳过（无公钥）"""
        key_dir = tempfile.mkdtemp(prefix="test_ft4_")
        try:
            km = KeyManager(key_dir=key_dir)
            svc = SigningService(key_manager=km, n_agents=1)
            tx = type("Tx", (), {
                "agent_id": "unknown", "action": [0.1], "timestamp": 1000,
                "nonce": 1, "signature_hex": "0x" + "ab" * 32, "extra": {},
                "tx_id": "tx2",
            })()
            class _BC:
                def get_pending_transactions(self):
                    return [tx]
            svc.verify_episode_transactions(_BC())
            assert svc.get_stats()["ecdsa_verify_count"] == 0
        finally:
            shutil.rmtree(key_dir, ignore_errors=True)
