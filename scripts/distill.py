"""从已校对样本提炼出 Skill 的 references/（汇总人运行）。

每条样本按 id 哈希固定分到训练集或评测集（约 1/10），评测集写到 build/eval.jsonl，不参与提炼。

用法:
  python scripts/distill.py                      # 全部重新生成
  python scripts/distill.py --only voice,memes   # 只重跑部分：scenarios voice memes background examples
  python scripts/distill.py --dry-run            # 不调 API，只把提示词写到 build/prompts/ 看看
"""
import argparse
import hashlib
import json
import random
from collections import defaultdict

from common import BG_SOURCES, BUILD, REFS, SCENES, llm, load_all_samples, load_prompt, write_jsonl
from stats import render as render_stats

EVAL_MOD = 10                 # id 哈希 % 10 == 0 的进评测集
MAX_ANALYSIS_PER_SCENE = 150  # 每个场景最多拿多少条去做风格分析
MAX_MEME_SAMPLES = 300
EXAMPLES_PER_SCENE = 40       # 每个场景放进 references/examples 的样本数
MIN_SCENE_SAMPLES = 3
PARTS = ["scenarios", "voice", "memes", "background", "examples"]
HEADER = "<!-- 由 scripts/distill.py 生成，重新运行会覆盖。手动补充请写在 manual.md -->\n\n"


def is_eval(sample):
    return int(hashlib.md5(sample["id"].encode("utf-8")).hexdigest(), 16) % EVAL_MOD == 0


def compact(s):
    return json.dumps({k: s[k] for k in ("id", "context", "reply", "tags", "note") if s.get(k)},
                      ensure_ascii=False)


def pick_diverse(samples, k, rng):
    """按首个 tag 分桶后轮流抽，避免全是同一种手法。"""
    if len(samples) <= k:
        return list(samples)
    buckets = defaultdict(list)
    for s in samples:
        buckets[(s.get("tags") or [""])[0]].append(s)
    for b in buckets.values():
        rng.shuffle(b)
    picked, queues = [], list(buckets.values())
    while len(picked) < k:
        for q in queues:
            if q and len(picked) < k:
                picked.append(q.pop())
    return picked


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", help="逗号分隔：" + ",".join(PARTS))
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()
    parts = set(args.only.split(",")) if args.only else set(PARTS)
    if parts - set(PARTS):
        raise SystemExit(f"未知部分：{parts - set(PARTS)}")

    samples = load_all_samples()
    if not samples:
        raise SystemExit("data/samples/ 下还没有校对好的样本")
    train = [s for s in samples if not is_eval(s)]
    BUILD.mkdir(exist_ok=True)
    write_jsonl(BUILD / "eval.jsonl", [s for s in samples if is_eval(s)])
    print(f"样本 {len(samples)} 条：训练 {len(train)}，评测 {len(samples) - len(train)} → build/eval.jsonl")

    by_scene = defaultdict(list)
    for s in train:
        by_scene[s["scene"]].append(s)
    rng = random.Random(42)

    def call(name, prompt, temperature):
        if args.dry_run:
            (BUILD / "prompts").mkdir(exist_ok=True)
            (BUILD / "prompts" / f"{name}.txt").write_text(prompt, encoding="utf-8")
            print(f"  [dry-run] {name}: {len(prompt)} 字")
            return f"（dry-run 占位：{name}）"
        print(f"  [LLM] {name}")
        return llm(prompt, temperature=temperature).strip()

    def write_ref(filename, title, body):
        if args.dry_run:
            return
        REFS.mkdir(parents=True, exist_ok=True)
        (REFS / filename).write_text(f"{HEADER}# {title}\n\n{body}\n", encoding="utf-8")
        print(f"  → references/{filename}")

    analyses = {}
    if parts & {"scenarios", "voice"}:
        print("\n[场景分析]")
        for scene in SCENES:
            items = by_scene.get(scene, [])
            if len(items) < MIN_SCENE_SAMPLES:
                print(f"  {scene}: 只有 {len(items)} 条，跳过")
                continue
            chosen = pick_diverse(items, MAX_ANALYSIS_PER_SCENE, rng)
            analyses[scene] = call(f"scene_{scene}", load_prompt(
                "scene_analysis", scene=scene, samples="\n".join(map(compact, chosen))), 0.5)

    if "scenarios" in parts:
        body = "\n\n".join(f"## {scene}\n\n{text}" for scene, text in analyses.items())
        write_ref("scenarios.md", "各场景回应策略", body or "（样本不足，暂无）")

    if "voice" in parts:
        print("\n[整体风格]")
        merged = "\n\n".join(f"## {scene}\n\n{text}" for scene, text in analyses.items())
        out = call("voice", load_prompt("merge_voice", scene_analyses=merged,
                                        catchphrase_stats=render_stats(train)), 0.5)
        write_ref("voice.md", "语言风格", out)

    if "memes" in parts:
        print("\n[梗词典]")
        noted = [s for s in train if s.get("note")]
        if noted:
            noted = rng.sample(noted, min(len(noted), MAX_MEME_SAMPLES))
            out = call("memes", load_prompt("memes", samples="\n".join(map(compact, noted))), 0.3)
            write_ref("memes.md", "梗词典", out)
        else:
            print("  没有带 note 的样本，跳过")

    if "background" in parts:
        print("\n[人物背景]")
        personal = by_scene.get("个人经历", [])
        sources = BG_SOURCES.read_text(encoding="utf-8") if BG_SOURCES.exists() else ""
        if personal or sources.strip():
            out = call("background", load_prompt(
                "background", personal_samples="\n".join(map(compact, personal)) or "（无）",
                other_sources=sources or "（无）"), 0.3)
            write_ref("background.md", "人物背景", out)
        else:
            print("  没有「个人经历」样本，也没有 data/background_sources.md，跳过")

    if "examples" in parts and not args.dry_run:
        print("\n[示例样本]")
        for scene, items in by_scene.items():
            chosen = pick_diverse(items, EXAMPLES_PER_SCENE, rng)
            write_jsonl(REFS / "examples" / f"{scene}.jsonl",
                        [{k: s[k] for k in ("id", "context", "reply", "tags")} for s in chosen])
            print(f"  → references/examples/{scene}.jsonl（{len(chosen)} 条）")


if __name__ == "__main__":
    main()
