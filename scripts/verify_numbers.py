#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""verify_numbers.py —— 注册表驱动的数字复算器（P0-1）。

从 ``results/`` 原始 JSON 按 glob+field 复算 mean/SD/Welch p/Cohen d/95%CI/
提升率/检验力，逐条与 ``number_registry.json`` 的 ``declared`` 比对；并校验
repo 与 backup 双数据源一致性。**绝不粉饰**：注册表被改坏即 FAIL（见自证变异）。

用法::

    python -X utf8 scripts/verify_numbers.py \\
        --registry ../deliverables/number_registry.json \\
        --data-root results \\
        --mirror ../backup/pkg_old_src_20260917/results \\
        [--only NR-1,NR-3] [--strict] [--check-mirror] [--overwrite]

退出码（架构 §4.2）::

    0  全部非 PENDING/PLANNED 条目 PASS，且无 FAIL（PENDING 不阻断）
    1  至少一条 FAIL（复算值≠声明值，或 n 不符）
    2  用法 / IO / 注册表 schema 错误
    3  数据文件缺失（data-root 不可读）
    4  --strict 下存在 PENDING/PLANNED 条目

设计约束：被 import 时零副作用；所有 IO 均在 ``main()`` 之后。
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

# 同目录共享库（脚本既可 `python scripts/x.py` 也可 `-m scripts.x` 运行）
sys.path.insert(0, str(Path(__file__).resolve().parent))
import assurance_common as ac  # noqa: E402

logger = ac.get_logger("verify_numbers")


# --------------------------------------------------------------------------- #
# 取值 / 复算
# --------------------------------------------------------------------------- #
def _collect_source(data_root: Path, src: Dict[str, Any]) -> Tuple[List[Path], List[float]]:
    """按 glob 读文件、抽取字段；切片表达式逐文件取均值。"""
    files = ac.resolve_glob(data_root, src["glob"])
    field = src["field"]
    vals: List[float] = []
    for f in files:
        data = ac.load_json(f)
        v = ac.extract_field(data, field)
        if isinstance(v, (list, tuple)):
            v = ac.mean(v)
        vals.append(float(v))
    return files, vals


def _check_n(entry: Dict[str, Any], role: str, n: int, errors: List[str]) -> None:
    """声明样本数校验：不符即记 err（→ FAIL）。"""
    ne = entry.get("n_expected")
    if isinstance(ne, int) and n != ne:
        errors.append(f"role={role} n={n}≠n_expected={ne}")


def _recompute_two_sample(entry, data_root, errors):
    srcs = {s["role"]: s for s in entry["sources"]}
    fa, va = _collect_source(data_root, srcs["a"])
    fb, vb = _collect_source(data_root, srcs["b"])
    _check_n(entry, "a", len(va), errors)
    _check_n(entry, "b", len(vb), errors)
    if len(va) < 2 or len(vb) < 2:
        errors.append("样本不足（<2），拒绝产出结论")
        return {}, len(fa) + len(fb)
    return ac.two_sample_stats(va, vb), len(fa) + len(fb)


def _recompute_multi_sample(entry, data_root, errors):
    data: Dict[str, List[float]] = {}
    total = 0
    for src in entry["sources"]:
        files, vals = _collect_source(data_root, src)
        total += len(files)
        _check_n(entry, src["role"], len(vals), errors)
        data[src["role"]] = vals
    computed: Dict[str, Any] = {}
    for role, vals in data.items():
        if not vals:
            continue
        computed["mean_" + role] = ac.mean(vals)
        computed["sd_" + role] = ac.stdev(vals)
    base = entry.get("baseline_role")
    if base in data and data[base]:
        for role, vals in data.items():
            if role == base or not vals:
                continue
            computed["p_" + role] = ac.welch_ttest(data[base], vals)["p"]
            computed["improvement_pct_" + role] = ac.improvement_pct(
                ac.mean(vals), ac.mean(data[base])
            )
    return computed, total


