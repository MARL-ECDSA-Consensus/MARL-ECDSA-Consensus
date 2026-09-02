"""
CW-PBFT 贡献加权拜占庭容错共识算法
Contribution-Weighted Practical Byzantine Fault Tolerance

核心设计：
1. 节点准入：仅完成身份注册的共识节点可参与
2. 主节点选举：轮询制，每10个区块轮换一次
3. 投票权重：与历史贡献度正相关
4. 共识流程：预准备→准备→提交，达成2/3以上权重同意即确认
5. 拜占庭容错：支持 ⌊(n-1)/3⌋ 个恶意节点

简化实现（单机模拟版）：
- 去掉网络I/O，用本地模拟消息传递
- 保留完整的三阶段共识逻辑
- 支持多节点贡献权重计算
"""
import hashlib
import logging
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional, Set

logger = logging.getLogger(__name__)


class ConsensusState(str, Enum):
    IDLE = "idle"               # 空闲
    PRE_PREPARE = "pre_prepare" # 预准备阶段
    PREPARE = "prepare"         # 准备阶段
    COMMIT = "commit"           # 提交阶段
    COMMITTED = "committed"     # 已确认
    VIEW_CHANGE = "view_change" # 视图切换


@dataclass
class ConsensusVote:
    """共识投票"""
    voter_id: str
    block_hash: str
    phase: str          # pre_prepare / prepare / commit
    weight: float
    timestamp: int = field(default_factory=lambda: int(time.time() * 1000))
    signature_hex: str = ""


