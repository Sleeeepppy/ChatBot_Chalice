"""下载切片音频（wav）和弹幕 / AI 字幕到 raw/。

用法:
  python scripts/download.py --owner 小明 [--cookies-from-browser chrome]
  python scripts/download.py BV1xxx BV1yyy
"""
import argparse
import shutil
import sys

import yt_dlp

from common import RAW, add_clip_args, read_clips, select_clips


def main():
    ap = argparse.ArgumentParser()
    add_clip_args(ap)
    ap.add_argument("--cookies-from-browser", help="chrome / edge / firefox，用于拿 AI 字幕和高码率")
    ap.add_argument("--no-subs", action="store_true", help="不下载弹幕和字幕")
    args = ap.parse_args()

    if not shutil.which("ffmpeg"):
        sys.exit("找不到 ffmpeg，请先安装并加入 PATH")
    RAW.mkdir(exist_ok=True)

    failed = []
    for row in select_clips(args, read_clips()):
        bv = row["bv"]
        if (RAW / f"{bv}.wav").exists():
            print(f"[跳过] {bv} 已存在")
            continue
        opts = {
            "format": "bestaudio/best",
            "outtmpl": str(RAW / f"{bv}.%(ext)s"),
            "noplaylist": True,
            "postprocessors": [{"key": "FFmpegExtractAudio", "preferredcodec": "wav"}],
        }
        if not args.no_subs:
            opts.update({"writesubtitles": True, "subtitleslangs": ["danmaku", "ai-zh"]})
        if args.cookies_from_browser:
            opts["cookiesfrombrowser"] = (args.cookies_from_browser,)
        print(f"[下载] {bv} {row['title']}")
        try:
            with yt_dlp.YoutubeDL(opts) as ydl:
                ydl.download([row["url"] or f"https://www.bilibili.com/video/{bv}"])
        except yt_dlp.utils.DownloadError as e:
            print(f"  失败：{e}")
            failed.append(bv)
    if failed:
        print(f"\n失败 {len(failed)} 个：{' '.join(failed)}")


if __name__ == "__main__":
    main()
