"""
更多模块剩余边界测试（RalphLoop 原子任务 FR）
覆盖：Block state_root/finalize、identity 状态更新（此前未单点覆盖）
通过标准：新增 ≥6 项测试全过
"""
import hashlib
import logging
import time

import pytest

from blockchain.ledger.block import Block, Transaction
from blockchain.ledger.world_state import WorldState
from blockchain.contracts.identity_contract import IdentityContract, ContractCaller

logging.basicConfig(level=logging.CRITICAL)

VALID_PK = "04" + "ab" * 64


def _make_tx(agent_id="agent_0", nonce=1):
    action = [0.1, 0.2]
    return Transaction(
        tx_id=hashlib.sha256(f"{agent_id}{nonce}".encode()).hexdigest()[:16],
        agent_id=agent_id,
        action=action,
        action_hash=hashlib.sha256(str(action).encode()).hexdigest()[:16],
        timestamp=int(time.time() * 1000),
        nonce=nonce,
        signature_hex="0x" + "ab" * 32,
        extra={'verified': True, 'message_hex': '00'},
    )


class TestStateRoot:
    def test_state_root_empty_zeros(self):
        """空交易 state_root 全零"""
        genesis = Block.create_genesis()
        b = Block(block_height=1, previous_hash=genesis.block_hash,
                  timestamp=int(time.time() * 1000), proposer="node_0",
                  transactions=[], state_root="0" * 64)
        assert b.compute_state_root() == "0" * 64

    def test_state_root_with_tx(self):
        """含交易 state_root 非全零（单元素 Merkle 返回 tx_id 16 字符，真实契约）"""
        genesis = Block.create_genesis()
        b = Block(block_height=1, previous_hash=genesis.block_hash,
                  timestamp=int(time.time() * 1000), proposer="node_0",
                  transactions=[_make_tx()], state_root="0" * 64)
        assert b.compute_state_root() != "0" * 64
        assert len(b.compute_state_root()) > 0


class TestFinalize:
    def test_finalize_empty_idempotent(self):
        """空交易 finalize 幂等"""
        genesis = Block.create_genesis()
        b = Block(block_height=1, previous_hash=genesis.block_hash,
                  timestamp=int(time.time() * 1000), proposer="node_0",
                  transactions=[], state_root="0" * 64)
        h1 = b.finalize()
        h2 = b.finalize()
        assert h1 == h2
        assert b.state_root == "0" * 64

    def test_finalize_with_tx_changes_hash(self):
        """含交易 finalize 后哈希变化"""
        genesis = Block.create_genesis()
        b = Block(block_height=1, previous_hash=genesis.block_hash,
                  timestamp=int(time.time() * 1000), proposer="node_0",
                  transactions=[_make_tx()], state_root="0" * 64)
        before = b.block_hash
        b.finalize()
        assert b.block_hash != before

    def test_finalize_roundtrip(self):
        """finalize 后序列化往返一致"""
        genesis = Block.create_genesis()
        b = Block(block_height=1, previous_hash=genesis.block_hash,
                  timestamp=int(time.time() * 1000), proposer="node_0",
                  transactions=[_make_tx()], state_root="0" * 64)
        b.finalize()
        restored = Block.from_dict(b.to_dict())
        assert restored.block_hash == b.block_hash


class TestUpdateStatus:
    def test_valid_update(self):
        """正常状态更新"""
        ws = WorldState()
        ic = IdentityContract(ws)
        ic.register("a0", VALID_PK)
        assert ic.update_status("a0", "warning", ContractCaller.PENALTY)["success"] is True
        assert ic.get_status("a0") == "warning"

    def test_unauthorized(self):
        """非授权调用方拒绝"""
        ws = WorldState()
        ic = IdentityContract(ws)
        ic.register("a0", VALID_PK)
        r = ic.update_status("a0", "warning", ContractCaller.SYSTEM)
        assert r["success"] is False
        assert "无权限" in r["error"]

    def test_invalid_status(self):
        """无效状态值拒绝"""
        ws = WorldState()
        ic = IdentityContract(ws)
        ic.register("a0", VALID_PK)
        r = ic.update_status("a0", "not_a_status", ContractCaller.PENALTY)
        assert r["success"] is False
        assert "无效" in r["error"]

    def test_unregistered(self):
        """未注册更新失败"""
        ws = WorldState()
        ic = IdentityContract(ws)
        r = ic.update_status("ghost", "warning", ContractCaller.PENALTY)
        assert r["success"] is False
        assert "不存在" in r["error"]


class TestActive:
    def test_active_after_register(self):
        """注册后活跃"""
        ws = WorldState()
        ic = IdentityContract(ws)
        ic.register("a0", VALID_PK)
        assert ic.is_active("a0") is True

    def test_inactive_after_ban(self):
        """封禁后非活跃"""
        ws = WorldState()
        ic = IdentityContract(ws)
        ic.register("a0", VALID_PK)
        ic.update_status("a0", "banned", ContractCaller.PENALTY)
        assert ic.is_active("a0") is False

    def test_inactive_unregistered(self):
        """未注册非活跃"""
        ws = WorldState()
        ic = IdentityContract(ws)
        assert ic.is_active("ghost") is False
