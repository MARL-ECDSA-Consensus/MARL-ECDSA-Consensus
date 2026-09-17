#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""scan_void_tokens.py —— 作废令牌扫描（P1-7 / NFR-3）。

命中两类红线：

1. 外置 ``void_tokens[]`` 清单中的数字/串（**数字边界正则**，避免浮点子串误报）；
2. ``semantic_rules[]`` 语义规则（如 ``40%\\s*拜占庭``、Dilithium 性能三元组）。

严重度分级（架构 §4.3）：

* 对外材料（thesis_drafts / 毕设深度研究 / README / PPT）→ ``block``
* 历史快照（archive / backup / 赛前 / 审计 / 核验…）→ ``snapshot``（打标不改写）
* 内部文档（PRD / 架构 / 审计底稿）→ ``info``
* 行内含「排除/应改为/所谓/未使用…」等**声明性上下文**，或命中处前面是
  ``path:line`` **代码行号引用** → 降级 ``info``（不是申报，而是讨论）

退出码：``0`` 无 blocking；``1`` 存在 blocking；``2`` 用法/配置错误。
被 import 时零副作用。
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

sys.path.insert(0, str(Path(__file__).resolve().parent))
import assurance_common as ac  # noqa: E402

logger = ac.get_logger("scan_void_tokens")

SCANNER = "scan_void_tokens"
_COMPANY_MSG = "作废令牌禁止出现在对外/论文材料（NFR-3）；历史文档须打『历史快照』标记"


def _compile_numeric(tok: str) -> re.Pattern:
    """数字边界正则：``(?<![\\w.])<tok>(?![\\w.])``。

    两侧对称排除 ``\\w`` 与 ``.``，避免 ``6026.5`` / ``v6026x`` / ``x6026`` /
    ``6026.`` 等被误报；负号兼容 ASCII ``-`` 与 Unicode 减号 ``−``（U+2212）。
    """
    if tok.startswith("-"):
        body = tok[1:]
        return re.compile(r"(?<![\w.])(?:-|\u2212)?" + re.escape(body) + r"(?![\w.])")
    return re.compile(r"(?<![\w.])" + re.escape(tok) + r"(?![\w.])")


def build_matchers(blacklist: Dict[str, Any]) -> List[Dict[str, Any]]:
    """构建 ``(regex, rule, hint)`` 匹配器列表。"""
    matchers: List[Dict[str, Any]] = []
    for item in blacklist.get("void_tokens", []):
        if isinstance(item, dict):
            tok, kind = item.get("token", ""), item.get("kind", "literal")
        else:
            tok, kind = str(item), "literal"
        if not tok:
            continue
        rx = _compile_numeric(tok) if kind in ("numeric", "percent") else re.compile(re.escape(tok))
        matchers.append({
            "regex": rx, "rule": "void_token", "hint": f"作废令牌 {tok}：{_COMPANY_MSG}",
            "needs_review": bool(item.get("needs_review")) if isinstance(item, dict) else False,
        })
    for r in blacklist.get("semantic_rules", []):
        matchers.append({
            "regex": re.compile(r["pattern"]),
            "rule": "semantic_rule:" + r.get("id", "?"),
            "hint": r.get("hint", ""),
        })
    return matchers


def _is_mention(line: str, markers: List[str]) -> bool:
    return any(mk in line for mk in markers)


def _is_code_line_ref(line: str, start: int, ref_pattern: str) -> bool:
    if not ref_pattern:
        return False
    return bool(re.search(ref_pattern, line[max(0, start - 80):start]))