def _recompute_delta(entry, data_root, errors):
    vals: Dict[str, List[float]] = {}
    total = 0
    for src in entry["sources"]:
        files, v = _collect_source(data_root, src)
        total += len(files)
        _check_n(entry, src["role"], len(v), errors)
        vals[src["role"]] = v
    computed: Dict[str, Any] = {}
    for pair in entry.get("pairs", []):
        a, b = vals.get(pair["a"], []), vals.get(pair["b"], [])
        if a and b:
            computed["delta_" + pair["label"]] = ac.mean(a) - ac.mean(b)
    return computed, total


def _consensus_rows(data_root: Path, rel: str) -> List[Dict[str, Any]]:
    return ac.load_json(Path(data_root) / rel).get("cw_pbft", []) or []


def _find_consensus(data_root: Path, entry: Dict[str, Any], match: Dict[str, Any]):
    p = Path(data_root) / entry["consensus_file"]
    doc = ac.load_json(p)
    out: Dict[str, Any] = {}
    ratio = match["byzantine_ratio"]
    for r in doc.get("cw_pbft", []):
        if r.get("n_nodes") == match["n_nodes"] and abs(r.get("byzantine_ratio", -1) - ratio) < 1e-9:
            out["cw_success_rate"] = r.get("success_rate")
            out["n_byzantine"] = r.get("n_byzantine")
            out["n_rounds"] = r.get("n_rounds")
            break
    for r in doc.get("standard_pbft", []):
        if r.get("n_nodes") == match["n_nodes"] and abs(r.get("byzantine_ratio", -1) - ratio) < 1e-9:
            out["std_success_rate"] = r.get("success_rate")
            break
    return out


def _recompute_consensus(entry, data_root, errors):
    if "matches" in entry:
        computed = {}
        for m in entry["matches"]:
            sub = _find_consensus(data_root, entry, m)
            if not sub:
                errors.append(f"未找到匹配行 {m}")
            computed[m["key"]] = sub
        return computed, len(entry["matches"])
    sub = _find_consensus(data_root, entry, entry["match"])
    if not sub:
        errors.append(f"未找到匹配行 {entry['match']}")
    return sub, 1


def _recompute_attack(entry, data_root, errors):
    doc = ac.load_json(Path(data_root) / "attack_defense_report.json")
    return {
        "defense_rate": doc["summary"]["defense_rate"],
        "n_attacks": len(doc.get("attacks", [])),
        "n_no_bc_success": doc["summary"].get("no_bc_success"),
    }, 1


def _recompute_code_check(entry, data_root, errors):
    computed: Dict[str, Any] = {}
    for chk in entry.get("checks", []):
        kind = chk["kind"]
        if kind in ("regex_capture", "regex_present"):
            path = ac.REPO_ROOT / chk["file"]
            if not path.exists():
                errors.append(f"代码文件缺失: {chk['file']}")
                continue
            m = re.search(chk["pattern"], ac.load_text(path))
            if kind == "regex_present":
                computed[chk["key"]] = bool(m)
            elif m:
                g = m.group(1)
                cast = chk.get("cast")
                if cast == "float":
                    computed[chk["key"]] = float(g)
                elif cast == "boolword":
                    computed[chk["key"]] = g.lower() == "true"
                else:
                    computed[chk["key"]] = g
            else:
                errors.append(f"未命中代码模式: {chk['key']}")
        elif kind == "json_nested_max":
            doc = ac.load_json(Path(data_root) / chk["data_file"])
            rows = ac.navigate(doc, chk["path"]) if chk.get("path") else doc
            mx: Optional[float] = None
            for r in rows:
                for v in (r.get(chk["subkey"], {}) or {}).values():
                    mx = v if mx is None else max(mx, v)
            computed[chk["key"]] = mx
        else:
            errors.append(f"未知 check kind: {kind}")
    return computed, 0


