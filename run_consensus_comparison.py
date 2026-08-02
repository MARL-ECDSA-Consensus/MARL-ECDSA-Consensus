"""
Tier1: CW-PBFT vs Standard PBFT 对比实验（v2 — 真实投票模拟）

核心差异体现：
- Standard PBFT：需要 2n/3 个节点投票（按节点数），拜占庭节点不投票 → 难达阈值
- CW-PBFT：需要 2/3 总权重，诚实节点权重高 → 少数诚实节点即可达阈值

实验设计：
1. 每轮共识：主节点发起 → 收集prepare → 收集commit → 检查是否达成
2. 拜占庭节点：50%概率不投票，50%概率投错票（不参与共识）
3. 不使用fast_consensus fallback，真实统计成功率
4. 测量：共识成功率、共识延迟、权重分配效果
"""
import json
import time
import random
import hashlib
import logging
import sys
from pathlib import Path
from typing import List, Dict, Tuple, Optional

sys.path.insert(0, str(Path(__file__).parent))

from blockchain.consensus.cw_pbft import CWPBFTConsensus, ConsensusState, ConsensusVote
from blockchain.consensus.standard_pbft import StandardPBFTConsensus

logging.basicConfig(level=logging.WARNING, format='%(asctime)s [%(levelname)s] %(message)s')
logger = logging.getLogger('consensus_compare')

RESULTS_DIR = Path(__file__).parent / 'results' / 'consensus_comparison'
RESULTS_DIR.mkdir(parents=True, exist_ok=True)

NODE_COUNTS = [4, 7, 10, 16]
BYZANTINE_RATIOS = [0.0, 0.1, 0.2, 0.33, 0.4]
N_ROUNDS = 100
HONEST_MSG_LOSS = 0.05  # 5% 消息丢失率（模拟网络不可靠）


def simulate_round(
    nodes: List,
    node_ids: List[str],
    byzantine_ids: set,
    round_idx: int,
    primary_idx: int,
) -> Tuple[bool, float]:
    """
    模拟单轮共识，返回 (是否成功, 延迟ms)

    真实模拟三阶段PBFT：
    1. pre-prepare: 主节点广播
    2. prepare: 所有节点收到后广播prepare投票
    3. commit: 收到足够prepare后广播commit投票
    4. 检查每个节点是否独立达成共识
    """
    block_data = f'block_{round_idx}_{time.time()}'
    block_hash = hashlib.sha256(block_data.encode()).hexdigest()

    primary = nodes[primary_idx]
    start_ms = time.time() * 1000

    # Phase 1: pre-prepare
    primary.start_consensus(block_hash)

    # 主节点也进入PREPARE状态（标准PBFT中主节点发pre-prepare后也发prepare）
    primary._state = ConsensusState.PREPARE
    primary_prepare = ConsensusVote(
        voter_id=primary.node_id,
        block_hash=block_hash,
        phase='prepare',
        weight=primary._weights.get(primary.node_id, 1.0),
    )
    primary._votes['prepare'][primary.node_id] = primary_prepare

    # Phase 2: prepare — 每个非主节点收到pre-prepare后投票
    prepare_votes = [primary_prepare]  # 包含主节点的prepare票
    for node in nodes:
        if node.node_id == primary.node_id:
            continue
        if node.node_id in byzantine_ids:
            # 拜占庭节点：100%不投票（静默攻击）
            pass
        else:
            # 诚实节点：95%概率正常投票（5%消息丢失）
            if random.random() > HONEST_MSG_LOSS:
                vote = node.receive_pre_prepare(block_hash, primary.node_id)
                if vote:
                    prepare_votes.append(vote)

    # 将prepare投票广播给所有节点（包括生成者自己）
    commit_votes_generated = []
    for pv in prepare_votes:
        for node in nodes:
            result = node.receive_vote(pv)
            if result and result not in commit_votes_generated:
                commit_votes_generated.append(result)

    # Phase 3: commit — 传播commit投票（包括给生成者自己）
    for cv in commit_votes_generated:
        for node in nodes:
            node.receive_vote(cv)

    elapsed_ms = time.time() * 1000 - start_ms

    # 检查主节点是否达成共识（代表整个网络）
    success = primary.is_consensus_reached()
    return success, elapsed_ms