def scan(root: Path, cfg: Dict[str, Any], blacklist: Dict[str, Any]) -> Dict[str, Any]:
    """扫描 ``root``，返回报告 dict。"""
    matchers = build_matchers(blacklist)
    ctx = blacklist.get("context_markers", {})
    mention = ctx.get("mention", [])
    ref_pat = ctx.get("code_line_ref", "")
    line_ref = re.compile(ctx["code_line_ref_line"]) if ctx.get("code_line_ref_line") else None
    text_ext = [e for e in cfg.get("include_ext", []) if e not in (".pptx", ".pdf")]
    hits: List[Dict[str, Any]] = []
    files_scanned = 0

    for path in ac.iter_files([root], text_ext, cfg.get("exclude_dirs", []), cfg.get("exclude_globs", [])):
        files_scanned += 1
        rel = path.relative_to(root).as_posix() if root in path.parents or root == path.parent else str(path)
        scope = ac.classify_path_scope(rel, cfg)
        default_sev = ac.scope_severity(scope)
        for lineno, line in ac.scan_text_lines(path):
            # 整行是否为代码引用行（含 path.py:123）：整数令牌在此行判为行号引用，非申报
            is_ref_line = bool(line_ref.search(line)) if line_ref else False
            for m in matchers:
                for mm in m["regex"].finditer(line):
                    if _is_mention(line, mention):
                        sev, context = ac.SEV_INFO, "mention"
                    elif _is_code_line_ref(line, mm.start(), ref_pat) or (mm.group(0).isdigit() and is_ref_line):
                        sev, context = ac.SEV_INFO, "code_line_ref"
                    else:
                        sev, context = default_sev, scope
                    hint = m["hint"]
                    # needs_review 令牌（如 40.6）存在可信新测值同数值碰撞：命中需人工确认，
                    # 从 block/snapshot 降级为 warn，且 warn 不影响退出码（仅 block 才 exit 1）。
                    if m.get("needs_review") and sev in (ac.SEV_BLOCK, ac.SEV_SNAPSHOT):
                        sev = ac.SEV_WARN
                        hint += "「此 token 存在可信新测值同数值碰撞（如 +40.6%），命中需人工确认是否为新测值」"
                    hits.append({
                        "file": rel, "line": lineno, "match": mm.group(0),
                        "rule": m["rule"], "severity": sev, "context": context,
                        "snippet": ac.snippet(line, mm.start(), mm.end()),
                        "hint": hint,
                    })

    counts = ac.scanner_severity_counts(hits)
    return {
        "scanner": SCANNER,
        "generated_at": ac.now_iso(),
        "root": ac.rel_to_workspace(root),
        "config_ref": ac.rel_to_workspace(ac.BLACKLIST_PATH),
        "summary": {
            "files_scanned": files_scanned, "hits": len(hits),
            "blocking": counts[ac.SEV_BLOCK],
            "block": counts[ac.SEV_BLOCK], "warn": counts[ac.SEV_WARN],
            "snapshot": counts[ac.SEV_SNAPSHOT], "info": counts[ac.SEV_INFO],
        },
        "hits": hits,
    }


def _resolve_root(root_arg: str, cfg: Dict[str, Any]) -> Path:
    if root_arg:
        p = Path(root_arg)
        return p if p.is_absolute() else (ac.WORKSPACE_ROOT / p)
    return ac.WORKSPACE_ROOT / cfg.get("scan_roots", ["deliverables"])[0]


def build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(description="作废令牌扫描器")
    ap.add_argument("--root", default="", help="扫描根（默认取配置 scan_roots[0]）")
    ap.add_argument("--config", default=str(ac.SCAN_TARGETS_PATH))
    ap.add_argument("--blacklist", default=str(ac.BLACKLIST_PATH))
    ap.add_argument("--overwrite", action="store_true", help="允许覆盖同名报告")
    ap.add_argument("--report", default=str(ac.REPORTS_DIR / "scan_void_tokens_report.json"))
    return ap


def main(argv: Optional[List[str]] = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        cfg = ac.load_scan_targets(args.config)
        blacklist = ac.load_blacklist(args.blacklist)
    except (OSError, json.JSONDecodeError) as exc:
        logger.error("配置读取错误：%s", exc)
        return ac.EXIT_USAGE
    root = _resolve_root(args.root, cfg)
    if not root.exists():
        logger.error("扫描根不存在：%s", root)
        return ac.EXIT_USAGE
    report = scan(root, cfg, blacklist)
    pj = ac.emit_scanner_report(report, args.report, overwrite=args.overwrite)
    s = report["summary"]
    logger.info("命中 %d（blocking=%d, snapshot=%d, info=%d），报告：%s",
                s["hits"], s["blocking"], s["snapshot"], s["info"], ac.rel_to_workspace(pj))
    return ac.EXIT_FAIL if s["blocking"] else ac.EXIT_OK


if __name__ == "__main__":
    sys.exit(main())
