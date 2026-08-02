"""
ECDSA工具类 - MARL-ECDSA共识链密码学核心
基于 NIST secp256r1 (P-256) 椭圆曲线
遵循 FIPS 186-5 标准 + RFC 6979 确定性k值生成
"""
import hashlib
import json
import logging
import os
import time
from typing import Tuple, Optional, Dict, Any

from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives.asymmetric.utils import (
    decode_dss_signature, encode_dss_signature
)

logger = logging.getLogger(__name__)
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.exceptions import InvalidSignature


class ECDSAUtils:
    """
    ECDSA工具类：封装完整的签名/验签流程
    - 密钥对生成（secp256r1）
    - 消息签名（SHA256+ECDSA，RFC 6979确定性k值由底层库保证）
    - 签名验证
    - 公私钥序列化/反序列化
    - DER格式签名解析（提取r,s值用于k值重用检测）
    """

    CURVE = ec.SECP256R1()

    # -------------------------------------------------------------------------
    # 密钥管理
    # -------------------------------------------------------------------------

    @staticmethod
    def generate_key_pair() -> Tuple[ec.EllipticCurvePrivateKey, ec.EllipticCurvePublicKey]:
        """
        生成 secp256r1 密钥对
        :return: (private_key, public_key)
        """
        private_key = ec.generate_private_key(ECDSAUtils.CURVE)
        public_key = private_key.public_key()
        return private_key, public_key

    @staticmethod
    def private_key_to_bytes(private_key: ec.EllipticCurvePrivateKey) -> bytes:
        """私钥序列化为 PEM 字节"""
        return private_key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption()
        )

    @staticmethod
    def public_key_to_bytes(public_key: ec.EllipticCurvePublicKey) -> bytes:
        """公钥序列化为 PEM 字节"""
        return public_key.public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo
        )

    @staticmethod
    def public_key_to_hex(public_key: ec.EllipticCurvePublicKey) -> str:
        """公钥序列化为十六进制字符串（用于链上存储）"""
        raw = public_key.public_bytes(
            encoding=serialization.Encoding.X962,
            format=serialization.PublicFormat.UncompressedPoint
        )
        return raw.hex()

    @staticmethod
    def private_key_from_bytes(pem_bytes: bytes) -> ec.EllipticCurvePrivateKey:
        """从 PEM 字节反序列化私钥"""
        return serialization.load_pem_private_key(
            pem_bytes, password=None
        )

    @staticmethod
    def public_key_from_bytes(pem_bytes: bytes) -> ec.EllipticCurvePublicKey:
        """从 PEM 字节反序列化公钥"""
        return serialization.load_pem_public_key(pem_bytes)

    @staticmethod
    def public_key_from_hex(hex_str: str) -> ec.EllipticCurvePublicKey:
        """从十六进制字符串反序列化公钥"""
        raw = bytes.fromhex(hex_str)
        return ec.EllipticCurvePublicKey.from_encoded_point(ECDSAUtils.CURVE, raw)

    # -------------------------------------------------------------------------
    # 消息构造与哈希
    # -------------------------------------------------------------------------

    @staticmethod
    def build_message(
        agent_id: str,
        action: Any,
        timestamp: int,
        nonce: int,
        extra: Optional[Dict] = None
    ) -> bytes:
        """
        构造待签名消息体
        格式: {agent_id, action_hash, timestamp, nonce, [extra]}
        :return: UTF-8编码的JSON字节串（稳定排序）
        """
        action_hash = hashlib.sha256(
            json.dumps(action, sort_keys=True, ensure_ascii=False).encode('utf-8')
        ).hexdigest()

        payload = {
            'agent_id': agent_id,
            'action_hash': action_hash,
            'timestamp': timestamp,
            'nonce': nonce,
        }
        if extra:
            payload.update(extra)

        return json.dumps(payload, sort_keys=True, ensure_ascii=False).encode('utf-8')

    @staticmethod
    def hash_message(message: bytes) -> bytes:
        """对消息计算 SHA-256 摘要"""
        return hashlib.sha256(message).digest()

    # -------------------------------------------------------------------------
    # 签名与验签
    # -------------------------------------------------------------------------

    @staticmethod
    def sign(
        private_key: ec.EllipticCurvePrivateKey,
        message: bytes
    ) -> bytes:
        """
        使用私钥对消息进行 ECDSA 签名（SHA-256哈希）
        使用 RFC 6979 确定性 k 值生成（deterministic_signing），防止 k 值重用
        :param private_key: 签名私钥
        :param message: 原始消息字节
        :return: DER 格式签名字节
        """
        # P1-12修复: 显式启用 RFC 6979 确定性 nonce，同一私钥+同一消息必须产生相同签名
        # （cryptography >= 38 支持 deterministic_signing；旧版签名默认随机 nonce 会破坏确定性承诺）
        signature = private_key.sign(
            message,
            ec.ECDSA(hashes.SHA256(), deterministic_signing=True),
        )
        return signature

    @staticmethod
    def verify(
        public_key: ec.EllipticCurvePublicKey,
        message: bytes,
        signature: bytes
    ) -> bool:
        """
        使用公钥验证 ECDSA 签名
        :return: True=验签通过，False=验签失败（消息被篡改/非法签名）
        """
        try:
            public_key.verify(signature, message, ec.ECDSA(hashes.SHA256()))
            return True
        except InvalidSignature:
            return False
        except Exception as e:
            logger.debug(f"ECDSA验签异常: {e}")
            return False
    # -------------------------------------------------------------------------

    @staticmethod
    def extract_rs(signature: bytes) -> Tuple[int, int]:
        """
        从 DER 格式签名中提取 (r, s) 值
        用于 k 值重用检测（相同的 r 值意味着使用了相同的 k）
        """
        r, s = decode_dss_signature(signature)
        return r, s

    @staticmethod
    def encode_rs(r: int, s: int) -> bytes:
        """将 (r, s) 值编码为 DER 格式签名"""
        return encode_dss_signature(r, s)

    # -------------------------------------------------------------------------
    # 完整签名流程（含消息构造）
    # -------------------------------------------------------------------------

    @staticmethod
    def sign_action(
        agent_id: str,
        private_key: ec.EllipticCurvePrivateKey,
        action: Any,
        nonce: int,
        timestamp: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        为智能体行为生成完整的签名包
        :return: 包含 message_bytes, signature_hex, timestamp, nonce 的字典
        """
        if timestamp is None:
            timestamp = int(time.time() * 1000)  # 毫秒时间戳

        message = ECDSAUtils.build_message(agent_id, action, timestamp, nonce)
        signature = ECDSAUtils.sign(private_key, message)
        r, s = ECDSAUtils.extract_rs(signature)

        return {
            'agent_id': agent_id,
            'action': action,
            'timestamp': timestamp,
            'nonce': nonce,
            'message_hex': message.hex(),
            'signature_hex': signature.hex(),
            'r': r,
            's': s,
        }

    @staticmethod
    def verify_action_package(
        package: Dict[str, Any],
        public_key: ec.EllipticCurvePublicKey
    ) -> bool:
        """
        验证智能体行为签名包
        :param package: sign_action() 返回的签名包
        :param public_key: 发送方的公钥
        :return: True=合法，False=非法
        """
        try:
            message = bytes.fromhex(package['message_hex'])
            signature = bytes.fromhex(package['signature_hex'])
            return ECDSAUtils.verify(public_key, message, signature)
        except Exception as e:
            logger.debug(f"ECDSA验签异常: {e}")
            return False
