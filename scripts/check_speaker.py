#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""说话人归属审计：查「把别人的话当成传主的话」这类错误

为什么需要这个脚本
------------------
`check_quotes.py` 只能验证「这句话在不在原文里」，验不了「这句话是谁说的」。
本项目实战中真出过两类归属错误：

  1. 金道宾案「不识可治与否」是**病家**问话（下接「予曰。可治。」），
     却被写成喻嘉言自认不确定。
  2. 《寓意草》每案后有胡卣臣评语，评语里也常引喻氏语或另出议论；
     一旦摘进 skill 而不标说话人，读者会当成喻嘉言原话。

本脚本专查第 2 类（可自动化的那类）：某条引文只出现在「胡卣臣先生曰」
之后的评语窗口内，却被当作喻语引用。

关键结构事实（本项目实测，49 案）
-------------------------------
评语位置**不固定**：39 案在案末，10 案在**案中**——评语之后还接着门人问答
或下一个子案（如袁仲卿案评语在第 768 字、全案 2769 字）。
所以「见评语即判案终」是错的，窗口必须按内容边界收，不能按案末收。

用法
----
    python3 check_speaker.py
    python3 check_speaker.py --docs cases references SKILL.md
    python3 check_speaker.py --window 150 --verbose

退出码：0 = 未发现评语误引；1 = 有疑似（需人工确认）
"""
import argparse
import glob
import os
import re
import sys

PUNCT = re.compile(r"[。，；：！？、\s…\uff0e·]")
QUOTE = re.compile(r"「([^」]{8,})」")
CASE_SPLIT = re.compile(r"(?m)^## ")
# 评语结束标志：遇到这些词说明已回到喻氏本人说话
STOP = re.compile(r"门人问|门人曰|门人请|答曰|余曰|予曰|问曰")
MARK = "胡卣臣先生曰"
# 已核实的误报：评语本身很短，窗口却把紧接其后的下一篇子案标题一并吞入。
# 命中这些前缀的引文只提示、不计入失败；新增条目必须写明核实理由。
ALLOW = {
    "此痘热尚未退":
        "胡卣臣评语仅『辨症用药。通于神明。究莫测其涯』二十余字，其后紧接子案标题"
        "『直叙顾明二郎三郎布痘为宵小所误』，窗口吞并下一篇所致；该语为喻氏『明告曰』原话。",
}


def norm(s: str) -> str:
    return PUNCT.sub("", s)


def load_comment_windows(corpus_path: str, window: int, verbose: bool):
    """返回 (评语窗口合并文本, 案数统计)。窗口按 STOP 词或硬上限收边。"""
    if not os.path.exists(corpus_path):
        print(f"未找到语料 {corpus_path}", file=sys.stderr)
        return "", (0, 0)
    with open(corpus_path, encoding="utf-8") as f:
        text = f.read()
    cases = CASE_SPLIT.split(text)[1:]
    blocks, mid, end = [], 0, 0
    for c in cases:
        i = c.find(MARK)
        if i < 0:
            continue
        m = STOP.search(c, i + len(MARK))
        stop = m.start() if m else len(c)
        stop = min(stop, i + window)
        blocks.append(c[i:stop])
        # 评语之后若还有大段正文，记为「案中」
        if len(c) - stop > 200:
            mid += 1
        else:
            end += 1
    if verbose:
        print(f"评语窗口: {len(blocks)} 段（案末 {end} / 案中 {mid}）")
    return "\n".join(blocks), (mid, end)


def collect_docs(args):
    if args.docs:
        out = []
        for d in args.docs:
            if os.path.isdir(d):
                out.extend(sorted(glob.glob(os.path.join(d, "*.md"))))
            elif os.path.exists(d):
                out.append(d)
        return out
    out = sorted(glob.glob("cases/*.md")) + sorted(glob.glob("references/*.md"))
    if os.path.exists("SKILL.md"):
        out.append("SKILL.md")
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description="审计引文的说话人归属（评语／病家语 vs 传主语）")
    ap.add_argument("--corpus", default="modules/01-yuyicao.md",
                    help="含胡卣臣评语的语料（默认 modules/01-yuyicao.md）")
    ap.add_argument("--docs", nargs="*", help="待检查文件/目录（默认 cases/ references/ SKILL.md）")
    ap.add_argument("--window", type=int, default=150,
                    help="评语窗口硬上限，防吞进下一子案（默认 150 字）")
    ap.add_argument("-v", "--verbose", action="store_true", help="输出窗口与受检统计")
    args = ap.parse_args()

    pin_raw, (mid, end) = load_comment_windows(args.corpus, args.window, args.verbose)
    if not pin_raw:
        print("没有评语窗口可查", file=sys.stderr)
        return 2
    pin = norm(pin_raw)

    suspects, checked = [], 0
    allowed = []
    for doc in collect_docs(args):
        with open(doc, encoding="utf-8") as f:
            lines = f.read().split("\n")
        for ln, line in enumerate(lines, 1):
            # 显式标了说话人的行跳过
            if line.startswith("#") or "胡卣臣" in line or "评语" in line:
                continue
            for q in QUOTE.findall(line):
                q = re.sub(r"[…\uff0e]{1,}.*$", "", q).replace("**", "").strip()
                n = norm(q)
                if len(n) < 8:
                    continue
                checked += 1
                if n in pin:
                    hit = next((k for k in ALLOW if q.startswith(k)), None)
                    if hit:
                        allowed.append((doc, ln, q[:38], ALLOW[hit]))
                    else:
                        suspects.append((doc, ln, q[:38]))

    if args.verbose:
        print(f"受检引文: {checked} 条")
    if allowed and args.verbose:
        print(f"\n已登记的误报（{len(allowed)} 条，不计入失败）：")
        for doc, ln, q, why in allowed:
            print(f"  i  {os.path.basename(doc)}:{ln}  「{q}…」")
            print(f"     理由：{why}")

    if suspects:
        print(f"\n疑似把胡卣臣评语当传主语（{len(suspects)} 条，需人工确认）：")
        for doc, ln, q in suspects:
            print(f"  ?  {os.path.basename(doc)}:{ln}  「{q}…」")
        print("\n处理：评语位置不固定（案末 %d / 案中 %d），摘引时须标明「胡卣臣评」。"
              % (end, mid))
        return 1
    print(f"说话人归属: 受检 {checked} 条，评语误引 0（另有 {len(allowed)} 条已登记误报）  [PASS]")
    return 0


if __name__ == "__main__":
    sys.exit(main())
