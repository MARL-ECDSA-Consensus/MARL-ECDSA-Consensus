"""
Blockchain 剩余边界测试（RalphLoop 原子任务 DU）
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
    def test_get_block_all_heights(self):
        """各高度查询一致"""
        bc = Blockchain()
        for i in range(3):
            bc.append_block(_make_block(bc.latest_block, [_make_tx(nonce=i)]))
        for h in range(4):
            block = bc.get_block(h)
            assert block is not None
            assert block.block_height == h

    def test_find_transaction_multiple_blocks(self):
        """多块内交易均可查"""
        bc = Blockchain()
        txs = [_make_tx(nonce=i) for i in range(6)]
        for i in range(0, 6, 2):
            bc.append_block(_make_block(bc.latest_block, txs[i:i + 2]))
        for tx in txs:
            assert bc.find_transaction(tx.tx_id) is not None

    def test_agent_transaction_limit(self):
        """按 agent 查询 limit 截断"""
        bc = Blockchain()
        for i in range(10):
            bc.append_block(_make_block(bc.latest_block, [_make_tx("agent_0", i)]))
        assert len(bc.get_agent_transactions("agent_0", limit=4)) == 4


class TestTxPoolLifecycle:
    def test_add_append_query(self):
        """入池→上链→查询完整链路"""
        bc = Blockchain()
        tx = _make_tx(nonce=1)
        bc.add_transaction(tx)
        assert bc.find_transaction(tx.tx_id) is None  # 未上链
        bc.append_block(_make_block(bc.latest_block, [tx]))
        assert bc.find_transaction(tx.tx_id) is not None  # 已上链
        assert bc.get_tx_pool_size() == 0

    def test_pool_to_chain_keeps_others(self):
        """部分上链保留其余交易"""
        bc = Blockchain()
        tx1 = _make_tx(nonce=1)
        tx2 = _make_tx(nonce=2)
        bc.add_transaction(tx1)
        bc.add_transaction(tx2)
        bc.append_block(_make_block(bc.latest_block, [tx1]))
        assert bc.get_tx_pool_size() == 1
        assert bc.get_pending_transactions()[0].tx_id == tx2.tx_id

    def test_pool_duplicate_rejected(self):
        """重复交易拒绝"""
        bc = Blockchain()
        tx = _make_tx(nonce=3)
        assert bc.add_transaction(tx) is True
        assert bc.add_transaction(tx) is False


class TestStatsEdge:
    def test_stats_height_blocks_relation(self):
        """total_blocks = height + 1"""
        bc = Blockchain()
        for i in range(4):
            bc.append_block(_make_block(bc.latest_block, []))
        stats = bc.get_stats()
        assert stats['total_blocks'] == stats['height'] + 1

    def test_latest_hash_changes_after_append(self):
        """追加后 latest_hash 变化"""
        bc = Blockchain()
        h0 = bc.get_stats()['latest_hash']
        bc.append_block(_make_block(bc.latest_block, []))
        assert bc.get_stats()['latest_hash'] != h0

    def test_validate_after_append_all(self):
        """全部追加后链有效"""
        bc = Blockchain()
        for i in range(6):
            bc.append_block(_make_block(bc.latest_block, [_make_tx(nonce=i)]))
        assert bc.validate_chain() is True
        assert bc.height == 6
