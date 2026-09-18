"""
E7 — R 判据边界验证（支撑 C3 改写：贡献度加权的容错增益条件）

背景
----
EXP-3（5 种子 × 2000 轮）证明：当贡献度权重为均匀（R=1）或真实 MARL
贡献度导出（R≈1.007）时，CW-PBFT 与标准 PBFT 完全等价——贡献度加权本身
不提供额外容错。路线 C PoC 进一步证明：引入参与率驱动的权重展宽使
R≈15 时，n=10/40% 省略故障下成功率 0%→94.5%。

本脚本对 M3 判据做**独立、可复跑的数值验证**，并显式澄清一个公式口径：
规划文档 §197 写作 `b < n/(2R+1)`，那是把 R 取为「拜占庭/诚实权重比」时的
互易形式；本报告采用路线 C PoC 报告 §24 的定义（R = 诚实权重 / 拜占庭权重，
均匀时 R=1），其正确安全条件为：

    诚实权重 ≥ 2/3 总权重  ⟺  拜占庭权重占比 β < 1/3
    β = f / ((1-f)·R + f)                     （f = 拜占庭节点占比）
    ⟹ 最大可容忍拜占庭节点占比  f_max = R / (R+2)

校验：
    R=1     → f_max = 1/3      ≈ 标准 PBFT（无增益）
    R≈1.007 → f_max ≈ 33.5%    ≈ n/3（无增益，数学必然）
    R=15    → f_max ≈ 88.2%    （增益显著，PoC 实测诚实权重占比 95.7%）

运行（本机 Py3.12，无需服务器，纯 math）：
    python scripts/legacy/analysis/r_judgment_verification.py
"""

import json
import math
import os
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent.parent


def byzantine_weight_fraction(f: float, R: float) -> float:
    """给定拜占庭节点占比 f 与权重集中度比 R=w_honest/w_byz，返回拜占庭权重占比 β。"""
    return f / ((1.0 - f) * R + f)


def max_byzantine_fraction(R: float) -> float:
    """最大可容忍拜占庭节点占比 f_max = R/(R+2)。"""
    return R / (R + 2)


def cw_pbft_safe(n: int, b_nodes: int, R: float) -> bool:
    """CW-PBFT 在该配置下能否达成安全共识（诚实权重 ≥ 2/3 总权重）。"""
    h = n - b_nodes
    w_h, w_b = R, 1.0  # 归一化：拜占庭权重单位 1，诚实为 R 倍
    total = h * w_h + b_nodes * w_b
    honest = h * w_h
    return honest >= (2.0 / 3.0) * total


def run() -> dict:
    R_scan = [1.0, 1.5, 3.0, 5.0, 8.0, 15.0]
    n_scan = [4, 7, 10, 16]

    # ── 1. R 扫描：f_max vs R ──
    scan = []
    for R in R_scan:
        fmax = max_byzantine_fraction(R)
        scan.append({
            "R": R,
            "f_max": round(fmax, 4),
            "f_max_pct": round(fmax * 100, 2),
            "note": "≈ 标准 PBFT (n/3)" if abs(R - 1.0) < 1e-6
                    else ("无增益（≈n/3）" if R < 1.5 else "增益显著"),
        })

    # ── 2. 复现路线 C PoC：R≈15, n=10/40% ──
    poc = []
    for n, f, R, cw_rate in [
        (10, 0.33, 14.93, 0.986), (10, 0.40, 15.00, 0.945),
        (16, 0.33, 15.00, 0.987), (16, 0.40, 15.00, 0.973),
        (4, 0.33, 14.27, 0.895),
    ]:
        beta = byzantine_weight_fraction(f, R)
        b_nodes = round(f * n)
        safe = cw_pbft_safe(n, b_nodes, R)
        poc.append({
            "config": f"n={n}, byz={int(f*100)}%", "R": R,
            "byzantine_weight_fraction": round(beta, 4),
            "beta_below_1_3": beta < 1 / 3,
            "cw_pbft_safe": safe,
            "poc_cw_rate": cw_rate,
        })

    # ── 3. 复现 EXP-3 三权重来源（R≈1.007 → 无增益） ──
    exp3 = {
        "uniform_R1": {
            "R": 1.0,
            "f_max_pct": round(max_byzantine_fraction(1.0) * 100, 2),
            "interpretation": "CW ≡ STD（与标准 PBFT 完全等价）",
        },
        "contribution_R1007": {
            "R": 1.007,
            "f_max_pct": round(max_byzantine_fraction(1.007) * 100, 2),
            "interpretation": "CW ≡ STD（增益≈0，无增益是数学必然）",
        },
        "legacy_R8": {
            "R": 8.0,
            "f_max_pct": round(max_byzantine_fraction(8.0) * 100, 2),
            "interpretation": "权重编码了故障先验（R 大）→ 展宽容错边界",
        },
    }

    # ── 4. 自检（断言已知值） ──
    checks = []
    def chk(name, cond, detail):
        checks.append({"name": name, "pass": bool(cond), "detail": detail})

    chk("R=1 → f_max≈1/3", abs(max_byzantine_fraction(1.0) - 1/3) < 1e-9,
        f"f_max={max_byzantine_fraction(1.0):.6f}")
    chk("R=1.007 → f_max≈33.5%≈n/3",
        abs(max_byzantine_fraction(1.007) - 1/3) < 0.01,
        f"f_max={max_byzantine_fraction(1.007)*100:.3f}%")
    chk("R=15 → f_max≈88.2%", abs(max_byzantine_fraction(15.0) - 15/17) < 1e-9,
        f"f_max={max_byzantine_fraction(15.0)*100:.3f}%")
    poc_beta = byzantine_weight_fraction(0.40, 15.0)
    chk("PoC n=10/40%/R=15 → β<1/3", poc_beta < 1/3,
        f"β={poc_beta*100:.3f}%")
    chk("PoC n=10/40%/R=15 → CW-PBFT 安全", cw_pbft_safe(10, 4, 15.0), "b_nodes=4")
    chk("EXP-3 n=10/40%/R=1 → 不安全（CW=STD 失败）",
        not cw_pbft_safe(10, 4, 1.0), "b_nodes=4, R=1")

    all_pass = all(c["pass"] for c in checks)

    report = {
        "title": "E7 — R 判据边界验证",
        "formula": "f_max = R/(R+2)  （R = 诚实权重 / 拜占庭权重；均匀 R=1）",
        "clarification": ("规划文档 §197 的 b < n/(2R+1) 是 R 取倒数定义时的互易形式；"
                         "本报告采用路线C PoC 定义，正确式为 f_max = R/(R+2)"),
        "r_scan": scan,
        "poc_reproduction": poc,
        "exp3_reproduction": exp3,
        "self_checks": checks,
        "all_checks_pass": all_pass,
    }

    out_path = REPO_ROOT / "results" / "consensus_comparison" / "r_judgment_verification.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)
    print(f"报告已保存: {out_path}")
    return report


