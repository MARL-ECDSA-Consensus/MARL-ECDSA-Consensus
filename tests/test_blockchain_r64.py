"""
Blockchain 剩余边界测试（RalphLoop 原子任务 EA）
覆盖：交易池容量边界、区块查询组合、统计边界（此前未单点覆盖）
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
    def test_capacity_edge(self):
        """交易池容量满前/满后边界"""
        bc = Blockchain()
        for i in range(bc.MAX_TX_POOL_SIZE):
            assert bc.add_transaction(_make_tx(nonce=i)) is True
        assert bc.add_transaction(_make_tx(nonce=999999)) is False
        assert bc.get_tx_pool_size() == bc.MAX_TX_POOL_SIZE

    def test_capacity_release(self):
        """上链释放后可加入"""
        bc = Blockchain()
        txs = [_make_tx(nonce=i) for i in range(30)]
        for tx in txs:
            bc.add_transaction(tx)
        bc.append_block(_make_block(bc.latest_block, txs[:15]))
        assert bc.get_tx_pool_size() == 15
        assert bc.add_transaction(_make_tx(nonce=100)) is True

    def test_pending_max(self):
        """get_pending max_count"""
        bc = Blockchain()
        for i in range(6):
            bc.add_transaction(_make_tx(nonce=i))
        assert len(bc.get_pending_transactions(max_count=2)) == 2


class TestBlockQuery:
    def test_get_blocks_from(self):
        """get_blocks_from 区间"""
        bc = Blockchain()
        for i in range(4):
            bc.append_block(_make_block(bc.latest_block, []))
        assert len(bc.get_blocks_from(2)) == 3  # 高度 2,3,4

    def test_find_missing(self):
        """不存在的交易 → None"""
        bc = Blockchain()
        assert bc.find_transaction("ghost") is None

    def test_agent_query_empty(self):
        """无该 agent 交易 → 空"""
        bc = Blockchain()
        bc.append_block(_make_block(bc.latest_block, [_make_tx("agent_1", 1)]))
        assert bc.get_agent_transactions("agent_0") == []


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

    def test_chain_valid(self):
        """多块链有效"""
        bc = Blockchain()
        for i in range(5):
            bc.append_block(_make_block(bc.latest_block, [_make_tx(nonce=i)]))
        assert bc.validate_chain() is True
        assert bc.height == 5