def recompute(entry: Dict[str, Any], data_root: Path) -> Tuple[Dict[str, Any], int, List[str]]:
    """按 analysis 类型复算单条；返回 ``(computed, files_scanned, errors)``。"""
    analysis = entry.get("analysis")
    errors: List[str] = []
    if analysis == "two_sample":
        computed, files = _recompute_two_sample(entry, data_root, errors)
    elif analysis == "multi_sample":
        computed, files = _recompute_multi_sample(entry, data_root, errors)
    elif analysis == "delta_arms":
        computed, files = _recompute_delta(entry, data_root, errors)
    elif analysis in ("consensus_row", "consensus_rows"):
        computed, files = _recompute_consensus(entry, data_root, errors)
    elif analysis == "attack_report":
        computed, files = _recompute_attack(entry, data_root, errors)
    elif analysis == "code_check":
        computed, files = _recompute_code_check(entry, data_root, errors)
    else:  # "none" / 缺失
        computed, files = {}, 0
    return computed, files, errors


# --------------------------------------------------------------------------- #
# 比对
# --------------------------------------------------------------------------- #
def _tol_for(key: str, tol: Dict[str, Any]) -> float:
    # 注意：百分比键形如 improvement_pct / improvement_pct_cars_010，故用 'pct' 子串判定
    if "pct" in key:
        return float(tol.get("pct_abs", 0.05))
    if "power" in key:
        return float(tol.get("power_abs", 0.02))
    if key == "welch_p" or key.endswith("_p") or key == "p_value":
        return float(tol.get("p_abs", 0.001))
    return float(tol.get("abs", 0.01))


def _compare_value(key: str, dec: Any, comp: Any, tol: Dict[str, Any]) -> Tuple[bool, Any]:
    if isinstance(dec, list):
        if not isinstance(comp, (list, tuple)) or len(dec) != len(comp):
            return False, None
        ok, deltas = True, []
        for d, c in zip(dec, comp):
            o, dl = _compare_value(key, d, c, tol)
            ok = ok and o
            deltas.append(dl)
        return ok, deltas
    if isinstance(dec, dict):
        if not isinstance(comp, dict):
            return False, None
        ok, dd = True, {}
        for k in dec:
            if k not in comp:
                return False, None
            o, dl = _compare_value(k, dec[k], comp[k], tol)
            ok = ok and o
            dd[k] = dl
        return ok, dd
    if isinstance(dec, bool) or isinstance(comp, bool):
        return dec == comp, None
    if isinstance(dec, str) or isinstance(comp, str):
        return str(dec) == str(comp), None
    try:
        delta = abs(float(dec) - float(comp))
    except (TypeError, ValueError):
        return False, None
    return delta <= _tol_for(key, tol), delta


def compare(entry: Dict[str, Any], computed: Dict[str, Any]) -> Tuple[bool, Dict[str, Any]]:
    """逐条比对 declared↔computed；返回 ``(all_ok, deltas)``。"""
    tol = entry.get("tolerance", {})
    ok, deltas = True, {}
    for key, dec in entry.get("declared", {}).items():
        if key not in computed:
            ok = False
            deltas[key] = "MISSING"
            continue
        o, dl = _compare_value(key, dec, computed[key], tol)
        ok = ok and o
        deltas[key] = dl
    return ok, deltas


# --------------------------------------------------------------------------- #
# 双数据源一致性
# --------------------------------------------------------------------------- #
def check_mirror(registry: Dict[str, Any], data_root: Path, mirror_root: Path) -> Dict[str, Any]:
    """repo↔backup 双源一致性：按注册表 glob 的文件名逐个比字段值。"""
    diffs: List[Dict[str, Any]] = []
    checked = 0
    seen_globs: set[str] = set()
    for entry in registry["entries"]:
        for src in entry.get("sources", []):
            g = src["glob"]
            if g in seen_globs:
                continue
            seen_globs.add(g)
            rf = ac.resolve_glob(data_root, g)
            mf = ac.resolve_glob(mirror_root, g)
            rmap = {p.name: p for p in rf}
            mmap = {p.name: p for p in mf}
            if set(rmap) != set(mmap):
                diffs.append({"glob": g, "only_repo": sorted(set(rmap) - set(mmap)),
                              "only_mirror": sorted(set(mmap) - set(rmap))})
            for name, rp in rmap.items():
                mp = mmap.get(name)
                if mp is None:
                    continue
                checked += 1
                try:
                    rv = ac.extract_field(ac.load_json(rp), src["field"])
                    mv = ac.extract_field(ac.load_json(mp), src["field"])
                except Exception as exc:  # noqa: BLE001
                    diffs.append({"file": name, "error": str(exc)})
                    continue
                if isinstance(rv, (list, tuple)):
                    rv = ac.mean(rv)
                if isinstance(mv, (list, tuple)):
                    mv = ac.mean(mv)
                if abs(float(rv) - float(mv)) > 1e-9:
                    diffs.append({"file": name, "repo": rv, "mirror": mv})
    return {"consistent": len(diffs) == 0, "files_compared": checked, "diffs": diffs}


