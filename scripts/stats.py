"""统计所有 reply 里的高频片段和句尾语气词，帮助找口头禅 → build/catchphrases.md

用法:
  python scripts/stats.py [--top 80]
"""
import argparse
import re
from collections import Counter

from common import BUILD, load_all_samples

# 太通用、不算口头禅的词
STOPWORDS = set("""
的 了 是 我 你 他 她 它 我们 你们 他们 这 那 这个 那个 就 都 也 还 在 有 和 跟 把 被 给 让 对 吧 吗 呢 啊 呀 哦 嗯
一个 一下 什么 怎么 为什么 没有 不是 可以 就是 然后 但是 因为 所以 如果 现在 时候 自己 这样 那样 知道 觉得 东西
""".split())
PARTICLES = set("啊吧呢吗嘛呀哦哇啦咯噢诶哈嗯哎")
SENT_SPLIT = re.compile(r"[，。！？!?,.、…\s~～]+")


def ngram_stats(replies, max_n=3, min_df=3, top=80):
    import jieba
    jieba.setLogLevel(60)
    df = Counter()
    for reply in replies:
        seen = set()
        for sent in SENT_SPLIT.split(reply):
            words = [w for w in jieba.lcut(sent) if w.strip()]
            for n in range(1, max_n + 1):
                for i in range(len(words) - n + 1):
                    gram = words[i:i + n]
                    text = "".join(gram)
                    if 2 <= len(text) <= 8 and not all(w in STOPWORDS for w in gram):
                        seen.add(text)
        df.update(seen)  # 按「出现在多少条样本里」计数，避免一条复读刷高
    grams = [(g, c) for g, c in df.items() if c >= min_df]
    # 长片段几乎总带着短片段出现时，只保留长的
    keep = []
    for g, c in sorted(grams, key=lambda x: -len(x[0])):
        if not any(g in k and kc >= 0.8 * c for k, kc in keep):
            keep.append((g, c))
    return sorted(keep, key=lambda x: -x[1])[:top]


def particle_stats(replies):
    cnt = Counter()
    for reply in replies:
        for sent in SENT_SPLIT.split(reply):
            if sent and sent[-1] in PARTICLES:
                cnt[sent[-1]] += 1
    return cnt.most_common()


def render(samples, top=80):
    replies = [s["reply"] for s in samples]
    lines = [f"共 {len(replies)} 条 reply\n", "### 高频片段（按出现的样本数）\n", "| 片段 | 样本数 |", "|---|---|"]
    lines += [f"| {g} | {c} |" for g, c in ngram_stats(replies, min_df=max(3, len(replies) // 200), top=top)]
    lines += ["\n### 句尾语气词\n", "| 语气词 | 次数 |", "|---|---|"]
    lines += [f"| {p} | {c} |" for p, c in particle_stats(replies)]
    return "\n".join(lines)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--top", type=int, default=80)
    args = ap.parse_args()
    samples = load_all_samples()
    if not samples:
        raise SystemExit("data/samples/ 下还没有校对好的样本")
    BUILD.mkdir(exist_ok=True)
    out = BUILD / "catchphrases.md"
    out.write_text(render(samples, args.top), encoding="utf-8")
    print(f"→ {out}")


if __name__ == "__main__":
    main()
