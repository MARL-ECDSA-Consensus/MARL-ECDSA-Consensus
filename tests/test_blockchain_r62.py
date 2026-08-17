"""
Blockchain 剩余边界测试（RalphLoop 原子任务 DW）
覆盖：交易池容量/查询组合、区块哈希/状态根、统计边界（此前未单点覆盖）
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


class TestTxPool:
    def test_capacity_full_reject(self):
        """交易池满后拒绝"""
        bc = Blockchain()
        for i in range(bc.MAX_TX_POOL_SIZE):
            bc.add_transaction(_make_tx(nonce=i))
        assert bc.add_transaction(_make_tx(nonce=999999)) is False

    def test_capacity_release_after_append(self):
        """上链释放容量"""
        bc = Blockchain()
        txs = [_make_tx(nonce=i) for i in range(50)]
        for tx in txs:
            bc.add_transaction(tx)
        bc.append_block(_make_block(bc.latest_block, txs[:25]))
        assert bc.get_tx_pool_size() == 25
        assert bc.add_transaction(_make_tx(nonce=200)) is True

    def test_pending_copy_isolated(self):
        """get_pending 返回副本（修改不影响内部）"""
        bc = Blockchain()
        bc.add_transaction(_make_tx(nonce=1))
        pending = bc.get_pending_transactions()
        pending.clear()
        assert bc.get_tx_pool_size() == 1


class TestHashStateRoot:
    def test_merkle_empty(self):
        """空 Merkle 根"""
        assert compute_merkle_root([]) == ""

    def test_merkle_single(self):
        """单元素 Merkle 根返回自身"""
        tx = _make_tx()
        assert compute_merkle_root([tx.tx_id]) == tx.tx_id

    def test_genesis_state_root_zeros(self):
        """创世 state_root 全零"""
        g = Block.create_genesis()
        assert g.state_root == "0" * 64
        assert g.previous_hash == "0" * 64


class TestStatsEdge:
    def test_stats_pending_chain(self):
        """交易池与链统计分离"""
        bc = Blockchain()
        tx = _make_tx(nonce=1)
        bc.add_transaction(tx)
        stats = bc.get_stats()
        assert stats['pending_transactions'] == 1
        assert stats['total_transactions'] == 0  # 未上链不计

    def test_latest_hash_preview(self):
        """latest_hash 预览格式"""
        bc = Blockchain()
        h = bc.get_stats()['latest_hash']
        assert h.endswith('...')
        assert len(h) == 19

    def test_validate_after_multi(self):
        """多块后链有效"""
        bc = Blockchain()
        for i in range(7):
            bc.append_block(_make_block(bc.latest_block, [_make_tx(nonce=i)]))
        assert bc.validate_chain() is True
        assert bc.height == 7
        assert bc.get_stats()['total_blocks'] == 8
