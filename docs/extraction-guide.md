# 提炼流程详解

这份文档写给所有参与提炼的人。阶段 ①~④ 每个人都要做，⑤~⑦ 由汇总人负责，但大家最好都看一下，知道自己标的数据最后会被怎么用。

---

## 0. 先搞清楚一件事：切片里的「弹幕」从哪来

B 站切片下载下来的弹幕，是**看切片的观众**发的，**不是**直播时 Chalice 看到的那些。直播间弹幕（Chalice 真正在回应的东西）一般只能从这几个地方拿到：

1. **Chalice 自己念出来**（"有人说我……"、"弹幕说……"）：最常见，转写里就有，标注时把这部分归到 `context.danmaku`
2. **画面上能看到的弹幕框**：有需要再截图 OCR，不强求
3. **切片作者加的字幕或注释**

切片自带的弹幕当**辅助材料**用：可以帮你看懂哪句是梗、观众在笑什么，但不要当成 Chalice 回应的对象。

---

## ① 认领切片

`clips.csv` 的列：

| 列 | 说明 |
|---|---|
| `bv` | BV 号，也是所有文件名的前缀 |
| `title` | 切片标题 |
| `url` | 链接 |
| `owner` | 认领人 |
| `status` | `todo` → `claimed` → `transcribed` → `annotated` → `reviewed` |
| `chalice_spk` | 转写里哪个说话人编号是 Chalice（`transcribe.py` 自动猜，人工确认） |
| `notes` | 备注（比如"连麦 XX"、"音质差"、"纯游戏无对话可跳过"） |

**批量生成清单**（一般由一个人来做）：拿到切片 UP 主的空间或合集链接后运行

```bash
python scripts/fetch_list.py "<合集或空间URL>" --keyword Chalice --cookies-from-browser chrome
```

已有的 BV 号会自动去重，可以反复跑。`--keyword` 用来只保留标题里带关键词的视频（切片 UP 主可能也切别的主播）。空间页经常要求登录，拿不到时加上 `--cookies-from-browser`。

认领时只改自己那几行，改完马上提交，减少冲突。

**优先级**：对话多的 > 纯操作的；有连麦或互动的 > 单人打游戏；高光、翻车、名场面优先。

---

## ② 下载音频

```bash
python scripts/download.py --owner 你的名字 --cookies-from-browser chrome
# 或者指定 BV 号
python scripts/download.py BV1xxx BV1yyy
```

- 下载音频到 `raw/<BV>.wav`，同时尝试下载弹幕（`<BV>.danmaku.xml`）和 B 站 AI 字幕（`<BV>.ai-zh.*`）。已下载过的会跳过
- 需要先装好 `ffmpeg` 并加入 PATH
- `--cookies-from-browser chrome`（或 `edge`、`firefox`）会使用浏览器里已登录的 B 站账号，AI 字幕一般要登录才能拿到
- 某个视频没有 AI 字幕时，可以用 `yt-dlp --list-subs <URL>` 查一下实际有哪些字幕
- `raw/` 已加入 `.gitignore`，**音视频不要提交**（体积大，也没必要）
- 有 AI 字幕的话，可以拿来和 ASR 结果对照纠错

---

## ③ 语音转写

```bash
python scripts/transcribe.py --owner 你的名字
```

- 用 FunASR（`paraformer-zh` + 标点 + `cam++` 说话人区分），有 GPU 自动用 GPU。第一次运行会下载模型
- 结果写到 `data/transcripts/<BV>.json`，每句包含 `start_ms` `end_ms` `spk` `text`
- 运行时会打印每个说话人的总时长和前几句话，并把**说话最多的那个**暂定为 Chalice，填进 `clips.csv` 的 `chalice_spk`
- [`data/hotwords.txt`](../data/hotwords.txt) 是热词表（Dota 术语、英雄名、人名、梗），可以明显减少错字。发现 ASR 老是认错哪个词就加进去，大家一起维护

转写完需要人工过一遍：

1. **确认 `chalice_spk` 填得对**。连麦时对方声音大，或者 Chalice 在看视频的切片，都可能猜错
2. **修明显错字**，尤其是 Dota 术语、英雄名、人名、梗，直接改 json 里的 `text`
3. 游戏音效、BGM 识别出来的乱码句子直接删掉

---

## ④ 标注成样本（核心）

### 样本格式

每个切片输出一个 `data/samples/<BV号>.jsonl`，**一行一条样本**。完整示例见 [`templates/sample.jsonl`](../templates/sample.jsonl)。

```json
{
  "id": "BV1xx411c7XX-003",
  "bv": "BV1xx411c7XX",
  "t": "03:12",
  "scene": "被嘲讽回击",
  "context": {
    "game": "中期一波团被零换五，经济落后 8k",
    "danmaku": "弹幕：又是你先死的",
    "others": [{"who": "队友", "text": "你怎么又先进去了"}],
    "prev": "（Chalice 上一句话，没有就留空）"
  },
  "reply": "Chalice 的原话，逐字照录，语气词、口头禅、脏话全部保留",
  "tags": ["自嘲", "甩锅"],
  "note": "梗或背景解释，看不懂这句的人需要知道什么"
}
```

