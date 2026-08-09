"""
攻击防御演示集成测试（RalphLoop 原子任务 AB）
覆盖：三种攻击 demo 的返回结构、无BC成功/有BC拦截、报告生成
通过标准：新增 ≥6 项测试全过
"""
import json
import logging
import shutil
import time

import pytest

import attack_defense_demo as demo

logging.basicConfig(level=logging.CRITICAL)


@pytest.fixture(autouse=True)
def cleanup_keys():
    """测试前后清理 keys_demo 临时密钥目录"""
    yield
    shutil.rmtree("./keys_demo", ignore_errors=True)


class TestObservationForgery:
    def test_result_structure(self):
        result = demo.demo_observation_forgery()
        assert result["attack_type"] == "observation_forgery"
        assert "no_bc" in result and "with_bc" in result

    def test_no_bc_success_with_bc_blocked(self):
        result = demo.demo_observation_forgery()
        assert result["no_bc"]["attack_successful"] is True
        assert result["with_bc"]["attack_successful"] is False

    def test_impersonation_blocked(self):
        """冒充他人身份签名被拦截"""
        result = demo.demo_observation_forgery()
        assert result["with_bc"]["impersonation_blocked"] is True


class TestMessageTampering:
    def test_result_structure(self):
        result = demo.demo_message_tampering()
        assert result["attack_type"] == "message_tampering"

    def test_no_bc_success_with_bc_blocked(self):
        result = demo.demo_message_tampering()
        assert result["no_bc"]["attack_successful"] is True
        assert result["with_bc"]["attack_successful"] is False

    def test_tampered_signature_invalid(self):
        """篡改消息的签名验证失败"""
        result = demo.demo_message_tampering()
        assert result["with_bc"]["signature_valid_tampered"] is False


class TestReplayAttack:
    def test_result_structure(self):
        result = demo.demo_replay_attack()
        assert result["attack_type"] == "replay_attack"

    def test_no_bc_success_with_bc_blocked(self):
        result = demo.demo_replay_attack()
        assert result["no_bc"]["attack_successful"] is True
        assert result["with_bc"]["attack_successful"] is False

    def test_replay_blocked_by_guard(self):
        """重放消息被 SecurityGuard 拦截（时间戳过期+nonce 重用）"""
        result = demo.demo_replay_attack()
        assert result["with_bc"]["replay_blocked"] is True
        assert result["with_bc"]["timestamp_expired"] is True


class TestGenerateReport:
    def test_report_summary(self):
        results = [demo.demo_observation_forgery()]
        report = demo.generate_report(results)
        assert report["summary"]["total_attacks"] == 1
        assert report["summary"]["no_bc_success"] == 1
        assert report["summary"]["with_bc_success"] == 0
        assert "100%" in report["summary"]["defense_rate"]

    def test_report_serializable(self):
        """报告可 JSON 序列化（default=str 兜底）"""
        results = [demo.demo_observation_forgery()]
        report = demo.generate_report(results)
        json.dumps(report, default=str)  # 不抛异常
