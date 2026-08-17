"""
Blockchain 剩余边界测试（RalphLoop 原子任务 EC）
覆盖：交易池容量、区块查询组合、统计边界（此前未单点覆盖）
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


class TestTxPool:
    def test_duplicate_reject(self):
        """重复交易拒绝"""
        bc = Blockchain()
        tx = _make_tx(nonce=1)
        assert bc.add_transaction(tx) is True
        assert bc.add_transaction(tx) is False

    def test_capacity_full_reject(self):
        """容量满后拒绝"""
        bc = Blockchain()
        for i in range(bc.MAX_TX_POOL_SIZE):
            bc.add_transaction(_make_tx(nonce=i))
        assert bc.add_transaction(_make_tx(nonce=999999)) is False

    def test_pending_slice(self):
        """max_count 截断"""
        bc = Blockchain()
        for i in range(5):
            bc.add_transaction(_make_tx(nonce=i))
        assert len(bc.get_pending_transactions(max_count=3)) == 3


class TestBlockQuery:
    def test_get_block_all_heights(self):
        """各高度查询"""
        bc = Blockchain()
        for i in range(3):
            bc.append_block(_make_block(bc.latest_block, [_make_tx(nonce=i)]))
        assert bc.get_block(2).block_height == 2

    def test_find_transaction(self):
        """交易查找（含多块）"""
        bc = Blockchain()
        txs = [_make_tx(nonce=i) for i in range(4)]
        bc.append_block(_make_block(bc.latest_block, txs[:2]))
        bc.append_block(_make_block(bc.latest_block, txs[2:]))
        assert bc.find_transaction(txs[0].tx_id) is not None
        assert bc.find_transaction(txs[3].tx_id) is not None

    def test_agent_query_cross_blocks(self):
        """跨块 agent 查询"""
        bc = Blockchain()
        bc.append_block(_make_block(bc.latest_block, [_make_tx("agent_2", 1)]))
        bc.append_block(_make_block(bc.latest_block, [_make_tx("agent_2", 2)]))
        assert len(bc.get_agent_transactions("agent_2")) == 2


class TestStats:
    def test_stats_blocks_txs(self):
        """块数/交易数统计"""
        bc = Blockchain()
        for i in range(4):
            bc.append_block(_make_block(bc.latest_block, [_make_tx(nonce=i)]))
        stats = bc.get_stats()
        assert stats['height'] == 4
        assert stats['total_blocks'] == 5
        assert stats['total_transactions'] == 4

    def test_pending_stat(self):
        """待处理统计"""
        bc = Blockchain()
        bc.add_transaction(_make_tx(nonce=1))
        assert bc.get_stats()['pending_transactions'] == 1

    def test_chain_valid(self):
        """多块链有效"""
        bc = Blockchain()
        for i in range(3):
            bc.append_block(_make_block(bc.latest_block, []))
        assert bc.validate_chain() is True
