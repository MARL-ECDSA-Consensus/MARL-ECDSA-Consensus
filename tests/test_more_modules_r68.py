"""
更多模块剩余边界测试（RalphLoop 原子任务 EJ）
覆盖：message_protocol 编解码/字段提取边界（此前未单点覆盖）
通过标准：新增 ≥6 项测试全过
"""
import logging

import pytest

from blockchain.network.message_protocol import MessageProtocol, MessageType

logging.basicConfig(level=logging.CRITICAL)


def _make_msg():
    return MessageProtocol.build(MessageType.CONSENSUS_PREPARE, "node_1",
                                 data={"hash": "abc", "weight": 1.5}, nonce=7)


class TestEncodeDecode:
    def test_encode_length_prefix(self):
        """编码含 4 字节长度前缀"""
        msg = _make_msg()
        encoded = MessageProtocol.encode(msg)
        prefix = int.from_bytes(encoded[:4], 'big')
        assert prefix == len(encoded[4:])

    def test_decode_roundtrip(self):
        """encode→decode 往返一致"""
        msg = _make_msg()
        decoded = MessageProtocol.decode(MessageProtocol.encode(msg))
        assert decoded == msg

    def test_decode_short_raises(self):
        """过短数据 → ValueError"""
        with pytest.raises(ValueError):
            MessageProtocol.decode(b'\x00\x01')  # 2 字节


class TestFieldExtraction:
    def test_get_msg_id(self):
        """msg_id 提取"""
        msg = _make_msg()
        assert len(MessageProtocol.get_msg_id(msg)) == 16

    def test_get_msg_type(self):
        """msg_type 提取"""
        msg = _make_msg()
        assert MessageProtocol.get_msg_type(msg) == MessageType.CONSENSUS_PREPARE

    def test_get_from_node(self):
        """from_node 提取"""
        msg = _make_msg()
        assert MessageProtocol.get_from_node(msg) == "node_1"

    def test_get_data(self):
        """data 提取"""
        msg = _make_msg()
        assert MessageProtocol.get_data(msg) == {"hash": "abc", "weight": 1.5}

    def test_get_signature_none(self):
        """无签名 → None"""
        msg = _make_msg()
        assert MessageProtocol.get_signature(msg) is None

    def test_get_signature_with_sig(self):
        """有签名 → 提取"""
        msg = MessageProtocol.build(MessageType.BLOCK, "node_0", {}, nonce=1,
                                    signature="sig_hex")
        assert MessageProtocol.get_signature(msg) == "sig_hex"


class TestBuildEdges:
    def test_build_with_data_none(self):
        """data=None 消息可构建"""
        msg = MessageProtocol.build(MessageType.HEARTBEAT, "node_0", None, nonce=1)
        assert msg["body"]["data"] is None

    def test_build_nonce_differs_msg_id(self):
        """nonce 不同 → 消息不同"""
        m1 = MessageProtocol.build(MessageType.HEARTBEAT, "node_0", {}, nonce=1)
        m2 = MessageProtocol.build(MessageType.HEARTBEAT, "node_0", {}, nonce=2)
        assert m1["header"]["nonce"] != m2["header"]["nonce"]
