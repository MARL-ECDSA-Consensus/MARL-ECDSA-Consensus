"""
更多模块剩余边界测试（RalphLoop 原子任务 DT）
覆盖：security_guard check_package 综合校验、ecdsa 消息构造/验签（此前未单点覆盖）
通过标准：新增 ≥6 项测试全过
"""
import hashlib
import logging
import time

import pytest

from blockchain.crypto.security_guard import SecurityGuard
from blockchain.crypto.ecdsa_utils import ECDSAUtils

logging.basicConfig(level=logging.CRITICAL)


def _pkg(agent_id="agent_0", ts=None, nonce=1, r=0x1000):
    return {
        "agent_id": agent_id,
        "timestamp": ts if ts is not None else int(time.time() * 1000),
        "nonce": nonce,
        "r": r,
    }


class TestCheckPackage:
    def test_valid_package_ok(self):
        """合法包 → OK"""
        guard = SecurityGuard()
        ok, reason = guard.check_package(_pkg())
        assert ok is True
        assert reason == 'OK'

    def test_expired_timestamp_fails(self):
        """过期时间戳 → 拦截"""
        guard = SecurityGuard()
        ok, reason = guard.check_package(_pkg(ts=int(time.time() * 1000) - 60000))
        assert ok is False
        assert "时间戳" in reason

    def test_nonce_replay_fails(self):
        """重复 nonce → 拦截"""
        guard = SecurityGuard()
        guard.check_package(_pkg(nonce=1))
        ok, reason = guard.check_package(_pkg(nonce=1, r=0x2000))
        assert ok is False
        assert "重放" in reason

    def test_r_reuse_fails(self):
        """k 值重用 → 拦截"""
        guard = SecurityGuard()
        guard.check_package(_pkg(nonce=1, r=0x3333))
        ok, reason = guard.check_package(_pkg(nonce=2, r=0x3333))
        assert ok is False
        assert "重用" in reason

    def test_fail_records_alert(self):
        """拦截后告警记录"""
        guard = SecurityGuard()
        guard.check_package(_pkg(ts=int(time.time() * 1000) - 60000))
        assert len(guard.get_alerts("agent_0")) == 1
        assert guard.get_fail_count("agent_0") == 1


class TestBuildMessage:
    def test_build_message_deterministic(self):
        """消息构造确定性"""
        m1 = ECDSAUtils.build_message("agent_0", [0.5], 1000, 1)
        m2 = ECDSAUtils.build_message("agent_0", [0.5], 1000, 1)
        assert m1 == m2

    def test_build_message_differs_by_nonce(self):
        """nonce 不同 → 消息不同"""
        m1 = ECDSAUtils.build_message("agent_0", [0.5], 1000, 1)
        m2 = ECDSAUtils.build_message("agent_0", [0.5], 1000, 2)
        assert m1 != m2

    def test_build_message_contains_hash(self):
        """消息含 action_hash（32 字节）"""
        msg = ECDSAUtils.build_message("agent_0", [0.5], 1000, 1)
        import json
        payload = json.loads(msg.decode('utf-8'))
        assert len(payload['action_hash']) == 64  # SHA-256 hex


class TestVerifyAction:
    def test_verify_roundtrip(self):
        """签名包验签往返"""
        priv, pub = ECDSAUtils.generate_key_pair()
        pkg = ECDSAUtils.sign_action("agent_0", priv, [0.5], nonce=3)
        assert ECDSAUtils.verify_action_package(pkg, pub) is True

    def test_verify_wrong_key_fails(self):
        """错误公钥验签失败"""
        priv, _ = ECDSAUtils.generate_key_pair()
        _, other_pub = ECDSAUtils.generate_key_pair()
        pkg = ECDSAUtils.sign_action("agent_0", priv, [0.5], nonce=3)
        assert ECDSAUtils.verify_action_package(pkg, other_pub) is False

    def test_pubkey_hex_roundtrip(self):
        """公钥 hex 往返"""
        _, pub = ECDSAUtils.generate_key_pair()
        hex_str = ECDSAUtils.public_key_to_hex(pub)
        restored = ECDSAUtils.public_key_from_hex(hex_str)
        assert restored.public_numbers().x == pub.public_numbers().x
