"""本地模拟 bot：把 skill/chalice-persona 的内容拼成系统提示词，调 DeepSeek 回复。
不依赖 dsh，改完 Skill 马上就能试效果。

用法:
  python scripts/try_skill.py                      # 交互模式，输入「名字: 消息」模拟群聊，exit 退出
  python scripts/try_skill.py --eval 20            # 拿 build/eval.jsonl 的 20 条对比原话 → build/eval_report.md
  python scripts/try_skill.py --eval 20 --blind    # 再生成盲测题 build/blind_test.md（答案在 blind_answers.md）
"""
import argparse
import json
import math
import random
import re

from common import BUILD, REFS, SKILL_DIR, llm, read_jsonl

TOP_K_EXAMPLES = 10
REF_ORDER = ["voice.md", "scenarios.md", "memes.md", "background.md", "dota.md", "manual.md"]


def load_examples():
    out = []
    for p in sorted((REFS / "examples").glob("*.jsonl")):
        for rec in read_jsonl(p):
            rec["scene"] = p.stem
            out.append(rec)
    return out


def bigrams(text):
    text = re.sub(r"\s+", "", text)
    return {text[i:i + 2] for i in range(len(text) - 1)}


def retrieve(query, examples, k=TOP_K_EXAMPLES):
    """按字 bigram 重合度取最相近的示例，模拟 bot 的按需检索。"""
    q = bigrams(query)
    def score(e):
        ctx = e["context"]
        text = " ".join([ctx.get("game", ""), ctx.get("danmaku", ""), ctx.get("prev", ""),
                         *[o.get("text", "") for o in ctx.get("others", [])], e["reply"]])
        b = bigrams(text)
        return len(q & b) / math.sqrt(len(b) + 1)
    return sorted(examples, key=score, reverse=True)[:k]


def system_prompt(query, examples):
    skill = (SKILL_DIR / "SKILL.md").read_text(encoding="utf-8")
    skill = re.sub(r"^---\n.*?\n---\n", "", skill, flags=re.S)  # 去掉 frontmatter
    parts = [skill, "\n（以下 references 内容已附上，无需再读取文件）"]
    for name in REF_ORDER:
        p = REFS / name
        if p.exists():
            parts.append(f"\n===== references/{name} =====\n{p.read_text(encoding='utf-8')}")
    if examples:
        shots = "\n".join(json.dumps({"scene": e["scene"], "context": e["context"], "reply": e["reply"]},
                                     ensure_ascii=False) for e in retrieve(query, examples))
        parts.append(f"\n===== 与当前对话最相近的原话示例 =====\n{shots}")
    return "\n".join(parts)


def context_to_chat(ctx):
    lines = []
    if ctx.get("game"):
        lines.append(f"[背景：你正在打 Dota，{ctx['game']}]")
    if ctx.get("prev"):
        lines.append(f"[你刚说过：{ctx['prev']}]")
    for o in ctx.get("others", []):
        lines.append(f"{o.get('who') or '某人'}: {o.get('text', '')}")
    if ctx.get("danmaku"):
        danmaku = re.sub(r"^弹幕[:：]\s*", "", ctx["danmaku"])
        lines.append(f"群友: {danmaku}")
    return "\n".join(lines) or "[背景：你在打 Dota，没人说话]"


def interactive(examples):
    history = []
    print("输入「名字: 消息」，不带名字默认是「群友」。exit 退出，reset 清空上下文。\n")
    while True:
        try:
            line = input("> ").strip()
        except (EOFError, KeyboardInterrupt):
            break
        if line == "exit":
            break
        if line == "reset":
            history = []
            continue
        if not line:
            continue
        if not re.match(r"^[^:：]{1,12}[:：]", line):
            line = f"群友: {line}"
        history.append({"role": "user", "content": line})
        recent = " ".join(m["content"] for m in history[-6:])
        reply = llm([{"role": "system", "content": system_prompt(recent, examples)}] + history[-20:])
        history.append({"role": "assistant", "content": reply})
        print(f"Chalice: {reply}\n")


def evaluate(n, blind, examples):
    eval_file = BUILD / "eval.jsonl"
    if not eval_file.exists():
        raise SystemExit("没有 build/eval.jsonl，先运行 distill.py")
    cases = read_jsonl(eval_file)[:n]
    report, results = ["# 评测报告\n"], []
    for i, case in enumerate(cases, 1):
        chat = context_to_chat(case["context"])
        print(f"[{i}/{len(cases)}] {case['id']}")
        bot = llm([{"role": "system", "content": system_prompt(chat, examples)},
                   {"role": "user", "content": chat}])
        results.append((chat, case["reply"], bot))
        report += [f"## {i}. {case['id']}（{case['scene']}）\n", "```", chat, "```",
                   f"- **原话**：{case['reply']}", f"- **bot**：{bot}\n"]
    (BUILD / "eval_report.md").write_text("\n".join(report), encoding="utf-8")
    print("→ build/eval_report.md")

    if blind:
        rng = random.Random()
        qs, ans = ["# 盲测：哪句是 Chalice 本人说的？\n"], ["# 盲测答案\n"]
        for i, (chat, real, bot) in enumerate(results, 1):
            real_first = rng.random() < 0.5
            a, b = (real, bot) if real_first else (bot, real)
            qs += [f"## {i}\n", "```", chat, "```", f"- A：{a}", f"- B：{b}\n"]
            ans.append(f"{i}. {'A' if real_first else 'B'}")
        (BUILD / "blind_test.md").write_text("\n".join(qs), encoding="utf-8")
        (BUILD / "blind_answers.md").write_text("\n".join(ans), encoding="utf-8")
        print("→ build/blind_test.md（发群里），答案在 build/blind_answers.md")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--eval", type=int, metavar="N")
    ap.add_argument("--blind", action="store_true")
    args = ap.parse_args()
    examples = load_examples()
    if args.eval:
        evaluate(args.eval, args.blind, examples)
    else:
        interactive(examples)


if __name__ == "__main__":
    main()