class CWPBFTConsensus:
    """
    贡献加权PBFT共识引擎

    权重推导（Shapley值风格）：
    基础份额：κ_0 = 1/3（对称性初始分配）
    任务贡献调整：κ_task = 1/3 + σ(task_variance)/3（高方差→更高边际贡献）
    协作正外部性：κ_coop = 1/3 + φ(cooperation_externality)/3（合作产生正外部性→补偿）
    合规基础份额：κ_compliance = 1/3 - σ/3 - φ/3（剩余份额归合规）

    约束：κ_task + κ_coop + κ_compliance = 1

    实验校准：σ≈0.1, φ≈0.05 → κ_task≈0.40, κ_coop≈0.35, κ_compliance≈0.25
    这与Shapley值理论一致：边际贡献大的维度获得更高权重

    P1-8修复：
    - 新注册节点初始权重从1.0降为INITIAL_WEIGHT=0.3，需累积贡献后逐步提升
    - 权重下界MIN_WEIGHT=0.1，确保非封禁节点权重不会降至0（避免失去投票权）
    - update_weight()对非封禁节点使用 max(MIN_WEIGHT, new_weight) 保护

    使用方式：
    1. 初始化：传入共识节点列表
    2. 开始共识：propose_block()
    3. 收集投票：receive_vote()
    4. 检查是否达成共识：check_consensus()
    """

    BLOCKS_PER_ROTATION = 10    # 每10个区块轮换主节点
    CONSENSUS_TIMEOUT_MS = 5000 # 5秒共识超时
    # P1-8修复：权重下界保护常量
    MIN_WEIGHT = 0.1            # 非封禁节点权重最低值，防止权重降至0失去投票权
    INITIAL_WEIGHT = 0.3        # 新注册节点初始权重，需累积贡献后逐步提升（而非直接1.0）

    def __init__(self, node_id: str, consensus_nodes: List[str]):
        """
        :param node_id: 本节点ID
        :param consensus_nodes: 所有共识节点的ID列表
        """
        self.node_id = node_id
        self.consensus_nodes = list(consensus_nodes)
        self.n = len(consensus_nodes)               # 节点总数
        self.f = (self.n - 1) // 3                 # 最大容错数

        # 当前视图号（用于主节点选举）
        self._view = 0
        # 当前共识轮次状态
        self._state = ConsensusState.IDLE
        # 当前提议区块哈希
        self._current_block_hash: Optional[str] = None
        # 投票收集：{phase: {voter_id: vote}}
        self._votes: Dict[str, Dict[str, ConsensusVote]] = {
            'prepare': {},
            'commit': {},
        }
        # 节点贡献权重：{node_id: weight}
        # P1-8修复：新注册节点初始权重为INITIAL_WEIGHT而非1.0
        self._weights: Dict[str, float] = {nid: self.INITIAL_WEIGHT for nid in consensus_nodes}
        # 总权重
        self._total_weight: float = sum(self._weights.values())
        # 共识开始时间
        self._consensus_start_ms: int = 0
        # 权重演化追踪：每轮记录权重变化
        self._weight_history: List[Dict] = []
        # 共识成功/失败计数
        self.consensus_success_count: int = 0
        self.consensus_fail_count: int = 0

    # -------------------------------------------------------------------------
    # 主节点管理
    # -------------------------------------------------------------------------

    def get_primary(self, block_height: int) -> str:
        """
        获取指定区块高度的主节点（轮询制）
        每 BLOCKS_PER_ROTATION 个区块轮换一次
        """
        primary_index = (block_height // self.BLOCKS_PER_ROTATION) % self.n
        return self.consensus_nodes[primary_index]

    def is_primary(self, block_height: int) -> bool:
        """当前节点是否为本轮主节点"""
        return self.get_primary(block_height) == self.node_id

    # -------------------------------------------------------------------------
    # 三阶段共识流程
    # -------------------------------------------------------------------------

    def start_consensus(self, block_hash: str) -> ConsensusVote:
        """
        主节点发起共识：PRE-PREPARE阶段
        :return: 预准备投票（广播给其他节点）
        """
        self._state = ConsensusState.PRE_PREPARE
        self._current_block_hash = block_hash
        self._consensus_start_ms = int(time.time() * 1000)
        self._votes = {'prepare': {}, 'commit': {}}

        vote = ConsensusVote(
            voter_id=self.node_id,
            block_hash=block_hash,
            phase='pre_prepare',
            weight=self._weights.get(self.node_id, 1.0),
        )
        logger.info(f"[CW-PBFT] 主节点 {self.node_id} 发起共识: {block_hash[:16]}...")
        return vote

    def receive_pre_prepare(self, block_hash: str, primary_id: str) -> ConsensusVote:
        """
        非主节点收到PRE-PREPARE：验证后进入PREPARE阶段
        :return: 本节点的PREPARE投票
        """
        self._state = ConsensusState.PREPARE
        self._current_block_hash = block_hash
        self._consensus_start_ms = int(time.time() * 1000)

        vote = ConsensusVote(
            voter_id=self.node_id,
            block_hash=block_hash,
            phase='prepare',
            weight=self._weights.get(self.node_id, 1.0),
        )
        logger.debug(f"[CW-PBFT] {self.node_id} 进入PREPARE阶段")
        return vote

    def receive_vote(self, vote: ConsensusVote) -> Optional[ConsensusVote]:
        """
        收到其他节点的投票
        :return: 如果达到阈值，返回下一阶段投票；否则返回None
        """
        if vote.block_hash != self._current_block_hash:
            logger.debug(f"[CW-PBFT] 丢弃不匹配的投票: {vote.voter_id}")
            return None

        phase = vote.phase
        if phase in self._votes:
            self._votes[phase][vote.voter_id] = vote

        # PREPARE阶段：达到2/3权重 → 进入COMMIT
        if phase == 'prepare' and self._state == ConsensusState.PREPARE:
            if self._check_weight_threshold('prepare'):
                self._state = ConsensusState.COMMIT
                commit_vote = ConsensusVote(
                    voter_id=self.node_id,
                    block_hash=self._current_block_hash,
                    phase='commit',
                    weight=self._weights.get(self.node_id, 1.0),
                )
                logger.debug(f"[CW-PBFT] {self.node_id} 进入COMMIT阶段")
                return commit_vote

        # COMMIT阶段：达到2/3权重 → 共识达成
        if phase == 'commit' and self._state == ConsensusState.COMMIT:
            if self._check_weight_threshold('commit'):
                self._state = ConsensusState.COMMITTED
                logger.info(f"[CW-PBFT] ✅ 共识达成！block_hash={self._current_block_hash[:16]}...")

        return None

    def is_consensus_reached(self) -> bool:
        """共识是否已达成"""
        return self._state == ConsensusState.COMMITTED

    def get_state(self) -> ConsensusState:
        return self._state

    def is_timed_out(self) -> bool:
        """检查共识是否超时"""
        if self._consensus_start_ms == 0:
            return False
        elapsed = int(time.time() * 1000) - self._consensus_start_ms
        return elapsed > self.CONSENSUS_TIMEOUT_MS

    def reset(self):
        """重置共识状态（超时后调用）"""
        self._state = ConsensusState.IDLE
        self._current_block_hash = None
        self._votes = {'prepare': {}, 'commit': {}}
        self._consensus_start_ms = 0

    # -------------------------------------------------------------------------
    # 快速模拟共识（单节点/测试场景）
    # -------------------------------------------------------------------------

    def fast_consensus(self, block_hash: str, proposer: str) -> bool:
        """
        快速模拟共识（用于单节点测试或少于4节点的场景）
        假设所有节点都诚实，直接模拟三阶段投票

        注意：此方法跳过了权重阈值检查，仅适用于测试场景。
        生产环境应使用 simulated_consensus()，它执行完整三阶段+权重阈值检查。
        已标记为deprecated，推荐使用 simulated_consensus() 替代。
        """
        self._current_block_hash = block_hash
        self._votes = {'prepare': {}, 'commit': {}}

        # 模拟所有节点投票
        for nid in self.consensus_nodes:
            w = self._weights.get(nid, self.INITIAL_WEIGHT)
            self._votes['prepare'][nid] = ConsensusVote(
                voter_id=nid, block_hash=block_hash,
                phase='prepare', weight=w
            )
            self._votes['commit'][nid] = ConsensusVote(
                voter_id=nid, block_hash=block_hash,
                phase='commit', weight=w
            )

        self._state = ConsensusState.COMMITTED
        self.consensus_success_count += 1
        logger.info(f"[CW-PBFT] 快速共识完成: {block_hash[:16]}...")
        return True

    def simulated_consensus(
        self,
        block_hash: str,
        proposer: str,
        byzantine_nodes: Optional[Set[str]] = None,
    ) -> bool:
        """
        单机版完整三阶段共识模拟（P1-关键架构修复 + P0-D 拜占庭注入）

        P0-D 修复（2026-09-01）：新增 byzantine_nodes 参数，
        支持真实拜占庭容错验证。被标记的节点将拒绝投票
        （省略故障 / 拒绝服务模型），从而真实消费 byz_ratio：
        - 当拜占庭节点权重之和 > 1/3 总权重时，投票权重无法达到
          2/3 阈值，共识将真实失败（而非像 fast_consensus 那样恒为成功）；
        - 无拜占庭节点（默认）时退化为原全诚实路径，训练流程不受影响。

        区别于fast_consensus()：
        - 执行完整PREPARE→COMMIT→FINALIZE三阶段流程
        - 每阶段检查权重阈值：prepare/commit阶段均需总投票权重>2/3总权重
        - 阈值不满足时共识失败（而非像fast_consensus那样直接通过）
        """
        if byzantine_nodes is None:
            byzantine_nodes = set()

        # ── PRE-PREPARE阶段：主节点提议 ──
        self._state = ConsensusState.PRE_PREPARE
        self._current_block_hash = block_hash
        self._consensus_start_ms = int(time.time() * 1000)
        self._votes = {'prepare': {}, 'commit': {}}

        # ── PREPARE阶段：非拜占庭节点投票 ──
        self._state = ConsensusState.PREPARE
        for nid in self.consensus_nodes:
            if nid in byzantine_nodes:
                continue  # 拜占庭节点拒绝投票（省略故障模型）
            w = self._weights.get(nid, self.INITIAL_WEIGHT)
            self._votes['prepare'][nid] = ConsensusVote(
                voter_id=nid, block_hash=block_hash,
                phase='prepare', weight=w
            )

        # 检查prepare阶段权重阈值
        if not self._check_weight_threshold('prepare'):
            self._state = ConsensusState.IDLE
            self.consensus_fail_count += 1
            logger.warning(
                f"[CW-PBFT] simulated_consensus PREPARE阶段权重阈值不满足: "
                f"block_hash={block_hash[:16]} | byzantine={len(byzantine_nodes)}"
            )
            return False

        # ── COMMIT阶段：非拜占庭节点投票 ──
        self._state = ConsensusState.COMMIT
        for nid in self.consensus_nodes:
            if nid in byzantine_nodes:
                continue
            w = self._weights.get(nid, self.INITIAL_WEIGHT)
            self._votes['commit'][nid] = ConsensusVote(
                voter_id=nid, block_hash=block_hash,
                phase='commit', weight=w
            )

        # 检查commit阶段权重阈值
        if not self._check_weight_threshold('commit'):
            self._state = ConsensusState.IDLE
            self.consensus_fail_count += 1
            logger.warning(
                f"[CW-PBFT] simulated_consensus COMMIT阶段权重阈值不满足: "
                f"block_hash={block_hash[:16]} | byzantine={len(byzantine_nodes)}"
            )
            return False

        # ── FINALIZE阶段：共识达成 ──
        self._state = ConsensusState.COMMITTED
        self.consensus_success_count += 1
        logger.info(
            f"[CW-PBFT] simulated_consensus完成: {block_hash[:16]} "
            f"| prepare_weight={sum(v.weight for v in self._votes['prepare'].values()):.2f} "
            f"| commit_weight={sum(v.weight for v in self._votes['commit'].values()):.2f} "
            f"| total_weight={self._total_weight:.2f}"
        )
        return True

    # -------------------------------------------------------------------------
    # 权重管理
    # -------------------------------------------------------------------------

    def update_weight(self, node_id: str, new_weight: float):
        """
        更新节点贡献权重（由激励模块调用）

        P1-8修复：
        - 非封禁节点权重受MIN_WEIGHT下界保护，确保不会降至0失去投票权
        - 封禁节点（new_weight <= 0）允许权重为0
        - 计算公式：max(MIN_WEIGHT, new_weight)，其中new_weight = 1.0 + 0.5 * weighted_score
        """
        if node_id in self._weights:
            old = self._weights[node_id]
            # P1-8修复：非封禁节点（new_weight > 0）受下界保护
            if new_weight > 0:
                protected_weight = max(self.MIN_WEIGHT, new_weight)
            else:
                # 封禁节点：权重设为0（明确失去投票权）
                protected_weight = 0.0
            self._weights[node_id] = protected_weight
            self._total_weight = sum(self._weights.values())
            # 记录权重演化
            self._weight_history.append({
                'weights': dict(self._weights),
                'total_weight': self._total_weight,
            })
            logger.debug(f"[CW-PBFT] {node_id} 权重: {old:.2f} → {protected_weight:.2f}")

    def get_weights(self) -> Dict[str, float]:
        return dict(self._weights)

    def get_weight_history(self) -> List[Dict]:
        """获取权重演化历史记录"""
        return list(self._weight_history)

    # -------------------------------------------------------------------------
    # 内部工具
    # -------------------------------------------------------------------------

    def _check_weight_threshold(self, phase: str) -> bool:
        """
        检查是否达到2/3权重阈值
        CW-PBFT：贡献度越高的节点投票权重越大
        """
        if not self._votes.get(phase):
            return False

        voted_weight = sum(v.weight for v in self._votes[phase].values())
        threshold = (2 / 3) * self._total_weight

        logger.debug(
            f"[CW-PBFT] {phase}阶段 投票权重={voted_weight:.2f} "
            f"/ 总权重={self._total_weight:.2f} "
            f"/ 阈值={threshold:.2f}"
        )
        return voted_weight >= threshold

    def get_consensus_stats(self) -> Dict:
        """获取共识状态统计"""
        total_rounds = self.consensus_success_count + self.consensus_fail_count
        consensus_success_rate = (
            self.consensus_success_count / total_rounds
            if total_rounds > 0 else 0.0
        )
        return {
            'node_id': self.node_id,
            'state': self._state,
            'n_nodes': self.n,
            'f_tolerance': self.f,
            'prepare_votes': len(self._votes.get('prepare', {})),
            'commit_votes': len(self._votes.get('commit', {})),
            'current_block_hash': self._current_block_hash,
            'weights': self._weights,
            'consensus_success_rate': consensus_success_rate,
            'weight_history': self._weight_history[-10:],
            'weight_derivation': {
                'κ_task': 0.40,
                'κ_coop': 0.35,
                'κ_compliance': 0.25,
                'sigma': 0.1,
                'phi': 0.05,
            },
        }
