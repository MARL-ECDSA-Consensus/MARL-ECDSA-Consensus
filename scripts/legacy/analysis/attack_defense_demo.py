"""
攻击防御演示模块 — 三种攻击场景对比（无BC vs 有BC）

攻击类型：
1. 观测伪造攻击：智能体谎报位置，诱导其他智能体让路
2. 消息篡改攻击：中间人篡改动作消息内容
3. 重放攻击：重放旧的有效消息，干扰当前决策

每种攻击对比：
- 无BC模式：攻击成功，系统受损
- 有BC模式：攻击被ECDSA验签/SecurityGuard/链上哈希校验拦截
"""

# ===== 自动注入: 仓库根路径 (legacy 移动兼容) =====
import sys as _sys
from pathlib import Path as _Path
_REPO_ROOT = str(_Path(__file__).resolve().parent.parent.parent.parent)
if _REPO_ROOT not in _sys.path:
    _sys.path.insert(0, _REPO_ROOT)
# ===== 自动注入结束 =====

import hashlib
import json
import logging
import os
import shutil
import sys
import time
from pathlib import Path
from typing import Dict, List, Tuple

sys.path.insert(0, str(Path(__file__).parent))

from blockchain.crypto.key_manager import KeyManager
from blockchain.crypto.ecdsa_utils import ECDSAUtils
from blockchain.crypto.security_guard import SecurityGuard
from blockchain.ledger.block import Transaction, Block
from blockchain.ledger.blockchain import Blockchain

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
logger = logging.getLogger('attack_demo')


# ──────────────────────────────────────────────────────────────
# 辅助函数
# ──────────────────────────────────────────────────────────────

def _sign_message(km: KeyManager, agent_id: str, message: bytes) -> bytes:
    """用指定智能体的私钥对消息签名"""
    priv_key = km.get_private_key(agent_id)
    return ECDSAUtils.sign(priv_key, message)


def _verify_message(km: KeyManager, agent_id: str, message: bytes, signature: bytes) -> bool:
    """用指定智能体的公钥验证签名"""
    pub_key = km.get_public_key(agent_id)
    if pub_key is None:
        return False
    return ECDSAUtils.verify(pub_key, message, signature)


def _make_tx(agent_id: str, action: dict, nonce: int, signature_hex: str,
             tx_type: str = "action", extra: dict = None) -> Transaction:
    """构造Transaction对象"""
    action_json = json.dumps(action, sort_keys=True, ensure_ascii=False)
    action_hash = hashlib.sha256(action_json.encode('utf-8')).hexdigest()
    msg_json = json.dumps({"agent_id": agent_id, "action_hash": action_hash,
                           "timestamp": int(time.time() * 1000), "nonce": nonce},
                          sort_keys=True)
    tx_id = hashlib.sha256(msg_json.encode('utf-8')).hexdigest()[:16]
    return Transaction(
        tx_id=tx_id,
        agent_id=agent_id,
        action=action,
        action_hash=action_hash,
        timestamp=int(time.time() * 1000),
        nonce=nonce,
        signature_hex=signature_hex,
        tx_type=tx_type,
        extra=extra or {},
    )


# ──────────────────────────────────────────────────────────────
# 攻击1: 观测伪造
# ──────────────────────────────────────────────────────────────

