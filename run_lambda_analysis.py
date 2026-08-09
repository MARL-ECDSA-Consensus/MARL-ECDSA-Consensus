"""
Tier2: Lambda敏感性分析 + 自适应λ vs 静态λ 对比实验

实验设计:
  1. Lambda敏感性: λ ∈ {0.0, 0.05, 0.1, 0.15, 0.2} × 3 seeds × 500ep
     - 验证λ对BC-MARL协作提升的影响曲线
     - 寻找最优λ区间
  
  2. 自适应 vs 静态: bc_marl(adaptive) vs bc_marl(static λ=0.1) × 3 seeds × 500ep
     - 验证自适应λ控制器对系统稳定性和最终性能的影响

输出:
  results/lambda_analysis/lambda_sensitivity_report.json
"""
import json
import logging
import os
import subprocess
import sys
import time
from pathlib import Path

import numpy as np
from scipy import stats

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
logger = logging.getLogger('lambda_analysis')

PYTHON = sys.executable
BASE_DIR = Path(__file__).parent
RESULTS_DIR = BASE_DIR / 'results' / 'lambda_analysis'
RESULTS_DIR.mkdir(parents=True, exist_ok=True)

SEEDS = [42, 123, 456]
N_EPISODES = 500

# ── 实验1: Lambda敏感性 ──
LAMBDA_VALUES = [0.0, 0.05, 0.1, 0.15, 0.2]

# ── 实验2: 自适应 vs 静态 ──
# bc_marl with --adaptive-lambda (default) vs --no-adaptive-lambda


def run_single(name, args, seed, n_episodes, output_file):
    """运行单次实验"""
    cmd = [
        PYTHON, str(BASE_DIR / 'train.py'),
        '--mode', 'bc_marl',
        '--seed', str(seed),
        '--n_episodes', str(n_episodes),
        '--save', str(output_file),
    ] + args

    logger.info(f"[RUN] {name}/seed{seed}")
    start = time.time()
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=300,
                            cwd=str(BASE_DIR))
    elapsed = time.time() - start

    if result.returncode != 0:
        logger.error(f"[FAIL] {name}/seed{seed}: {result.stderr[-300:]}")
        return None

    logger.info(f"[DONE] {name}/seed{seed} in {elapsed:.1f}s")
    return str(output_file)


def extract_metrics(filepath):
    """提取关键指标"""
    with open(filepath, 'r', encoding='utf-8') as f:
        data = json.load(f)

    env_rewards = data.get('env_rewards', [])
    total_rewards = data.get('episode_rewards', [])
    coop_rates = data.get('cooperation_rates', [])
    lambda_history = data.get('lambda_history', [])

    window = min(50, len(env_rewards))
    # 收敛速度：首次达到最终性能80%的回合数
    final_perf = float(np.mean(env_rewards[-window:])) if env_rewards else 0.0
    convergence_episode = len(env_rewards)
    if final_perf != 0:
        threshold = final_perf * 0.8 if final_perf > 0 else final_perf * 1.2
        for i in range(len(env_rewards)):
            rolling = float(np.mean(env_rewards[max(0, i-10):i+1]))
            if (rolling > threshold if final_perf > 0 else rolling < threshold):
                convergence_episode = i
                break

    return {
        'env_reward_last50': float(np.mean(env_rewards[-window:])) if env_rewards else 0.0,
        'env_reward_std_last50': float(np.std(env_rewards[-window:])) if env_rewards else 0.0,
        'total_reward_last50': float(np.mean(total_rewards[-window:])) if total_rewards else 0.0,
        'coop_rate_last50': float(np.mean(coop_rates[-window:])) if coop_rates else 0.0,
        'coop_rate_std_last50': float(np.std(coop_rates[-window:])) if coop_rates else 0.0,
        'env_reward_all': float(np.mean(env_rewards)) if env_rewards else 0.0,
        'coop_rate_all': float(np.mean(coop_rates)) if coop_rates else 0.0,
        'convergence_episode': convergence_episode,
        'lambda_mean': float(np.mean(lambda_history)) if lambda_history else 0.0,
        'lambda_std': float(np.std(lambda_history)) if lambda_history else 0.0,
        'lambda_final': float(lambda_history[-1]) if lambda_history else 0.0,
        'lambda_min': float(np.min(lambda_history)) if lambda_history else 0.0,
        'lambda_max': float(np.max(lambda_history)) if lambda_history else 0.0,
    }


