#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""提取原文 Markdown 的标题结构（书级 / 卷级 / 篇目级）→ JSON

用于 references/20-original-text-digitalization.md 的行号索引体系第一步。

用法：
    python3 extract_titles.py --src modules/06-yishu-11zhong.md --out titles.json
    python3 extract_titles.py --src book.md --out book.json \
        --vol-special "四圣心源卷二·六气解" --appendix "校余偶识"

参数：
    --src          必填，原文 Markdown 路径
    --out          可选，输出 JSON（默认 titles.json）
    --vol-special  可选可重复：本身是 ### 层级、但语义上属于「卷」的标题。
                   默认空（只按标题中含"卷"字判定卷级）
    --appendix     可选可重复：卷末附录标题，强制降为篇目级
    --quiet        只输出统计，不打印卷级清单

设计说明：
    原版把 SRC 与两条黄元御专属规则（VOL_SPECIAL / 校余偶识）硬编码在文件里，
    换一本书就崩。此版全部外置为参数，默认行为对任意结构规整的原文可用。
"""
import argparse
import json
import re
import sys

NOISE_PUNCT = re.compile(r"[。，；？！、]")
VOL_NUM = "一二三四五六七八九十百"
H1_RE = re.compile(r"^# (?!#)(.+)$")
SEC_RE = re.compile(r"^#{2,4} (.+)$")


def is_noise(title: str, h1_titles: set) -> bool:
    """过滤 OCR 噪音标题（页眉 / 书末笔画索引 / 纯页码 / 乱码残片）。"""
    t = title.strip()
    # 「一、元气亏损内伤外感等症」这类带序号的标题含顿号，不能被 NOISE_PUNCT 误杀
    if re.match(r"^[一二三四五六七八九十]+、", t):
        return False
    # 带［］【】的篇题即使很长也是真标题（如「太阳经上篇［凡风伤卫之证，列于此篇，法五十三条］」）
    if re.search(r"[［\[【].{0,60}[］\]】]", t):
        return False
    if len(t) > 30:
        return True
    if NOISE_PUNCT.search(t):
        return True
    if len(t) > 12 and re.search(r"[者也矣焉耳]$", t):
        return True
    if t in h1_titles:                                   # 页眉：标题 == 书/卷名
        return True
    if re.match(r"^[一二三四五六七八九十百]+划$", t):     # 书末笔画索引
        return True
    if re.match(r"^第?\d+页?$", t):                       # 纯页码
        return True
    if t.startswith("·"):                                # 页眉残片
        return True
    if re.search(r"[A-Za-z]", t):                        # OCR 乱码（含拉丁字母）
        return True
    return False


def main() -> int:
    ap = argparse.ArgumentParser(description="提取原文 Markdown 标题结构")
    ap.add_argument("--src", required=True, help="原文 Markdown 路径")
    ap.add_argument("--out", default="titles.json", help="输出 JSON（默认 titles.json）")
    ap.add_argument("--vol-special", action="append", default=[],
                    help="以 ### 层级出现的真实卷标题（可重复）")
    ap.add_argument("--appendix", action="append", default=[],
                    help="卷末附录标题，强制归篇目级（可重复）")
    ap.add_argument("--quiet", action="store_true", help="不打印卷级清单")
    args = ap.parse_args()

    vol_special = set(args.vol_special)
    appendix = set(args.appendix)

    # 第一遍：收集一级标题，用于页眉过滤
    h1_titles = set()
    with open(args.src, encoding="utf-8") as f:
        for line in f:
            m = H1_RE.match(line.rstrip("\n"))
            if m:
                h1_titles.add(m.group(1).strip())

    books, vols, secs = [], [], []
    with open(args.src, encoding="utf-8") as f:
        for lineno, line in enumerate(f, 1):
            line = line.rstrip("\n")
            if not line.strip():
                continue
            m = H1_RE.match(line)
            if m:
                title = m.group(1).strip()
                if title in appendix:
                    secs.append((lineno, title))
                elif "卷" in title:
                    vols.append((lineno, title))
                else:
                    books.append((lineno, title))
                continue
            m = SEC_RE.match(line)
            if m:
                title = m.group(1).strip()
                # 卷级：显式指定，或标题形如「XX卷三」（章节名极少含"卷N"）
                if title in vol_special or re.search(rf"卷[{VOL_NUM}]+", title):
                    vols.append((lineno, title))
                    continue
                if is_noise(title, h1_titles):
                    continue
                secs.append((lineno, title))

    print(f"书级标题: {len(books)}")
    print(f"卷级标题(含 ###/#### 层级): {len(vols)}")
    print(f"篇目级标题(过滤后): {len(secs)}")

    with open(args.out, "w", encoding="utf-8") as f:
        json.dump({"books": books, "vols": vols, "secs": secs},
                  f, ensure_ascii=False, indent=1)
    print(f"已写出: {args.out}")

    if not args.quiet:
        print("\n=== 卷级标题 ===")
        for ln, t in vols:
            print(f"  L{ln}: {t}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