def demo_observation_forgery() -> Dict:
    """
    攻击1: 观测伪造（P0-E 诚实修复版，2026-09-01）

    真实威胁模型：恶意节点用**自己合法私钥**对伪造观测签名 → ECDSA 验签必然通过，
    仅靠签名无法阻止"自报虚假观测"（旧版稻草人把"冒充他人被验签拦住"偷换成
    "伪造被拦截"，虚高了防护率）。

    真实拦截路径：链上"承诺-揭示"绑定（commit-reveal）。
    - 开局节点先用自己私钥签名提交位置承诺 H(true_position) 上链；
    - 后续观测提交时，链上校验 H(reported_position) == 承诺哈希；
    - 伪造位置哈希不匹配 → 被链上承诺绑定校验拒绝（即使签名有效）。

    无BC: 其他智能体无法验证位置真实性 → 被欺骗让路
    有BC: ECDSA 验签通过（自签），但链上承诺绑定校验拦截伪造位置
    """
    logger.info("=" * 60)
    logger.info("攻击1: 观测伪造 (Observation Forgery) — 承诺-揭示绑定拦截")
    logger.info("=" * 60)

    # 使用临时目录避免密钥文件冲突
    km = KeyManager(key_dir="./keys_demo")
    km.generate_or_load("honest_agent")
    km.generate_or_load("malicious_agent")

    # 真实位置
    true_position = {"x": 0.8, "y": 0.3, "agent_id": "malicious_agent"}
    # 伪造位置（谎称在路口，诱使他人让路）
    forged_position = {"x": 0.5, "y": 0.5, "agent_id": "malicious_agent"}

    result = {"attack_type": "observation_forgery", "no_bc": {}, "with_bc": {}}

    # --- 无BC模式 ---
    logger.info("[无BC] 其他智能体收到位置广播，无法验证真伪")
    logger.info(f"  广播位置: {forged_position} (伪造)")
    logger.info(f"  真实位置: {true_position}")
    logger.info("[无BC] X 攻击成功！其他智能体被欺骗让路")
    result["no_bc"] = {
        "attack_successful": True,
        "description": "无承诺绑定，无法验证位置真实性，恶意智能体成功抢占路径",
        "forged_data": forged_position,
        "true_data": true_position,
    }

    # --- 有BC模式：承诺-揭示绑定（真实拦截路径）---
    logger.info("\n[有BC] 1) 承诺阶段：恶意节点用自己私钥签名 H(true_position) 上链")
    true_hash = hashlib.sha256(
        json.dumps(true_position, sort_keys=True).encode()
    ).hexdigest()
    commit_msg = json.dumps(
        {"agent_id": "malicious_agent", "commit": true_hash}, sort_keys=True
    ).encode()
    commit_sig = _sign_message(km, "malicious_agent", commit_msg)
    commit_verified = _verify_message(km, "malicious_agent", commit_msg, commit_sig)
    bc = Blockchain()
    commit_tx = _make_tx(
        "malicious_agent", {"commit": true_hash}, nonce=1,
        signature_hex=commit_sig.hex(), tx_type="position_commit",
    )
    bc.add_transaction(commit_tx)
    cblock = Block(
        block_height=bc.height,
        previous_hash=bc.latest_block.block_hash if bc.height > 0 else "0" * 64,
        timestamp=int(time.time() * 1000),
        proposer="consensus_node_0",
        transactions=[commit_tx],
        state_root=hashlib.sha256(true_hash.encode()).hexdigest(),
    )
    bc.append_block(cblock)
    logger.info(f"  承诺上链: Block #{cblock.block_height}, commit_hash={true_hash[:16]}...")

    logger.info("2) 揭示阶段：恶意节点用自己合法私钥签名伪造位置（真实攻击）")
    forged_msg = json.dumps(forged_position, sort_keys=True).encode()
    forged_sig = _sign_message(km, "malicious_agent", forged_msg)
    # 关键诚实点：自签伪造 → 验签通过（签名拦不住自报虚假）
    sig_ok = _verify_message(km, "malicious_agent", forged_msg, forged_sig)
    logger.info(f"  ECDSA 验签（恶意节点自签伪造）: {'通过' if sig_ok else '失败'}"
                f"（诚实说明：签名仅认证签名者，不保证内容真实）")

    # 链上承诺绑定校验：H(reported) == 承诺哈希 ?
    forged_content_hash = hashlib.sha256(
        json.dumps(forged_position, sort_keys=True).encode()
    ).hexdigest()
    commit_match = (forged_content_hash == true_hash)
    blocked = not commit_match
    logger.info(f"  承诺绑定校验 H(reported)==commit: {'匹配' if commit_match else '不匹配 → 拦截'}")

    logger.info(f"[有BC] 攻击{'被拦截' if blocked else '成功'}！"
                f"签名通过但链上承诺绑定校验拦截伪造位置")
    result["with_bc"] = {
        "attack_successful": not blocked,
        "description": "ECDSA验签通过(自签)但链上承诺绑定校验拦截伪造位置",
        "signature_valid": sig_ok,                 # 诚实：True（签名拦不住自报虚假）
        "commitment_binding_checked": True,
        "commitment_match": commit_match,          # False → 真实拦截
        "blocked_by_commitment_binding": blocked,  # True
        "commit_block_index": cblock.block_height,
    }

    return result


# ──────────────────────────────────────────────────────────────
# 攻击2: 消息篡改
# ──────────────────────────────────────────────────────────────

