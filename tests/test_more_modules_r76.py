"""
更多模块剩余边界测试（RalphLoop 原子任务 EZ）
覆盖：signing_service 签名流程、world_state 行为记录（此前未单点覆盖）
通过标准：新增 ≥6 项测试全过
"""
import logging
import shutil
import tempfile
import time

import pytest

from marl.integration.signing_service import SigningService
from blockchain.crypto.key_manager import KeyManager
from blockchain.crypto.security_guard import SecurityGuard
from blockchain.ledger.world_state import WorldState

logging.basicConfig(level=logging.CRITICAL)


@pytest.fixture
def keyed():
    key_dir = tempfile.mkdtemp(prefix="test_ez_")
    km = KeyManager(key_dir=key_dir)
    guard = SecurityGuard()
    for i in range(3):
        km.generate_or_load(f"agent_{i}")
    svc = SigningService(key_manager=km, security_guard=guard, n_agents=3)
    yield svc, km
    shutil.rmtree(key_dir, ignore_errors=True)


class TestSigning:
    def test_sign_verify_success(self, keyed):
        """正常签名+校验 → verified True"""
        svc, _ = keyed
        pkg = svc.sign_and_verify("agent_0", [0.1], 1, int(time.time() * 1000))
        assert pkg is not None
        assert pkg.get('verified') is True

    def test_sign_missing_key(self, keyed):
        """缺失密钥 → None"""
        svc, _ = keyed
        pkg = svc.sign_and_verify("ghost", [0.1], 1, int(time.time() * 1000))
        assert pkg is None

    def test_stats_count(self, keyed):
        """签名计数"""
        svc, _ = keyed
        for nonce in range(1, 3):
            svc.sign_and_verify("agent_0", [0.1], nonce, int(time.time() * 1000))
        assert svc.get_stats()['ecdsa_sign_count'] == 2

    def test_replay_blocked(self, keyed):
        """重复 nonce 拦截"""
        svc, _ = keyed
        ts = int(time.time() * 1000)
        svc.sign_and_verify("agent_0", [0.1], 1, ts)
        pkg2 = svc.sign_and_verify("agent_0", [0.2], 1, ts)
        assert pkg2.get('verified') is False


class TestRecordAction:
    def test_action_accumulates(self):
        """行为哈希累积"""
        ws = WorldState()
        ws.register_agent("a0", "0x" + "ab" * 32)
        ws.record_action("a0", "h1", 3)
        ws.record_action("a0", "h2", 5)
        assert ws._behaviors["a0"].action_hashes == ["h1", "h2"]
        assert ws._behaviors["a0"].last_active_block == 5

    def test_action_unregistered_noop(self):
        """未注册行为 noop"""
        ws = WorldState()
        ws.record_action("ghost", "h1", 1)  # 不崩溃

    def test_betrayal_rounds(self):
        """背叛轮次记录"""
        ws = WorldState()
        ws.register_agent("a0", "0x" + "ab" * 32)
        ws.record_betrayal("a0", 7)
        assert ws._behaviors["a0"].betrayal_rounds == [7]
        assert ws.get_betrayal_count("a0") == 1

    def test_betrayal_unregistered(self):
        """未注册背叛 noop"""
        ws = WorldState()
        ws.record_betrayal("ghost", 1)  # 不崩溃
        assert ws.get_betrayal_count("ghost") == 0


class TestScoreFlow:
    def test_score_contribution(self):
        """积分/贡献联动"""
        ws = WorldState()
        ws.register_agent("a0", "0x" + "ab" * 32)
        ws.add_score("a0", 10.0)
        ws.add_score("a0", -3.0)
        assert ws.get_score("a0") == 7.0
        assert ws.get_contribution("a0") == 10.0  # 仅正增量

    def test_get_score_unregistered(self):
        """未注册积分 KeyError（P2-13 契约）"""
        ws = WorldState()
        with pytest.raises(KeyError):
            ws.get_score("ghost")
