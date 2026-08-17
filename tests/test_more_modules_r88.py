"""
更多模块剩余边界测试（RalphLoop 原子任务 FX）
覆盖：security_guard check_package 综合、identity 注册校验（此前未单点覆盖）
通过标准：新增 ≥6 项测试全过
"""
import logging
import time

import pytest

from blockchain.crypto.security_guard import SecurityGuard
from blockchain.ledger.world_state import WorldState
from blockchain.contracts.identity_contract import IdentityContract

logging.basicConfig(level=logging.CRITICAL)

VALID_PK = "04" + "ab" * 64


def _pkg(agent_id="agent_0", ts=None, nonce=1, r=0x1000):
    return {
        "agent_id": agent_id,
        "timestamp": ts if ts is not None else int(time.time() * 1000),
        "nonce": nonce,
        "r": r,
    }


class TestCheckPackage:
    def test_valid_ok(self):
        """合法包 OK"""
        guard = SecurityGuard()
        ok, reason = guard.check_package(_pkg())
        assert ok is True
        assert reason == 'OK'

    def test_expired_fails(self):
        """过期时间戳拦截"""
        guard = SecurityGuard()
        ok, _ = guard.check_package(_pkg(ts=int(time.time() * 1000) - 60000))
        assert ok is False

    def test_nonce_replay_fails(self):
        """nonce 重放拦截"""
        guard = SecurityGuard()
        guard.check_package(_pkg(nonce=1))
        ok, _ = guard.check_package(_pkg(nonce=1, r=0x2000))
        assert ok is False

    def test_r_reuse_fails(self):
        """k 重用拦截"""
        guard = SecurityGuard()
        guard.check_package(_pkg(nonce=1, r=0x3333))
        ok, _ = guard.check_package(_pkg(nonce=2, r=0x3333))
        assert ok is False

    def test_fail_alert_recorded(self):
        """拦截后告警/风险"""
        guard = SecurityGuard()
        guard.check_package(_pkg(ts=int(time.time() * 1000) - 60000))
        assert len(guard.get_alerts("agent_0")) == 1
        assert guard.get_fail_count("agent_0") == 1
        assert guard.get_risk_level("agent_0") == "WARNING"


class TestRegisterValidation:
    def test_register_valid(self):
        """正常注册"""
        ws = WorldState()
        ic = IdentityContract(ws)
        assert ic.register("a0", VALID_PK)["success"] is True
        assert ic.get_public_key("a0") == VALID_PK

    def test_register_none_agent(self):
        """None agent_id 拒绝（P3-11）"""
        ws = WorldState()
        ic = IdentityContract(ws)
        r = ic.register(None, VALID_PK)
        assert r["success"] is False
        assert "不能为空" in r["error"]

    def test_register_none_pk(self):
        """None 公钥拒绝"""
        ws = WorldState()
        ic = IdentityContract(ws)
        r = ic.register("a0", None)
        assert r["success"] is False
        assert "公钥" in r["error"]

    def test_register_bad_format(self):
        """非法公钥格式拒绝"""
        ws = WorldState()
        ic = IdentityContract(ws)
        r = ic.register("a0", "not_hex")
        assert r["success"] is False
        assert "格式" in r["error"]

    def test_register_duplicate(self):
        """重复注册拒绝"""
        ws = WorldState()
        ic = IdentityContract(ws)
        ic.register("a0", VALID_PK)
        r = ic.register("a0", VALID_PK)
        assert r["success"] is False
        assert "已注册" in r["error"]


class TestPubkeyFormat:
    def test_130_hex_valid(self):
        """130 字符非压缩公钥合法"""
        assert IdentityContract._validate_public_key("04" + "ab" * 64) is True

    def test_66_hex_valid(self):
        """66 字符压缩公钥合法"""
        assert IdentityContract._validate_public_key("02" + "cd" * 32) is True

    def test_invalid_rejected(self):
        """非法长度/空/None 拒绝"""
        assert IdentityContract._validate_public_key("04" + "ab" * 10) is False
        assert IdentityContract._validate_public_key("") is False
        assert IdentityContract._validate_public_key(None) is False
