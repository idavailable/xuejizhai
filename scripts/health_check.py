#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""蒸馏器自身健康检查（把 SKILL.md 里「注册前必检」的条款变成可执行断言）

实现 6 项检查，任一失败退出码 1，可直接接 CI：

  1. 版本一致性   SKILL.md frontmatter / README 徽章 / CHANGELOG 首条 / index.html 四处的版本号必须相同（S16）
  2. 死链         SKILL.md 引用的 references/ 文件必须真实存在（产出模板文件除外）（B5 必检）
  3. 孤儿文件     references/ 下每个文件都必须被 SKILL.md 提及，防「写了没人用」（S12）
  4. 近似重复     任意两份 md 的行集相似度 > 阈值即报警，防同文档两版本并存（G3）
  5. 编码卫生     U+FFFD 替换符残留（白名单见 --allow-fffd）（S15）
  6. 行号残留     SKILL.md 正文直写行号（`详见第N行` / `L1234`），只允许存在于 INDEX 文件（V3.6）

用法：
    python3 scripts/health_check.py
    python3 scripts/health_check.py --root . --dup-threshold 0.85
    python3 scripts/health_check.py --quiet          # 只输出失败项
"""
import argparse
import os
import re
import sys
from collections import defaultdict

# 蒸馏「产出 skill」时才存在的文件，框架侧不应存在，不算死链
TEMPLATE_PATHS = {
    "references/01-core-philosophy.md", "references/02-decision-heuristics.md",
    "references/03-expression-dna.md", "references/04-antipatterns-boundaries.md",
    "references/05-biography-legacy.md", "references/06-tensions.md",
    "references/07-intellectual-lineage.md", "references/08-faq.md",
    "references/09-clinical-safety.md", "references/11-diet-wellness.md",
    "references/12-dosage-framework.md", "references/23-gongfa-system.md",
    "references/24-formula-pattern-system.md", "references/modern-disease-mapping.md",
    "references/02_Decision.md",
}

# 这些文件本身就是在讲乱码/编码，含 U+FFFD 属正常示例
DEFAULT_FFFD_ALLOW = {"references/32-encoding-hygiene.md", "references/18-error-handling.md"}

VER_RE = re.compile(r"V(\d+\.\d+(?:\.\d+)?[a-z]?)")


class Result:
    def __init__(self):
        self.rows = []

    def add(self, name, ok, detail=""):
        self.rows.append((name, ok, detail))

    @property
    def failed(self):
        return [r for r in self.rows if not r[1]]


def read(p):
    with open(p, encoding="utf-8", errors="replace") as f:
        return f.read()


def check_version(root, res):
    """四处版本号必须一致。"""
    found = {}
    skill = os.path.join(root, "SKILL.md")
    if os.path.exists(skill):
        m = re.search(r"^version:\s*(\S+)", read(skill), re.M)
        if m:
            found["SKILL.md frontmatter"] = m.group(1).lstrip("Vv")
    readme = os.path.join(root, "README.md")
    if os.path.exists(readme):
        m = re.search(r"版本-(V[\d.]+[a-z]?)-", read(readme))
        if m:
            found["README 徽章"] = m.group(1).lstrip("Vv")
    clog = os.path.join(root, "CHANGELOG.md")
    if os.path.exists(clog):
        m = re.search(r"^##\s*(V[\d.]+[a-z]?)", read(clog), re.M)
        if m:
            found["CHANGELOG 首条"] = m.group(1).lstrip("Vv")
    idx = os.path.join(root, "index.html")
    if os.path.exists(idx):
        m = re.search(r"版本\s*<b>\s*(V[\d.]+[a-z]?)\s*</b>", read(idx))
        if m:
            found["index.html"] = m.group(1).lstrip("Vv")

    if len(found) < 2:
        res.add("1. 版本一致性", True,
                f"仅 {len(found)} 处版本来源（{found}），单点无需交叉校验")
        return
    uniq = set(found.values())
    detail = " / ".join(f"{k}={v}" for k, v in found.items())
    res.add("1. 版本一致性", len(uniq) == 1, detail if len(uniq) == 1 else f"不一致: {detail}")


def check_links(root, res):
    skill_path = os.path.join(root, "SKILL.md")
    if not os.path.exists(skill_path):
        res.add("2. 死链", False, "SKILL.md 不存在")
        return
    text = read(skill_path)
    refs = set(re.findall(r"(?:references|cases|modules)/[A-Za-z0-9_./-]+\.(?:md|txt|py)", text))
    dead = []
    for r in sorted(refs):
        if r in TEMPLATE_PATHS:
            continue
        if r.startswith("modules/") or r.startswith("cases/"):
            continue          # 产出 skill 的原文/医案目录，框架侧本就没有
        if not os.path.exists(os.path.join(root, r)):
            dead.append(r)
    res.add("2. 死链", not dead, f"死链 {len(dead)}: {dead}" if dead else f"检查 {len(refs)} 条引用")


def check_orphans(root, res):
    refdir = os.path.join(root, "references")
    skill_path = os.path.join(root, "SKILL.md")
    if not (os.path.isdir(refdir) and os.path.exists(skill_path)):
        res.add("3. 孤儿文件", True, "跳过（无 references/ 或 SKILL.md）")
        return
    text = read(skill_path)
    orphans = [f for f in sorted(os.listdir(refdir))
               if f.endswith(".md") and f not in text]
    res.add("3. 孤儿文件", not orphans,
            f"未被 SKILL.md 引用: {orphans}" if orphans else "全部被引用")


def check_dup(root, res, threshold=0.9):
    mds = []
    for d, _, fs in os.walk(root):
        if ".git" in d:
            continue
        for f in fs:
            if f.endswith(".md"):
                mds.append(os.path.join(d, f))
    sig = {}
    for p in mds:
        lines = {l.strip() for l in read(p).split("\n") if len(l.strip()) > 20}
        if len(lines) > 30:
            sig[p] = lines
    dups = []
    keys = sorted(sig)
    for i in range(len(keys)):
        for j in range(i + 1, len(keys)):
            a, b = sig[keys[i]], sig[keys[j]]
            inter = len(a & b)
            if not inter:
                continue
            jac = inter / len(a | b)
            if jac >= threshold:
                dups.append(f"{os.path.relpath(keys[i], root)} ≈ "
                            f"{os.path.relpath(keys[j], root)} ({jac:.0%})")
    res.add("4. 近似重复", not dups,
            " / ".join(dups) if dups else f"比较 {len(sig)} 份 md，无近似重复")


def check_encoding(root, res, allow):
    bad = []
    for d, _, fs in os.walk(root):
        if ".git" in d:
            continue
        for f in fs:
            if not f.endswith((".md", ".html", ".py", ".json")):
                continue
            p = os.path.join(d, f)
            rel = os.path.relpath(p, root).replace("\\", "/")
            if rel in allow:
                continue
            t = read(p)
            n = t.count("\ufffd")
            if n:
                bad.append(f"{rel}({n})")
    res.add("5. 编码卫生", not bad, f"U+FFFD 残留: {bad}" if bad else "0 处 U+FFFD")


def check_lineno(root, res):
    skill_path = os.path.join(root, "SKILL.md")
    if not os.path.exists(skill_path):
        res.add("6. 行号残留", False, "SKILL.md 不存在")
        return
    # 讲「禁止写行号」的条款本身会引用行号做反例，这类行豁免
    EXEMPT = re.compile(r"禁止|反例|错误示范|❌")
    hits = []
    for i, line in enumerate(read(skill_path).split("\n"), 1):
        if EXEMPT.search(line):
            continue
        if re.search(r"详见第\s*\d+\s*行|见第\s*\d+\s*行|约\s*\d+\s*行|\bL\d{2,}\b", line):
            hits.append(i)
    res.add("6. 行号残留", not hits, f"行 {hits[:12]}" if hits else "0 处")


def main() -> int:
    ap = argparse.ArgumentParser(description="蒸馏器自身健康检查")
    ap.add_argument("--root", default=".", help="仓库根目录（默认当前目录）")
    ap.add_argument("--dup-threshold", type=float, default=0.9, help="近似重复判定阈值")
    ap.add_argument("--allow-fffd", default="", help="额外允许含 U+FFFD 的相对路径，逗号分隔")
    ap.add_argument("--quiet", action="store_true", help="只输出失败项")
    args = ap.parse_args()

    allow = set(DEFAULT_FFFD_ALLOW) | {x.strip() for x in args.allow_fffd.split(",") if x.strip()}

    res = Result()
    check_version(args.root, res)
    check_links(args.root, res)
    check_orphans(args.root, res)
    check_dup(args.root, res, args.dup_threshold)
    check_encoding(args.root, res, allow)
    check_lineno(args.root, res)

    for name, ok, detail in res.rows:
        if args.quiet and ok:
            continue
        print(f"{'✅' if ok else '❌'} {name}" + (f" — {detail}" if detail else ""))

    print(f"\n汇总: {len(res.rows) - len(res.failed)}/{len(res.rows)} 通过")
    return 1 if res.failed else 0


if __name__ == "__main__":
    sys.exit(main())