字段要求：

| 字段 | 要求 |
|---|---|
| `reply` | **必须逐字**。"嗯""啊""卧槽""好好好"这些都别删，它们就是风格本身。一条样本只放一次完整回应（可以是几句连着说的） |
| `context` | 写清楚 Chalice 是**在回应什么**。四个子字段按实际情况填，用不上的留空字符串或空数组 |
| `context.game` | 用一句话描述游戏局势，不需要很精确 |
| `scene` | 从下面的场景分类里**选一个**，实在没有合适的就选「其他」，并在 `note` 里说明 |
| `tags` | 可多选，描述回应的手法（见下） |
| `note` | 可选，但只要有梗就一定写，汇总时很有用 |

### 场景分类（scene，单选）

| scene | 说明 |
|---|---|
| `读弹幕回应` | 念出弹幕并回应（中性或正面的） |
| `被嘲讽回击` | 被弹幕、队友或对手嘲讽时的反应 |
| `高光时刻` | 打出好操作、赢团、翻盘 |
| `失误翻车` | 自己送了、操作失误、输团 |
| `吐槽队友` | |
| `吐槽对手` | |
| `连麦闲聊` | 和其他主播或嘉宾的非游戏聊天 |
| `游戏讲解` | 认真讲出装、思路、版本理解 |
| `个人经历` | 聊自己的生活、过去、职业经历（**人物背景的主要来源**） |
| `其他` | |

觉得需要新增场景的话提 Issue 讨论，不要私自加，否则汇总时对不齐。

### 手法标签（tags，多选）

`自嘲` `阴阳怪气` `夸张` `嘴硬` `甩锅` `认真` `破防` `装傻` `反问` `复读` `玩梗` `骂人` `讲道理` `转移话题`

场景和标签的权威列表都在 `scripts/common.py` 的 `SCENES` / `TAGS` 里，`validate.py` 按它检查。要增删的话先提 Issue，然后同时改 common.py 和这份文档。

### 怎么切样本

- 一个**触发**（一条弹幕、一句别人的话、一个游戏事件）+ Chalice 对它的**回应** = 一条样本
- Chalice 自己没被触发也在说的（自言自语、碎碎念）同样有价值：`scene` 按内容选，`context` 里只写 `game`
- 一个 3 分钟的切片通常能切出 5~15 条。不用追求数量，**有个人特色的**优先
- 纯报点（"上上上""撤撤撤"）这种谁都会说的话可以跳过

### 用 LLM 起草，人工校对

```bash
python scripts/annotate.py --owner 你的名字   # → data/samples/<BV>.draft.jsonl
python scripts/validate.py --drafts          # 标出 reply 和转写对不上的条目
```

`annotate.py` 用 [`prompts/annotate.txt`](../prompts/annotate.txt) 让 DeepSeek 起草，自动编号、修正不在分类表里的 scene/tags。草稿出来后**一定要人工逐条检查**：

- `reply` 是不是 Chalice 原话。LLM 很爱"顺手润色"，`validate.py --drafts` 会把对不上转写的条目标出来，重点看这些
- 说话人有没有搞混
- `scene` 和 `tags` 合不合理
- 梗有没有解释错；LLM 漏掉的好片段自己补上，没意思的删掉

校对完把 `<BV>.draft.jsonl` 改名为 `<BV>.jsonl`（草稿不会进 git），跑 `python scripts/validate.py` 确认 0 个错误，把 `clips.csv` 的状态改成 `annotated`，然后提 PR。

---

## ⑤ 提炼风格（汇总人）

样本攒到 **300 条以上**再开始第一轮提炼，之后每多 200~300 条迭代一次。

```bash
python scripts/distill.py --dry-run          # 不调 API，提示词写到 build/prompts/，先检查样本量和长度
python scripts/distill.py                    # 全部生成
python scripts/distill.py --only voice,memes # 只重跑部分
```

`distill.py` 依次做这些事：

1. **切评测集**：按样本 id 的哈希固定抽约 1/10 写到 `build/eval.jsonl`，**这部分不参与提炼**，留给 ⑦ 用。因为按哈希分，样本增加后原来的评测样本不会跑到训练集里
2. **统计口头禅**：调用 `stats.py`，对所有 `reply` 统计高频片段（按出现的样本数计，不会被一条复读刷高）和句尾语气词。单独运行 `python scripts/stats.py` 会写到 `build/catchphrases.md`
3. **按场景分析**：每个 scene 抽最多 150 条（按手法标签分散抽），用 `prompts/scene_analysis.txt` 让 DeepSeek 归纳
4. **生成 references**：

| 产出文件 | 来源 | 内容 |
|---|---|---|
| `voice.md` | 各场景分析 + 口头禅统计 → `merge_voice.txt` | 整体语言风格：速写、口头禅表、句式、语气词、幽默和攻击性、反模式 |
| `scenarios.md` | 各场景分析拼接 | 每个场景的回应策略和代表性原话 |
| `memes.md` | 带 `note` 的样本 → `memes.txt` | 梗词典 |
| `background.md` | 「个人经历」样本 + [`data/background_sources.md`](../data/background_sources.md) → `background.txt` | 人物背景，每条带来源 |
| `examples/<scene>.jsonl` | 每个场景按标签分散抽 40 条 | few-shot 原话 |

