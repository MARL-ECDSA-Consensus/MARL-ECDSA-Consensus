#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
run_weight_broadening_full.py — 路线C「参与率驱动权重展宽」全量实验（2026-09-19）

与 PoC（run_weight_broadening_poc.py）的关系：
    本脚本是 PoC 的**升格版**，展宽机制的数值与逻辑**逐字继承** PoC，不做任何调参：
        FLOOR=0.25   MIN_W=0.1   MAX_W=1.5   EPOCH_ROUNDS=50   HONEST_MSG_LOSS=0.05
    差异仅在规模与对照完整性：
        1) 种子 5 → 10（SEEDS 见下方常量）
        2) 四档权重对照同场跑：uniform / contribution / legacy / dynamic
        3) 配置网格 n∈{4,10,16} × byz∈{0.33,0.40}，每格 10 seed × 2000 轮
        4) 统计学补齐：Welch t / Cohen's d / 95%CI（复用 scripts/assurance_common.py，
           纯标准库，样本<2 时 fail-closed）

四档权重语义：
    uniform       全节点 w=1.0                  → R=1，CW-PBFT ≡ 标准 PBFT 的理论基线
    contribution  真实 MARL 训练产出的 bc_scores 归一化 → w=1.0+0.5*(s/max) ∈ [1.49,1.5]
                  （与 run_consensus_repeated.py 既有 contribution 口径一致，R≈1.007）
    legacy        拜占庭节点手工压到 w=0.2、诚实节点 1.0+0.3*(idx%3)
                  ⚠ 该档**预知坏节点身份**，属实验假象，仅作对照组，禁止作为创新点申报
                  → 输出带 is_artifact_control=true + warning
    dynamic       路线C：参与率驱动展宽 + 纪元冻结(50轮) + MAX_W=1.5 钳制 + FLOOR=0.25
                  初始权重默认 uniform（PoC 原样），可用 --dynamic-init contribution 切换

诚实红线：
    本脚本**不**为「结果好看」做任何调参。若某格扩到 10 seed 后效应消失或反转，
    原样输出并在 verdict 字段标注 "NO_GAIN" / "REVERSED"，不做任何抑制。

统计口径：
    ±SD 一律 sample SD（ddof=1）；Cohen's d 用 pooled SD（ddof=1）；
    Welch t 与 95%CI 用 assurance_common.welch_ttest / ci95_diff（Welch 自由度）。
    注：PoC 报告用的是 pstdev（ddof=0），故 5-seed 子集数值会有微小差异，属口径变更。

