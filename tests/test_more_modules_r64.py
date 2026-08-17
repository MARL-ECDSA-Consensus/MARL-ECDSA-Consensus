"""
更多模块剩余边界测试（RalphLoop 原子任务 EB）
覆盖：cooperation_detector 回合判定/重置、adaptive_lambda 计算边界（此前未单点覆盖）
通过标准：新增 ≥6 项测试全过
"""
import logging

import numpy as np
import pytest

from marl.integration.cooperation_detector import CooperationDetector
from marl.integration.adaptive_lambda import AdaptiveLambdaController

logging.basicConfig(level=logging.CRITICAL)


def _obs(n=3, n_lm=3, near_own=False):
    rows = []
    for i in range(n):
        lm = np.random.rand(n_lm, 2) * 0.8 + 0.1
        if near_own:
            lm[i % n_lm] = np.array([0.01, 0.01])
        rows.append(np.array([0.1, 0.1, 0.5, 0.5] + lm.flatten().tolist()))
    return rows


class TestEpisodeCooperation:
    def test_high_coop_detected(self):
        """高合作率 → did_cooperate True"""
        cd = CooperationDetector(n_agents=3, n_landmarks=3)
        obs = _obs(3, near_own=True)
        cd.detect_cooperation(obs, ["a0", "a1", "a2"])
        cd.detect_cooperation(obs, ["a0", "a1", "a2"])
        did_coop, did_betray = cd.get_episode_cooperation("a0")
        assert did_coop is True
        assert did_betray is False

    def test_low_coop_neutral(self):
        """全远观测 → 中性（coop_rate=0 不判合作）"""
        cd = CooperationDetector(n_agents=3, n_landmarks=3)
        import numpy as _np
        rows = []
        for i in range(3):
            lm = _np.full((3, 2), 0.9)
            rows.append(_np.array([0.1, 0.1, 0.5, 0.5] + lm.flatten().tolist()))
        cd.detect_cooperation(rows, ["a0", "a1", "a2"])
        did_coop, did_betray = cd.get_episode_cooperation("a0")
        assert did_coop is False
        assert did_betray is False

    def test_never_detected_default(self):
        """未检测 → (False, False)"""
        cd = CooperationDetector(n_agents=3, n_landmarks=3)
        assert cd.get_episode_cooperation("ghost") == (False, False)

    def test_reset_episode(self):
        """reset_episode 清空累积"""
        cd = CooperationDetector(n_agents=3, n_landmarks=3)
        cd.detect_cooperation(_obs(3, near_own=True), ["a0", "a1", "a2"])
        cd.reset_episode()
        assert cd.get_episode_cooperation("a0") == (False, False)


class TestCooperationStatus:
    def test_get_status_after_detect(self):
        """最近一步状态"""
        cd = CooperationDetector(n_agents=3, n_landmarks=3)
        cd.detect_cooperation(_obs(3, near_own=True), ["a0", "a1", "a2"])
        status = cd.get_cooperation_status()
        assert status["a0"] is True

    def test_get_status_empty_initial(self):
        """初始状态空"""
        cd = CooperationDetector(n_agents=3, n_landmarks=3)
        assert cd.get_cooperation_status() == {}


class TestAdaptiveLambda:
    def test_compute_valid_range(self):
        """λ 输出在范围内（私有属性 _lambda_min/_lambda_max）"""
        c = AdaptiveLambdaController(lambda_base=0.1)
        stats = {'consensus_stats': {'success_rate': 0.9, 'rounds': 100},
                 'detector_stats': {'cooperation_rate': 0.8},
                 'security_stats': {'pass_count': 90, 'fail_count': 10}}
        lam = c.compute_adaptive_lambda(stats)
        assert c._lambda_min - 1e-9 <= lam <= c._lambda_max + 1e-9

    def test_compute_empty_stats(self):
        """空统计 → 不崩溃"""
        c = AdaptiveLambdaController(lambda_base=0.1)
        lam = c.compute_adaptive_lambda({})
        assert isinstance(lam, float)

    def test_history_records(self):
        """历史记录增长"""
        c = AdaptiveLambdaController()
        c.compute_adaptive_lambda({})
        c.compute_adaptive_lambda({})
        assert len(c.get_adaptation_history()) == 2

    def test_reset_restores(self):
        """reset 恢复基准"""
        c = AdaptiveLambdaController(lambda_base=0.2)
        c.compute_adaptive_lambda({})
        c.reset()
        assert c._current_lambda == 0.2
        assert len(c.get_adaptation_history()) == 0