生成的文件开头都有「重新运行会覆盖」的标记。**想手动补充的内容写进 `references/manual.md`**（脚本不会动它），`references/dota.md` 也是手写的。

直播之外的人物信息（百科、采访、你们知道的事）请贴进 `data/background_sources.md`，并注明出处。

**原则：示例比形容词管用。** "他说话很幽默"对模型几乎没用，5 条真实原话才有用。所以提示词里要求每个结论都附原话。

---

## ⑥ 组装 Skill（汇总人）

```
skill/chalice-persona/
├── SKILL.md                 # 手写：人设、群聊→场景映射、回复流程、硬规则
└── references/
    ├── voice.md             # distill.py 生成
    ├── scenarios.md         # distill.py 生成
    ├── memes.md             # distill.py 生成
    ├── background.md        # distill.py 生成
    ├── manual.md            # 手写，优先级最高，脚本不覆盖
    ├── dota.md              # 手写
    └── examples/<场景>.jsonl # distill.py 生成
```

[`SKILL.md`](../skill/chalice-persona/SKILL.md) 已经有初稿，用的是通用 Skill 格式：开头是 frontmatter（`name`、`description`），正文**写短**，只放核心规则和 references 索引，细节放进 references 按需读取。第一次跑完 distill 后，汇总人要做的是：

1. 把 voice.md 里的「人物语言速写」浓缩成两三句，填进 SKILL.md 的 TODO 位置
2. 通读生成的 references，删掉明显不对或空泛的内容（下次重跑会被覆盖，长期有效的修改写进 manual.md）
3. 对照 `scenarios.md`，检查 SKILL.md 里「群聊→场景」的映射表是否需要调整

### 接入 dsh

- 怎么挂载以 dsh 的 Skill/插件文档为准，把 `skill/chalice-persona/` 整个目录放进去
- 如果你用的 dsh 版本不能直接读 SKILL.md，就退一步：SKILL.md 的正文当**系统提示词**，`references/` 当**知识库**，每次回复前按场景检索 examples 里最相似的几条拼进上下文。效果基本一样
- 微信回复要短：可以在硬规则里限制字数，或者让 bot 把长回复拆成几条发

---

## ⑦ 评测与迭代（所有人）

`try_skill.py` 不依赖 dsh：它把 SKILL.md 和所有 references 拼成系统提示词，再按字面相似度检索 10 条 examples，然后调 DeepSeek 回复。改完 Skill 可以马上试，不用重新部署 bot。

```bash
python scripts/try_skill.py                     # 交互模式：输入「名字: 消息」模拟群聊，reset 清空，exit 退出
python scripts/try_skill.py --eval 30           # 评测集前 30 条，原话和 bot 回复并排 → build/eval_report.md
python scripts/try_skill.py --eval 30 --blind   # 再生成盲测题 build/blind_test.md，答案在 blind_answers.md
```

1. **离线对比**：看 `eval_report.md`，重点是语气、长度、口头禅频率像不像，不要求内容和原话一致
2. **群内盲测**：把 `blind_test.md` 发到群里，让大家猜哪句是本人说的。猜对率越接近 50%，说明越像
3. **收集坏例子**：bot（真实部署的或者 try_skill 的）说了不像 Chalice 的话，就把群聊上下文、bot 的回复，以及「Chalice 应该会怎么说」一起写进 Issue，打 `bad-case` 标签
4. **对症修改**：

| 现象 | 改哪里 |
|---|---|
| 太礼貌、太像 AI 助手 | SKILL.md 硬规则；manual.md 写上具体反例 |
| 口头禅刷屏 | manual.md 写清频率限制 |
| 某个场景回得不像 | 补这个场景的样本 → `distill.py --only scenarios,examples` |
| 梗用错 | manual.md 补用法说明和反例 |
| 编造经历 | background_sources.md 补信息 → `distill.py --only background` |
| 提炼出来的东西空泛 | 改 `prompts/` 里对应的提示词，重跑 |
| 群里的专属叫法、老梗 | manual.md 的「群内设定」 |

> try_skill 是一次性把所有 references 塞进上下文，dsh 实际可能是按需读取，两者效果会有些差别。最终还是以微信里的真实表现为准。

---

## 协作约定

- 文件名一律用 BV 号：`data/transcripts/BVxxx.json`、`data/samples/BVxxx.jsonl`
- 一个 PR 包含若干个切片的 transcripts + samples，以及 `clips.csv` 的状态更新
- 提 PR 前先跑 `python scripts/validate.py`，要求 0 个错误
- review 时重点看：`reply` 是否逐字（validate 的警告逐条确认）、`scene`/`tags` 是否合理
- 场景分类、样本格式要改的话，先提 Issue 统一，再改 `scripts/common.py` 和这份文档
- 改了 `prompts/` 的话，在 PR 里贴一下改前和改后的提炼结果对比
