"""
更多模块剩余边界测试（RalphLoop 原子任务 EH）
覆盖：world_state 积分/状态、identity 注册/状态（此前未单点覆盖）
通过标准：新增 ≥6 项测试全过
"""
import logging

import pytest

from blockchain.ledger.world_state import WorldState, AgentStatus
from blockchain.contracts.identity_contract import IdentityContract, ContractCaller

logging.basicConfig(level=logging.CRITICAL)

VALID_PK = "04" + "ab" * 64


class TestWorldScore:
    def test_add_score_positive_contribution(self):
        """正增量计入累计贡献"""
        ws = WorldState()
        ws.register_agent("a0", "0x" + "ab" * 32)
        ws.add_score("a0", 10.0)
        assert ws.get_score("a0") == 10.0
        assert ws.get_contribution("a0") == 10.0

    def test_add_score_negative_no_contribution(self):
        """负增量不计入累计贡献"""
        ws = WorldState()
        ws.register_agent("a0", "0x" + "ab" * 32)
        ws.add_score("a0", -5.0)
        assert ws.get_score("a0") == -5.0
        assert ws.get_contribution("a0") == 0.0

    def test_get_score_unregistered_raises(self):
        """未注册 get_score → KeyError（P2-13 契约）"""
        ws = WorldState()
        with pytest.raises(KeyError):
            ws.get_score("ghost")

    def test_add_score_unregistered_noop(self):
        """未注册 add_score → noop"""
        ws = WorldState()
        ws.add_score("ghost", 5.0)  # 不崩溃
        assert "ghost" not in ws.get_all_scores()


class TestWorldStatus:
    def test_update_weight(self):
        """权重更新"""
        ws = WorldState()
        ws.register_agent("a0", "0x" + "ab" * 32)
        ws.update_consensus_weight("a0", 0.7)
        assert ws.get_consensus_weight("a0") == 0.7

    def test_update_weight_unregistered(self):
        """未注册权重更新 noop"""
        ws = WorldState()
        ws.update_consensus_weight("ghost", 0.5)  # 不崩溃
        assert ws.get_consensus_weight("ghost") == 0.0

    def test_set_status(self):
        """状态设置/查询"""
        ws = WorldState()
        ws.register_agent("a0", "0x" + "ab" * 32)
        ws.set_agent_status("a0", AgentStatus.BANNED)
        assert ws.get_agent_status("a0") == AgentStatus.BANNED


class TestIdentityRegister:
    def test_register_valid(self):
        """正常注册"""
        ws = WorldState()
        ic = IdentityContract(ws)
        assert ic.register("a0", VALID_PK)["success"] is True
        assert ic.get_public_key("a0") == VALID_PK

    def test_register_duplicate(self):
        """重复注册拒绝"""
        ws = WorldState()
        ic = IdentityContract(ws)
        ic.register("a0", VALID_PK)
        r = ic.register("a0", VALID_PK)
        assert r["success"] is False
        assert "已注册" in r["error"]

    def test_register_none_pk(self):
        """None 公钥拒绝"""
        ws = WorldState()
        ic = IdentityContract(ws)
        r = ic.register("a0", None)
        assert r["success"] is False
        assert "公钥" in r["error"]


class TestIdentityStatus:
    def test_update_status(self):
        """状态更新"""
        ws = WorldState()
        ic = IdentityContract(ws)
        ic.register("a0", VALID_PK)
        assert ic.update_status("a0", "warning", ContractCaller.PENALTY)["success"] is True
        assert ic.get_status("a0") == "warning"

    def test_update_status_unauthorized(self):
        """非授权调用方拒绝"""
        ws = WorldState()
        ic = IdentityContract(ws)
        ic.register("a0", VALID_PK)
        r = ic.update_status("a0", "warning", ContractCaller.SYSTEM)
        assert r["success"] is False
        assert "无权限" in r["error"]

    def test_list_agents(self):
        """list_agents 摘要"""
        ws = WorldState()
        ic = IdentityContract(ws)
        ic.register("a0", VALID_PK)
        agents = ic.list_agents()
        assert len(agents) == 1
        assert agents[0]["agent_id"] == "a0"
