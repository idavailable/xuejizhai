#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""引文压缩审计：查“截短后意思变了”

为什么需要第四个检查
--------------------
check_quotes 验字句（有没有改字）、check_speaker 验说话人（谁说的），
两道都过了，仍可能失真：把「若阳证忽变阴厥者，万中无一」截成
「阳证忽变阴厥万中无一」，丢掉「若…者」这个假设框架——字字都在原文里，
命题却从“假设条件下极罕见”变成了“断言不存在”。

机器判不出“意思变没变”，但判得出“哪里被截了”。本脚本只读不写，
把每条引文放回原文，列出它的**前文／后文／丢掉的前缀／丢掉的后缀**，
截掉的东西一眼可见。

本项目实战中它查出过：
  - 《医门法律》「仍用逆流挽舟之法」与《寓意草》「急流挽舟」并存，
    推翻了我此前"逆流挽舟是后世通称"的错误标注（单书阶段的结论在扩书后变质）。

分类
----
  [全] 起于句首、止于句末        -> 无截断
  [省] 作者标了省略号            -> 有意截短
  [截] 其余                      -> 须人看

注意：电子本几乎每数字一「。」断句，《尚论篇》更是几乎不分句，
所以「句界」只是形式标记，**不等于语义完整**。真正要看的是丢掉部分。

用法
----
    python3 audit_truncation.py                      # 汇总 + 高风险
    python3 audit_truncation.py --md 核对表.md        # 出完整核对表
    python3 audit_truncation.py --hot                # 只看丢了否定/条件词的
