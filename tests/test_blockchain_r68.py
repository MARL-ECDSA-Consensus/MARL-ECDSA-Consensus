"""
Blockchain 剩余边界测试（RalphLoop 原子任务 EI）
覆盖：Block finalize/Merkle、交易池边界、统计组合（此前未单点覆盖）
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


class TestBlockFinalize:
    def test_finalize_empty_stable(self):
        """空交易 finalize 幂等（state_root 恒全零）"""
        genesis = Block.create_genesis()
        b = _make_block(genesis, [])
        h1 = b.finalize()
        h2 = b.finalize()
        assert h1 == h2
        assert b.state_root == "0" * 64

    def test_finalize_with_tx_changes(self):
        """含交易 finalize 后哈希变化"""
        genesis = Block.create_genesis()
        b = _make_block(genesis, [_make_tx()])
        before = b.block_hash
        b.finalize()
        assert b.block_hash != before

    def test_merkle_deterministic(self):
        """Merkle 根确定性"""
        hashes = ["a" * 64, "b" * 64]
        assert compute_merkle_root(hashes) == compute_merkle_root(hashes)


class TestTxPool:
    def test_duplicate_reject(self):
        """重复拒绝"""
        bc = Blockchain()
        tx = _make_tx(nonce=1)
        assert bc.add_transaction(tx) is True
        assert bc.add_transaction(tx) is False

    def test_capacity_release(self):
        """上链释放"""
        bc = Blockchain()
        txs = [_make_tx(nonce=i) for i in range(40)]
        for tx in txs:
            bc.add_transaction(tx)
        bc.append_block(_make_block(bc.latest_block, txs[:20]))
        assert bc.get_tx_pool_size() == 20

    def test_pending_max(self):
        """max_count 截断"""
        bc = Blockchain()
        for i in range(6):
            bc.add_transaction(_make_tx(nonce=i))
        assert len(bc.get_pending_transactions(max_count=2)) == 2


class TestStats:
    def test_stats_blocks_relation(self):
        """total_blocks = height + 1"""
        bc = Blockchain()
        for i in range(3):
            bc.append_block(_make_block(bc.latest_block, []))
        stats = bc.get_stats()
        assert stats['total_blocks'] == stats['height'] + 1

    def test_latest_hash_format(self):
        """latest_hash 预览"""
        bc = Blockchain()
        h = bc.get_stats()['latest_hash']
        assert h.endswith('...') and len(h) == 19

    def test_chain_valid_multi(self):
        """多块链有效"""
        bc = Blockchain()
        for i in range(5):
            bc.append_block(_make_block(bc.latest_block, [_make_tx(nonce=i)]))
        assert bc.validate_chain() is True
        assert bc.height == 5
