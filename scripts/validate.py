"""检查样本格式，并找出 reply 和转写原文对不上的条目（多半是被 LLM 润色了）。

用法:
  python scripts/validate.py            # 检查所有已校对样本（提 PR 前跑一遍）
  python scripts/validate.py --drafts   # 同时检查草稿，校对时用
  python scripts/validate.py BV1xxx     # 只检查指定切片
"""
import argparse
import json
import sys
from difflib import SequenceMatcher

from common import SAMPLES, SCENES, TAGS, TRANSCRIPTS, normalize_text, read_jsonl, sample_files

VERBATIM_THRESHOLD = 0.9  # reply 中能在转写里按顺序找到的字符比例


def coverage(reply, transcript):
    """在转写里找最像 reply 的一段（窗口为 reply 两倍长），返回 reply 被覆盖的字符比例。"""
    r = normalize_text(reply)
    if not r or r in transcript:
        return 1.0
    width, step, best = len(r) * 2, max(1, len(r) // 2), 0.0
    for i in range(0, max(1, len(transcript) - len(r) + 1), step):
        blocks = SequenceMatcher(None, r, transcript[i:i + width], autojunk=False).get_matching_blocks()
        best = max(best, sum(b.size for b in blocks) / len(r))
    return best


def check_record(rec, ids):
    errs = []
    for key in ("id", "bv", "scene", "context", "reply", "tags"):
        if key not in rec:
            errs.append(f"缺少字段 {key}")
    if errs:
        return errs
    if rec["id"] in ids:
        errs.append(f"id 重复：{rec['id']}")
    ids.add(rec["id"])
    if rec["scene"] not in SCENES:
        errs.append(f"scene 不在分类表里：{rec['scene']}")
    if not isinstance(rec["tags"], list) or any(t not in TAGS for t in rec["tags"]):
        errs.append(f"tags 有不在列表里的：{rec['tags']}")
    if not str(rec["reply"]).strip():
        errs.append("reply 为空")
    ctx = rec["context"]
    if not isinstance(ctx, dict) or not isinstance(ctx.get("others", []), list):
        errs.append("context 格式不对")
    return errs


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("bv", nargs="*")
    ap.add_argument("--drafts", action="store_true")
    args = ap.parse_args()

    files = sample_files()
    if args.drafts:
        files += sorted(SAMPLES.glob("*.draft.jsonl"))
    if args.bv:
        files = [f for f in files if f.name.split(".")[0] in args.bv]

    n_err = n_warn = n_rec = 0
    ids = set()
    for f in files:
        bv = f.name.split(".")[0]
        try:
            recs = read_jsonl(f)
        except ValueError as e:
            print(f"✗ {e}")
            n_err += 1
            continue
        tfile = TRANSCRIPTS / f"{bv}.json"
        transcript = (normalize_text("".join(s["text"] for s in json.loads(tfile.read_text(encoding="utf-8"))))
                      if tfile.exists() else None)
        for rec in recs:
            n_rec += 1
            # 草稿和校对版可能同时存在，id 去重只在同类文件间做
            for e in check_record(rec, ids if not f.name.endswith(".draft.jsonl") else set()):
                print(f"✗ {f.name} {rec.get('id', '?')}: {e}")
                n_err += 1
            if transcript is not None and rec.get("reply"):
                c = coverage(rec["reply"], transcript)
                if c < VERBATIM_THRESHOLD:
                    print(f"⚠ {f.name} {rec.get('id', '?')}: reply 与转写只对上 {c:.0%}，检查是否被改写：{rec['reply'][:40]}")
                    n_warn += 1
        if transcript is None:
            print(f"⚠ {f.name}: 没有对应转写，跳过原话比对")

    print(f"\n{len(files)} 个文件，{n_rec} 条样本，{n_err} 个错误，{n_warn} 个警告")
    print("（警告不一定是错：手动修正过 ASR 错字的 reply 也会对不上）")
    sys.exit(1 if n_err else 0)


if __name__ == "__main__":
    main()