纯标准库（assurance_common 亦纯标准库），无需 torch/numpy。
"""
import sys
import json
import random
import hashlib
import time
import logging
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[3]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))
if str(_REPO_ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT / "scripts"))

from blockchain.consensus.cw_pbft import CWPBFTConsensus, ConsensusState
from blockchain.consensus.standard_pbft import StandardPBFTConsensus

from assurance_common import welch_ttest, cohens_d, ci95_diff, mean, stdev  # 纯标准库

# ── 机制参数（与 PoC 逐字一致，禁止调参）──
HONEST_MSG_LOSS = 0.05
EPOCH_ROUNDS = 50
FLOOR = 0.25
MIN_W = 0.1
MAX_W = 1.5

# ── 实验规模 ──
SEEDS = [42, 123, 456, 789, 1024, 2026, 3141, 5926, 7777, 8888]
NODE_COUNTS = [4, 10, 16]
BYZ_RATIOS = [0.33, 0.40]
MODES = ["uniform", "contribution", "legacy", "dynamic"]

ARTIFACT_WARNING = (
    "legacy 档在构造权重时直接读取 byzantine 身份集合（拜占庭 w=0.2、诚实 1.0+0.3*(idx%3)），"
    "等于协议事先知道谁是坏节点。该增益是实验假象，仅作对照组，禁止作为创新点申报。"
)


# ──────────────────────────────────────────────────────────────────────────────
# 权重构造
# ──────────────────────────────────────────────────────────────────────────────

def make_weights(mode, node_ids, byz_ids, scores):
    """构造初始权重映射。

    contribution 档：w = 1.0 + 0.5 * (s / max(s))，与 run_consensus_repeated.py:48 口径一致。
    scores 为空时调用方须先 fail-closed（见 load_scores）。
    """
    w = {}
    if mode == "uniform":
        for nid in node_ids:
            w[nid] = 1.0
    elif mode == "legacy":
        # ⚠ 实验假象对照组：此处读取 byz_ids 即"预知坏节点身份"，数值保持不变
        for nid in node_ids:
            if nid in byz_ids:
                w[nid] = 0.2
            else:
                idx = int(nid.split("_")[1])
                w[nid] = 1.0 + 0.3 * (idx % 3)
    elif mode == "contribution":
        if not scores:
            raise ValueError("contribution 档需要真实 bc_scores；未提供时禁止静默回退到合成数据")
        mx = max(scores.values())
        keys = sorted(scores.keys())
        for nid in node_ids:
            i = int(nid.split("_")[1])
            k = keys[i % len(keys)]
            w[nid] = 1.0 + 0.5 * (scores[k] / mx)
    elif mode == "dynamic":
        # 初值由 --dynamic-init 决定；此处返回 uniform，调用方按需覆盖
        for nid in node_ids:
            w[nid] = 1.0
    else:
        raise ValueError(f"未知权重档: {mode}")
    return w


def r_ratio(wmap):
    vals = list(wmap.values())
    mn = min(vals)
    if mn <= 0:
        return float("inf")
    return max(vals) / mn


def honest_weight_share(wmap, node_ids, byz_ids):
    tot = sum(wmap.values())
    if tot <= 0:
        return float("nan")
    return sum(wmap[n] for n in node_ids if n not in byz_ids) / tot


# ──────────────────────────────────────────────────────────────────────────────
# 模拟器
# ──────────────────────────────────────────────────────────────────────────────

def simulate_static(n_nodes, byz_ratio, n_rounds, seed, wmap):
    """静态权重 CW-PBFT（uniform / contribution / legacy 三档共用）"""
    random.seed(seed)
    node_ids = [f"node_{i}" for i in range(n_nodes)]
    n_byz = int(n_nodes * byz_ratio)
    byz_ids = set(node_ids[:n_byz])
    engine = CWPBFTConsensus(node_id="node_0", consensus_nodes=node_ids)
    for nid, wv in wmap.items():
        engine.update_weight(nid, wv)
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
    return succ / n_rounds


def simulate_dynamic(n_nodes, byz_ratio, n_rounds, seed, init_weights=None):
    """路线C：参与率驱动权重展宽 + 纪元冻结 + 钳制（PoC 逻辑逐字继承）"""
    random.seed(seed)
    node_ids = [f"node_{i}" for i in range(n_nodes)]
    n_byz = int(n_nodes * byz_ratio)
    byz_ids = set(node_ids[:n_byz])
    engine = CWPBFTConsensus(node_id="node_0", consensus_nodes=node_ids)
    weights = dict(init_weights) if init_weights else {nid: 1.0 for nid in node_ids}
    for nid, w in weights.items():
        engine.update_weight(nid, w)
    part_total = {nid: 0 for nid in node_ids}
    part_rounds = 0
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
        part_rounds += 1
        for nid in engine._votes.get('prepare', {}):
            part_total[nid] += 1
        if (r + 1) % EPOCH_ROUNDS == 0 and (r + 1) < n_rounds:
            new_w = {}
            for nid in node_ids:
                p = part_total[nid] / max(part_rounds, 1)
                raw = weights[nid] * (FLOOR + (1 - FLOOR) * p)
                new_w[nid] = max(MIN_W, min(MAX_W, raw))
            m = sum(new_w.values()) / len(new_w)
            weights = {nid: w / m for nid, w in new_w.items()}
            for nid, w in weights.items():
                engine.update_weight(nid, w)
            part_total = {nid: 0 for nid in node_ids}
            part_rounds = 0
    return succ / n_rounds, weights


def simulate_std(n_nodes, byz_ratio, n_rounds, seed):
    """标准 PBFT 基线（等权重、按节点数 2/3 阈值）"""
    random.seed(seed)
    node_ids = [f"node_{i}" for i in range(n_nodes)]
    n_byz = int(n_nodes * byz_ratio)
    byz_ids = set(node_ids[:n_byz])
    engine = StandardPBFTConsensus(node_id="node_0", consensus_nodes=node_ids)
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
    return succ / n_rounds


# ──────────────────────────────────────────────────────────────────────────────
# 单格运行
# ──────────────────────────────────────────────────────────────────────────────

def run_cell(n_nodes, byz_ratio, n_rounds, scores_by_seed, dynamic_init, modes, per_seed_dir):
    """一格 = (n, byz)：10 seed × 指定权重档。STD 基线每 seed 只算一次，四档共用（配对比较）。"""
    node_ids = [f"node_{i}" for i in range(n_nodes)]
    n_byz = int(n_nodes * byz_ratio)
    byz_ids = set(node_ids[:n_byz])

    # STD 基线（与权重档无关，同 seed 结果完全一致）
    std_rates = [simulate_std(n_nodes, byz_ratio, n_rounds, s) for s in SEEDS]

    # 逐 seed 落盘：让 number_registry 的 two_sample 复算能真正回溯到「文件 + 字段」
    if per_seed_dir:
        per_seed_dir.mkdir(parents=True, exist_ok=True)
        for s, v in zip(SEEDS, std_rates):
            (per_seed_dir / f"n{n_nodes}_b{byz_ratio:.2f}_std_seed{s}.json").write_text(
                json.dumps({"n_nodes": n_nodes, "byzantine_ratio": byz_ratio,
                            "seed": s, "engine": "standard_pbft",
                            "success_rate": v}, ensure_ascii=False, indent=2),
                encoding="utf-8")

    out_rows = []
    for mode in modes:
        cw_rates, r_finals, honest_shares = [], [], []
        for s in SEEDS:
            scores = (scores_by_seed or {}).get(s)
            if mode == "dynamic":
                init = None
                if dynamic_init == "contribution":
                    init = make_weights("contribution", node_ids, byz_ids, scores)
                rate, final_w = simulate_dynamic(n_nodes, byz_ratio, n_rounds, s, init)
            else:
                wmap = make_weights(mode, node_ids, byz_ids, scores)
                rate = simulate_static(n_nodes, byz_ratio, n_rounds, s, wmap)
                final_w = wmap
            cw_rates.append(rate)
            r_finals.append(r_ratio(final_w))
            honest_shares.append(honest_weight_share(final_w, node_ids, byz_ids))

        # 四档全部落盘：uniform/legacy 同样需要可回溯（uniform 是 R=1 理论退化验证，
        # legacy 是假象对照组，均须带 is_artifact_control 标记供下游识别）
        if per_seed_dir:
            for s, v in zip(SEEDS, cw_rates):
                (per_seed_dir / f"n{n_nodes}_b{byz_ratio:.2f}_{mode}_cw_seed{s}.json").write_text(
                    json.dumps({"n_nodes": n_nodes, "byzantine_ratio": byz_ratio,
                                "seed": s, "engine": "cw_pbft", "weight_mode": mode,
                                "success_rate": v}, ensure_ascii=False, indent=2),
                    encoding="utf-8")

        wt = welch_ttest(cw_rates, std_rates)
        lo, hi, _df = ci95_diff(cw_rates, std_rates)
        row = {
            "n_nodes": n_nodes,
            "byzantine_ratio": byz_ratio,
            "weight_mode": mode,
            "n_seeds": len(SEEDS),
            "n_rounds": n_rounds,
            "cw_mean": mean(cw_rates),
            "cw_sd": stdev(cw_rates, ddof=1),
            "std_mean": mean(std_rates),
            "std_sd": stdev(std_rates, ddof=1),
            "diff_mean": mean(cw_rates) - mean(std_rates),
            "cw_rates": cw_rates,
            "std_rates": std_rates,
            "welch_p": wt["p"],
            "welch_t": wt["t"],
            "welch_df": wt["df"],
            "cohens_d": cohens_d(cw_rates, std_rates),
            "ci95_diff": [lo, hi],
            "R_final_mean": mean(r_finals),
            "honest_weight_share_mean": mean(honest_shares),
            "is_artifact_control": mode == "legacy",
        }
        if mode == "legacy":
            row["warning"] = ARTIFACT_WARNING
        # 结论判定（不做任何抑制：无增益/反转照实标注）
        if row["welch_p"] < 0.05 and row["diff_mean"] > 0:
            row["verdict"] = "GAIN_SIGNIFICANT"
        elif row["diff_mean"] < 0 and row["welch_p"] < 0.05:
            row["verdict"] = "REVERSED"
        elif abs(row["diff_mean"]) < 1e-9:
            row["verdict"] = "IDENTICAL"
        else:
            row["verdict"] = "NO_GAIN"
        out_rows.append(row)
    return out_rows


# ──────────────────────────────────────────────────────────────────────────────
# 真实贡献度分数加载
# ──────────────────────────────────────────────────────────────────────────────

def load_scores(index_path, n_nodes, contrib_source):
    """从 e2e 产出的索引 JSON 加载 (n → seed → scores)。

    contrib_source:
        normalized_scores  → 原始 bc_scores（由调用方归一化，口径同既有 contribution 档）
        production_weights → 生产链路 cw_pbft 中真实落地的权重（w=1.0+0.5*weighted_score）
    """
    if not index_path:
        return None
    p = Path(index_path)
    if not p.exists():
        raise SystemExit(f"[FAIL-CLOSED] 贡献度索引不存在: {p}")
    data = json.loads(p.read_text(encoding="utf-8"))
    runs = data["runs_by_n"].get(str(n_nodes))
    if not runs:
        raise SystemExit(f"[FAIL-CLOSED] 索引中缺少 n={n_nodes} 的真实训练分数: {p}")
    out = {}
    for s in SEEDS:
        rec = runs.get(str(s))
        if rec is None:
            raise SystemExit(f"[FAIL-CLOSED] 索引缺少 n={n_nodes} seed={s} 的真实训练分数")
        out[s] = rec["production_weights"] if contrib_source == "production_weights" else rec["bc_scores"]
    return out


# ──────────────────────────────────────────────────────────────────────────────

def main():
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--rounds", type=int, default=2000)
    ap.add_argument("--nodes", default="4,10,16")
    ap.add_argument("--ratios", default="0.33,0.40")
    ap.add_argument("--modes", default="uniform,contribution,legacy,dynamic")
    ap.add_argument("--dynamic-init", choices=["uniform", "contribution"], default="uniform")
    ap.add_argument("--contrib-source", choices=["normalized_scores", "production_weights"],
                    default="normalized_scores")
    ap.add_argument("--scores-index", default=None,
                    help="e2e 产出的 bc_scores_index.json；contribution/dynamic(contribution-init) 档必需")
    ap.add_argument("--out", default=None)
    ap.add_argument("--per-seed-dir", default=None,
                    help="逐 seed 落盘目录（供 number_registry two_sample 复算）；"
                         "默认 results/consensus_comparison/weight_broadening_full/")
    ap.add_argument("--no-per-seed", action="store_true", help="不落逐 seed 文件")
    ap.add_argument("--smoke", action="store_true", help="冒烟：1 seed / 200 轮 / 仅 n=4")
    a = ap.parse_args()

    logging.basicConfig(level=logging.WARNING)
    logging.getLogger("blockchain.consensus.cw_pbft").setLevel(logging.ERROR)

    modes = [m.strip() for m in a.modes.split(",") if m.strip()]
    need_scores = ("contribution" in modes) or (a.dynamic_init == "contribution")

    if a.smoke:
        globals()["SEEDS"] = [42]
        nodes, ratios, rounds = [4], [0.33], 200
    else:
        nodes = [int(x) for x in a.nodes.split(",")]
        ratios = [float(x) for x in a.ratios.split(",")]
        rounds = a.rounds

    if a.no_per_seed:
        per_seed_dir = None
    elif a.per_seed_dir:
        per_seed_dir = Path(a.per_seed_dir)
    else:
        per_seed_dir = _REPO_ROOT / "results" / "consensus_comparison" / "weight_broadening_full"

    results = []
    t0 = time.time()
    for n in nodes:
        scores_by_seed = load_scores(a.scores_index, n, a.contrib_source) if need_scores else None
        for br in ratios:
            rows = run_cell(n, br, rounds, scores_by_seed, a.dynamic_init, modes, per_seed_dir)
            results.extend(rows)
            for r in rows:
                print(f"  n={n:>3} byz={br*100:>3.0f}% mode={r['weight_mode']:>12} | "
                      f"CW {r['cw_mean']*100:>5.1f}±{r['cw_sd']*100:.1f}%  "
                      f"STD {r['std_mean']*100:>5.1f}±{r['std_sd']*100:.1f}%  "
                      f"Δ {r['diff_mean']*100:+6.1f}%  p={r['welch_p']:.2e}  "
                      f"d={r['cohens_d']:+.2f}  R={r['R_final_mean']:.3f}  "
                      f"honest_w={r['honest_weight_share_mean']*100:.1f}%  {r['verdict']}")

    out = {
        "meta": {
            "script": "scripts/legacy/experiments/run_weight_broadening_full.py",
            "generated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
            "seeds": SEEDS,
            "n_rounds": rounds,
            "epoch_rounds": EPOCH_ROUNDS,
            "floor": FLOOR, "min_w": MIN_W, "max_w": MAX_W,
            "honest_msg_loss": HONEST_MSG_LOSS,
            "dynamic_init": a.dynamic_init,
            "contrib_source": a.contrib_source,
            "sd_ddof": 1,
            "cohens_d_ddof": 1,
            "stats_backend": "scripts/assurance_common.py (welch_ttest / cohens_d / ci95_diff, stdlib only)",
            "scores_index": a.scores_index,
            "per_seed_dir": str(per_seed_dir) if per_seed_dir else None,
            "smoke": bool(a.smoke),
            "elapsed_sec": round(time.time() - t0, 1),
            "mechanism": "participation-driven decay, epoch-frozen(50), clipped[0.1,1.5]",
        },
        "results": results,
    }
    op = (Path(a.out) if a.out else
          _REPO_ROOT / "results" / "consensus_comparison" / "weight_broadening_full_report.json")
    op.parent.mkdir(parents=True, exist_ok=True)
    with open(op, "w", encoding="utf-8") as f:
        json.dump(out, f, indent=2, ensure_ascii=False)
    print(f"\n[报告写入] {op}  ({len(results)} 行, {out['meta']['elapsed_sec']}s)")


if __name__ == "__main__":
    main()