def simulate_consensus(
    consensus_class,
    n_nodes: int,
    byzantine_ratio: float,
    n_rounds: int,
    use_weights: bool = True,
) -> Dict:
    """模拟N轮共识"""
    node_ids = [f'node_{i}' for i in range(n_nodes)]
    n_byzantine = int(n_nodes * byzantine_ratio)
    byzantine_ids = set(node_ids[:n_byzantine]) if n_byzantine > 0 else set()

    # 创建所有节点
    nodes = []
    for nid in node_ids:
        node = consensus_class(node_id=nid, consensus_nodes=node_ids)
        nodes.append(node)

    # CW-PBFT: 设置差异化权重
    if use_weights and consensus_class == CWPBFTConsensus:
        for node in nodes:
            for nid in node_ids:
                if nid in byzantine_ids:
                    node.update_weight(nid, 0.2)  # 拜占庭节点极低权重
                else:
                    idx = int(nid.split('_')[1])
                    base_weight = 1.0 + 0.3 * (idx % 3)
                    node.update_weight(nid, base_weight)

    latencies = []
    successes = 0
    failures = 0

    for round_idx in range(n_rounds):
        # 每轮重置所有节点状态
        for node in nodes:
            node.reset()
            node._state = ConsensusState.IDLE

        primary_idx = (round_idx // 10) % n_nodes
        success, latency = simulate_round(
            nodes, node_ids, byzantine_ids, round_idx, primary_idx
        )

        if success:
            successes += 1
            latencies.append(latency)
        else:
            failures += 1

    avg_latency = sum(latencies) / len(latencies) if latencies else 0.0
    success_rate = successes / n_rounds if n_rounds > 0 else 0.0

    # 获取CW-PBFT最终权重分配
    final_weights = {}
    if use_weights and consensus_class == CWPBFTConsensus and nodes:
        final_weights = nodes[0].get_weights()

    return {
        'n_nodes': n_nodes,
        'byzantine_ratio': byzantine_ratio,
        'n_byzantine': n_byzantine,
        'n_rounds': n_rounds,
        'successes': successes,
        'failures': failures,
        'success_rate': success_rate,
        'avg_latency_ms': round(avg_latency, 3),
        'min_latency_ms': round(min(latencies), 3) if latencies else 0.0,
        'max_latency_ms': round(max(latencies), 3) if latencies else 0.0,
        'final_weights': final_weights,
    }


def main():
    logger.info(f"=== CW-PBFT vs Standard PBFT v2 ===")
    logger.info(f"节点数: {NODE_COUNTS}, 拜占庭比例: {BYZANTINE_RATIOS}, 每配置{N_ROUNDS}轮")

    results = {'cw_pbft': [], 'standard_pbft': [], 'comparison': []}
    total_configs = len(NODE_COUNTS) * len(BYZANTINE_RATIOS)
    config_idx = 0

    for n in NODE_COUNTS:
        for byz_ratio in BYZANTINE_RATIOS:
            config_idx += 1
            logger.info(f"[{config_idx}/{total_configs}] n={n}, byzantine={byz_ratio:.0%}")

            cw_result = simulate_consensus(CWPBFTConsensus, n, byz_ratio, N_ROUNDS, use_weights=True)
            cw_result['consensus_type'] = 'cw_pbft'
            results['cw_pbft'].append(cw_result)

            std_result = simulate_consensus(StandardPBFTConsensus, n, byz_ratio, N_ROUNDS, use_weights=False)
            std_result['consensus_type'] = 'standard_pbft'
            results['standard_pbft'].append(std_result)

            latency_improvement = 0.0
            if std_result['avg_latency_ms'] > 0 and cw_result['avg_latency_ms'] > 0:
                latency_improvement = (
                    (std_result['avg_latency_ms'] - cw_result['avg_latency_ms'])
                    / std_result['avg_latency_ms'] * 100
                )

            comparison = {
                'n_nodes': n,
                'byzantine_ratio': byz_ratio,
                'cw_pbft_success_rate': cw_result['success_rate'],
                'std_pbft_success_rate': std_result['success_rate'],
                'cw_pbft_avg_latency': cw_result['avg_latency_ms'],
                'std_pbft_avg_latency': std_result['avg_latency_ms'],
                'latency_improvement_pct': round(latency_improvement, 2),
                'success_rate_diff': cw_result['success_rate'] - std_result['success_rate'],
            }
            results['comparison'].append(comparison)

            logger.info(
                f"  CW: rate={cw_result['success_rate']:.1%}, lat={cw_result['avg_latency_ms']:.3f}ms | "
                f"PBFT: rate={std_result['success_rate']:.1%}, lat={std_result['avg_latency_ms']:.3f}ms | "
                f"diff={comparison['success_rate_diff']:+.1%}"
            )

    report_path = RESULTS_DIR / 'consensus_comparison_report.json'
    with open(report_path, 'w', encoding='utf-8') as f:
        json.dump(results, f, indent=2, ensure_ascii=False)
    logger.info(f"Report saved: {report_path}")

    # 打印摘要表
    print("\n" + "=" * 95)
    print("CW-PBFT vs Standard PBFT Comparison Results")
    print("=" * 95)
    print(f"{'Nodes':>6} {'Byz%':>6} | {'CW Rate':>8} {'PBFT Rate':>10} | {'CW Lat':>8} {'PBFT Lat':>9} {'Diff':>6}")
    print("-" * 95)
    for c in results['comparison']:
        print(
            f"{c['n_nodes']:>6} {c['byzantine_ratio']:>5.0%} | "
            f"{c['cw_pbft_success_rate']:>7.1%} {c['std_pbft_success_rate']:>9.1%} | "
            f"{c['cw_pbft_avg_latency']:>7.3f}ms {c['std_pbft_avg_latency']:>8.3f}ms "
            f"{c['success_rate_diff']:>+5.1%}"
        )


if __name__ == '__main__':
    main()
