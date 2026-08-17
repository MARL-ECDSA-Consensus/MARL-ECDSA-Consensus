"""
更多模块剩余边界测试（RalphLoop 原子任务 ET）
覆盖：security_guard 告警/风险、signing_service 验签（此前未单点覆盖）
通过标准：新增 ≥6 项测试全过
"""
import hashlib
import logging
import shutil
import tempfile
import time

import pytest

from blockchain.crypto.security_guard import SecurityGuard
from blockchain.crypto.key_manager import KeyManager
from marl.integration.signing_service import SigningService

logging.basicConfig(level=logging.CRITICAL)


def _pkg(agent_id="agent_0", ts=None, nonce=1, r=0x1000):
    return {
        "agent_id": agent_id,
        "timestamp": ts if ts is not None else int(time.time() * 1000),
        "nonce": nonce,
        "r": r,
    }


class TestAlerts:
    def test_alerts_filtered_by_agent(self):
        """按 agent 过滤告警"""
        guard = SecurityGuard()
        guard.check_package(_pkg(agent_id="a0", ts=int(time.time() * 1000) - 60000))
        guard.check_package(_pkg(agent_id="a1", ts=int(time.time() * 1000) - 60000))
        a0_alerts = guard.get_alerts("a0")
        assert len(a0_alerts) == 1
        assert a0_alerts[0]["agent_id"] == "a0"
        assert len(guard.get_alerts()) == 2

    def test_alerts_empty_initial(self):
        """初始无告警"""
        guard = SecurityGuard()
        assert guard.get_alerts() == []


class TestRiskLevel:
    def test_risk_normal(self):
        """0 失败 → NORMAL"""
        guard = SecurityGuard()
        assert guard.get_risk_level("a0") == "NORMAL"

    def test_risk_warning(self):
        """2 失败 → WARNING（_pkg 默认 agent_id=agent_0）"""
        guard = SecurityGuard()
        for i in range(2):
            guard.check_package(_pkg(nonce=i, ts=int(time.time() * 1000) - 60000))
        assert guard.get_risk_level("agent_0") == "WARNING"

    def test_risk_danger(self):
        """5 失败 → DANGER（_pkg 默认 agent_id=agent_0）"""
        guard = SecurityGuard()
        for i in range(5):
            guard.check_package(_pkg(nonce=i, ts=int(time.time() * 1000) - 60000))
        assert guard.get_risk_level("agent_0") == "DANGER"

    def test_fail_count(self):
        """失败计数（_pkg 默认 agent_id=agent_0）"""
        guard = SecurityGuard()
        guard.check_package(_pkg(ts=int(time.time() * 1000) - 60000))
        assert guard.get_fail_count("agent_0") == 1
        assert guard.get_fail_count("ghost") == 0


class TestSigningVerify:
    def test_verify_no_bc(self):
        """无 bc_node → 直接返回"""
        key_dir = tempfile.mkdtemp(prefix="test_et_")
        try:
            km = KeyManager(key_dir=key_dir)
            km.generate_or_load("a0")
            svc = SigningService(key_manager=km, n_agents=1)
            svc.verify_episode_transactions(None)  # 不崩溃
        finally:
            shutil.rmtree(key_dir, ignore_errors=True)

    def test_verify_empty_pool(self):
        """空交易池 → 验签数不增长"""
        key_dir = tempfile.mkdtemp(prefix="test_et2_")
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
        key_dir = tempfile.mkdtemp(prefix="test_et3_")
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
            assert svc.get_stats()["ecdsa_verify_count"] == 0  # 无签名跳过
        finally:
            shutil.rmtree(key_dir, ignore_errors=True)
