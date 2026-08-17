"""
Blockchain 剩余边界测试（RalphLoop 原子任务 DY）
覆盖：区块查询组合、交易池生命周期、统计边界（此前未单点覆盖）
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


class TestBlockQuery:
    def test_get_block_all(self):
        """各高度区块查询"""
        bc = Blockchain()
        for i in range(3):
            bc.append_block(_make_block(bc.latest_block, [_make_tx(nonce=i)]))
        assert bc.get_block(0).block_height == 0
        assert bc.get_block(3).block_height == 3

    def test_find_across_blocks(self):
        """跨块交易查找"""
        bc = Blockchain()
        txs = [_make_tx(nonce=i) for i in range(4)]
        bc.append_block(_make_block(bc.latest_block, txs[:2]))
        bc.append_block(_make_block(bc.latest_block, txs[2:]))
        for tx in txs:
            assert bc.find_transaction(tx.tx_id) is not None

    def test_agent_query(self):
        """按 agent 查询"""
        bc = Blockchain()
        bc.append_block(_make_block(bc.latest_block, [_make_tx("agent_1", 1)]))
        bc.append_block(_make_block(bc.latest_block, [_make_tx("agent_1", 2)]))
        assert len(bc.get_agent_transactions("agent_1")) == 2


class TestTxPoolLifecycle:
    def test_add_reject_duplicate(self):
        """重复交易拒绝"""
        bc = Blockchain()
        tx = _make_tx(nonce=1)
        assert bc.add_transaction(tx) is True
        assert bc.add_transaction(tx) is False

    def test_append_removes_pool(self):
        """上链移除池中交易"""
        bc = Blockchain()
        tx = _make_tx(nonce=2)
        bc.add_transaction(tx)
        bc.append_block(_make_block(bc.latest_block, [tx]))
        assert bc.get_tx_pool_size() == 0

    def test_partial_append_keeps_rest(self):
        """部分上链保留其余"""
        bc = Blockchain()
        tx1 = _make_tx(nonce=1)
        tx2 = _make_tx(nonce=2)
        bc.add_transaction(tx1)
        bc.add_transaction(tx2)
        bc.append_block(_make_block(bc.latest_block, [tx1]))
        assert bc.get_tx_pool_size() == 1


class TestStats:
    def test_stats_multi_blocks(self):
        """多块统计"""
        bc = Blockchain()
        for i in range(5):
            bc.append_block(_make_block(bc.latest_block, [_make_tx(nonce=i)]))
        stats = bc.get_stats()
        assert stats['height'] == 5
        assert stats['total_blocks'] == 6
        assert stats['total_transactions'] == 5

    def test_latest_hash_preview(self):
        """latest_hash 预览格式"""
        bc = Blockchain()
        assert bc.get_stats()['latest_hash'].endswith('...')

    def test_validate_chain(self):
        """多块后链有效"""
        bc = Blockchain()
        for i in range(4):
            bc.append_block(_make_block(bc.latest_block, []))
        assert bc.validate_chain() is True