def welch_ttest(a, b):
    """Welch's t-test"""
    if len(a) < 2 or len(b) < 2:
        return {"test": "insufficient_data"}
    t_stat, p_value = stats.ttest_ind(a, b, equal_var=False)
    pooled_std = np.sqrt(
        ((len(a) - 1) * np.var(a, ddof=1) + (len(b) - 1) * np.var(b, ddof=1)) /
        (len(a) + len(b) - 2)
    )
    cohens_d = (np.mean(a) - np.mean(b)) / pooled_std if pooled_std > 0 else 0.0
    return {
        "t_statistic": float(t_stat),
        "p_value": float(p_value),
        "cohens_d": float(cohens_d),
        "significant": p_value < 0.05,
        "mean_a": float(np.mean(a)),
        "mean_b": float(np.mean(b)),
        "improvement_pct": float((np.mean(a) - np.mean(b)) / abs(np.mean(b)) * 100) if np.mean(b) != 0 else 0.0,
    }


def run_lambda_sensitivity():
    """实验1: Lambda敏感性分析"""
    logger.info("=" * 60)
    logger.info("实验1: Lambda敏感性分析")
    logger.info(f"λ值: {LAMBDA_VALUES} × {len(SEEDS)} seeds × {N_EPISODES}ep")
    logger.info("=" * 60)

    results = {}
    for lam in LAMBDA_VALUES:
        name = f"lambda_{lam:.2f}"
        results[name] = []

        for seed in SEEDS:
            output_file = RESULTS_DIR / f"{name}_seed{seed}.json"
            args = ['--lambda_weight', str(lam)]

            if lam == 0.0:
                # λ=0 等同于 pure_marl
                args = ['--mode', 'pure_marl', '--lambda_weight', '0.0']

            filepath = run_single(name, args, seed, N_EPISODES, output_file)
            if filepath and os.path.exists(filepath):
                metrics = extract_metrics(filepath)
                metrics['seed'] = seed
                metrics['lambda_value'] = lam
                results[name].append(metrics)

    return results


def run_adaptive_vs_static():
    """实验2: 自适应λ vs 静态λ"""
    logger.info("=" * 60)
    logger.info("实验2: 自适应λ vs 静态λ 对比")
    logger.info(f"2组 × {len(SEEDS)} seeds × {N_EPISODES}ep")
    logger.info("=" * 60)

    results = {'adaptive': [], 'static': []}

    # 自适应λ（默认启用）
    for seed in SEEDS:
        output_file = RESULTS_DIR / f"adaptive_seed{seed}.json"
        args = ['--adaptive-lambda', '--lambda_weight', '0.1']
        filepath = run_single('adaptive', args, seed, N_EPISODES, output_file)
        if filepath and os.path.exists(filepath):
            metrics = extract_metrics(filepath)
            metrics['seed'] = seed
            metrics['type'] = 'adaptive'
            results['adaptive'].append(metrics)

    # 静态λ
    for seed in SEEDS:
        output_file = RESULTS_DIR / f"static_seed{seed}.json"
        args = ['--no-adaptive-lambda', '--lambda_weight', '0.1']
        filepath = run_single('static', args, seed, N_EPISODES, output_file)
        if filepath and os.path.exists(filepath):
            metrics = extract_metrics(filepath)
            metrics['seed'] = seed
            metrics['type'] = 'static'
            results['static'].append(metrics)

    return results


def _build_lambda_sensitivity(sensitivity_results):
    """构建λ敏感性分析数据"""
    data = {}
    for name, runs in sensitivity_results.items():
        if not runs:
            continue
        env_rewards = [r['env_reward_last50'] for r in runs]
        coop_rates = [r['coop_rate_last50'] for r in runs]
        data[name] = {
            'lambda_value': runs[0]['lambda_value'],
            'env_reward': {'mean': float(np.mean(env_rewards)), 'std': float(np.std(env_rewards)), 'values': env_rewards},
            'coop_rate': {'mean': float(np.mean(coop_rates)), 'std': float(np.std(coop_rates)), 'values': coop_rates},
        }
    best_lambda = max(data, key=lambda k: data[k]['env_reward']['mean']) if data else None
    best_val = data[best_lambda]['env_reward']['mean'] if best_lambda else None
    data['best_lambda'] = {'value': best_lambda, 'env_reward': best_val}
    return data


