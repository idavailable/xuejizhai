#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""由 titles.json 生成原文全文检索索引（Markdown，含书目总览 / 关键词速查 / 逐书篇目）

配合 extract_titles.py 使用；产出物即 references/20 要求的「独立 INDEX 文件」。

用法：
    # 通用（无预设：书名/卷名原样使用，不生成关键词速查表）
    python3 gen_index.py --titles titles.json --src modules/06-book.md --out modules/06-book-INDEX.md

    # 带预设（黄元御医书十一种示例，见 scripts/presets/huangyuanyu.json）
    python3 gen_index.py --titles titles.json --out modules/06-yishu-11zhong-INDEX.md \
        --config scripts/presets/huangyuanyu.json

参数：
    --titles    必填，extract_titles.py 产出的 JSON
    --out       必填，输出索引 Markdown 路径
    --src       可选，原文路径（用于统计总行数与文件大小）
    --config    可选，JSON 预设。可含字段：
                  index_title   索引大标题
                  source_name   源文件在 skill 内的相对路径（写进索引头部）
                  total_lines   原文总行数（缺省则从 --src 统计）
                  book_display  {原文书名: 正名}
                  vol_display   {原文卷名: 正名}
                  books_meta    {正名: 内容提要}
                  keywords      [[关键词, 定位], ...]
                  notes         勘误与排版说明（字符串）

设计说明：
    原版把 TOTAL_LINES / BOOK_DISPLAY / VOL_DISPLAY / books_meta / 48 条 keyword_map
    全部硬编码在脚本里，只能产黄元御一本书的索引。此版把「人物/书专属数据」移入
    预设 JSON，脚本本体与书目无关。
