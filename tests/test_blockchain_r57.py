"""
Blockchain 剩余边界测试（RalphLoop 原子任务 DM）
覆盖：交易池容量边界、区块查询组合、持久化重载边界（此前未单点覆盖）
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


class TestTxPoolCapacity:
    def test_capacity_edge_full(self):
        """交易池满后新交易被拒"""
        bc = Blockchain()
        for i in range(bc.MAX_TX_POOL_SIZE):
            bc.add_transaction(_make_tx(nonce=i))
        assert bc.add_transaction(_make_tx(nonce=999999)) is False
        assert bc.get_tx_pool_size() == bc.MAX_TX_POOL_SIZE

    def test_capacity_release_after_append(self):
        """上链释放容量后新交易可加入"""
        bc = Blockchain()
        txs = [_make_tx(nonce=i) for i in range(100)]
        for tx in txs:
            bc.add_transaction(tx)
        bc.append_block(_make_block(bc.latest_block, txs[:50]))
        assert bc.get_tx_pool_size() == 50
        assert bc.add_transaction(_make_tx(nonce=200)) is True

    def test_pending_order_fifo(self):
        """交易池 FIFO 顺序保持"""
        bc = Blockchain()
        txs = [_make_tx(nonce=i) for i in range(6)]
        for tx in txs:
            bc.add_transaction(tx)
        pending = bc.get_pending_transactions()
        assert [t.nonce for t in pending] == [0, 1, 2, 3, 4, 5]


class TestQueryCombo:
    def test_find_oldest_tx(self):
        """可查最早区块的交易"""
        bc = Blockchain()
        old_tx = _make_tx(nonce=1)
        bc.append_block(_make_block(bc.latest_block, [old_tx]))
        bc.append_block(_make_block(bc.latest_block, [_make_tx(nonce=2)]))
        assert bc.find_transaction(old_tx.tx_id) is not None

    def test_agent_query_cross_blocks(self):
        """跨块按 agent 查询聚合"""
        bc = Blockchain()
        bc.append_block(_make_block(bc.latest_block, [_make_tx("agent_1", 1), _make_tx("agent_2", 2)]))
        bc.append_block(_make_block(bc.latest_block, [_make_tx("agent_1", 3)]))
        txs = bc.get_agent_transactions("agent_1")
        assert len(txs) == 2

    def test_get_blocks_from_0_genesis(self):
        """get_blocks_from(0) 含创世"""
        bc = Blockchain()
        bc.append_block(_make_block(bc.latest_block, []))
        blocks = bc.get_blocks_from(0)
        assert blocks[0].block_height == 0
        assert blocks[0].previous_hash == "0" * 64


class TestPersistReload:
    def test_reload_restores_blocks(self, tmp_path):
        """重载恢复全部区块"""
        persist = tmp_path / "chain.json"
        bc1 = Blockchain(persist_path=str(persist))
        for i in range(5):
            bc1.append_block(_make_block(bc1.latest_block, [_make_tx(nonce=i)]))
        bc2 = Blockchain(persist_path=str(persist))
        assert bc2.height == 5
        assert bc2.validate_chain() is True

    def test_reload_then_continue(self, tmp_path):
        """重载后继续追加新块"""
        persist = tmp_path / "chain.json"
        bc1 = Blockchain(persist_path=str(persist))
        bc1.append_block(_make_block(bc1.latest_block, []))
        bc2 = Blockchain(persist_path=str(persist))
        bc2.append_block(_make_block(bc2.latest_block, []))
        assert bc2.height == 2
        assert bc2.validate_chain() is True

    def test_reload_stats_equal(self, tmp_path):
        """重载前后统计一致"""
        persist = tmp_path / "chain.json"
        bc1 = Blockchain(persist_path=str(persist))
        for i in range(3):
            bc1.append_block(_make_block(bc1.latest_block, [_make_tx(nonce=i)]))
        s1 = bc1.get_stats()
        bc2 = Blockchain(persist_path=str(persist))
        assert bc2.get_stats() == s1