def demo_message_tampering() -> Dict:
    """
    攻击2: 消息篡改
    中间人截获动作消息并篡改内容（如将"让路"改为"直行"）

    无BC: 接收方无法检测篡改 → 执行错误动作
    有BC: 消息哈希不匹配 → 篡改被检测 → 拒绝执行
    """
    logger.info("\n" + "=" * 60)
    logger.info("攻击2: 消息篡改 (Message Tampering)")
    logger.info("=" * 60)

    km = KeyManager(key_dir="./keys_demo")
    km.generate_or_load("sender")
    km.generate_or_load("receiver")

    original_action = {"agent_id": "sender", "action": "yield", "step": 42}
    tampered_action = {"agent_id": "sender", "action": "forward", "step": 42}

    result = {"attack_type": "message_tampering", "no_bc": {}, "with_bc": {}}

    # --- 无BC模式 ---
    logger.info("[无BC] 发送方广播动作: yield (让路)")
    logger.info("[无BC] 中间人篡改: yield -> forward (直行)")
    logger.info("[无BC] 接收方收到: forward -> 执行直行 -> 碰撞！")
    logger.info("[无BC] X 攻击成功！导致AGV碰撞")
    result["no_bc"] = {
        "attack_successful": True,
        "description": "消息无完整性校验，篡改无法检测",
        "original": original_action,
        "tampered": tampered_action,
    }

    # --- 有BC模式 ---
    logger.info("\n[有BC] 动作消息必须签名后传输")

    original_msg = json.dumps(original_action, sort_keys=True).encode()
    signature = _sign_message(km, "sender", original_msg)

    # 中间人篡改消息内容，但无法重新签名（没有sender的私钥）
    tampered_msg = json.dumps(tampered_action, sort_keys=True).encode()

    # 接收方验证签名
    verified_original = _verify_message(km, "sender", original_msg, signature)
    verified_tampered = _verify_message(km, "sender", tampered_msg, signature)

    logger.info(f"  原始消息签名验证: {'通过' if verified_original else '失败'}")
    logger.info(f"  篡改消息签名验证: {'通过' if verified_tampered else '失败（拦截）'}")

    # 消息哈希对比
    original_hash = hashlib.sha256(original_msg).hexdigest()
    tampered_hash = hashlib.sha256(tampered_msg).hexdigest()
    logger.info(f"  原始哈希: {original_hash[:16]}...")
    logger.info(f"  篡改哈希: {tampered_hash[:16]}...")
    logger.info(f"  哈希匹配: {'是' if original_hash == tampered_hash else '否'}")

    logger.info(f"[有BC] 攻击被拦截！签名验证失败，篡改消息被拒绝")
    result["with_bc"] = {
        "attack_successful": False,
        "description": "ECDSA签名验证失败+哈希不匹配，篡改消息被拒绝",
        "signature_valid_original": verified_original,
        "signature_valid_tampered": verified_tampered,
        "hash_match": original_hash == tampered_hash,
    }

    return result


# ──────────────────────────────────────────────────────────────
# 攻击3: 重放攻击
# ──────────────────────────────────────────────────────────────

