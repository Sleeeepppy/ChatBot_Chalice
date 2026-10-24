"""把 B 站合集 / UP 主空间 / 单个视频加入 clips.csv（按 BV 号去重）。

用法:
  python scripts/fetch_list.py <URL> [<URL> ...] [--keyword Chalice] [--cookies-from-browser chrome]
"""
import argparse

import yt_dlp

from common import read_clips, write_clips


def flatten(info):
    if info.get("_type") in ("playlist", "multi_video"):
        for e in info.get("entries") or []:
            if e:
                yield from flatten(e)
    else:
        yield info


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("urls", nargs="+")
    ap.add_argument("--keyword", help="只保留标题包含该关键词的视频")
    ap.add_argument("--cookies-from-browser", help="chrome / edge / firefox，空间页常需登录")
    args = ap.parse_args()

    opts = {"extract_flat": "in_playlist", "quiet": True, "skip_download": True}
    if args.cookies_from_browser:
        opts["cookiesfrombrowser"] = (args.cookies_from_browser,)

    rows = read_clips()
    known = {r["bv"] for r in rows}
    added = 0
    with yt_dlp.YoutubeDL(opts) as ydl:
        for url in args.urls:
            for e in flatten(ydl.extract_info(url, download=False)):
                bv, title = e.get("id"), (e.get("title") or "").replace("\n", " ")
                if not bv or bv in known:
                    continue
                if args.keyword and args.keyword not in title:
                    continue
                link = e.get("webpage_url") or e.get("url") or f"https://www.bilibili.com/video/{bv}"
                rows.append({"bv": bv, "title": title, "url": link, "owner": "",
                             "status": "todo", "chalice_spk": "", "notes": ""})
                known.add(bv)
                added += 1
    write_clips(rows)
    print(f"新增 {added} 条，clips.csv 共 {len(rows)} 条")


if __name__ == "__main__":
    main()