# --------------------------------------------------------------------------- #
# 报告
# --------------------------------------------------------------------------- #
def _render_markdown(report: Dict[str, Any]) -> str:
    s = report["summary"]
    lines = [
        "# 数字复算报告（number_verification_report）",
        "",
        f"- 生成时间：{report['generated_at']}",
        f"- 注册表：`{report['registry_ref']}`",
        f"- 数据源：`{report['data_root']}`（镜像：`{report['mirror_root']}`，commit `{report['commit']}`）",
        f"- 汇总：total={s['total']} PASS={s['pass']} FAIL={s['fail']} PENDING={s['pending']} INVALID={s['invalid']}",
        f"- 双源一致：{'是' if report.get('mirror_consistent') else '**否**'}"
        + (f"（比较 {report['mirror']['files_compared']} 个文件，{len(report['mirror']['diffs'])} 处差异）"
           if report.get("mirror") else ""),
        "",
        "| ID | 状态 | 复算值（摘要） | 差异 | 备注 |",
        "|---|---|---|---|---|",
    ]
    for e in report["entries"]:
        comp = e.get("computed", {})
        brief = ", ".join(
            f"{k}={v:.4f}" if isinstance(v, float) else f"{k}={v}"
            for k, v in list(comp.items())[:4]
        )
        dmax = ""
        if isinstance(e.get("deltas"), dict):
            nums = [abs(v) for v in e["deltas"].values() if isinstance(v, (int, float))]
            if nums:
                dmax = f"max|Δ|={max(nums):.4g}"
        note = e.get("reason") or e.get("notes", "")
        lines.append(f"| {e['id']} | {e['status']} | {brief} | {dmax} | {note} |")
    lines.append("")
    return "\n".join(lines)


def _emit_report(report: Dict[str, Any], report_json: Path, overwrite: bool) -> None:
    pj = ac.safe_write_json(report, report_json, overwrite=overwrite)
    ac.safe_write_text(_render_markdown(report), pj.with_suffix(".md"), overwrite=overwrite)
    logger.info("报告已写出：%s", ac.rel_to_workspace(pj))
    logger.info("人读清单：%s", ac.rel_to_workspace(pj.with_suffix('.md')))


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #
def _resolve(p: str, default: Path) -> Path:
    if not p:
        return default
    cand = Path(p)
    if cand.is_absolute():
        return cand
    if cand.exists():
        return cand.resolve()
    return (ac.REPO_ROOT / cand).resolve()


def build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(description="注册表驱动的数字复算器")
    ap.add_argument("--registry", default=str(ac.REGISTRY_PATH), help="注册表 JSON")
    ap.add_argument("--data-root", default=str(ac.RESULTS_DIR), help="原始数据根（repo results）")
    ap.add_argument("--mirror", default=str(ac.MIRROR_ROOT), help="镜像数据根（backup results）")
    ap.add_argument("--only", default="", help="仅校验指定条目，逗号分隔，如 NR-1,NR-3")
    ap.add_argument("--strict", action="store_true", help="存在 PENDING/PLANNED 即退出码 4")
    ap.add_argument("--check-mirror", action="store_true", help="执行 repo↔backup 双源一致性校验")
    ap.add_argument("--run-tests", action="store_true", help="复跑 pytest 核实测试数量（NR-19）")
    ap.add_argument("--overwrite", action="store_true", help="允许覆盖同名报告（默认防覆盖另存）")
    ap.add_argument("--report", default=str(ac.REPORTS_DIR / "number_verification_report.json"))
    return ap


