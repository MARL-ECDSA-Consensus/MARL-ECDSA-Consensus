"""
Blockchain 剩余边界测试（RalphLoop 原子任务 EM）
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
    def test_capacity_full_reject(self):
        """容量满后拒绝"""
        bc = Blockchain()
        for i in range(bc.MAX_TX_POOL_SIZE):
            bc.add_transaction(_make_tx(nonce=i))
        assert bc.add_transaction(_make_tx(nonce=999999)) is False

    def test_capacity_release(self):
        """上链释放容量"""
        bc = Blockchain()
        txs = [_make_tx(nonce=i) for i in range(30)]
        for tx in txs:
            bc.add_transaction(tx)
        bc.append_block(_make_block(bc.latest_block, txs[:15]))
        assert bc.get_tx_pool_size() == 15
        assert bc.add_transaction(_make_tx(nonce=100)) is True

    def test_duplicate_reject(self):
        """重复拒绝"""
        bc = Blockchain()
        tx = _make_tx(nonce=1)
        assert bc.add_transaction(tx) is True
        assert bc.add_transaction(tx) is False


class TestBlockQuery:
    def test_get_block_all_heights(self):
        """各高度查询"""
        bc = Blockchain()
        for i in range(3):
            bc.append_block(_make_block(bc.latest_block, [_make_tx(nonce=i)]))
        assert bc.get_block(2).block_height == 2
        assert bc.get_block(50) is None

    def test_find_cross_blocks(self):
        """跨块交易查找"""
        bc = Blockchain()
        txs = [_make_tx(nonce=i) for i in range(4)]
        bc.append_block(_make_block(bc.latest_block, txs[:2]))
        bc.append_block(_make_block(bc.latest_block, txs[2:]))
        for tx in txs:
            assert bc.find_transaction(tx.tx_id) is not None

    def test_agent_query(self):
        """agent 查询"""
        bc = Blockchain()
        bc.append_block(_make_block(bc.latest_block, [_make_tx("agent_1", 1)]))
        assert len(bc.get_agent_transactions("agent_1")) == 1
        assert bc.get_agent_transactions("ghost") == []


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

    def test_latest_hash(self):
        """latest_hash 预览"""
        bc = Blockchain()
        h = bc.get_stats()['latest_hash']
        assert h.endswith('...') and len(h) == 19

    def test_chain_valid(self):
        """多块链有效"""
        bc = Blockchain()
        for i in range(4):
            bc.append_block(_make_block(bc.latest_block, []))
        assert bc.validate_chain() is True
        assert bc.height == 4
