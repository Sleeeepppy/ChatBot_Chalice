# 提示词

所有提示词都放在 [`prompts/`](../prompts/) 目录，脚本会直接读取这些文件。想换个问法就直接改 txt 文件，**不用改代码**。不用脚本、在 DeepSeek 网页版里手动跑也可以：复制文件内容，把 `{{变量}}` 替换掉就行。

| 文件 | 谁调用 | 变量 | 作用 |
|---|---|---|---|
| `annotate.txt` | `annotate.py` | `title` `transcript` `scenes` `tags` | 把转写起草成样本 |
| `scene_analysis.txt` | `distill.py` | `scene` `samples` | 分析单个场景的回应策略 → scenarios.md |
| `merge_voice.txt` | `distill.py` | `scene_analyses` `catchphrase_stats` | 合并成整体语言风格 → voice.md |
| `memes.txt` | `distill.py` | `samples` | 整理梗词典 → memes.md |
| `background.txt` | `distill.py` | `personal_samples` `other_sources` | 整理人物背景 → background.md |

- `{{scenes}}` 和 `{{tags}}` 会自动从 `scripts/common.py` 里的 `SCENES` / `TAGS` 填入，保证分类表只有一份
- 手动跑 `annotate.txt` 时，转写要整理成 `[mm:ss] Chalice: 文本` / `[mm:ss] 其他人1: 文本` 的格式，效果比直接贴 JSON 好
- 改了提示词之后，在 PR 里说明改了什么、为什么改，方便大家对比提炼效果
