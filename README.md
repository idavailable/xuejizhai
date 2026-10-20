# 薛立斋 · 四书思维技能

> ⚠️ **仅供中医文献与学术方法研究，不构成诊疗建议，不提供处方与剂量。**

[![Version](https://img.shields.io/badge/版本-V0.2.0-blue)](CHANGELOG.md)
[![Corpus](https://img.shields.io/badge/语料-四书%2013万字-orange)]()
[![Coverage](https://img.shields.io/badge/15维度-14%2F15-green)]()

把明代医家**薛己（薛立斋）**的《内科摘要》《外科枢要》《女科撮要》《正体类要》，蒸馏成可被 AI 调用的人物技能。

## 先破一个成见

"薛立斋只会温补"——四书用方频次不支持这句话：

| 方 | 次 | 方 | 次 |
|---|--:|---|--:|
| 补中益气 | 390 | 逍遥 | 119 |
| **六味地黄** | **198** | **八味地黄** | **116** |
| 四物 | 151 | 四君 | 70 |

六味（滋阴）多于八味（温阳）；四物（血）多于四君（气）。他的第一方是补中益气，不是桂附。

## 三条要点

1. **脾胃为五脏根本**，且直接推出"黄柏知母不宜轻用，恐复伤胃气"。
2. **朝夕分补不是固定方对**：三例三配法，是"一天分两段各治一条线"的时间结构。
3. **外科伤科皆从内治**：《正体类要》主治大法全落内科，"若行克伐，则虚者益虚，滞者益滞，祸不旋踵"。

## 语料来源

| 书 | 来源 |
|---|---|
| 内科摘要 | cmedalib `oldTCMBooks/902.htm` |
| 外科枢要 | cmedalib `oldTCMBooksA/081.htm` |
| 女科撮要 | cmedalib `oldTCMBooks/906.htm` |
| 正体类要 | cmedalib `oldTCMBooksA/319.htm` |

四书均为公版古籍；电子文本来自上述站点（该站标注"只作自学研究"）。本仓库保存目的是文本校勘与引文校验，如权利人异议即移除 `modules/`。

## 安装

```bash
git clone https://github.com/idavailable/xuejizhai.git ~/.workbuddy/skills/xuejizhai
# 或
cp -r xuejizhai ~/.workbuddy/skills/xuejizhai
```

自检：

```bash
cd ~/.workbuddy/skills/xuejizhai
python3 scripts/health_check.py
python3 scripts/check_quotes.py
```

## 覆盖率 14/15

缺：9 生平（生卒无确考）；15 功法不适用。
**v0.2.0 补齐**：7 饮食（`references/11`）、8 条辨框架（`references/41`）。

## 许可

代码与方法 MIT；`modules/` 古籍原文属公有领域，不适用 MIT。
