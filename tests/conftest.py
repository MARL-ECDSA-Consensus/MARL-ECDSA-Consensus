"""
测试共享夹具 (Fixtures)
"""
import pytest
import os
import sys

# 确保项目根目录在 sys.path 中
_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)


@pytest.fixture(scope="session")
def ecdsa_utils():
    """ECDSA 工具类实例"""
    from blockchain.crypto.ecdsa_utils import ECDSAUtils
    return ECDSAUtils


@pytest.fixture(scope="function")
def key_pair(ecdsa_utils):
    """生成新的 ECDSA 密钥对 (每个测试独立)"""
    private_key, public_key = ecdsa_utils.generate_key_pair()
    return private_key, public_key


@pytest.fixture(scope="function")
def security_guard():
    """创建新的 SecurityGuard 实例"""
    from blockchain.crypto.security_guard import SecurityGuard
    return SecurityGuard()


@pytest.fixture(scope="function")
def sample_transaction():
    """创建一个示例交易"""
    from blockchain.ledger.block import Transaction
    import hashlib
    tx = Transaction(
        tx_id="",
        agent_id="agent_0",
        action={"move": "up", "position": [0.5, 0.3]},
        action_hash=hashlib.sha256(b"test_action").hexdigest(),
        timestamp=1000000,
        nonce=1,
        signature_hex="a1b2c3d4",
        tx_type="action"
    )
    tx.tx_id = tx.compute_hash()
    return tx


@pytest.fixture(scope="function")
def block_chain_instance():
    """创建区块链实例"""
    from blockchain.ledger.blockchain import Blockchain
    return Blockchain()


@pytest.fixture(scope="function")
def signed_package(key_pair):
    """创建已签名的动作包（使用 sign_action 完整流程）"""
    private_key, public_key = key_pair
    import time
    from blockchain.crypto.ecdsa_utils import ECDSAUtils

    return ECDSAUtils.sign_action(
        agent_id="agent_0",
        private_key=private_key,
        action={"action": 2, "position": [0.5, 0.3]},
        nonce=1,
        timestamp=int(time.time() * 1000)
    )
