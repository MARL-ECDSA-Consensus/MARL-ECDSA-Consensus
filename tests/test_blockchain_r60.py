"""
Blockchain 剩余边界测试（RalphLoop 原子任务 DS）
覆盖：Block finalize/序列化组合、交易哈希、链统计边界（此前未单点覆盖）
通过标准：新增 ≥6 项测试全过
"""
import hashlib
import logging
import time

import pytest

from blockchain.ledger.block import Block, Transaction
from blockchain.ledger.blockchain import Blockchain

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


def _make_block(prev_block, transactions):
    return Block(
        block_height=prev_block.block_height + 1,
        previous_hash=prev_block.block_hash,
        timestamp=int(time.time() * 1000),
        proposer="node_0",
        transactions=transactions,
        state_root="0" * 64,
    )


class TestBlockFinalize:
    def test_finalize_updates_hash(self):
        """finalize 更新 state_root 后哈希变化（含交易区块）"""
        genesis = Block.create_genesis()
        b = _make_block(genesis, [_make_tx()])
        before = b.block_hash
        b.finalize()
        assert b.block_hash != before  # state_root 全零→Merkle 根 → 哈希变

    def test_finalize_restore_roundtrip(self):
        """finalize 后序列化恢复一致"""
        genesis = Block.create_genesis()
        b = _make_block(genesis, [_make_tx()])
        b.finalize()
        restored = Block.from_dict(b.to_dict())
        assert restored.block_hash == b.block_hash
        assert restored.state_root == b.state_root

    def test_genesis_constant_hash(self):
        """创世哈希恒定"""
        assert Block.create_genesis().block_hash == Block.create_genesis().block_hash


class TestTxHash:
    def test_tx_hash_deterministic_same_ts(self):
        """同 timestamp 交易哈希确定"""
        tx1 = _make_tx("agent_0", 1)
        tx1.timestamp = 1000
        tx2 = _make_tx("agent_0", 1)
        tx2.timestamp = 1000
        assert tx1.compute_hash() == tx2.compute_hash()

    def test_tx_hash_differs_by_nonce(self):
        """不同 nonce → 不同哈希"""
        tx1 = _make_tx("agent_0", 1)
        tx1.timestamp = 1000
        tx2 = _make_tx("agent_0", 2)
        tx2.timestamp = 1000
        assert tx1.compute_hash() != tx2.compute_hash()

    def test_tx_hash_64_hex(self):
        """交易哈希 64 hex"""
        tx = _make_tx()
        assert len(tx.compute_hash()) == 64


class TestChainStats:
    def test_stats_large_chain(self):
        """20 块链统计一致"""
        bc = Blockchain()
        for i in range(20):
            bc.append_block(_make_block(bc.latest_block, [_make_tx(nonce=i)]))
        stats = bc.get_stats()
        assert stats['height'] == 20
        assert stats['total_blocks'] == 21
        assert stats['total_transactions'] == 20

    def test_stats_zero_blocks(self):
        """仅创世统计"""
        bc = Blockchain()
        stats = bc.get_stats()
        assert stats['height'] == 0
        assert stats['total_blocks'] == 1
        assert stats['total_transactions'] == 0
        assert stats['pending_transactions'] == 0

    def test_pending_tx_stat(self):
        """待处理交易统计"""
        bc = Blockchain()
        bc.add_transaction(_make_tx(nonce=1))
        assert bc.get_stats()['pending_transactions'] == 1
        assert bc.get_stats()['total_transactions'] == 0
