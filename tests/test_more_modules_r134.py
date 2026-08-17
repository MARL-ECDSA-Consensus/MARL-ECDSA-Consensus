"""
更多模块剩余边界测试（RalphLoop 原子任务 JL）
覆盖：Transaction/Block 序列化、message 编解码边界（此前未单点覆盖）
通过标准：新增 ≥6 项测试全过
"""
import hashlib
import logging
import time

import pytest

from blockchain.ledger.block import Block, Transaction
from blockchain.network.message_protocol import MessageProtocol, MessageType

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


class TestTxSerialize:
    def test_tx_roundtrip(self):
        """Transaction 序列化往返"""
        tx = _make_tx("agent_0", 5)
        restored = Transaction.from_dict(tx.to_dict())
        assert restored == tx

    def test_tx_hash_excludes_txid(self):
        """交易哈希不含 tx_id 本身"""
        tx = _make_tx("agent_0", 1)
        tx2 = Transaction.from_dict(tx.to_dict())
        tx2.tx_id = "different"
        assert tx.compute_hash() == tx2.compute_hash()

    def test_tx_hash_64_hex(self):
        """交易哈希 64 hex"""
        assert len(_make_tx().compute_hash()) == 64


class TestBlockRoundtrip:
    def test_block_roundtrip_finalized(self):
        """finalize 后 Block 往返一致"""
        genesis = Block.create_genesis()
        b = Block(block_height=1, previous_hash=genesis.block_hash,
                  timestamp=int(time.time() * 1000), proposer="node_0",
                  transactions=[_make_tx()], state_root="0" * 64)
        b.finalize()
        restored = Block.from_dict(b.to_dict())
        assert restored.block_hash == b.block_hash
        assert restored.state_root == b.state_root

    def test_genesis_roundtrip(self):
        """创世块往返一致"""
        g = Block.create_genesis()
        restored = Block.from_dict(g.to_dict())
        assert restored.block_hash == g.block_hash


class TestEncodeDecode:
    def test_encode_length_prefix(self):
        """编码含 4 字节长度前缀"""
        msg = MessageProtocol.build(MessageType.HEARTBEAT, "node_0", {"a": 1}, nonce=1)
        encoded = MessageProtocol.encode(msg)
        length = int.from_bytes(encoded[:4], 'big')
        assert length == len(encoded[4:])

    def test_decode_roundtrip(self):
        """encode→decode 往返一致"""
        msg = MessageProtocol.build(MessageType.CONSENSUS_PREPARE, "node_1",
                                    {"h": "abc"}, nonce=2)
        decoded = MessageProtocol.decode(MessageProtocol.encode(msg))
        assert decoded == msg

    def test_decode_short_raises(self):
        """过短数据 ValueError"""
        with pytest.raises(ValueError):
            MessageProtocol.decode(b"\x00\x01")

    def test_unicode_roundtrip(self):
        """Unicode 内容编解码"""
        msg = MessageProtocol.build(MessageType.HEARTBEAT, "node_0",
                                    {"msg": "区块链共识协同"}, nonce=1)
        decoded = MessageProtocol.decode(MessageProtocol.encode(msg))
        assert decoded["body"]["data"]["msg"] == "区块链共识协同"


class TestFieldExtraction:
    def test_get_msg_id(self):
        """msg_id 提取"""
        msg = MessageProtocol.build(MessageType.HEARTBEAT, "node_1", {}, nonce=1)
        assert len(MessageProtocol.get_msg_id(msg)) == 16

    def test_get_data_none(self):
        """无 data → None"""
        msg = MessageProtocol.build(MessageType.HEARTBEAT, "node_0", None, nonce=1)
        assert MessageProtocol.get_data(msg) is None

    def test_get_signature_with_sig(self):
        """有签名提取"""
        msg = MessageProtocol.build(MessageType.BLOCK, "node_0", {}, nonce=1,
                                    signature="sig_hex")
        assert MessageProtocol.get_signature(msg) == "sig_hex"
