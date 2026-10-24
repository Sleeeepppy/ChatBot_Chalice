# Chalice Skill —— 让聊天 bot 学会 Chalice 说话

从 B 站上的 Chalice（Dota2 主播）直播切片里，提炼他对**游戏局势 / 直播弹幕 / 其他主播**的回应方式、口头禅和人物背景，做成一个 Skill，接到基于 dsh（DeepSeek Harness）的微信 bot 上，让 bot 聊天时像 Chalice。

> 朋友间娱乐项目，不设内容边界：样本**逐字保留原话**（脏话、阴阳、互喷照录），不要美化。

## 整体流程

```
B站切片 ─▶ ①认领 ─▶ ②下载 ─▶ ③转写 ─▶ ④标注 ─▶ ⑤提炼 ─▶ ⑥组装 Skill ─▶ ⑦评测迭代
          clips.csv  download  transcribe  annotate   distill    SKILL.md      try_skill
                                           +validate  +stats                   回到 ④/⑤/⑥
          ──────────── 所有人并行，各做各的切片 ────────────   ───── 1~2 人汇总 ─────
```

| 阶段 | 谁做 | 脚本 | 产出 |
|---|---|---|---|
| ① 认领切片 | 每个人 | `fetch_list.py`（生成清单） | `clips.csv` 里填上名字 |
| ② 下载音频 | 每个人 | `download.py` | `raw/<BV>.wav`（不进 git） |
| ③ 语音转写 | 每个人 | `transcribe.py` | `data/transcripts/<BV>.json` |
| ④ 标注样本 | 每个人 | `annotate.py` 起草 → 人工校对 → `validate.py` | `data/samples/<BV>.jsonl` |
| ⑤ 提炼风格 | 汇总人 | `distill.py`（内含 `stats.py`） | `skill/chalice-persona/references/` |
| ⑥ 组装 Skill | 汇总人 | 手动 | `skill/chalice-persona/SKILL.md` |
| ⑦ 评测迭代 | 所有人 | `try_skill.py` | 评测报告、盲测题、bad case |

**最费时间、最值得多人分担的是 ③④**，上百个切片平摊下来每人十几二十个就够了。

## 快速上手（协作者）

```bash
pip install -r requirements.txt          # 另需安装 ffmpeg 并加入 PATH
cp .env.example .env                     # 填入 DeepSeek API key
```

```bash
# ① 认领：在 clips.csv 里把 owner 填成你的名字、status 改成 claimed，提交到 main

# ② 下载你认领的切片
python scripts/download.py --owner 你的名字 --cookies-from-browser chrome

# ③ 转写，然后检查 clips.csv 里自动填的 chalice_spk 对不对
python scripts/transcribe.py --owner 你的名字

# ④ 让 DeepSeek 起草样本 → data/samples/<BV>.draft.jsonl
python scripts/annotate.py --owner 你的名字
python scripts/validate.py --drafts      # 找出被 LLM 改写过的 reply
#    人工逐条校对草稿，改完把 <BV>.draft.jsonl 改名为 <BV>.jsonl
python scripts/validate.py               # 0 个错误再提交
```

然后新建分支，提交 `data/transcripts/` 和 `data/samples/` 下自己的文件，并把 `clips.csv` 的状态改成 `annotated`，提 PR。

**标注之前请务必读一遍 [提炼流程详解](docs/extraction-guide.md)**，尤其是「样本格式」和「场景分类」两节，这样大家标出来的东西才一致。

## 汇总人

```bash
python scripts/distill.py --dry-run      # 先看看提示词和样本量
python scripts/distill.py                # 生成 references/
python scripts/try_skill.py              # 本地模拟群聊，试试像不像
python scripts/try_skill.py --eval 30 --blind   # 和原话对比 + 生成盲测题
```

把 `skill/chalice-persona/` 整个目录放进 dsh 使用。日常迭代主要改这几个地方：`references/manual.md`（手写规则和梗，不会被脚本覆盖）、`SKILL.md`、`prompts/`。

## 目录结构

```
├── clips.csv                  # 切片清单 + 认领表
├── requirements.txt / .env.example
├── docs/
│   ├── extraction-guide.md    # 提炼流程详解（必读）
│   └── prompts.md             # 提示词说明
├── prompts/                   # 提示词模板（脚本直接读取，可以随时改）
├── scripts/                   # 流水线脚本
├── templates/sample.jsonl     # 样本格式示例
├── data/
│   ├── hotwords.txt           # ASR 热词（Dota 术语、人名），大家一起补
│   ├── background_sources.md  # 直播外的人物信息（注明出处）
│   ├── transcripts/           # 转写结果（提交）
│   └── samples/               # 校对好的样本（提交）
├── raw/                       # 音视频（不提交）
├── build/                     # 评测集、统计、报告（不提交）
└── skill/chalice-persona/     # 最终产物：Skill 本体
    ├── SKILL.md
    └── references/            # voice / scenarios / memes / background 由 distill.py 生成
                               # manual / dota 手写
```