"""
import argparse
import json
import os
import sys


def main() -> int:
    ap = argparse.ArgumentParser(description="生成原文全文检索索引")
    ap.add_argument("--titles", required=True, help="extract_titles.py 产出的 JSON")
    ap.add_argument("--out", required=True, help="输出索引 Markdown 路径")
    ap.add_argument("--src", default=None, help="原文路径（统计行数/体积）")
    ap.add_argument("--config", default=None, help="JSON 预设（书名映射/提要/关键词）")
    args = ap.parse_args()

    with open(args.titles, encoding="utf-8") as f:
        data = json.load(f)
    books_raw, vols_raw, secs = data["books"], data["vols"], data["secs"]

    cfg = {}
    if args.config:
        with open(args.config, encoding="utf-8") as f:
            cfg = json.load(f)

    index_title = cfg.get("index_title", "原文全文检索索引")
    source_name = cfg.get("source_name", os.path.basename(args.src or "原文.md"))
    BOOK_DISPLAY = cfg.get("book_display", {})
    VOL_DISPLAY = cfg.get("vol_display", {})
    books_meta = cfg.get("books_meta", {})
    keyword_map = [tuple(k) for k in cfg.get("keywords", [])]

    # 总行数：配置 > 源文件 > 标题最大行号 + 余量
    TOTAL_LINES = cfg.get("total_lines")
    src_lines = 0
    if args.src and os.path.exists(args.src):
        with open(args.src, encoding="utf-8") as f:
            src_lines = sum(1 for _ in f)
        TOTAL_LINES = TOTAL_LINES or src_lines
        size_mb = os.path.getsize(args.src) / 1024 / 1024
    else:
        size_mb = 0
    if not TOTAL_LINES:
        all_ln = [ln for ln, _ in books_raw + vols_raw + secs]
        TOTAL_LINES = (max(all_ln) + 100) if all_ln else 0

    # 书级列表（附录标题由 extract_titles 的 --appendix 处理，此处不再特判）
    book_list = list(books_raw)

    book_bounds = []
    for i, (ln, name) in enumerate(book_list):
        end = book_list[i + 1][0] - 1 if i + 1 < len(book_list) else TOTAL_LINES
        book_bounds.append((ln, name, end))

    # 卷归属书 + 卷名正名
    book_of_vol = {}
    for vln, vname in vols_raw:
        owner = None
        for bln, bname, bend in book_bounds:
            if bln <= vln <= bend:
                owner = bname
                break
        if owner is None:
            continue
        vname = VOL_DISPLAY.get(vname, vname)
        book_of_vol.setdefault(owner, []).append((vln, vname))

    # 卷内去重：同名卷只留行号最小者（防页眉残留）
    for bname in book_of_vol:
        seen = {}
        for vln, vname in book_of_vol[bname]:
            seen.setdefault(vname, vln)
        book_of_vol[bname] = [(vln, vname) for vname, vln in seen.items()]

    vol_bounds = {}
    for bname, vlist in book_of_vol.items():
        bend = next(e for b, n, e in book_bounds if n == bname)
        vlist_sorted = sorted(vlist)
        for i, (vln, vname) in enumerate(vlist_sorted):
            vend = vlist_sorted[i + 1][0] - 1 if i + 1 < len(vlist_sorted) else bend
            vol_bounds[vname] = (vln, vend)

    def locate_owner(ln):
        for bln, bname, bend in book_bounds:
            if bln <= ln <= bend:
                for vln, vn in book_of_vol.get(bname, []):
                    vs, ve = vol_bounds[vn]
                    if vs <= ln <= ve:
                        return bname, vn
                return bname, None
        return None, None

    secs_by_book = {}
    for sln, stitle in secs:
        bname, vname = locate_owner(sln)
        if bname is None:
            continue
        secs_by_book.setdefault(bname, []).append((sln, stitle, vname))

    # 篇目去重（同书同标题只留最小行号，剔除目录复述）
    for bname in secs_by_book:
        seen = {}
        for sln, stitle, vname in secs_by_book[bname]:
            seen.setdefault(stitle, (sln, stitle, vname))
        secs_by_book[bname] = sorted(seen.values())

    lines = []
    A = lines.append

    A(f"# {index_title}")
    A("")
    vol_note = f"共 {TOTAL_LINES} 行" + (f" / {size_mb:.1f}MB" if size_mb >= 0.1 else "")
    A(f"> **源文件**：`{source_name}`（{vol_note}）")
    A("> **用途**：AI 检索路由表。检索任何著作、篇目、病症、方剂、药物时，**先在本索引中定位行号**，再打开源文件读取原文。")
    A("")
    A("## 使用说明（AI 检索三步法）")
    A("")
    A("1. **定位**：在本索引搜索关键词（书名 / 篇名 / 病症 / 方名 / 药名），得到目标行号 `Lxxxx`")
    A(f"2. **读取**：`file_read {source_name}`，`offset = Lxxxx - 5`，`limit = 80`（以上下文 5 行为起点，可容忍 ±2 行偏差）")
    A("3. **溯源**：引用原文时保留行号出处，方便复核")
    A("")
    A("⚠️ 本文件只做定位，不收录原文。原文一律读源文件。")
    A("")

    # ── 书目总览 ──
    A(f"## 书目总览（{len(book_bounds)} 部）")
    A("")
    A("| # | 书名 | 起始行 | 结束行 | 卷数 | 内容提要 |")
    A("|---|------|--------|--------|------|----------|")
    for i, (bln, bname, bend) in enumerate(book_bounds, 1):
        nvol = len(book_of_vol.get(bname, []))
        shown = BOOK_DISPLAY.get(bname, bname)
        meta = books_meta.get(shown, "")
        A(f"| {i} | **{shown}** | {bln} | {bend} | {nvol} 卷 | {meta} |")
    A("")
    notes = cfg.get("notes")
    if notes:
        A(f"> **勘误与排版说明**：{notes}")
        A("")

    # ── 关键词速查 ──
    if keyword_map:
        A("## 关键词速查")
        A("")
        A("| 关键词 | 定位 |")
        A("|--------|------|")
        for kw, loc in keyword_map:
            A(f"| {kw} | {loc} |")
        A("")
        A("> 更多词条：直接检索下方「逐书篇目索引」中对应书的篇目名。")
        A("")

    # ── 逐书篇目索引 ──
    A("## 逐书篇目索引")
    A("")
    for i, (bln, bname, bend) in enumerate(book_bounds, 1):
        shown = BOOK_DISPLAY.get(bname, bname)
        A(f"### {i}. {shown}（L{bln}–L{bend}）")
        A("")
        vols = book_of_vol.get(bname, [])
        secs_this = secs_by_book.get(bname, [])
        if vols:
            A("| 卷 | 行号 | 主要篇目 |")
            A("|-----|------|----------|")
            for vln, vname in vols:
                vsecs = [s for s in secs_this if s[2] == vname]
                if vsecs:
                    first = vsecs[0][1]
                    rest = "、".join(s[1] for s in vsecs[1:6])
                    more = f" 等{len(vsecs)}篇" if len(vsecs) > 6 else ""
                    A(f"| {vname} | L{vln} | {first}；{rest}{more} |")
                else:
                    A(f"| {vname} | L{vln} | — |")
            A("")
        A(f"**完整篇目（{len(secs_this)}条）**：")
        A("")
        for sln, stitle, _ in secs_this:
            A(f"- `L{sln}` {stitle}")
        A("")

    A("---")
    A("生成说明：本索引由脚本自动提取源文件标题生成（含二~四级标题，去重页眉/目录复述），行号与源文件一一对应。")
    A("生成命令：`python3 scripts/extract_titles.py ... && python3 scripts/gen_index.py ...`")

    os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
    with open(args.out, "w", encoding="utf-8", newline="\n") as f:
        f.write("\n".join(lines))

    print(f"生成完成: {args.out}")
    print(f"书目: {len(book_bounds)} 部 / 总行数: {TOTAL_LINES} / 索引行数: {len(lines)}")
    print(f"文件大小: {os.path.getsize(args.out)/1024:.1f} KB")
    return 0


if __name__ == "__main__":
    sys.exit(main())
