"""
合作检测服务 — 从 BlockchainMARLBridge 拆分出的子组件（P2-D）
职责：合作/背叛检测 + 回合内累积统计 + per-step 结果缓存
"""
import logging
from typing import Dict, List, Optional, Tuple, Any

logger = logging.getLogger(__name__)


class CooperationDetector:
    """
    合作与背叛检测服务

    封装完整检测流水线：
    1. detect_cooperation() — 每步检测各智能体是否合作（simple_spread 场景）
    2. get_episode_cooperation() — 回合结束时判定最终合作/背叛
    3. get_cooperation_status() — 最近一步的检测结果（per-step）
    4. reset_episode() — 重置回合内累积状态

    观测格式：[vel_x, vel_y, pos_x, pos_y, lm1_dx, lm1_dy, lm2_dx, lm2_dy, ...]
    """

    def __init__(self, n_agents: int = 3, n_landmarks: int = 3):
        self.n_agents = n_agents
        self.n_landmarks = n_landmarks

        # 回合内合作状态累积 {agent_id: {'coop': count, 'betray': count, 'total': count}}
        self._episode_coop: Dict[str, Dict[str, int]] = {}

        # 最近一步的合作检测结果（per-step）
        self._last_step_coop: Dict[str, Optional[bool]] = {}

    def detect_cooperation(
        self,
        observations: List[Any],
        agent_ids: List[str],
        cooperation_threshold: float = 0.5,
        selfish_flags: Optional[List[bool]] = None,
    ) -> Dict[str, Optional[bool]]:
        """
        检测各智能体本步是否合作（v3 修正版）

        核心修正：
        1. 阈值 0.5（在 world_size=1.0 的环境中合理）
        2. 移除"靠近其他目标点=背叛"的误判
        3. 合作判定：dist < threshold → True / 中性 → None
        4. selfish_flags：P2修复后表示"本步是否实际背叛"而非"是否是自私智能体"
           - True = 本步实际背叛（由should_betray()决定）
           - False = 本步未背叛（即使agent是selfish类型，70%的正常步也不会被标记）

        :param observations: 各智能体观测值列表
        :param agent_ids: 智能体 ID 列表
        :param cooperation_threshold: 合作距离阈值
        :param selfish_flags: 本步背叛标记列表（True=本步背叛，而非is_selfish标记）
        :return: {agent_id: True(合作) / False(背叛) / None(中性)}
        """
        import numpy as np
        step_status: Dict[str, Optional[bool]] = {}
        sf = selfish_flags if selfish_flags else [False] * len(agent_ids)

        for i, (obs, agent_id) in enumerate(zip(observations, agent_ids)):
            # P2修复：selfish_flags=True表示"本步实际背叛"而非"是自私智能体"
            # 只有真正背叛的步才标记为False，70%正常步不会被误判
            if i < len(sf) and sf[i]:
                step_status[agent_id] = False
                continue

            try:
                obs_arr = np.array(obs, dtype=float)
                n_lm = self.n_landmarks
                lm_rel = obs_arr[4:4 + 2 * n_lm].reshape(-1, 2)
                own_idx = i % n_lm
                dist_to_own = float(np.linalg.norm(lm_rel[own_idx]))
                min_dist_any = min(
                    float(np.linalg.norm(lm_rel[j])) for j in range(n_lm)
                )

                if dist_to_own < cooperation_threshold:
                    step_status[agent_id] = True
                elif min_dist_any < cooperation_threshold:
                    step_status[agent_id] = True
                else:
                    step_status[agent_id] = None
            except Exception as e:
                logger.warning(f"[CooperationDetector] 合作检测异常 {agent_id}: {e}")
                step_status[agent_id] = None

        # 累积到回合统计（用于结算判定）
        for agent_id, status in step_status.items():
            if agent_id not in self._episode_coop:
                self._episode_coop[agent_id] = {'coop': 0, 'betray': 0, 'total': 0}
            self._episode_coop[agent_id]['total'] += 1
            if status is True:
                self._episode_coop[agent_id]['coop'] += 1
            elif status is False:
                self._episode_coop[agent_id]['betray'] += 1

        # 存储 per-step 结果（用于实时合作率统计）
        self._last_step_coop = dict(step_status)

        return step_status

    def get_episode_cooperation(self, agent_id: str) -> Tuple[bool, bool]:
        """
        根据回合内累积状态判断最终合作/背叛（v2 修正版）

        :param agent_id: 智能体 ID
        :return: (did_cooperate, did_betray)

        修正逻辑：
        - 合作步数 > 30% → 合作（宽松阈值）
        - 背叛步数 > 50% → 背叛（严格阈值，仅 selfish 模式产生 False）
        - bc_marl 模式下不会产生真正背叛，中性不判背叛
        """
        stats = self._episode_coop.get(
            agent_id, {'coop': 0, 'betray': 0, 'total': 0}
        )
        total = max(1, stats['total'])
        coop_rate = stats['coop'] / total
        betray_rate = stats['betray'] / total

        did_cooperate = coop_rate > 0.3
        did_betray = betray_rate > 0.5
        return did_cooperate, did_betray

    def get_cooperation_status(self) -> Dict[str, Optional[bool]]:
        """获取最近一步的合作状态（per-step，用于实时统计）"""
        return dict(self._last_step_coop)

    def reset_episode(self) -> None:
        """重置回合内累积状态"""
        self._episode_coop = {}

    def get_stats(self) -> Dict:
        """获取合作检测统计"""
        return {
            'episode_coop_agents': len(self._episode_coop),
            'last_step_coop': dict(self._last_step_coop),
        }