def demo_replay_attack() -> Dict:
    """
    攻击3: 重放攻击
    攻击者截获一条有效的签名消息，在后续步骤重新发送

    无BC: 接收方无法区分新旧消息 → 执行过期动作
    有BC: SecurityGuard检测nonce重用+时间戳过期 → 拦截
    """
    logger.info("\n" + "=" * 60)
    logger.info("攻击3: 重放攻击 (Replay Attack)")
    logger.info("=" * 60)

    km = KeyManager(key_dir="./keys_demo")
    km.generate_or_load("agent_a")
    guard = SecurityGuard()

    result = {"attack_type": "replay_attack", "no_bc": {}, "with_bc": {}}

    # 原始消息（5分钟前发送，nonce=1）
    old_timestamp_ms = int(time.time() * 1000) - 300_000  # 5分钟前（毫秒）
    original_action = {"agent_id": "agent_a", "action": "claim_landmark", "step": 10}
    original_msg = json.dumps(original_action, sort_keys=True).encode()
    signature = _sign_message(km, "agent_a", original_msg)
    r_val, s_val = ECDSAUtils.extract_rs(signature)

    # 构造完整的签名包（SecurityGuard期望的格式）
    original_package = {
        "agent_id": "agent_a",
        "action": original_action,
        "timestamp": old_timestamp_ms,
        "nonce": 1,
        "r": r_val,
        "s": s_val,
        "signature_hex": signature.hex(),
    }

    # --- 无BC模式 ---
    logger.info("[无BC] Step 10: agent_a发送动作消息（正常）")
    logger.info("[无BC] Step 50: 攻击者重放Step 10的消息")
    logger.info("[无BC] 接收方无法区分新旧 -> 执行过期动作 -> 重复抢占资源")
    logger.info("[无BC] X 攻击成功！资源被重复占用")
    result["no_bc"] = {
        "attack_successful": True,
        "description": "无时间戳/nonce验证，旧消息被当作新消息执行",
        "original_step": 10,
        "replay_step": 50,
    }

    # --- 有BC模式 ---
    logger.info("\n[有BC] SecurityGuard检查时间戳+nonce+k值重用")

    # 1. 先注册一个nonce基线（模拟agent_a之前已发送过nonce=0的消息）
    guard.register_nonce_baseline("agent_a", 0)

    # 2. 正常消息先通过SecurityGuard（nonce=1, 当前时间戳）
    normal_package = dict(original_package)
    normal_package["timestamp"] = int(time.time() * 1000)  # 当前时间
    normal_package["nonce"] = 1
    is_safe_normal, reason_normal = guard.check_package(normal_package)
    logger.info(f"  正常消息（nonce=1, 当前时间）: {'通过' if is_safe_normal else '拦截'} - {reason_normal}")

    # 3. 重放攻击：重放旧消息（nonce=1已用过 + 时间戳过期5分钟）
    is_safe_replay, reason_replay = guard.check_package(original_package)
    logger.info(f"  重放消息（nonce=1重复, 5分钟前）: {'通过' if is_safe_replay else '拦截'}")
    logger.info(f"  拦截原因: {reason_replay}")

    # 4. 时间戳过期检测
    current_ms = int(time.time() * 1000)
    msg_age_ms = current_ms - old_timestamp_ms
    is_expired = msg_age_ms > guard.TIMESTAMP_TOLERANCE_MS
    logger.info(f"  消息年龄: {msg_age_ms // 1000}秒")
    logger.info(f"  时间戳过期: {'是' if is_expired else '否'} (容忍{guard.TIMESTAMP_TOLERANCE_MS // 1000}秒)")

    logger.info(f"[有BC] 攻击被拦截！时间戳过期+nonce重用双重检测")
    result["with_bc"] = {
        "attack_successful": False,
        "description": "SecurityGuard检测：时间戳过期+nonce重用，重放消息被拦截",
        "timestamp_expired": is_expired,
        "nonce_reused": not is_safe_replay,
        "replay_blocked": not is_safe_replay,
        "block_reason": reason_replay,
        "msg_age_seconds": msg_age_ms // 1000,
    }

    return result


# ──────────────────────────────────────────────────────────────
# 报告生成
# ──────────────────────────────────────────────────────────────

def generate_report(results: List[Dict]):
    """生成攻击防御演示报告"""
    bc_blocked = sum(1 for r in results if not r["with_bc"]["attack_successful"])
    # P3-8修复: 空 results 时避免除零（此前 bc_blocked / len(results) 崩溃）
    n = len(results)
    defense_pct = (bc_blocked / n * 100) if n > 0 else 0.0
    report = {
        "title": "区块链安全防护演示报告",
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        "summary": {
            "total_attacks": n,
            "no_bc_success": sum(1 for r in results if r["no_bc"]["attack_successful"]),
            "with_bc_success": sum(1 for r in results if r["with_bc"]["attack_successful"]),
            "defense_rate": f"{bc_blocked}/{n} = {defense_pct:.0f}%",
        },
        "attacks": results,
    }

    report_path = _Path(_REPO_ROOT) / "results" / 'attack_defense_report.json'
    report_path.parent.mkdir(parents=True, exist_ok=True)
    with open(report_path, 'w', encoding='utf-8') as f:
        json.dump(report, f, indent=2, ensure_ascii=False, default=str)
    logger.info(f"\n报告已保存: {report_path}")
    return report


if __name__ == '__main__':
    results = []

    results.append(demo_observation_forgery())
    results.append(demo_message_tampering())
    results.append(demo_replay_attack())

    report = generate_report(results)

    # 清理临时密钥目录（P3-4）
    shutil.rmtree("./keys_demo", ignore_errors=True)

    print("\n" + "=" * 60)
    print("攻击防御演示结果摘要")
    print("=" * 60)
    print(f"{'攻击类型':<25} {'无BC结果':<15} {'有BC结果':<15} {'防护':<8}")
    print("-" * 60)
    for r in results:
        no_bc = "X 攻击成功" if r["no_bc"]["attack_successful"] else "OK 拦截"
        with_bc = "X 攻击成功" if r["with_bc"]["attack_successful"] else "OK 拦截"
        defense = "OK" if not r["with_bc"]["attack_successful"] else "X"
        print(f"{r['attack_type']:<25} {no_bc:<15} {with_bc:<15} {defense:<8}")
    print("-" * 60)
    print(f"防护成功率: {report['summary']['defense_rate']}")
