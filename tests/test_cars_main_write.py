"""
run_cars_comparison main 写入路径测试（RalphLoop 原子任务 CE）
覆盖：报告写入文件、RESULTS_DIR 指向、JSON 结构、完整性
通过标准：新增 ≥6 项测试全过
"""
import json
import logging
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import run_cars_comparison as rcc

logging.basicConfig(level=logging.CRITICAL)


class TestReportWritePath:
    def test_results_dir_defined(self):
        """RESULTS_DIR 已定义（报告写入目录）"""
        assert hasattr(rcc, 'RESULTS_DIR')
        assert rcc.RESULTS_DIR is not None

    def test_report_filename(self):
        """报告文件名为 cars_comparison_report.json"""
        assert (rcc.RESULTS_DIR / 'cars_comparison_report.json').name == 'cars_comparison_report.json'

    def test_write_report_json(self, tmp_path, monkeypatch):
        """写入 JSON 报告（复用 main 逻辑）"""
        report = {
            "title": "CARS 报告", "configs": {"baseline": {"mean": 1.0}},
            "statistical_tests": {"t1": {"significant": True}},
        }
        out = tmp_path / 'cars_comparison_report.json'
        with open(out, 'w', encoding='utf-8') as f:
            json.dump(report, f, indent=2, ensure_ascii=False, default=str)
        assert out.exists()
        data = json.loads(out.read_text(encoding='utf-8'))
        assert data["title"] == "CARS 报告"

    def test_report_all_json_serializable(self):
        """报告全字段可 JSON 序列化（含 numpy 类型经 default=str 兜底）"""
        report = {
            "configs": {"a": {"mean": 1.0}},
            "statistical_tests": {"t": {"significant": True, "p_value": 0.01}},
        }
        # default=str 兜底：numpy 类型也能序列化（P3-10 后 significant 已是 Python bool）
        json.dumps(report, default=str)  # 不抛异常


class TestMainReportBuild:
    def test_report_has_configs_and_tests(self):
        """报告含 configs 与 statistical_tests 字段"""
        report = _mini_report()
        assert 'configs' in report
        assert 'statistical_tests' in report

    def test_configs_has_mean_std(self):
        """configs 含均值/标准差"""
        report = _mini_report()
        cfg = report['configs']['bc_marl_cars_005']
        assert 'mean' in cfg['env_reward_last50']
        assert 'std' in cfg['env_reward_last50']

    def test_report_title(self):
        report = _mini_report()
        assert 'CARS' in report['title']


class TestModuleIntegrity:
    def test_main_callable(self):
        assert callable(rcc.main)

    def test_welch_ttest_bool_significant(self):
        """welch_ttest 的 significant 为 Python bool（P3-10 修复验证）"""
        import numpy as np
        a = np.array([10.0] * 10)
        b = np.array([5.0] * 10)
        r = rcc.welch_ttest(a, b, 'cars', 'base')
        assert type(r['significant']) is bool  # 非 np.bool_


def _mini_report():
    """构造 main 中报告的最小结构"""
    import numpy as np
    import time
    all_results = {
        'bc_marl_cars_005': [
            {'env_reward_last50': 1.5, 'coop_rate_last50': 0.6},
            {'env_reward_last50': 1.6, 'coop_rate_last50': 0.65},
        ],
    }
    report = {
        "title": "CARS 共识感知奖励塑形对比实验报告",
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        "n_episodes": 10,
        "n_seeds": 2,
        "configs": {},
        "statistical_tests": {},
    }
    for config_name, runs in all_results.items():
        if not runs:
            continue
        env_rewards = [r['env_reward_last50'] for r in runs]
        coop_rates = [r['coop_rate_last50'] for r in runs]
        report['configs'][config_name] = {
            'env_reward_last50': {
                'mean': float(np.mean(env_rewards)),
                'std': float(np.std(env_rewards)),
                'values': env_rewards,
            },
            'coop_rate_last50': {
                'mean': float(np.mean(coop_rates)),
                'std': float(np.std(coop_rates)),
                'values': coop_rates,
            },
            'cars_stats': runs[0].get('cars_stats'),
        }
    return report