def main(argv: Optional[List[str]] = None) -> int:
    args = build_parser().parse_args(argv)

    registry_path = _resolve(args.registry, ac.REGISTRY_PATH)
    data_root = _resolve(args.data_root, ac.RESULTS_DIR)
    mirror_root = _resolve(args.mirror, ac.MIRROR_ROOT)

    if not registry_path.exists():
        logger.error("注册表不存在：%s", registry_path)
        return ac.EXIT_USAGE
    try:
        registry = ac.load_json(registry_path)
    except (OSError, json.JSONDecodeError) as exc:
        logger.error("注册表读取/schema 错误：%s", exc)
        return ac.EXIT_USAGE
    if not isinstance(registry.get("entries"), list):
        logger.error("注册表缺少 entries 列表（schema 错误）")
        return ac.EXIT_USAGE

    if not data_root.exists():
        logger.error("data-root 不可读：%s", data_root)
        return ac.EXIT_DATA_MISSING

    only = {x.strip() for x in args.only.split(",") if x.strip()}
    counts = {"total": 0, "pass": 0, "fail": 0, "pending": 0, "invalid": 0, "planned": 0}
    entries_out: List[Dict[str, Any]] = []
    has_fail = False

    for entry in registry["entries"]:
        if only and entry["id"] not in only:
            continue
        counts["total"] += 1
        declared_status = entry.get("status", "PENDING")
        analysis = entry.get("analysis", "none")

        computed: Dict[str, Any] = {}
        files = 0
        errors: List[str] = []
        if analysis != "none":
            computed, files, errors = recompute(entry, data_root)

        if declared_status in ("INVALID", "PLANNED"):
            status = declared_status
        elif analysis == "none" and declared_status == "PENDING":
            status = "PENDING"
        elif errors:
            status = "FAIL"
        else:
            ok, _ = compare(entry, computed)
            status = "PASS" if ok else "FAIL"

        _, deltas = compare(entry, computed) if computed else (False, {})

        if status == "FAIL":
            has_fail = True
            counts["fail"] += 1
        elif status == "PENDING":
            counts["pending"] += 1
        elif status == "PLANNED":
            counts["planned"] += 1
        elif status == "INVALID":
            counts["invalid"] += 1
        else:
            counts["pass"] += 1

        reason = "; ".join(errors) if errors else ""
        entries_out.append({
            "id": entry["id"],
            "status": status,
            "analysis": analysis,
            "computed": computed,
            "declared": entry.get("declared", {}),
            "deltas": deltas,
            "files_scanned": files,
            "n_expected": entry.get("n_expected"),
            "reason": reason,
            "notes": entry.get("notes", ""),
        })
        logger.info("%-6s %s%s", entry["id"], status, f"  [{reason}]" if reason else "")

    mirror_info = None
    mirror_consistent = None
    if args.check_mirror:
        mirror_info = check_mirror(registry, data_root, mirror_root)
        mirror_consistent = mirror_info["consistent"]

    report = {
        "schema_version": "1.0",
        "generated_at": ac.now_iso(),
        "registry_ref": ac.rel_to_workspace(registry_path),
        "data_root": ac.rel_to_workspace(data_root),
        "mirror_root": ac.rel_to_workspace(mirror_root),
        "commit": registry.get("commit", ""),
        "primary_metric": registry.get("primary_metric", ""),
        "summary": counts,
        "mirror_consistent": mirror_consistent,
        "mirror": mirror_info,
        "entries": entries_out,
    }

    report_json = _resolve(args.report, ac.REPORTS_DIR / "number_verification_report.json")
    _emit_report(report, report_json, overwrite=args.overwrite)

    logger.info("汇总：total=%d PASS=%d FAIL=%d PENDING=%d INVALID=%d",
                counts["total"], counts["pass"], counts["fail"], counts["pending"], counts["invalid"])

    if has_fail:
        logger.error("存在 FAIL —— 阻断（退出码 1）")
        return ac.EXIT_FAIL
    if args.strict and (counts["pending"] or counts["planned"]):
        logger.warning("--strict 下存在 PENDING/PLANNED（退出码 4）")
        return ac.EXIT_STRICT_PENDING
    logger.info("通过（退出码 0）")
    return ac.EXIT_OK


if __name__ == "__main__":
    sys.exit(main())
