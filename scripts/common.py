"""各脚本共用的路径、常量和工具函数。"""
import csv
import json
import os
import re
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / "raw"
TRANSCRIPTS = ROOT / "data" / "transcripts"
SAMPLES = ROOT / "data" / "samples"
HOTWORDS = ROOT / "data" / "hotwords.txt"
BG_SOURCES = ROOT / "data" / "background_sources.md"
PROMPTS = ROOT / "prompts"
SKILL_DIR = ROOT / "skill" / "chalice-persona"
REFS = SKILL_DIR / "references"
BUILD = ROOT / "build"
CLIPS_CSV = ROOT / "clips.csv"

# 改这两个列表前先在 Issue 里讨论，改完同步 docs/extraction-guide.md
SCENES = ["读弹幕回应", "被嘲讽回击", "高光时刻", "失误翻车", "吐槽队友",
          "吐槽对手", "连麦闲聊", "游戏讲解", "个人经历", "其他"]
TAGS = ["自嘲", "阴阳怪气", "夸张", "嘴硬", "甩锅", "认真", "破防", "装傻",
        "反问", "复读", "玩梗", "骂人", "讲道理", "转移话题"]

CLIP_FIELDS = ["bv", "title", "url", "owner", "status", "chalice_spk", "notes"]
STATUSES = ["todo", "claimed", "transcribed", "annotated", "reviewed"]

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")


# ---------- clips.csv ----------

def read_clips():
    if not CLIPS_CSV.exists():
        return []
    with CLIPS_CSV.open(encoding="utf-8-sig", newline="") as f:
        return [{k: (row.get(k) or "").strip() for k in CLIP_FIELDS} for row in csv.DictReader(f)]


def write_clips(rows):
    with CLIPS_CSV.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=CLIP_FIELDS)
        w.writeheader()
        w.writerows(rows)


def add_clip_args(parser):
    parser.add_argument("bv", nargs="*", help="BV 号；不填则用 --owner 筛选")
    parser.add_argument("--owner", help="处理 clips.csv 里认领人是这个名字的全部切片")


def select_clips(args, rows):
    if args.bv:
        wanted = set(args.bv)
        picked = [r for r in rows if r["bv"] in wanted]
        missing = wanted - {r["bv"] for r in picked}
        if missing:
            sys.exit(f"clips.csv 里没有：{', '.join(sorted(missing))}")
        return picked
    if args.owner:
        return [r for r in rows if r["owner"] == args.owner]
    sys.exit("请指定 BV 号或 --owner")


def bump_status(row, status):
    """只往前推进状态，不回退。"""
    cur = row["status"] if row["status"] in STATUSES else "todo"
    if STATUSES.index(status) > STATUSES.index(cur):
        row["status"] = status


# ---------- JSONL ----------

def read_jsonl(path):
    out = []
    with Path(path).open(encoding="utf-8") as f:
        for i, line in enumerate(f, 1):
            line = line.strip()
            if line:
                try:
                    out.append(json.loads(line))
                except json.JSONDecodeError as e:
                    raise ValueError(f"{path}:{i} 不是合法 JSON：{e}") from None
    return out


def write_jsonl(path, records):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as f:
        for r in records:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")


def parse_jsonl_loose(text):
    """解析 LLM 输出的 JSONL，容忍代码块和杂行。"""
    out = []
    for line in text.splitlines():
        line = line.strip().rstrip(",")
        if line.startswith("{"):
            try:
                out.append(json.loads(line))
            except json.JSONDecodeError:
                pass
    return out


def sample_files():
    """已校对的样本文件（不含 *.draft.jsonl）。"""
    return sorted(p for p in SAMPLES.glob("*.jsonl") if not p.name.endswith(".draft.jsonl"))


def load_all_samples():
    samples = []
    for p in sample_files():
        samples.extend(read_jsonl(p))
    return samples


# ---------- 转写 ----------

def mmss(ms):
    s = int(ms) // 1000
    return f"{s // 60:02d}:{s % 60:02d}"


def format_transcript(sentences, chalice_spk):
    lines = []
    for s in sentences:
        who = "Chalice" if str(s["spk"]) == str(chalice_spk) else f"其他人{s['spk']}"
        lines.append(f"[{mmss(s['start_ms'])}] {who}: {s['text']}")
    return lines


def normalize_text(s):
    """去掉标点空白，用于比对原话。"""
    return re.sub(r"[\W_]+", "", s).lower()


# ---------- 提示词 / LLM ----------

def load_prompt(name, **vars):
    text = (PROMPTS / f"{name}.txt").read_text(encoding="utf-8")
    vars.setdefault("scenes", " / ".join(SCENES))
    vars.setdefault("tags", " ".join(TAGS))
    for k, v in vars.items():
        text = text.replace("{{" + k + "}}", str(v))
    left = re.findall(r"\{\{(\w+)\}\}", text)
    if left:
        raise ValueError(f"提示词 {name} 缺少变量：{left}")
    return text


def _load_env():
    env_file = ROOT / ".env"
    if env_file.exists():
        for line in env_file.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


_client = None


def llm(messages, temperature=0.7, retries=3):
    """调用 DeepSeek（OpenAI 兼容接口）。messages 可以是字符串（当作单条 user 消息）。"""
    global _client
    if _client is None:
        _load_env()
        key = os.environ.get("DEEPSEEK_API_KEY")
        if not key:
            sys.exit("缺少 DEEPSEEK_API_KEY：复制 .env.example 为 .env 并填入")
        from openai import OpenAI
        _client = OpenAI(api_key=key, base_url=os.environ.get("DEEPSEEK_BASE_URL", "https://api.deepseek.com"))
    if isinstance(messages, str):
        messages = [{"role": "user", "content": messages}]
    model = os.environ.get("DEEPSEEK_MODEL", "deepseek-chat")
    for attempt in range(retries):
        try:
            resp = _client.chat.completions.create(model=model, messages=messages, temperature=temperature)
            return resp.choices[0].message.content or ""
        except Exception as e:  # 网络抖动、限流等，退避重试
            if attempt == retries - 1:
                raise
            print(f"  LLM 调用失败（{e}），{2 ** attempt * 5}s 后重试")
            time.sleep(2 ** attempt * 5)
