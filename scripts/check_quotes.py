#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""引文核验：检查 skill 里所有「」引文是否真实存在于语料文件

用途：防止蒸馏过程中"记忆漂移"导致的改字、改标点、臆补缺字。
本项目实战中，此脚本抓出过三类错：
  1. 标点从俗（原文句号密断被改成逗号）  -> 由"去标点比对"查出
  2. 用字错（凿空妄谭 -> 妄谈）          -> 由"原始比对"查出
  3. 臆补缺字（红炉炼 被补成 红炉煅炼）  -> 由"原始比对"查出

用法：
    python3 check_quotes.py
    python3 check_quotes.py --docs cases references/02-decision-heuristics.md
    python3 check_quotes.py --corpus modules/01-yuyicao.md modules/02-yimen-falu.md
    python3 check_quotes.py --min-len 10 --quiet

退出码：0 = 实质引文全部命中；1 = 有未命中（CI 可拦）
"""
import argparse
import glob
import os
import re
import sys

PUNCT = re.compile(r"[。，；：！？、\s…\uff0e·]")
QUOTE = re.compile(r"「([^」]{4,})」")
# 这些章节里的是"反例／模板／格式占位"，本就不是原文引用，跳过
EXEMPT_HEAD = re.compile(r"❌|⛔|不会说|绝不会|反例|模板|错误说法|格式|示范|认可|话术|拟作|易错|诚实标注|示例")
PLACEHOLDER = re.compile(r"[XxNn]|[／+]")


def norm(s: str) -> str:
    """去标点与空白，用于过滤'仅标点不同'的差异。"""
    return PUNCT.sub("", s)


def main() -> int:
    ap = argparse.ArgumentParser(description="核验「」引文是否真实存在于语料")
    ap.add_argument("--docs", nargs="*", help="待检查文件/目录（默认 cases/ references/ SKILL.md）")
    ap.add_argument("--corpus", nargs="*",
                    default=["modules/01-yuyicao.md", "modules/02-yimen-falu.md",
                             "modules/03-shanglun-pian.md"],
                    help="语料文件")
    ap.add_argument("--min-len", type=int, default=8,
                    help="硬性核验门槛：短于此长度的引文只作提示、不影响退出码（默认 8）")
    ap.add_argument("--short-len", type=int, default=4,
                    help="彻底忽略短于此长度的引号内容，视为标签（默认 4）")
    ap.add_argument("--quiet", action="store_true", help="只输出汇总与未命中项")
    args = ap.parse_args()

    corpus_paths = [p for p in args.corpus if os.path.exists(p)]
    if not corpus_paths:
        print("未找到语料文件，无法核验", file=sys.stderr)
        return 2
    raws, norms = [], []
    for p in corpus_paths:
        with open(p, encoding="utf-8") as f:
            t = f.read()
        raws.append(t)
        norms.append(norm(t))
    raw, normed = "\n".join(raws), "\n".join(norms)

    if args.docs:
        docs = []
        for d in args.docs:
            docs.extend(sorted(glob.glob(os.path.join(d, "*.md"))) if os.path.isdir(d) else [d])
    else:
        docs = sorted(glob.glob("cases/*.md")) + sorted(glob.glob("references/*.md"))
        if os.path.exists("SKILL.md"):
            docs.append("SKILL.md")

    exact = loose = total = 0
    short_total = short_ok = 0
    only_punct, missing, short_missing = [], [], []
    for doc in docs:
        if not os.path.exists(doc):
            continue
        with open(doc, encoding="utf-8") as f:
            lines = f.read().split("\n")
        head = ""
        for line in lines:
            if line.startswith("#"):
                head = line
                continue
            if EXEMPT_HEAD.search(head) or line.lstrip().startswith(("- ❌", "❌", "| 「您好")):
                continue
            if "❌" in line or "⛔" in line:
                continue
            for q in QUOTE.findall(line):
                q = re.sub(r"[…\uff0e]{1,}.*$", "", q).replace("**", "").strip()
                if PLACEHOLDER.search(q) or re.search(r"[-—>→/]", q):
                    continue          # 占位符、并列选项、标签串（如 证-机-方-效）
                n = len(norm(q))
                if n < args.short_len:
                    continue          # 太短，判不了是引文还是标签
                found = q in raw or norm(q) in normed
                if n < args.min_len:
                    # 短引文：仅提示，不计入失败。术语型短引文最容易改字，值得人看一眼
                    short_total += 1
                    if found:
                        short_ok += 1
                    else:
                        short_missing.append((doc, q))
                    continue
                total += 1
                if q in raw:
                    exact += 1
                elif norm(q) in normed:
                    loose += 1
                    only_punct.append((doc, q[:36]))
                else:
                    missing.append((doc, q[:36]))

    if not args.quiet:
        print(f"语料: {', '.join(corpus_paths)}")
        print(f"引文总数: {total}")
        print(f"  OK 字面完全一致: {exact}")
        print(f"  ~  仅标点不同  : {loose}")
        print(f"  X  字句不符    : {len(missing)}")

    if only_punct and not args.quiet:
        print("\n仅标点差异（文首已声明「标点从俗」则属预期）：")
        for doc, q in only_punct[:8]:
            print(f"  {os.path.basename(doc)}: 「{q}...」")

    if short_missing and not args.quiet:
        print(f"\n短引文待核（{args.short_len}–{args.min_len - 1} 字，仅提示不判错；多为术语／标签）：")
        for doc, q in short_missing[:12]:
            print(f"  ?  {os.path.basename(doc)}: 「{q}」")
        if len(short_missing) > 12:
            print(f"  ... 另 {len(short_missing) - 12} 条")

    if missing:
        print("\n字句不符（需回原文核对：可能改字／脱字／臆补）：")
        for doc, q in missing:
            print(f"  {os.path.basename(doc)}: 「{q}...」")
        return 1

    if args.quiet:
        print(f"引文核验: {total} 条，字面一致 {exact}，仅标点 {loose}，不符 0  [PASS]")
        print(f"短引文: {short_ok}/{short_total} 命中，待核 {len(short_missing)}")
    elif short_total:
        print(f"\n短引文: {short_ok}/{short_total} 命中，待核 {len(short_missing)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
