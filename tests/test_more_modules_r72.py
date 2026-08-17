"""
更多模块剩余边界测试（RalphLoop 原子任务 ER）
覆盖：identity_contract 状态更新/活跃性、action_recorder 批量过滤（此前未单点覆盖）
通过标准：新增 ≥6 项测试全过
"""
import logging

import pytest

from blockchain.ledger.world_state import WorldState
from blockchain.contracts.identity_contract import IdentityContract, ContractCaller

logging.basicConfig(level=logging.CRITICAL)

VALID_PK = "04" + "ab" * 64


class TestUpdateStatus:
    def test_valid_update(self):
        """正常状态更新"""
        ws = WorldState()
        ic = IdentityContract(ws)
        ic.register("a0", VALID_PK)
        assert ic.update_status("a0", "warning", ContractCaller.PENALTY)["success"] is True
        assert ic.get_status("a0") == "warning"

    def test_unauthorized_caller(self):
        """非授权调用方拒绝"""
        ws = WorldState()
        ic = IdentityContract(ws)
        ic.register("a0", VALID_PK)
        r = ic.update_status("a0", "warning", ContractCaller.SYSTEM)
        assert r["success"] is False
        assert "无权限" in r["error"]

    def test_invalid_status_value(self):
        """无效状态值拒绝"""
        ws = WorldState()
        ic = IdentityContract(ws)
        ic.register("a0", VALID_PK)
        r = ic.update_status("a0", "not_a_status", ContractCaller.PENALTY)
        assert r["success"] is False
        assert "无效" in r["error"]

    def test_unregistered_agent(self):
        """未注册更新失败"""
        ws = WorldState()
        ic = IdentityContract(ws)
        r = ic.update_status("ghost", "warning", ContractCaller.PENALTY)
        assert r["success"] is False
        assert "不存在" in r["error"]


class TestActiveStatus:
    def test_is_active_after_register(self):
        """注册后活跃"""
        ws = WorldState()
        ic = IdentityContract(ws)
        ic.register("a0", VALID_PK)
        assert ic.is_active("a0") is True

    def test_is_active_after_ban(self):
        """封禁后非活跃"""
        ws = WorldState()
        ic = IdentityContract(ws)
        ic.register("a0", VALID_PK)
        ic.update_status("a0", "banned", ContractCaller.PENALTY)
        assert ic.is_active("a0") is False

    def test_is_active_unregistered(self):
        """未注册非活跃"""
        ws = WorldState()
        ic = IdentityContract(ws)
        assert ic.is_active("ghost") is False


class TestListAgents:
    def test_list_summary(self):
        """list_agents 摘要"""
        ws = WorldState()
        ic = IdentityContract(ws)
        ic.register("a0", VALID_PK)
        ic.register("a1", VALID_PK)
        agents = ic.list_agents()
        assert len(agents) == 2
        assert {a["agent_id"] for a in agents} == {"a0", "a1"}

    def test_list_empty(self):
        """空列表"""
        ws = WorldState()
        ic = IdentityContract(ws)
        assert ic.list_agents() == []


class TestRecorderFilter:
    def test_batch_filters_unverified(self):
        """批量过滤未验证行为"""
        from marl.integration.action_recorder import ActionRecorder
        class _BC:
            def __init__(self):
                self.txs = []
            def add_transaction(self, tx):
                self.txs.append(tx)
        bc = _BC()
        ar = ActionRecorder(bc_node=bc, n_agents=3)
        pkg_true = {'signature_hex': '0x' + 'ab' * 32, 'message_hex': '00',
                    'r': 1, 's': 2, 'verified': True}
        pkg_false = {'signature_hex': '0x' + 'ab' * 32, 'message_hex': '00',
                     'r': 3, 's': 4, 'verified': False}
        ar.record_action("a0", 1, [0.1], 1.0, 1000, 1, pkg_true)
        ar.record_action("a1", 2, [0.2], 1.0, 1001, 2, pkg_false)
        ar.batch_upload()
        assert len(bc.txs) == 1  # 仅可信行为上链
        assert ar.get_stats()['tx_count'] == 1

    def test_batch_no_sig_allowed(self):
        """无签名包行为默认可信（向后兼容）"""
        from marl.integration.action_recorder import ActionRecorder
        class _BC:
            def __init__(self):
                self.txs = []
            def add_transaction(self, tx):
                self.txs.append(tx)
        bc = _BC()
        ar = ActionRecorder(bc_node=bc, n_agents=3)
        ar.record_action("a0", 1, [0.1], 1.0, 1000, 1, None)  # 无签名包
        ar.batch_upload()
        assert len(bc.txs) == 1  # 无 verified 字段视为可信
