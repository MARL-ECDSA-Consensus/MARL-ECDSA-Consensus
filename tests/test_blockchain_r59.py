"""
Blockchain 剩余边界测试（RalphLoop 原子任务 DQ）
覆盖：区块哈希/状态根组合、交易池批量边界、链统计持久化（此前未单点覆盖）
通过标准：新增 ≥6 项测试全过
"""
import hashlib
import logging
import time

import pytest

from blockchain.ledger.block import Block, Transaction, compute_merkle_root
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


class TestHashStateRoot:
    def test_merkle_root_deterministic(self):
        """Merkle 根确定性"""
        hashes = ["a" * 64, "b" * 64]
        assert compute_merkle_root(hashes) == compute_merkle_root(hashes)

    def test_merkle_root_order_sensitive(self):
        """Merkle 根顺序敏感（防重排）"""
        r1 = compute_merkle_root(["a" * 64, "b" * 64])
        r2 = compute_merkle_root(["b" * 64, "a" * 64])
        assert r1 != r2

    def test_state_root_empty_zeros(self):
        """空交易区块 state_root 全零"""
        genesis = Block.create_genesis()
        b = _make_block(genesis, [])
        assert b.compute_state_root() == "0" * 64

    def test_state_root_with_tx(self):
        """含交易区块 state_root 非全零"""
        genesis = Block.create_genesis()
        b = _make_block(genesis, [_make_tx()])
        assert b.compute_state_root() != "0" * 64


class TestTxPoolBatch:
    def test_batch_unique_all_added(self):
        """批量唯一交易全部加入"""
        bc = Blockchain()
        txs = [_make_tx(nonce=i) for i in range(15)]
        added = sum(1 for tx in txs if bc.add_transaction(tx))
        assert added == 15
        assert bc.get_tx_pool_size() == 15

    def test_batch_duplicates_deduped(self):
        """批量重复去重"""
        bc = Blockchain()
        tx = _make_tx(nonce=1)
        bc.add_transaction(tx)
        bc.add_transaction(tx)
        bc.add_transaction(_make_tx(nonce=2))
        assert bc.get_tx_pool_size() == 2

    def test_pending_slice(self):
        """get_pending max_count 截断"""
        bc = Blockchain()
        for i in range(10):
            bc.add_transaction(_make_tx(nonce=i))
        assert len(bc.get_pending_transactions(max_count=4)) == 4


class TestPersistStats:
    def test_stats_reload_equal(self, tmp_path):
        """重载前后统计一致"""
        persist = tmp_path / "chain.json"
        bc1 = Blockchain(persist_path=str(persist))
        for i in range(4):
            bc1.append_block(_make_block(bc1.latest_block, [_make_tx(nonce=i)]))
        s1 = bc1.get_stats()
        bc2 = Blockchain(persist_path=str(persist))
        assert bc2.get_stats() == s1

    def test_stats_blocks_height(self):
        """total_blocks = height + 1"""
        bc = Blockchain()
        bc.append_block(_make_block(bc.latest_block, []))
        stats = bc.get_stats()
        assert stats['total_blocks'] == stats['height'] + 1

    def test_latest_hash_preview(self):
        """latest_hash 预览格式"""
        bc = Blockchain()
        assert bc.get_stats()['latest_hash'].endswith('...')
        assert len(bc.get_stats()['latest_hash']) == 19