def _print_markdown(report: dict):
    lines = []
    lines.append(f"# {report['title']}\n")
    lines.append(f"**安全条件**：`{report['formula']}`\n")
    lines.append(f"> ⚠️ 口径澄清：{report['clarification']}\n")
    lines.append("## R 扫描：f_max vs R\n")
    lines.append("| R | f_max | f_max(%) | 说明 |")
    lines.append("|---|---|---|---|")
    for s in report["r_scan"]:
        lines.append(f"| {s['R']} | {s['f_max']} | {s['f_max_pct']} | {s['note']} |")
    lines.append("\n## 复现路线 C PoC（R≈15）\n")
    lines.append("| 配置 | R | 拜占庭权重占比 β | β<1/3 | CW-PBFT 安全 | PoC 实测成功率 |")
    lines.append("|---|---|---|---|---|---|")
    for p in report["poc_reproduction"]:
        lines.append(f"| {p['config']} | {p['R']} | {p['byzantine_weight_fraction']} | "
                     f"{p['beta_below_1_3']} | {p['cw_pbft_safe']} | {p['poc_cw_rate']} |")
    lines.append("\n## 复现 EXP-3 三权重来源\n")
    for k, v in report["exp3_reproduction"].items():
        lines.append(f"- **{k}**（R={v['R']}）：f_max={v['f_max_pct']}% — {v['interpretation']}")
    lines.append("\n## 自检\n")
    for c in report["self_checks"]:
        mark = "✅" if c["pass"] else "❌"
        lines.append(f"- {mark} {c['name']} — {c['detail']}")
    lines.append(f"\n**结论**：{'全部自检通过' if report['all_checks_pass'] else '存在失败项，需复查'}\n")
    md_path = REPO_ROOT / "results" / "consensus_comparison" / "r_judgment_verification.md"
    md_path.parent.mkdir(parents=True, exist_ok=True)
    md_path.write_text("\n".join(lines), encoding="utf-8")
    print(f"Markdown 已保存: {md_path}")


if __name__ == "__main__":
    rep = run()
    _print_markdown(rep)
    print("\n=== R 扫描 ===")
    for s in rep["r_scan"]:
        print(f"  R={s['R']:<5} f_max={s['f_max_pct']:>6}%  {s['note']}")
    print("\n=== 自检 ===")
    for c in rep["self_checks"]:
        print(f"  [{'PASS' if c['pass'] else 'FAIL'}] {c['name']} ({c['detail']})")
    print(f"\nALL_CHECKS_PASS = {rep['all_checks_pass']}")
    assert rep["all_checks_pass"], "E7 自检存在失败项"