def _build_adaptive_comparison(adaptive_results):
    """构建自适应vs静态对比数据"""
    data = {}
    for name, runs in adaptive_results.items():
        if not runs:
            continue
        env_rewards = [r['env_reward_last50'] for r in runs]
        coop_rates = [r['coop_rate_last50'] for r in runs]
        data[name] = {
            'env_reward': {'mean': float(np.mean(env_rewards)), 'std': float(np.std(env_rewards)), 'values': env_rewards},
            'coop_rate': {'mean': float(np.mean(coop_rates)), 'std': float(np.std(coop_rates)), 'values': coop_rates},
            'lambda_mean': float(np.mean([r['lambda_mean'] for r in runs])),
            'lambda_std': float(np.mean([r['lambda_std'] for r in runs])),
        }
    ad_env = [r['env_reward_last50'] for r in adaptive_results.get('adaptive', [])]
    st_env = [r['env_reward_last50'] for r in adaptive_results.get('static', [])]
    ad_coop = [r['coop_rate_last50'] for r in adaptive_results.get('adaptive', [])]
    st_coop = [r['coop_rate_last50'] for r in adaptive_results.get('static', [])]
    data['ttest_env_reward'] = welch_ttest(ad_env, st_env)
    data['ttest_coop_rate'] = welch_ttest(ad_coop, st_coop)
    return data


def _print_lambda_sensitivity(data):
    """打印λ敏感性分析结果"""
    print("\n" + "=" * 70)
    print("Lambda敏感性分析结果")
    print("=" * 70)
    print(f"{'λ值':<12} {'env_reward(last50)':<22} {'合作率(last50)':<22}")
    print("-" * 70)
    for name, d in data.items():
        if name == 'best_lambda':
            continue
        print(f"λ={d['lambda_value']:<8.2f} {d['env_reward']['mean']:>8.2f}±{d['env_reward']['std']:<10.2f} {d['coop_rate']['mean']:>8.1%}±{d['coop_rate']['std']:<10.1%}")
    print("-" * 70)
    bl = data.get('best_lambda', {})
    if bl.get('value'):
        print(f"最优λ = {bl['value']} (env_reward = {bl['env_reward']:.2f})")


def _print_adaptive_comparison(data):
    """打印自适应对比结果"""
    print("\n" + "=" * 70)
    print("自适应λ vs 静态λ 对比结果")
    print("=" * 70)
    print(f"{'类型':<15} {'env_reward':<22} {'合作率':<22} {'λ均值':<12}")
    print("-" * 70)
    for name in ['adaptive', 'static']:
        d = data.get(name, {})
        if not d:
            continue
        label = '自适应λ' if name == 'adaptive' else '静态λ'
        print(f"{label:<13} {d['env_reward']['mean']:>8.2f}±{d['env_reward']['std']:<10.2f} {d['coop_rate']['mean']:>8.1%}±{d['coop_rate']['std']:<10.1%} {d.get('lambda_mean',0):.4f}")
    print("-" * 70)
    for key in ['ttest_env_reward', 'ttest_coop_rate']:
        t = data.get(key, {})
        if 'p_value' in t:
            sig = "***" if t['p_value'] < 0.001 else "**" if t['p_value'] < 0.01 else "*" if t['p_value'] < 0.05 else "ns"
            label = 'env_reward' if 'env' in key else 'coop_rate'
            print(f"{label}: improvement={t['improvement_pct']:+.1f}% p={t['p_value']:.4f} d={t['cohens_d']:.2f} {sig}")


def generate_report(sensitivity_results, adaptive_results):
    """生成综合报告"""
    report = {
        "title": "Lambda敏感性分析 + 自适应vs静态对比实验报告",
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        "n_episodes": N_EPISODES,
        "n_seeds": len(SEEDS),
        "lambda_sensitivity": _build_lambda_sensitivity(sensitivity_results),
        "adaptive_vs_static": _build_adaptive_comparison(adaptive_results),
    }
    _print_lambda_sensitivity(report['lambda_sensitivity'])
    _print_adaptive_comparison(report['adaptive_vs_static'])

    report_path = RESULTS_DIR / 'lambda_sensitivity_report.json'
    with open(report_path, 'w', encoding='utf-8') as f:
        json.dump(report, f, indent=2, ensure_ascii=False, default=str)
    logger.info(f"\n报告已保存: {report_path}")
    # P3-3修复: 生成报告应返回报告对象（此前只写文件返回 None，调用方无法获取结果）
    return report


def main():
    # 实验1: Lambda敏感性
    sensitivity_results = run_lambda_sensitivity()

    # 实验2: 自适应 vs 静态
    adaptive_results = run_adaptive_vs_static()

    # 生成报告
    generate_report(sensitivity_results, adaptive_results)


if __name__ == '__main__':
    main()
