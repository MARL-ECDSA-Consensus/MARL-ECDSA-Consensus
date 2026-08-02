"""
密钥管理器
负责智能体本地密钥对的生成、持久化存储、加载
私钥仅存储于本地，绝不上链传输
"""
import os
import json
import logging
from pathlib import Path
from typing import Optional, Dict, Tuple

from cryptography.hazmat.primitives.asymmetric import ec

from .ecdsa_utils import ECDSAUtils

logger = logging.getLogger(__name__)


class KeyManager:
    """
    智能体密钥管理器
    - 本地生成并安全存储密钥对
    - 按 agent_id 索引，支持多智能体
    - 仅暴露公钥用于链上注册，私钥绝不离开本地
    """

    def __init__(self, key_dir: str = "./keys"):
        self.key_dir = Path(key_dir)
        self.key_dir.mkdir(parents=True, exist_ok=True)
        self._key_cache: Dict[str, Tuple[ec.EllipticCurvePrivateKey, ec.EllipticCurvePublicKey]] = {}

    # -------------------------------------------------------------------------
    # 核心接口
    # -------------------------------------------------------------------------

    def generate_or_load(self, agent_id: str) -> Tuple[ec.EllipticCurvePrivateKey, ec.EllipticCurvePublicKey]:
        """
        为指定智能体生成或加载密钥对
        如果本地已有密钥文件则加载，否则生成新密钥对并保存
        """
        if agent_id in self._key_cache:
            return self._key_cache[agent_id]

        priv_path = self.key_dir / f"{agent_id}_private.pem"
        pub_path = self.key_dir / f"{agent_id}_public.pem"

        if priv_path.exists() and pub_path.exists():
            # 从磁盘加载
            private_key = ECDSAUtils.private_key_from_bytes(priv_path.read_bytes())
            public_key = ECDSAUtils.public_key_from_bytes(pub_path.read_bytes())
            logger.info(f"[KeyManager] 已加载 {agent_id} 的密钥对")
        else:
            # 生成新密钥对并保存
            private_key, public_key = ECDSAUtils.generate_key_pair()
            priv_path.write_bytes(ECDSAUtils.private_key_to_bytes(private_key))
            # P0-2: 私钥文件权限保护 — 仅 owner 可读写，防止其他用户读取私钥
            # Windows 平台 os.chmod 对文件权限的支持有限，但至少尝试执行
            try:
                os.chmod(str(priv_path), 0o600)
            except (OSError, AttributeError):
                logger.debug(f"[KeyManager] os.chmod(0o600) 在当前平台不可用或失败，跳过")
            pub_path.write_bytes(ECDSAUtils.public_key_to_bytes(public_key))
            logger.info(f"[KeyManager] 已为 {agent_id} 生成新密钥对")

        self._key_cache[agent_id] = (private_key, public_key)
        return private_key, public_key

    def get_public_key(self, agent_id: str) -> Optional[ec.EllipticCurvePublicKey]:
        """获取指定智能体的公钥（不暴露私钥）"""
        pair = self._key_cache.get(agent_id)
        if pair:
            return pair[1]
        pub_path = self.key_dir / f"{agent_id}_public.pem"
        if pub_path.exists():
            pub_key = ECDSAUtils.public_key_from_bytes(pub_path.read_bytes())
            return pub_key
        return None

    def get_public_key_hex(self, agent_id: str) -> Optional[str]:
        """获取公钥的十六进制字符串表示（用于链上注册）"""
        pub_key = self.get_public_key(agent_id)
        if pub_key:
            return ECDSAUtils.public_key_to_hex(pub_key)
        return None

    def get_private_key(self, agent_id: str) -> Optional[ec.EllipticCurvePrivateKey]:
        """获取私钥（仅限本地使用）"""
        pair = self._key_cache.get(agent_id)
        if pair:
            return pair[0]
        priv_path = self.key_dir / f"{agent_id}_private.pem"
        if priv_path.exists():
            priv_key = ECDSAUtils.private_key_from_bytes(priv_path.read_bytes())
            return priv_key
        return None

    def remove_key(self, agent_id: str) -> bool:
        """删除智能体密钥（谨慎使用）"""
        self._key_cache.pop(agent_id, None)
        priv_path = self.key_dir / f"{agent_id}_private.pem"
        pub_path = self.key_dir / f"{agent_id}_public.pem"
        removed = False
        if priv_path.exists():
            priv_path.unlink()
            removed = True
        if pub_path.exists():
            pub_path.unlink()
            removed = True
        return removed

    def list_agents(self) -> list:
        """列出所有已注册密钥的智能体ID"""
        agents = set()
        for f in self.key_dir.glob("*_private.pem"):
            agent_id = f.stem.replace("_private", "")
            agents.add(agent_id)
        return list(agents)
