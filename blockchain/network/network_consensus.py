"""
网络版 CW-PBFT 共识引擎
通过真实 P2P 网络（asyncio TCP）传递共识消息，实现真正的分布式三阶段共识

P1-7修复：投票广播附加ECDSA签名+验证
- _broadcast_vote()：发送投票前用私钥对投票数据签名
- _on_prepare()和_on_commit()：收到投票后验证签名，确认voter_id与签名公钥绑定

Architecture：
  ConsensusNode = P2PNode + CWPBFTConsensus + asyncio event loop
  每个 ConsensusNode 运行在独立线程的 event loop 上
  主线程通过 run_coroutine_threadsafe 触发异步操作
"""
import asyncio
import hashlib
import json
import logging
import threading
import time
from typing import Dict, List, Optional, Callable

from .p2p_node import P2PNode
from .message_protocol import MessageProtocol, MessageType
from ..consensus.cw_pbft import ConsensusVote, ConsensusState
from ..consensus.factory import create_consensus_engine

logger = logging.getLogger(__name__)


class NetworkConsensusNode:
    """
    真实网络共识节点
    P2P 节点 + 共识引擎（CW-PBFT/标准PBFT/快速）的完整组合
    """

    def __init__(
        self,
        node_id: str,
        host: str,
        port: int,
        all_node_ids: List[str],
        key_manager=None,  # P1-7修复：注入KeyManager用于投票签名
        consensus_mode: str = None,  # cw_pbft / standard_pbft / fast，None时读config.json
    ):
        self.node_id = node_id
        self.host = host
        self.port = port
        self.all_node_ids = all_node_ids
        self.key_manager = key_manager  # P1-7修复：密钥管理器引用
        self.consensus_mode = consensus_mode

        # P2P 底层通信（P1-9修复：传递key_manager给P2PNode）
        self.p2p = P2PNode(node_id, host, port, is_consensus_node=True, key_manager=key_manager)
        # 共识引擎（工厂创建，支持模式切换）
        self.cw_pbft = create_consensus_engine(node_id, all_node_ids, mode=consensus_mode)

        # asyncio event loop（专用线程）
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._thread: Optional[threading.Thread] = None
        self._ready = threading.Event()

        # 共识完成通知
        self._consensus_done = threading.Event()
        self._consensus_result: Optional[bool] = None

        # 消息计数
        self.msg_sent = 0
        self.msg_received = 0
        self.consensus_rounds = 0

        # 注册共识消息处理器
        self.p2p.register_handler(MessageType.CONSENSUS_PREPREPARE, self._on_preprepare)
        self.p2p.register_handler(MessageType.CONSENSUS_PREPARE, self._on_prepare)
        self.p2p.register_handler(MessageType.CONSENSUS_COMMIT, self._on_commit)

    # -------------------------------------------------------------------------
    # 启动 / 停止
    # -------------------------------------------------------------------------

    def start(self):
        """在独立线程启动 asyncio event loop 和 P2P 节点"""
        self._loop = asyncio.new_event_loop()
        self._thread = threading.Thread(
            target=self._run_loop, daemon=True, name=f"p2p-{self.node_id}"
        )
        self._thread.start()
        if not self._ready.wait(timeout=5):
            raise RuntimeError(f"P2P节点 {self.node_id} 启动超时或失败")

    def _run_loop(self):
        """event loop 线程入口"""
        asyncio.set_event_loop(self._loop)
        self._loop.run_until_complete(self._async_start())

    async def _async_start(self):
        await self.p2p.start()
        self._ready.set()
        # 永久运行，等待外部 stop()
        try:
            while True:
                await asyncio.sleep(1)
        except asyncio.CancelledError:
            pass

    def stop(self):
        """停止节点"""
        if self._loop and self._loop.is_running():
            future = asyncio.run_coroutine_threadsafe(self.p2p.stop(), self._loop)
            future.result(timeout=3)

    def clear_msg_cache(self):
        """安全清除消息去重缓存（通过 event loop，避免线程冲突）"""
        if self._loop and self._loop.is_running():
            async def _clear():
                self.p2p._seen_msg_ids.clear()
            future = asyncio.run_coroutine_threadsafe(_clear(), self._loop)
            future.result(timeout=2)

    # -------------------------------------------------------------------------
    # 连接到其他节点
    # -------------------------------------------------------------------------

    def connect_to(self, target_node_id: str, host: str, port: int):
        """主动连接到另一个节点（同步阻塞调用）"""
        future = asyncio.run_coroutine_threadsafe(
            self.p2p.connect_to(host, port, target_node_id),
            self._loop
        )
        future.result(timeout=5)

    # -------------------------------------------------------------------------
    # 发起共识（供主节点调用）
    # -------------------------------------------------------------------------

    def propose_consensus(self, block_hash: str, timeout: float = 3.0) -> bool:
        """
        主节点发起一轮共识（CW-PBFT/标准PBFT/快速模式）
        广播 PRE-PREPARE → 收集 PREPARE + COMMIT → 共识完成
        :return: 是否达成共识
        """
        self._consensus_done.clear()
        self._consensus_result = None
        self.consensus_rounds += 1

        # fast 模式：单轮确认，跳过网络三阶段与权重阈值（性能演示）
        if self.consensus_mode == 'fast':
            ok = self.cw_pbft.fast_consensus(block_hash, self.node_id)
            self._consensus_result = bool(ok)
            self._consensus_done.set()
            logger.info(f"[NetConsensus] {self.node_id} fast模式快速共识: {block_hash[:16]}... -> {ok}")
            return ok

        # 主节点发起 PRE-PREPARE，进入 PRE_PREPARE 状态
        vote = self.cw_pbft.start_consensus(block_hash)

        # 主节点自己也进入 PREPARE 状态并构造 PREPARE 票
        from ..consensus.cw_pbft import ConsensusVote as _CV, ConsensusState as _CS
        self.cw_pbft._state = _CS.PREPARE
        prepare_vote = _CV(
            voter_id=self.node_id,
            block_hash=block_hash,
            phase='prepare',
            weight=self.cw_pbft._weights.get(self.node_id, 1.0),
        )
        # 主节点把自己的 prepare 票加到投票池（必须在广播前完成，避免线程竞争）
        self.cw_pbft._votes['prepare'][self.node_id] = prepare_vote

        # 一次性异步广播 PRE-PREPARE + PREPARE（确保本地票已就位后再发消息）
        async def _broadcast_both():
            await self._broadcast_vote(MessageType.CONSENSUS_PREPREPARE, vote)
            await self._broadcast_vote(MessageType.CONSENSUS_PREPARE, prepare_vote)

        future = asyncio.run_coroutine_threadsafe(_broadcast_both(), self._loop)
        future.result(timeout=3)
        logger.info(f"[NetConsensus] {self.node_id} 广播 PRE-PREPARE: {block_hash[:16]}...")

        # 等待共识完成（_on_commit 里会 set _consensus_done）
        reached = self._consensus_done.wait(timeout=timeout)
        return reached and bool(self._consensus_result)

    # -------------------------------------------------------------------------
    # 消息处理器（异步，运行在 P2P 线程的 event loop）
    # -------------------------------------------------------------------------

    async def _on_preprepare(self, msg: Dict, from_node: str):
        """收到 PRE-PREPARE：验证后广播自己的 PREPARE"""
        self.msg_received += 1
        data = MessageProtocol.get_data(msg)
        block_hash = data.get("block_hash", "")
        primary_id = data.get("voter_id", from_node)

        # 如果处于上轮残留状态（COMMITTED），先重置再处理新轮
        from ..consensus.cw_pbft import ConsensusState as _CS
        if self.cw_pbft._state == _CS.COMMITTED:
            logger.info(f"[NetConsensus] {self.node_id} 收到新轮 PRE-PREPARE，重置上轮 COMMITTED 状态")
            self.cw_pbft.reset()

        prepare_vote = self.cw_pbft.receive_pre_prepare(block_hash, primary_id)

        # 关键：副本节点必须把自己的 PREPARE 票加入本地投票池！
        # 否则 _check_weight_threshold 统计时缺少自己的票，导致阈值永远不够
        self.cw_pbft._votes['prepare'][self.node_id] = prepare_vote

        logger.debug(f"[NetConsensus] {self.node_id} ← PRE-PREPARE from {from_node}")
        await self._broadcast_vote(MessageType.CONSENSUS_PREPARE, prepare_vote)

    async def _on_prepare(self, msg: Dict, from_node: str):
        """收到 PREPARE：验证签名后若达到 2/3 权重则广播 COMMIT"""
        self.msg_received += 1
        data = MessageProtocol.get_data(msg)
        voter_id = data.get("voter_id", from_node)

        # P1-7修复：验证投票签名，确认voter_id与签名公钥绑定
        if not self._verify_vote_signature(data, voter_id):
            logger.warning(f"[NetConsensus] {self.node_id} 丢弃 PREPARE：签名验证失败 from {voter_id}")
            return

        vote = ConsensusVote(
            voter_id=voter_id,
            block_hash=data.get("block_hash", ""),
            phase="prepare",
            weight=data.get("weight", 1.0),
        )
        logger.debug(f"[NetConsensus] {self.node_id} <- PREPARE from {from_node}")

        # 严格校验：_current_block_hash 必须已由 start_consensus/receive_pre_prepare 设置
        # 不再从投票消息自动设置——防止上轮残留消息污染哈希
        if self.cw_pbft._current_block_hash is None:
            logger.warning(f"[NetConsensus] {self.node_id} 丢弃 PREPARE：_current_block_hash 未设置")
            return
        if vote.block_hash != self.cw_pbft._current_block_hash:
            logger.warning(f"[NetConsensus] {self.node_id} 丢弃 PREPARE：hash 不匹配 "
                          f"({vote.block_hash[:8]} vs {self.cw_pbft._current_block_hash[:8]})")
            return

        # 确保当前节点处于 PREPARE 状态
        from ..consensus.cw_pbft import ConsensusState as _CS
        if self.cw_pbft._state != _CS.COMMITTED:
            self.cw_pbft._state = _CS.PREPARE

        commit_vote = self.cw_pbft.receive_vote(vote)
        if commit_vote:
            # 达到 2/3 权重阈值：
            # 1. 把自己的 COMMIT 加进自己的投票池（本地直接计入，不走网络去重）
            self.cw_pbft._votes['commit'][self.node_id] = commit_vote
            # 2. 广播 COMMIT 给其他节点
            await self._broadcast_vote(MessageType.CONSENSUS_COMMIT, commit_vote)
            # 3. 本节点也立即检查是否因本次 commit 达到阈值（短路：本地不走 _on_commit）
            from ..consensus.cw_pbft import ConsensusState as _CS
            self.cw_pbft._state = _CS.COMMIT
            if self.cw_pbft._check_weight_threshold('commit'):
                self.cw_pbft._state = _CS.COMMITTED
                self._consensus_result = True
                self._consensus_done.set()
                logger.info(f"[NetConsensus] {self.node_id} confirmed consensus complete (local)")

    async def _on_commit(self, msg: Dict, from_node: str):
        """收到 COMMIT：验证签名后若达到 2/3 权重则共识完成"""
        self.msg_received += 1
        data = MessageProtocol.get_data(msg)
        voter_id = data.get("voter_id", from_node)

        # P1-7修复：验证投票签名，确认voter_id与签名公钥绑定
        if not self._verify_vote_signature(data, voter_id):
            logger.warning(f"[NetConsensus] {self.node_id} 丢弃 COMMIT：签名验证失败 from {voter_id}")
            return

        vote = ConsensusVote(
            voter_id=voter_id,
            block_hash=data.get("block_hash", ""),
            phase="commit",
            weight=data.get("weight", 1.0),
        )
        logger.debug(f"[NetConsensus] {self.node_id} <- COMMIT from {from_node}")

        # 严格校验：_current_block_hash 必须已由 start_consensus/receive_pre_prepare 设置
        if self.cw_pbft._current_block_hash is None:
            logger.warning(f"[NetConsensus] {self.node_id} 丢弃 COMMIT：_current_block_hash 未设置")
            return
        if vote.block_hash != self.cw_pbft._current_block_hash:
            logger.warning(f"[NetConsensus] {self.node_id} 丢弃 COMMIT：hash 不匹配 "
                          f"({vote.block_hash[:8]} vs {self.cw_pbft._current_block_hash[:8]})")
            return

        # 确保在 COMMIT 状态才能统计
        from ..consensus.cw_pbft import ConsensusState as _CS
        if self.cw_pbft._state != _CS.COMMITTED:
            self.cw_pbft._state = _CS.COMMIT

        self.cw_pbft.receive_vote(vote)

        if self.cw_pbft.is_consensus_reached():
            self._consensus_result = True
            self._consensus_done.set()
            logger.info(f"[NetConsensus] {self.node_id} confirmed consensus complete")

    # -------------------------------------------------------------------------
    # 内部广播
    # -------------------------------------------------------------------------

    async def _broadcast_vote(self, msg_type: MessageType, vote: ConsensusVote):
        """
        将投票封装后广播给所有节点

        P1-7修复：发送投票前用proposer/voter的私钥对投票数据签名
        签名覆盖字段：voter_id + block_hash + phase + weight + timestamp
        """
        data = {
            "voter_id": vote.voter_id,
            "block_hash": vote.block_hash,
            "phase": vote.phase,
            "weight": vote.weight,
            "timestamp": vote.timestamp,
        }

        # P1-7修复：ECDSA签名投票数据
        signature_hex = None
        if self.key_manager is not None:
            priv_key = self.key_manager.get_private_key(vote.voter_id)
            if priv_key is not None:
                from ..crypto.ecdsa_utils import ECDSAUtils
                message_bytes = json.dumps(data, sort_keys=True).encode('utf-8')
                message_hash = hashlib.sha256(message_bytes).digest()
                sig = ECDSAUtils.sign(priv_key, message_hash)
                signature_hex = sig.hex()
                data["signature_hex"] = signature_hex  # 将签名附带在data中供接收方验证

        await self.p2p.broadcast(msg_type, data, signature=signature_hex)
        self.msg_sent += 1

    def _verify_vote_signature(self, data: Dict, voter_id: str) -> bool:
        """
        P1-7修复：验证投票消息的ECDSA签名

        验证流程：
        1. 从data中提取signature_hex
        2. 重新构造签名消息体（排除signature_hex自身）
        3. 用voter_id对应的公钥验签，确认voter_id与签名公钥绑定

        无key_manager时：宽松验证（仅检查签名格式），适用于纯P2P测试场景
        """
        signature_hex = data.get("signature_hex")
        if signature_hex is None:
            if self.key_manager is not None:
                logger.warning(f"[NetConsensus] 投票无签名: voter={voter_id}")
                return False
            # 无key_manager时允许无签名投票（向后兼容）
            return True

        try:
            # 构造签名消息体（排除signature_hex自身）
            verify_data = {
                "voter_id": data.get("voter_id", ""),
                "block_hash": data.get("block_hash", ""),
                "phase": data.get("phase", ""),
                "weight": data.get("weight", 1.0),
                "timestamp": data.get("timestamp", 0),
            }
            message_bytes = json.dumps(verify_data, sort_keys=True).encode('utf-8')
            message_hash = hashlib.sha256(message_bytes).digest()
            signature_bytes = bytes.fromhex(signature_hex)

            if self.key_manager is not None:
                pub_key = self.key_manager.get_public_key(voter_id)
                if pub_key is None:
                    logger.warning(f"[NetConsensus] 无法获取voter={voter_id}的公钥")
                    return False
                from ..crypto.ecdsa_utils import ECDSAUtils
                verified = ECDSAUtils.verify(pub_key, message_hash, signature_bytes)
                if not verified:
                    logger.warning(
                        f"[NetConsensus] 签名验证失败: voter={voter_id}，"
                        f"voter_id与签名公钥不绑定"
                    )
                return verified
            else:
                # 无key_manager时：宽松验证（仅检查签名格式）
                return len(signature_bytes) >= 64
        except Exception as e:
            logger.warning(f"[NetConsensus] 签名验证异常: voter={voter_id}, {e}")
            return False

    # -------------------------------------------------------------------------
    # 权重更新（由外部激励模块调用）
    # -------------------------------------------------------------------------

    def update_weight(self, node_id: str, weight: float):
        self.cw_pbft.update_weight(node_id, weight)

    def get_weights(self) -> Dict[str, float]:
        return self.cw_pbft.get_weights()

    def get_stats(self) -> Dict:
        return {
            "node_id": self.node_id,
            "port": self.port,
            "msg_sent": self.msg_sent,
            "msg_received": self.msg_received,
            "consensus_rounds": self.consensus_rounds,
            "network": self.p2p.get_network_stats(),
            "weights": self.get_weights(),
        }