"""
import argparse
import glob
import os
import re
import sys

PUNCT = re.compile(r"[。，；：！？、\s…\uff0e·]")
QUOTE = re.compile(r"「([^」]{4,})」")
SENT_END = "。！？；"
NEG = set("不无未非勿莫弗毋")
COND = set("若如但虽惟苟或使假傥")
CORPUS = ["modules/01-yuyicao.md", "modules/02-yimen-falu.md", "modules/03-shanglun-pian.md"]


def build_index(raw: str):
    chars, idx = [], []
    for i, ch in enumerate(raw):
        if PUNCT.match(ch):
            continue
        chars.append(ch)
        idx.append(i)
    return "".join(chars), idx


def back_to_bound(raw: str, pos: int) -> int:
    """从 pos 向前找句界／换行，返回丢掉的片段起点"""
    ls = pos
    while ls > 0 and raw[ls - 1] not in SENT_END and raw[ls - 1] != "\n":
        ls -= 1
    return ls


def main() -> int:
    ap = argparse.ArgumentParser(description="引文压缩审计（只读，不改文件）")
    ap.add_argument("--md", help="输出核对表的 markdown 路径")
    ap.add_argument("--docs", nargs="*", help="待查文件/目录，默认 cases references SKILL.md")
    ap.add_argument("--ctx", type=int, default=14, help="前文/后文各取多少字（默认 14）")
    ap.add_argument("--hot", action="store_true", help="只列丢了否定／条件词的")
    args = ap.parse_args()

    raw = "\n".join(open(p, encoding="utf-8").read() for p in CORPUS if os.path.exists(p))
    if not raw:
        print("未找到语料", file=sys.stderr)
        return 2
    sn, idx = build_index(raw)

    docs = args.docs or (sorted(glob.glob("cases/*.md")) + sorted(glob.glob("references/*.md"))
                         + (["SKILL.md"] if os.path.exists("SKILL.md") else []))
    flat = []
    for d in docs:
        flat.extend(sorted(glob.glob(os.path.join(d, "*.md"))) if os.path.isdir(d) else [d])

    rows, miss = [], []
    counts = {"全": 0, "省": 0, "截": 0}
    for d in flat:
        if not os.path.exists(d):
            continue
        for ln, line in enumerate(open(d, encoding="utf-8").read().split("\n"), 1):
            if line.startswith("#") or "胡卣臣" in line:
                continue
            for m in QUOTE.finditer(line):
                q = m.group(1)
                marked = "…" in q or "\uff0e" in q
                qn = PUNCT.sub("", re.split(r"[…\uff0e]{1,}", q.replace("**", ""))[0])
                if len(qn) < 4:
                    continue
                p = sn.find(qn)
                if p < 0:
                    miss.append((d, ln, q[:24]))
                    continue
                s, e = idx[p], idx[p + len(qn) - 1]
                head_ok = s == 0 or raw[s - 1] in SENT_END + "\n"
                tail_ok = e + 1 >= len(raw) or raw[e + 1] in SENT_END
                kind = "全" if (head_ok and tail_ok) else ("省" if marked else "截")
                counts[kind] += 1

                ls = back_to_bound(raw, s)
                drop_pre = re.sub(r"\s+", "", raw[ls:s])
                le = e + 1
                while le < len(raw) and raw[le] not in SENT_END and raw[le] != "\n":
                    le += 1
                drop_post = re.sub(r"\s+", "", raw[e + 1:le])
                flags = []
                if any(c in NEG for c in drop_pre):
                    flags.append("前丢否定")
                if any(c in COND for c in drop_pre):
                    flags.append("前丢条件")
                if any(c in NEG for c in drop_post):
                    flags.append("后丢否定")
                if any(c in COND for c in drop_post):
                    flags.append("后丢条件")

                rows.append(dict(doc=d, ln=ln, q=q, kind=kind,
                                 pre=re.sub(r"\s+", " ", raw[max(0, s - args.ctx):s]),
                                 post=re.sub(r"\s+", " ", raw[e + 1:e + 1 + args.ctx]),
                                 drop_pre=drop_pre[:60], drop_post=drop_post[:60],
                                 flags=",".join(flags)))

    total = sum(counts.values())
    print(f"引文总数 {total}    [全] {counts['全']}  [省] {counts['省']}  [截] {counts['截']}")
    if miss:
        print(f"⚠ 未定位 {len(miss)} 条（多为标签／粗体／模板，check_quotes 另管）：")
        for d, ln, q in miss[:5]:
            print(f"    {os.path.basename(d)}:{ln} 「{q}」")

    hot = [r for r in rows if r["flags"] and len(r["drop_pre"]) + len(r["drop_post"]) < 120]
    if hot:
        print(f"\n=== 丢掉了否定／条件词（{len(hot)} 条，逐条看是否改变命题）===")
        for r in hot[:40]:
            print(f"\n{os.path.basename(r['doc'])}:{r['ln']}  [{r['flags']}]")
            print(f"  引文：{r['q'][:56]}")
            print(f"  前丢：{r['drop_pre'] or '—'}   后丢：{r['drop_post'] or '—'}")
        if len(hot) > 40:
            print(f"\n… 另 {len(hot) - 40} 条，见核对表")
    else:
        print("\n未发现丢掉否定／条件词的截断。")

    if args.md:
        with open(args.md, "w", encoding="utf-8") as f:
            f.write("# 引文压缩核对表\n\n")
            f.write(f"共 {total} 条：句界完整 {counts['全']}、已标省略 {counts['省']}、"
                    f"句中截断 {counts['截']}。\n\n")
            f.write("**判读法**：只看「前丢／后丢」两栏。若被丢掉的是条件（若…者）、"
                    "转折（但／然／虽）、否定（不／无／未必），这条引文可能已失真，须补全或加省略号。\n\n")
            f.write("> 电子本几乎每数字一「。」断句，《尚论篇》更几乎不分句，"
                    "故「句界」只是形式标记，不等于语义完整。\n\n")
            f.write("| # | 位置 | 类 | 引文 | 前丢 | 后丢 |\n|--:|---|:--:|---|---|---|\n")
            for i, r in enumerate(rows, 1):
                if r["kind"] == "全":
                    continue
                f.write(f"| {i} | {os.path.basename(r['doc'])}:{r['ln']} | {r['kind']} | "
                        f"{r['q'][:60]} | {r['drop_pre'][:24]} | {r['drop_post'][:24]} |\n")
        print(f"\n核对表已写 {args.md}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
