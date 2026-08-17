"""
更多模块剩余边界测试（RalphLoop 原子任务 GT）
覆盖：Transaction/Block 序列化、incentive 结算排名（此前未单点覆盖）
通过标准：新增 ≥6 项测试全过
"""
import hashlib
import logging
import time

import pytest

from blockchain.ledger.block import Block, Transaction
from blockchain.ledger.world_state import WorldState
from blockchain.contracts.incentive_contract import IncentiveContract, ContributionScore

logging.basicConfig(level=logging.CRITICAL)


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


class TestTxSerialize:
    def test_tx_roundtrip(self):
        """Transaction 序列化往返"""
        tx = _make_tx("agent_0", 5)
        restored = Transaction.from_dict(tx.to_dict())
        assert restored == tx

    def test_tx_hash_excludes_txid(self):
        """交易哈希不含 tx_id 本身"""
        tx = _make_tx("agent_0", 1)
        tx2 = Transaction.from_dict(tx.to_dict())
        tx2.tx_id = "different"
        assert tx.compute_hash() == tx2.compute_hash()

    def test_tx_hash_64_hex(self):
        """交易哈希 64 hex"""
        assert len(_make_tx().compute_hash()) == 64


class TestBlockRoundtrip:
    def test_block_roundtrip_finalized(self):
        """finalize 后 Block 往返一致"""
        genesis = Block.create_genesis()
        b = Block(block_height=1, previous_hash=genesis.block_hash,
                  timestamp=int(time.time() * 1000), proposer="node_0",
                  transactions=[_make_tx()], state_root="0" * 64)
        b.finalize()
        restored = Block.from_dict(b.to_dict())
        assert restored.block_hash == b.block_hash
        assert restored.state_root == b.state_root

    def test_genesis_roundtrip(self):
        """创世块往返一致"""
        g = Block.create_genesis()
        restored = Block.from_dict(g.to_dict())
        assert restored.block_hash == g.block_hash


class TestSettleRank:
    def test_rank_bonus_top(self):
        """排名1 获得加成 ≥ 排名2"""
        ws = WorldState()
        for i in range(4):
            ws.register_agent(f"agent_{i}", f"0x{'ab' * 32}")
        contract = IncentiveContract(ws)
        scores = [
            ContributionScore("agent_0", 1.0, 1.0, 1.0),
            ContributionScore("agent_1", 0.8, 1.0, 1.0),
            ContributionScore("agent_2", 0.5, 1.0, 1.0),
            ContributionScore("agent_3", 0.2, 1.0, 1.0),
        ]
        deltas = contract.settle_rewards(1, scores)
        assert deltas["agent_0"] >= deltas["agent_1"]
        assert deltas["agent_0"] >= 10.0

    def test_settle_empty(self):
        """空评分空增量"""
        ws = WorldState()
        contract = IncentiveContract(ws)
        assert contract.settle_rewards(1, []) == {}

    def test_settle_betrayal(self):
        """背叛惩罚 -20"""
        ws = WorldState()
        ws.register_agent("agent_0", "0x" + "ab" * 32)
        contract = IncentiveContract(ws)
        cs = ContributionScore("agent_0", 0.5, 0.0, 0.0)
        deltas = contract.settle_rewards(1, [cs])
        assert deltas["agent_0"] == -20.0

    def test_history_query(self):
        """结算历史查询"""
        ws = WorldState()
        ws.register_agent("agent_0", "0x" + "ab" * 32)
        contract = IncentiveContract(ws)
        cs = ContributionScore("agent_0", 0.5, 1.0, 1.0)
        contract.settle_rewards(5, [cs])
        history = contract.get_settlement_history(5)
        assert len(history) == 1
        assert history[0]["agent_id"] == "agent_0"


class TestBCReward:
    def test_lambda_scaling(self):
        """BC 奖励 = λ * 积分"""
        ws = WorldState()
        ws.register_agent("a0", "0x" + "ab" * 32)
        ws.add_score("a0", 10.0)
        contract = IncentiveContract(ws)
        assert contract.compute_bc_reward("a0", lambda_weight=0.1) == 1.0
        assert contract.compute_bc_reward("a0", lambda_weight=0.5) == 5.0

    def test_zero_score(self):
        """零积分 → 0"""
        ws = WorldState()
        ws.register_agent("a0", "0x" + "ab" * 32)
        contract = IncentiveContract(ws)
        assert contract.compute_bc_reward("a0") == 0.0