# =============================================================================
# 多节点网络管理器（一键启动整个 P2P 共识网络）
# =============================================================================

class P2PConsensusNetwork:
    """
    多节点 P2P 共识网络管理器
    一键启动 N 个 ConsensusNode，自动完成 全连接拓扑 建立

    使用方式：
        net = P2PConsensusNetwork(n_nodes=3, base_port=7001)
        net.start()
        success = net.run_consensus(block_hash)
        stats = net.get_stats()
        net.stop()
    """

    BASE_HOST = "127.0.0.1"

    def __init__(self, n_nodes: int = 3, base_port: int = 7001, key_manager=None,
                 consensus_mode: str = None):
        self.n_nodes = n_nodes
        self.base_port = base_port
        self.node_ids = [f"agent_{i}" for i in range(n_nodes)]
        self.nodes: Dict[str, NetworkConsensusNode] = {}
        self._started = False
        self.key_manager = key_manager  # P1-7修复：注入KeyManager
        self.consensus_mode = consensus_mode  # cw_pbft / standard_pbft / fast

        # 统计
        self.total_consensus_rounds = 0
        self.total_msg_sent = 0
        self.total_msg_received = 0
        self.network_msg_log: List[Dict] = []   # 消息事件日志（供 Dashboard 展示）

    def start(self):
        """启动所有节点并建立全连接拓扑"""
        if self._started:
            return

        # 1. 创建并启动各节点
        for i, node_id in enumerate(self.node_ids):
            port = self.base_port + i
            node = NetworkConsensusNode(
                node_id=node_id,
                host=self.BASE_HOST,
                port=port,
                all_node_ids=self.node_ids,
                key_manager=self.key_manager,  # P1-7修复：传递key_manager
                consensus_mode=self.consensus_mode,  # 共识模式透传
            )
            node.start()
            self.nodes[node_id] = node

        time.sleep(0.3)   # 等待所有节点 TCP 服务就绪

        # 2. 建立全连接拓扑：编号小的连编号大的（每对只有1条TCP连接）
        #    TCP 本身是双向的——双方都能通过同一条连接读写
        #    避免双向连接导致 _connections 被覆盖、_read_loop 遗弃等问题
        for i, src_id in enumerate(self.node_ids):
            for j in range(i + 1, self.n_nodes):
                dst_id = self.node_ids[j]
                dst_port = self.base_port + j
                try:
                    self.nodes[src_id].connect_to(dst_id, self.BASE_HOST, dst_port)
                    logger.info(f"[P2PNetwork] {src_id} ──→ {dst_id}:{dst_port}")
                except Exception as e:
                    logger.warning(f"[P2PNetwork] 连接失败 {src_id}→{dst_id}: {e}")

        time.sleep(0.2)   # 等待握手完成
        self._started = True
        logger.info(f"[P2PNetwork] ✅ {self.n_nodes} 节点网络启动，全连接拓扑建立完成")

    def run_consensus(self, block_hash: str, primary_idx: int = 0) -> bool:
        """
        运行一轮真实 P2P CW-PBFT 共识
        :param block_hash: 待确认的区块哈希
        :param primary_idx: 主节点索引
        :return: 是否达成共识
        """
        if not self._started:
            self.start()

        # 每轮开始前重置所有节点的 CW-PBFT 状态
        # 等待上一轮异步消息处理完毕（增加等待时间，确保 TCP 缓冲区清空）
        time.sleep(0.3)
        for node in self.nodes.values():
            node.cw_pbft.reset()
            node._consensus_done.clear()
            node._consensus_result = None
            # 安全清空 msg_id 去重缓存（通过 event loop，避免线程冲突）
            node.clear_msg_cache()

        # 再等待一小段时间，让 reset 后的异步清理完成
        time.sleep(0.1)

        primary_id = self.node_ids[primary_idx % self.n_nodes]
        primary_node = self.nodes[primary_id]

        t0 = time.time()
        result = primary_node.propose_consensus(block_hash, timeout=3.0)
        elapsed_ms = int((time.time() - t0) * 1000)

        # 日志记录
        entry = {
            "round": self.total_consensus_rounds,
            "block_hash": block_hash[:16],
            "primary": primary_id,
            "success": result,
            "elapsed_ms": elapsed_ms,
            "timestamp": int(time.time() * 1000),
        }
        self.network_msg_log.append(entry)

        self.total_consensus_rounds += 1
        if result:
            logger.info(
                f"[P2PNetwork] 第{self.total_consensus_rounds}轮共识 ✅ "
                f"主节点={primary_id} 用时={elapsed_ms}ms"
            )
        else:
            logger.warning(
                f"[P2PNetwork] 第{self.total_consensus_rounds}轮共识 ❌ 超时"
            )
        return result

    def update_weights(self, weight_dict: Dict[str, float]):
        """更新所有节点的贡献权重"""
        for node_id, weight in weight_dict.items():
            if node_id in self.nodes:
                for target_node in self.nodes.values():
                    target_node.update_weight(node_id, weight)

    def get_weights(self) -> Dict[str, float]:
        """获取当前投票权重（从任意节点读取）"""
        if not self.nodes:
            return {}
        first = next(iter(self.nodes.values()))
        return first.get_weights()

    def stop(self):
        """停止所有节点"""
        for node in self.nodes.values():
            try:
                node.stop()
            except Exception as e:
                logger.warning(f"停止节点 {node.node_id} 时出错: {e}")
        self._started = False
        logger.info("[P2PNetwork] 所有节点已停止")

    def get_stats(self) -> Dict:
        """获取网络汇总统计"""
        total_sent = sum(n.msg_sent for n in self.nodes.values())
        total_recv = sum(n.msg_received for n in self.nodes.values())
        node_stats = {nid: node.get_stats() for nid, node in self.nodes.items()}

        return {
            "n_nodes": self.n_nodes,
            "total_consensus_rounds": self.total_consensus_rounds,
            "total_msg_sent": total_sent,
            "total_msg_received": total_recv,
            "weights": self.get_weights(),
            "nodes": node_stats,
            "recent_log": self.network_msg_log[-20:],   # 最近20条日志
        }

    def __enter__(self):
        self.start()
        return self

    def __exit__(self, *args):
        self.stop()
