"""
后量子 Dilithium 适配器测试
验证适配器模式：ECDSA / Dilithium 统一接口、零 API 变更迁移
"""
import logging

import pytest

from blockchain.crypto.dilithium_adapter import (
    ECDSAAdapter, DilithiumAdapter, SignatureAdapter,
)

logging.basicConfig(level=logging.CRITICAL)


class TestAdapterInterface:
    def test_abc_interface(self):
        """SignatureAdapter 为抽象基类，含 sign/verify/get_algorithm_name"""
        assert SignatureAdapter.__abstractmethods__  # 至少含抽象方法

    def test_ecdsa_adapter(self):
        a = ECDSAAdapter()
        assert a.get_algorithm_name().startswith('ECDSA')
        assert a.get_security_level()  # 非空

    def test_dilithium_adapter_exists(self):
        a = DilithiumAdapter()
        # 未安装 pqcrypto 时回退 ECDSA，名称含 Dilithium 标识
        assert 'dilithium' in a.get_algorithm_name().lower()
        assert a.get_security_level()


class TestAdapterBehavior:
    def test_sign_verify_roundtrip(self):
        """适配器 sign→verify 往返一致"""
        for adapter_cls in [ECDSAAdapter, DilithiumAdapter]:
            a = adapter_cls()
            priv, pub = a.generate_key_pair() if hasattr(a, 'generate_key_pair') else (None, None)
            # 若适配器提供密钥生成则测试签名往返
            if priv is not None:
                msg = b'post-quantum adapter test'
                sig = a.sign(priv, msg)
                assert a.verify(pub, msg, sig) is True
                # 篡改消息应验证失败
                assert a.verify(pub, b'tampered', sig) is False
