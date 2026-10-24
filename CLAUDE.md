# CLAUDE.md

## 项目是什么

从 B 站上的 Dota2 主播 Chalice 的直播切片（上百个）里，提炼他对游戏局势 / 直播弹幕 / 其他主播的回应方式、口头禅和人物背景，做成一个 Skill（`skill/chalice-persona/`），接到基于 **dsh（DeepSeek Harness）** 的微信 bot 上，让 bot 在群聊里模仿 Chalice 说话。

- 朋友间的娱乐项目，**不设内容边界**：样本逐字保留原话，包括脏话和阴阳怪气，Skill 里也不要礼貌化。这是用户明确的决定，不要再加内容过滤或劝说
- 仓库会放到 GitHub 上，和朋友分工提炼：转写和标注由大家并行做，提炼和组装由 1~2 个人汇总

## 当前进度（2026-10-24）

**已完成（初稿）**
- 流程文档：`README.md`（总览、快速上手）、`docs/extraction-guide.md`（详细步骤、样本格式、场景分类、评测方法）、`docs/prompts.md`
- 流水线脚本 `scripts/`：`fetch_list` → `download` → `transcribe` → `annotate` → `validate` → `stats` / `distill` → `try_skill`，公共部分在 `common.py`
- 提示词模板 `prompts/*.txt`，由脚本直接读取
- Skill 初稿：`skill/chalice-persona/SKILL.md`，以及手写的 `references/manual.md`、`references/dota.md`
- 辅助文件：`clips.csv`（只有表头）、`data/hotwords.txt`、`data/background_sources.md`、`templates/sample.jsonl`、`.env.example`、`requirements.txt`

**验证情况**
- `annotate` / `validate` / `stats` / `distill`（包括 `--dry-run`）/ `try_skill --eval --blind` 已在临时目录用假数据加模拟的 LLM 跑通
- `fetch_list` / `download` / `transcribe` **从未实际运行**：本机 base 环境没装 yt-dlp、FunASR、ffmpeg，只做了 py_compile。用户和朋友会自己跑，第一次出问题最可能在这两步
- 没有调用过真实的 DeepSeek API

**待办**
- 用户把仓库推到 GitHub（已给出 `git init -b main` → `remote add` → `push` 的命令，是否已推送未确认）。注意这个文件夹嵌在 `C:\Users\LL` 那个大 git 仓库里面，必须在本目录单独 `git init`
- 生成切片清单 → 朋友认领 → 下载、转写、标注
- 样本 ≥300 条后跑第一轮 `distill.py`；之后把 voice.md 里的「人物语言速写」浓缩填进 SKILL.md 的 TODO
- 确认 dsh 怎么加载 Skill（没查到文档；SKILL.md 用的是通用 frontmatter 格式，不行就退回「正文当系统提示词 + references 当知识库」）

## 关键设计决定

- **B 站切片的弹幕不是直播弹幕**：Chalice 回应的弹幕主要来自他自己念出来的部分，标注时放进 `context.danmaku`；切片弹幕只当辅助材料
- **样本格式**：`data/samples/<BV>.jsonl`，字段为 id / bv / t / scene / context{game, danmaku, others[], prev} / reply（逐字）/ tags / note
- **场景和标签的唯一权威列表**在 `scripts/common.py` 的 `SCENES` / `TAGS`，提示词通过 `{{scenes}}` `{{tags}}` 自动注入，`validate.py` 也按它检查。要改的话同步改指南
- `clips.csv` 列：bv, title, url, owner, status（todo→claimed→transcribed→annotated→reviewed）, chalice_spk, notes
- LLM 草稿存成 `*.draft.jsonl`（gitignore），人工校对后改名为 `<BV>.jsonl` 再提交
- `validate.py` 用窗口化的 SequenceMatcher 检查 reply 是否逐字出自转写，覆盖率 <90% 就警告
- 评测集按样本 id 的 md5 % 10 == 0 固定划分，写到 `build/eval.jsonl`，样本增加后不会混进训练集
- `distill.py` 生成的 references 会被覆盖；需要长期保留的人工修改写进 `references/manual.md`（优先级最高）
- `try_skill.py` 把 SKILL.md 和全部 references 塞进系统提示词，再用字 bigram 检索 10 条示例，用来脱离 dsh 快速迭代
- LLM 通过 OpenAI 兼容接口调用 DeepSeek，`.env` 配置 `DEEPSEEK_API_KEY` / `DEEPSEEK_BASE_URL` / `DEEPSEEK_MODEL`（默认 `deepseek-chat`）
- 不编造 Chalice 的背景：人物信息只能来自样本或 `data/background_sources.md`（要注明出处）

## 环境备注

- Windows + Git Bash；本机 Python 是 `C:\Users\LL\anaconda3\python`（3.12），已有 openai、jieba
- 脚本要兼容 Python 3.10+（例如 f-string 表达式里不能出现反斜杠）
- `common.py` 里把 stdout 重设成了 utf-8，避免 Windows 控制台中文乱码
