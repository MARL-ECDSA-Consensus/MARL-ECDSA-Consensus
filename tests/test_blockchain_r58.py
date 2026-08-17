"""
Blockchain 剩余边界测试（RalphLoop 原子任务 DO）
覆盖：交易池去重/容量、区块查询边界、持久化+交易组合（此前未单点覆盖）
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


class TestTxPoolEdge:
    def test_duplicate_add_rejected(self):
        """重复交易拒绝（去重）"""
        bc = Blockchain()
        tx = _make_tx(nonce=1)
        assert bc.add_transaction(tx) is True
        assert bc.add_transaction(tx) is False
        assert bc.get_tx_pool_size() == 1

    def test_different_tx_accepted(self):
        """不同交易均接受"""
        bc = Blockchain()
        assert bc.add_transaction(_make_tx(nonce=1)) is True
        assert bc.add_transaction(_make_tx(nonce=2)) is True
        assert bc.get_tx_pool_size() == 2

    def test_pending_max_count(self):
        """get_pending max_count 截断"""
        bc = Blockchain()
        for i in range(8):
            bc.add_transaction(_make_tx(nonce=i))
        assert len(bc.get_pending_transactions(max_count=3)) == 3


class TestBlockQuery:
    def test_get_block_negative_none(self):
        bc = Blockchain()
        assert bc.get_block(-1) is None
        assert bc.get_block(99) is None

    def test_latest_block_tail(self):
        """latest_block 始终为链尾"""
        bc = Blockchain()
        for i in range(3):
            bc.append_block(_make_block(bc.latest_block, []))
        assert bc.latest_block.block_height == 3

    def test_get_blocks_from_beyond(self):
        """越界起始 → 空列表"""
        bc = Blockchain()
        assert bc.get_blocks_from(50) == []


class TestPersistTxCombo:
    def test_persist_pool_not_saved(self, tmp_path):
        """交易池不随链持久化（重载后池空）"""
        persist = tmp_path / "chain.json"
        bc1 = Blockchain(persist_path=str(persist))
        bc1.add_transaction(_make_tx(nonce=1))
        bc2 = Blockchain(persist_path=str(persist))
        assert bc2.get_tx_pool_size() == 0

    def test_persist_onchain_tx_found(self, tmp_path):
        """上链交易持久化后可查"""
        persist = tmp_path / "chain.json"
        bc1 = Blockchain(persist_path=str(persist))
        tx = _make_tx(nonce=7)
        bc1.append_block(_make_block(bc1.latest_block, [tx]))
        bc2 = Blockchain(persist_path=str(persist))
        assert bc2.find_transaction(tx.tx_id) is not None

    def test_persist_reload_chain_valid(self, tmp_path):
        """重载后链有效"""
        persist = tmp_path / "chain.json"
        bc1 = Blockchain(persist_path=str(persist))
        for i in range(4):
            bc1.append_block(_make_block(bc1.latest_block, [_make_tx(nonce=i)]))
        bc2 = Blockchain(persist_path=str(persist))
        assert bc2.validate_chain() is True
        assert bc2.height == 4


class TestChainStats:
    def test_stats_after_multi_blocks(self):
        """多块统计一致性"""
        bc = Blockchain()
        for i in range(5):
            bc.append_block(_make_block(bc.latest_block, [_make_tx(nonce=i)]))
        stats = bc.get_stats()
        assert stats['height'] == 5
        assert stats['total_blocks'] == 6  # 含创世
        assert stats['total_transactions'] == 5

    def test_genesis_only_stats(self):
        """仅创世统计"""
        bc = Blockchain()
        stats = bc.get_stats()
        assert stats['height'] == 0
        assert stats['total_blocks'] == 1
        assert stats['pending_transactions'] == 0
