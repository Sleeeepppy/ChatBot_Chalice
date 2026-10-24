"""用 FunASR 转写 raw/<BV>.wav → data/transcripts/<BV>.json，并猜测哪个说话人是 Chalice。

用法:
  python scripts/transcribe.py --owner 小明
  python scripts/transcribe.py BV1xxx [--force]

转写完一定要检查 clips.csv 里自动填的 chalice_spk 对不对。
"""
import argparse
import json
from collections import defaultdict

from common import (HOTWORDS, RAW, TRANSCRIPTS, add_clip_args, bump_status, mmss,
                    read_clips, select_clips, write_clips)


def load_model():
    import torch
    from funasr import AutoModel
    return AutoModel(
        model="paraformer-zh",
        vad_model="fsmn-vad",
        punc_model="ct-punc",
        spk_model="cam++",  # 说话人区分
        device="cuda:0" if torch.cuda.is_available() else "cpu",
        disable_update=True,
    )


def speaker_summary(sentences):
    dur, lines = defaultdict(int), defaultdict(list)
    for s in sentences:
        dur[s["spk"]] += s["end_ms"] - s["start_ms"]
        if len(lines[s["spk"]]) < 3:
            lines[s["spk"]].append(f"[{mmss(s['start_ms'])}] {s['text']}")
    return sorted(dur, key=dur.get, reverse=True), dur, lines


def main():
    ap = argparse.ArgumentParser()
    add_clip_args(ap)
    ap.add_argument("--force", action="store_true", help="覆盖已有转写")
    args = ap.parse_args()

    rows = read_clips()
    todo = []
    for r in select_clips(args, rows):
        if not args.force and (TRANSCRIPTS / f"{r['bv']}.json").exists():
            continue
        if not (RAW / f"{r['bv']}.wav").exists():
            print(f"[跳过] {r['bv']} 没有音频，先运行 download.py")
            continue
        todo.append(r)
    if not todo:
        print("没有需要转写的切片")
        return

    hotword = " ".join(HOTWORDS.read_text(encoding="utf-8").split()) if HOTWORDS.exists() else ""
    model = load_model()
    TRANSCRIPTS.mkdir(parents=True, exist_ok=True)

    for row in todo:
        bv = row["bv"]
        print(f"\n[转写] {bv} {row['title']}")
        res = model.generate(input=str(RAW / f"{bv}.wav"), batch_size_s=300, hotword=hotword)
        sentences = [{"start_ms": s["start"], "end_ms": s["end"], "spk": s.get("spk", 0), "text": s["text"]}
                     for s in res[0].get("sentence_info", [])]
        (TRANSCRIPTS / f"{bv}.json").write_text(
            json.dumps(sentences, ensure_ascii=False, indent=1), encoding="utf-8")

        order, dur, lines = speaker_summary(sentences)
        for spk in order:
            print(f"  spk{spk}: {dur[spk] / 1000:.0f}s")
            for l in lines[spk]:
                print(f"      {l}")
        if order and not row["chalice_spk"]:
            row["chalice_spk"] = str(order[0])  # 主播通常说话最多
            print(f"  → 暂定 Chalice = spk{order[0]}（说话最多），不对请改 clips.csv")
        bump_status(row, "transcribed")
        write_clips(rows)


if __name__ == "__main__":
    main()
