"""
Blockchain 剩余边界测试（RalphLoop 原子任务 EE）
覆盖：Block 序列化/哈希、交易池容量、链统计边界（此前未单点覆盖）
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


class TestBlockSerialize:
    def test_tx_roundtrip(self):
        """Transaction 序列化往返"""
        tx = _make_tx("agent_0", 5)
        restored = Transaction.from_dict(tx.to_dict())
        assert restored == tx

    def test_tx_compute_hash(self):
        """交易哈希 64 hex"""
        tx = _make_tx()
        assert len(tx.compute_hash()) == 64

    def test_block_roundtrip(self):
        """Block 序列化往返（finalize 后）"""
        genesis = Block.create_genesis()
        b = _make_block(genesis, [_make_tx()])
        b.finalize()
        restored = Block.from_dict(b.to_dict())
        assert restored.block_hash == b.block_hash
        assert restored.state_root == b.state_root


class TestTxPool:
    def test_capacity_release(self):
        """上链释放容量"""
        bc = Blockchain()
        txs = [_make_tx(nonce=i) for i in range(20)]
        for tx in txs:
            bc.add_transaction(tx)
        bc.append_block(_make_block(bc.latest_block, txs[:10]))
        assert bc.get_tx_pool_size() == 10

    def test_pending_copy(self):
        """get_pending 副本隔离"""
        bc = Blockchain()
        bc.add_transaction(_make_tx(nonce=1))
        p = bc.get_pending_transactions()
        p.clear()
        assert bc.get_tx_pool_size() == 1


class TestStats:
    def test_stats_height_blocks(self):
        """高度/块数统计"""
        bc = Blockchain()
        bc.append_block(_make_block(bc.latest_block, []))
        stats = bc.get_stats()
        assert stats['height'] == 1
        assert stats['total_blocks'] == 2

    def test_latest_hash_changes(self):
        """追加后 latest_hash 变化"""
        bc = Blockchain()
        h0 = bc.get_stats()['latest_hash']
        bc.append_block(_make_block(bc.latest_block, []))
        assert bc.get_stats()['latest_hash'] != h0

    def test_chain_valid(self):
        """多块链有效"""
        bc = Blockchain()
        for i in range(3):
            bc.append_block(_make_block(bc.latest_block, [_make_tx(nonce=i)]))
        assert bc.validate_chain() is True
        assert bc.height == 3
