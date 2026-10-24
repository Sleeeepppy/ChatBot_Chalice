"""用 DeepSeek 把转写起草成样本 → data/samples/<BV>.draft.jsonl（不进 git）。

人工逐条校对后，把文件改名为 <BV>.jsonl 再提交。

用法:
  python scripts/annotate.py --owner 小明
  python scripts/annotate.py BV1xxx [--force]
"""
import argparse
import json

from common import (SAMPLES, SCENES, TAGS, TRANSCRIPTS, add_clip_args, format_transcript,
                    llm, load_prompt, parse_jsonl_loose, read_clips, select_clips, write_jsonl)

CHUNK_LINES = 250  # 每次喂给 LLM 的转写行数


def clean(rec, bv, idx):
    ctx = rec.get("context") if isinstance(rec.get("context"), dict) else {}
    others = ctx.get("others") if isinstance(ctx.get("others"), list) else []
    note = str(rec.get("note") or "")
    scene = rec.get("scene")
    if scene not in SCENES:
        note = f"[LLM 给的场景：{scene}] {note}".strip()
        scene = "其他"
    tags = rec.get("tags") or []
    if isinstance(tags, str):
        tags = tags.replace("，", " ").replace(",", " ").split()
    tags = [t for t in tags if t in TAGS]
    return {
        "id": f"{bv}-{idx:03d}",
        "bv": bv,
        "t": str(rec.get("t") or ""),
        "scene": scene,
        "context": {
            "game": str(ctx.get("game") or ""),
            "danmaku": str(ctx.get("danmaku") or ""),
            "others": [{"who": str(o.get("who") or ""), "text": str(o.get("text") or "")}
                       for o in others if isinstance(o, dict)],
            "prev": str(ctx.get("prev") or ""),
        },
        "reply": str(rec.get("reply") or "").strip(),
        "tags": tags,
        "note": note,
    }


def main():
    ap = argparse.ArgumentParser()
    add_clip_args(ap)
    ap.add_argument("--force", action="store_true", help="已有校对版也重新起草")
    args = ap.parse_args()

    for row in select_clips(args, read_clips()):
        bv = row["bv"]
        tfile = TRANSCRIPTS / f"{bv}.json"
        if not tfile.exists():
            print(f"[跳过] {bv} 还没转写")
            continue
        if (SAMPLES / f"{bv}.jsonl").exists() and not args.force:
            print(f"[跳过] {bv} 已有校对版样本")
            continue
        if not row["chalice_spk"]:
            print(f"[跳过] {bv} 的 chalice_spk 没填")
            continue

        lines = format_transcript(json.loads(tfile.read_text(encoding="utf-8")), row["chalice_spk"])
        recs = []
        for i in range(0, len(lines), CHUNK_LINES):
            chunk = "\n".join(lines[i:i + CHUNK_LINES])
            print(f"[起草] {bv} 第 {i // CHUNK_LINES + 1} 段")
            out = llm(load_prompt("annotate", title=row["title"], transcript=chunk), temperature=0.3)
            recs.extend(r for r in parse_jsonl_loose(out) if r.get("reply"))
        recs = [clean(r, bv, i) for i, r in enumerate(recs, 1)]
        dst = SAMPLES / f"{bv}.draft.jsonl"
        write_jsonl(dst, recs)
        print(f"  {len(recs)} 条 → {dst.relative_to(SAMPLES.parent.parent)}，校对后改名为 {bv}.jsonl")


if __name__ == "__main__":
    main()
