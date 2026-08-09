"""
run_cars_comparison 实验脚本测试（RalphLoop 原子任务 AK）
覆盖：extract_metrics 空/有数据/cars_stats 透传、welch_ttest 边界
通过标准：新增 ≥6 项测试全过
"""
import json
import logging
from pathlib import Path

import numpy as np
import pytest

import run_cars_comparison as rcc

logging.basicConfig(level=logging.CRITICAL)


def _write_results(tmp_path, name, data):
    p = tmp_path / f"{name}.json"
    p.write_text(json.dumps(data), encoding='utf-8')
    return str(p)


class TestExtractMetrics:
    def test_empty_data_zeros(self, tmp_path):
        """空数据 → 所有指标回退 0.0"""
        path = _write_results(tmp_path, "empty", {})
        m = rcc.extract_metrics(path)
        assert m["env_reward_last50"] == 0.0
        assert m["coop_rate_all"] == 0.0
        assert m["cars_stats"] is None

    def test_basic_metrics(self, tmp_path):
        """有数据 → 正确计算均值/最后50"""
        data = {"env_rewards": [1.0] * 100, "episode_rewards": [2.0] * 100,
                "cooperation_rates": [0.5] * 100}
        path = _write_results(tmp_path, "basic", data)
        m = rcc.extract_metrics(path)
        assert m["env_reward_last50"] == pytest.approx(1.0)
        assert m["total_reward_last50"] == pytest.approx(2.0)
        assert m["coop_rate_all"] == pytest.approx(0.5)

    def test_cars_stats_passthrough(self, tmp_path):
        """cars_stats 透传（若存在于数据中）"""
        data = {"env_rewards": [1.0] * 10, "consensus_shaping_stats": {"bonus": 0.05}}
        path = _write_results(tmp_path, "cars", data)
        m = rcc.extract_metrics(path)
        assert m["cars_stats"] == {"bonus": 0.05}


class TestWelchTTest:
    def test_insufficient_data(self):
        """样本不足 → insufficient_data"""
        r = rcc.welch_ttest([1.0], [2.0, 3.0], "a", "b")
        assert r["test"] == "insufficient_data"

    def test_significant_difference(self):
        """显著差异：p < 0.05（np 类型需真值判断）"""
        np.random.seed(7)
        a = np.random.normal(10.0, 0.5, 50)
        b = np.random.normal(5.0, 0.5, 50)
        r = rcc.welch_ttest(a, b, "cars", "baseline")
        assert bool(r["significant"]) is True
        assert float(r["p_value"]) < 0.05

    def test_same_group_not_significant(self):
        """相同组 → 不显著"""
        a = np.random.normal(5.0, 0.1, 50)
        r = rcc.welch_ttest(a, a, "x", "x")
        assert float(r["p_value"]) > 0.05

    def test_improvement_pct(self):
        """improvement_pct 计算"""
        a = np.array([12.0] * 20)
        b = np.array([10.0] * 20)
        r = rcc.welch_ttest(a, b, "a", "b")
        assert r["improvement_pct"] == pytest.approx(20.0)


class TestConstants:
    def test_configs_defined(self):
        """实验配置组已定义"""
        assert isinstance(rcc.CONFIGS, list)
        assert len(rcc.CONFIGS) >= 1

    def test_seeds_defined(self):
        assert isinstance(rcc.SEEDS, list)
        assert len(rcc.SEEDS) >= 1
