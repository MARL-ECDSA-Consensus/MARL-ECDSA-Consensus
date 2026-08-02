"""
结算协调服务 — 从 BlockchainMARLBridge 拆分出的子组件（P2-D）
职责：贡献度评分 + 激励结算 + 积分同步 + 奖励融合
"""
import logging
from typing import Dict, List, Optional

from blockchain.contracts.incentive_contract import ContributionScore

logger = logging.getLogger(__name__)


class SettlementCoordinator:
    """
    激励结算与奖励融合服务

    封装完整结算流水线：
    1. compute_contribution_scores() — 构造各智能体贡献度评分
    2. settle() — 调用激励合约结算（或模拟结算）
    3. update_rewards_and_scores() — 更新 bc_rewards/bc_scores
    4. compute_total_reward() — 奖励融合公式 total = env + λ*bc
    5. get_bc_scores() — 累计积分查询（委托 WorldState）
    6. get_bc_rewards() — 本回合积分变化查询

    P2-C 修复：WorldState 为唯一积分源（有 incentive_contract 时）
    _bc_scores 仅在 ablate 模式下作为 fallback
    """

    def __init__(
        self,
        incentive_contract=None,
        n_agents: int = 3,
        lambda_weight: float = 0.1,
    ):
        self.incentive_contract = incentive_contract
        self.lambda_weight = lambda_weight

        # 链上累计积分（仅 ablate 模式 fallback）
        self._bc_scores: Dict[str, float] = {
            f"agent_{i}": 0.0 for i in range(n_agents)
        }

        # 本回合积分变化量（每回合重置）
        self._bc_rewards: Dict[str, float] = {
            f"agent_{i}": 0.0 for i in range(n_agents)
        }

    def compute_contribution_scores(
        self,
        agent_ids: List[str],
        env_rewards: List[float],
        coop_results: Dict[str, tuple],
    ) -> List[ContributionScore]:
        """
        构造各智能体的贡献度评分

        :param agent_ids: 智能体 ID 列表
        :param env_rewards: 环境奖励列表
        :param coop_results: {agent_id: (did_cooperate, did_betray)}
        :return: List[ContributionScore]
        """
        scores = []
        for i, agent_id in enumerate(agent_ids):
            did_cooperate, did_betray = coop_results.get(
                agent_id, (False, False)
            )
            env_r = float(env_rewards[i]) if i < len(env_rewards) else 0.0
            # 归一化环境奖励到 [0, 1]
            # P2修复：SimpleSpreadEnv的local_reward实际范围约[-1.0, 2.0]
            # 修正映射区间为 [-1.5, 2.0] → [0.0, 1.0]，更贴合实际奖励分布
            # 原公式 (env_r + 5) / 10 假设范围[-5,5]，导致大部分奖励被压缩到0.3-0.4区间
            norm_env_r = max(0.0, min(1.0, (env_r + 1.5) / 3.5))

            if self.incentive_contract is not None:
                cs = self.incentive_contract.compute_contribution(
                    agent_id=agent_id,
                    env_reward=norm_env_r,
                    did_cooperate=did_cooperate,
                    did_betray=did_betray,
                )
            else:
                # 模拟模式（无激励合约）
                cs = ContributionScore(
                    agent_id=agent_id,
                    task_score=norm_env_r,
                    cooperation_score=(
                        1.0 if did_cooperate
                        else (0.0 if did_betray else 0.5)
                    ),
                    compliance_score=0.0 if did_betray else 1.0,
                )
            scores.append(cs)
        return scores

    def settle(
        self,
        episode: int,
        scores: List[ContributionScore],
    ) -> Dict[str, float]:
        """
        激励结算

        :param episode: 回合编号
        :param scores: 贡献度评分列表
        :return: {agent_id: delta} 各智能体本回合积分变化量
        """
        if self.incentive_contract is not None:
            deltas = self.incentive_contract.settle_rewards(episode, scores)
        else:
            deltas = self._simulate_settlement(scores)
        return deltas

    def update_rewards_and_scores(self, deltas: Dict[str, float]) -> None:
        """
        更新本回合 bc_reward 和累计 bc_scores

        P2-C 修复：WorldState 为唯一积分源（有 incentive_contract 时）
        _bc_scores 仅在 ablate 模式（无 incentive_contract）下更新
        """
        for agent_id, delta in deltas.items():
            if self.incentive_contract is None:
                # ablate 模式：无 WorldState，_bc_scores 是唯一源
                self._bc_scores[agent_id] = self._bc_scores.get(agent_id, 0.0) + delta
            # 正常模式：settle_rewards() 已更新 WorldState，无需再更新 _bc_scores
            self._bc_rewards[agent_id] = delta

    def compute_total_reward(self, agent_id: str, env_reward: float) -> float:
        """
        计算融合区块链激励后的总奖励
        total_reward = env_reward + λ * bc_reward
        """
        bc_reward = self._bc_rewards.get(agent_id, 0.0)
        # 归一化：将 bc_reward 裁剪到 [-20, 20] 防止主导奖励
        bc_reward_clipped = max(-20.0, min(20.0, bc_reward))
        total = env_reward + self.lambda_weight * bc_reward_clipped
        return total

    def get_all_total_rewards(
        self,
        env_rewards: List[float],
        agent_ids: List[str],
    ) -> List[float]:
        """批量计算所有智能体的融合奖励"""
        return [
            self.compute_total_reward(aid, env_rewards[i])
            for i, aid in enumerate(agent_ids)
        ]

    def get_bc_scores(self) -> Dict[str, float]:
        """
        获取累计积分（用于展示/排行榜）

        P2-C修复：WorldState 为权威积分源（有 incentive_contract 时委托 WorldState）
        ablate 模式下使用 _bc_scores fallback
        """
        if self.incentive_contract is not None:
            try:
                return dict(self.incentive_contract._ws.get_all_scores())
            except Exception as e:
                logger.warning(
                    f"[SettlementCoordinator] WorldState积分读取失败，"
                    f"fallback到_bc_scores: {e}"
                )
        return dict(self._bc_scores)

    def get_bc_rewards(self) -> Dict[str, float]:
        """获取本回合积分变化（用于奖励计算）"""
        return dict(self._bc_rewards)

    def _simulate_settlement(
        self, scores: List[ContributionScore]
    ) -> Dict[str, float]:
        """模拟模式：直接计算激励 delta（温和惩罚策略，降方差）"""
        deltas = {}
        for cs in scores:
            aid = cs.agent_id
            if cs.compliance_score == 0.0:
                # 背叛：温和惩罚（降至-8，避免方差爆炸）
                delta = -8.0
            else:
                # 合作：基础奖励 + 贡献加成
                delta = 10.0 + 5.0 * cs.weighted_score
            deltas[aid] = delta
        return deltas

    def get_stats(self) -> Dict:
        """获取结算统计"""
        return {
            'bc_scores': dict(self._bc_scores),
            'bc_rewards': dict(self._bc_rewards),
            'lambda_weight': self.lambda_weight,
        }
