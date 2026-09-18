#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
run_consensus_repeated.py — 共识对比的重复实验 + 权重来源诊断（新增，不动 legacy 脚本）
用途：
  1) EXP-3：合成权重(legacy) 5 种子重复 → 均值±SD（补"每配置 n=1"缺口）
  2) 诊断：比较三种权重来源在 n=10、33%/40% 下的 CW-PBFT vs 标准 PBFT：
       legacy       = 拜占庭 0.2、诚实 1.0+0.3*(idx%3)  （R≈8，原实验假象）
       uniform      = 全节点权重 1.0                       （R=1，真实贡献度近似）
       contribution = 真实 bc_scores 归一化作权重          （R≈1.008，真实数据）
  关键：legacy 里拜占庭被人工压到 0.2（"协议事先知道谁是坏节点"）；uniform/contribution
        不做这种特殊降权 —— 这才是"贡献度加权能否带来额外容错"的诚实检验。

纯标准库，零第三方依赖。python3 直接跑。
"""
import sys, os, json, random, hashlib, time, statistics as st
from pathlib import Path

_REPO_ROOT = str(Path(__file__).resolve().parent.parent.parent.parent)
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

from blockchain.consensus.cw_pbft import CWPBFTConsensus, ConsensusState
from blockchain.consensus.standard_pbft import StandardPBFTConsensus

HONEST_MSG_LOSS = 0.05
SEEDS = [42, 123, 456, 789, 1024]


def make_weights(mode, node_ids, byzantine_ids, scores):
    w = {}
    if mode == "legacy":
        for nid in node_ids:
            if nid in byzantine_ids:
                w[nid] = 0.2
            else:
                idx = int(nid.split("_")[1])
                w[nid] = 1.0 + 0.3 * (idx % 3)
    elif mode == "uniform":
        for nid in node_ids:
            w[nid] = 1.0
    elif mode == "contribution":
        mx = max(scores.values())
        keys = sorted(scores.keys())
        for nid in node_ids:
            i = int(nid.split("_")[1])
            k = keys[i % len(keys)]
            w[nid] = 1.0 + 0.5 * (scores[k] / mx)
    return w


def simulate(consensus_class, n_nodes, byz_ratio, n_rounds, weight_mode, seed, scores=None):
    random.seed(seed)
    node_ids = [f"node_{i}" for i in range(n_nodes)]
    n_byz = int(n_nodes * byz_ratio)
    byz_ids = set(node_ids[:n_byz])
    engine = consensus_class(node_id="node_0", consensus_nodes=node_ids)
    final_weights = None
    if consensus_class is CWPBFTConsensus and weight_mode is not None:
        wmap = make_weights(weight_mode, node_ids, byz_ids, scores or {})
        for nid, wv in wmap.items():
            engine.update_weight(nid, wv)
        final_weights = dict(wmap)
    succ = 0
    for r in range(n_rounds):
        engine.reset()
        engine._state = ConsensusState.IDLE
        silent = set(byz_ids)
        for nid in node_ids:
            if nid not in byz_ids and random.random() < HONEST_MSG_LOSS:
                silent.add(nid)
        proposer = engine.get_primary(0)
        bh = hashlib.sha256(f"{seed}:{r}".encode()).hexdigest()
        if engine.simulated_consensus(bh, proposer, byzantine_nodes=silent):
            succ += 1
    return succ / n_rounds, final_weights


def r_ratio(wmap):
    if not wmap or len(wmap) < 2:
        return None
    vals = list(wmap.values())
    mn = min(vals)
    return max(vals) / mn if mn > 0 else float("inf")


def run_repeated(n_nodes, byz_ratio, n_rounds, weight_mode, scores=None):
    cw_rates, std_rates = [], []
    for s in SEEDS:
        c, cw = simulate(CWPBFTConsensus, n_nodes, byz_ratio, n_rounds, weight_mode, s, scores)
        sd, _ = simulate(StandardPBFTConsensus, n_nodes, byz_ratio, n_rounds, None, s, scores)
        cw_rates.append(c); std_rates.append(sd)
    return {
        "n_nodes": n_nodes, "byzantine_ratio": byz_ratio, "weight_mode": weight_mode,
        "n_seeds": len(SEEDS), "n_rounds": n_rounds,
        "cw_mean": st.mean(cw_rates), "cw_sd": st.pstdev(cw_rates),
        "std_mean": st.mean(std_rates), "std_sd": st.pstdev(std_rates),
        "diff_mean": st.mean(cw_rates) - st.mean(std_rates),
        "cw_rates": cw_rates, "std_rates": std_rates,
        "R": r_ratio(make_weights(weight_mode, [f"node_{i}" for i in range(n_nodes)],
                                  set(f"node_{i}" for i in range(int(n_nodes*byz_ratio))), scores or {})) if weight_mode else None,
    }


def main():
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--rounds", type=int, default=2000)
    ap.add_argument("--mode", choices=["exp3", "diagnostic"], default="exp3")
    ap.add_argument("--scores-file", default=None)
    a = ap.parse_args()

    scores = None
    if a.scores_file:
        scores = json.load(open(a.scores_file, encoding="utf-8"))

    out = {"results": [], "meta": {"rounds": a.rounds, "seeds": SEEDS}}

    if a.mode == "exp3":
        configs = [(n, r) for n in [4, 7, 10, 16] for r in [0.0, 0.1, 0.2, 0.33, 0.4]]
    else:
        configs = [(10, 0.33), (10, 0.4), (16, 0.4)]

    for (n, r) in configs:
        if a.mode == "exp3":
            modes = ["legacy"]
        else:
            modes = ["legacy", "uniform", "contribution"]
        for m in modes:
            res = run_repeated(n, r, a.rounds, m, scores)
            out["results"].append(res)
            print(f"  n={n:>3} byz={r*100:>3.0f}% mode={m:>12} R={res['R'] or 1.0:>6.3f} | "
                  f"CW {res['cw_mean']*100:>5.1f}±{res['cw_sd']*100:.1f}%  "
                  f"STD {res['std_mean']*100:>5.1f}±{res['std_sd']*100:.1f}%  "
                  f"diff {res['diff_mean']*100:+6.1f}%")

    op = Path(_REPO_ROOT) / "results" / "consensus_comparison" / f"repeated_{a.mode}_report.json"
    op.parent.mkdir(parents=True, exist_ok=True)
    with open(op, "w", encoding="utf-8") as f:
        json.dump(out, f, indent=2, ensure_ascii=False)
    print(f"\n[报告写入] {op}")


if __name__ == "__main__":
    main()
