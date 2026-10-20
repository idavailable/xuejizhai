#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""全量校验：索引中的 `Lxxxx` 行号 + 标题，是否与源文件逐行一致

用于 references/25-index-audit.md 的「行号只允许存在于独立 INDEX 文件，且必须由脚本校验」。

用法：
    python3 validate_index.py --index modules/06-book-INDEX.md --src modules/06-book.md
    python3 validate_index.py --index modules/06-book-INDEX.md --src modules/06-book.md --quiet

退出码：0 = 全部一致；1 = 存在不匹配（可接 CI）
"""
import argparse
import re
import sys


def main() -> int:
    ap = argparse.ArgumentParser(description="校验索引行号与源文件一致性")
    ap.add_argument("--index", required=True, help="索引 Markdown 路径")
    ap.add_argument("--src", required=True, help="源文件路径")
    ap.add_argument("--quiet", action="store_true", help="仅输出汇总与不匹配项")
    ap.add_argument("--max-print", type=int, default=40, help="每类最多打印条数（默认 40）")
    args = ap.parse_args()

    with open(args.src, encoding="utf-8") as f:
        src_lines = f.readlines()
    with open(args.index, encoding="utf-8") as f:
        idx = f.read()

    # 1) 篇目条目：- `L1234` 标题
    pat = re.compile(r"- `L(\d+)` (.+)")
    mismatch, checked = [], 0
    for m in pat.finditer(idx):
        ln, title = int(m.group(1)), m.group(2).strip()
        checked += 1
        if ln < 1 or ln > len(src_lines):
            mismatch.append((ln, title, "<行号越界>"))
            continue
        actual = src_lines[ln - 1].strip()
        if not actual.startswith("#"):
            mismatch.append((ln, title, f"非标题行: {actual[:30]}"))
            continue
        actual_title = actual.lstrip("#").strip()
        if actual_title != title:
            mismatch.append((ln, title, f"标题不一致: {actual_title[:30]}"))

    print(f"篇目条目总数: {checked}")
    print(f"不匹配: {len(mismatch)}")
    for ln, t, reason in mismatch[:args.max_print]:
        print(f"  L{ln} [{t}] -> {reason}")

    # 2) 卷表行号：| 卷名 | L1234 |
    vol_pat = re.compile(r"\| ([^|]+) \| L(\d+) \|")
    vol_mismatch = []
    for m in vol_pat.finditer(idx):
        vname, ln = m.group(1).strip(), int(m.group(2))
        if "主要篇目" in vname or "行号" in vname or "卷" not in vname:
            continue
        if ln < 1 or ln > len(src_lines):
            vol_mismatch.append((ln, vname, "<越界>"))
            continue
        actual = src_lines[ln - 1].strip()
        if not actual.startswith("#"):
            vol_mismatch.append((ln, vname, f"非标题行: {actual[:30]}"))
            continue
        actual_title = actual.lstrip("#").strip()
        if actual_title != vname:
            vol_mismatch.append((ln, vname, f"不一致: {actual_title[:40]}"))

    print(f"卷条目不匹配: {len(vol_mismatch)}")
    for ln, t, reason in vol_mismatch[:args.max_print]:
        print(f"  L{ln} [{t}] -> {reason}")

    return 1 if (mismatch or vol_mismatch) else 0


if __name__ == "__main__":
    sys.exit(main())
