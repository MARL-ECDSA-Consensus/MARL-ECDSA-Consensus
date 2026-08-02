"""
自私智能体封装
用于模拟自私/背叛行为，测试区块链激励机制的抗干扰能力
"""
import logging
import random
from typing import Any, Optional

logger = logging.getLogger(__name__)


class SelfishAgentWrapper:
    """
    自私智能体封装器
    包装任意MARL智能体，通过开关控制自私行为模式
    
    自私模式：
    - 只考虑自身局部奖励，忽略全局协作目标
    - 随机概率选择背叛行为（挤占他人目标点）
    - 用于对照实验：测试不同自私比例下区块链激励的效果
    """

    def __init__(
        self,
        agent_id: str,
        base_agent,                    # 底层MARL智能体
        is_selfish: bool = False,      # 是否为自私模式
        betrayal_prob: float = 0.3,    # 自私模式下的背叛概率
        n_actions: int = 5,            # 动作空间大小（用于背叛时选择随机动作）
    ):
        self.agent_id = agent_id
        self.base_agent = base_agent
        self.is_selfish = is_selfish
        self.betrayal_prob = betrayal_prob
        self.n_actions = n_actions
        self._betrayal_count = 0
        self._total_steps = 0

    def get_reward(self, global_reward: float, local_reward: float) -> float:
        """
        获取智能体使用的奖励信号
        - 诚实智能体：使用全局奖励（激励合作）
        - 自私智能体：仅使用局部奖励（激励自私）
        """
        if self.is_selfish:
            return local_reward
        return global_reward

    def should_betray(self) -> bool:
        """
        判断当前步是否采取背叛行为
        仅在自私模式下有效
        """
        if not self.is_selfish:
            return False
        return random.random() < self.betrayal_prob

    def step(self, obs, hidden_state=None):
        """
        执行一步决策
        - 诚实模式：正常调用底层智能体
        - 自私模式：有概率修改动作以实现背叛
        """
        self._total_steps += 1
        action, new_hidden = self.base_agent.get_action(obs, hidden_state) if hasattr(
            self.base_agent, 'get_action') else (0, hidden_state)

        if self.should_betray():
            self._betrayal_count += 1
            # P1-3 修复：背叛时真正替换为随机动作（可能挤占他人目标点）
            action = random.randint(0, self.n_actions - 1)
            logger.debug(f"[SelfishAgent] {self.agent_id} 执行背叛动作(action={action})，累计背叛{self._betrayal_count}次")

        return action, new_hidden

    def get_stats(self) -> dict:
        betrayal_rate = self._betrayal_count / max(1, self._total_steps)
        return {
            'agent_id': self.agent_id,
            'is_selfish': self.is_selfish,
            'betrayal_count': self._betrayal_count,
            'total_steps': self._total_steps,
            'betrayal_rate': betrayal_rate,
        }


def create_agents(
    n_agents: int,
    selfish_ratio: float = 0.0,
    base_agent_class=None,
    agent_kwargs: Optional[dict] = None
) -> list:
    """
    批量创建智能体列表
    :param n_agents: 智能体总数
    :param selfish_ratio: 自私智能体比例（0.0-1.0）
    :param base_agent_class: 底层MARL智能体类
    :param agent_kwargs: 底层智能体初始化参数
    :return: SelfishAgentWrapper 列表
    """
    agent_kwargs = agent_kwargs or {}
    n_selfish = max(1, round(n_agents * selfish_ratio)) if selfish_ratio > 0 else 0
    agents = []

    for i in range(n_agents):
        agent_id = f"agent_{i}"
        is_selfish = i < n_selfish

        if base_agent_class is not None:
            base = base_agent_class(agent_id=agent_id, **agent_kwargs)
        else:
            base = None

        wrapper = SelfishAgentWrapper(
            agent_id=agent_id,
            base_agent=base,
            is_selfish=is_selfish,
            betrayal_prob=0.3 if is_selfish else 0.0,
        )
        agents.append(wrapper)

        if is_selfish:
            logger.info(f"[AgentFactory] 创建自私智能体: {agent_id}")

    logger.info(
        f"[AgentFactory] 共创建 {n_agents} 个智能体，"
        f"其中 {n_selfish} 个自私（比例={selfish_ratio:.1%}）"
    )
    return agents
