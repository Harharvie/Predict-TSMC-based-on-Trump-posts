#!/usr/bin/env python3
"""每日 X 總結 Thread — 自動發到 @trumpcodeai

每天 UTC 22:00（JST 07:00）自動執行：
1. 讀當天的 pipeline log + flash meta
2. 統計：幾篇推文、幾個信號、方向分佈
3. 發一則總結 Thread：主推（英文統計）+ 回覆（中文摘要）+ 回覆（日文摘要）

用法：
  python3 x_daily_summary.py              # 發今天的總結
  python3 x_daily_summary.py 2026-03-25   # 發指定日期
  python3 x_daily_summary.py --dry-run    # 只顯示不發
"""

import json
import glob
import sys
import time
import random
from datetime import datetime, timezone, timedelta
from pathlib import Path

BASE = Path(__file__).parent

def log(msg):
    ts = datetime.now(timezone.utc).strftime("%H:%M:%S")
    print(f"[{ts}] {msg}")


def collect_day_data(target_date: str) -> dict:
    """收集指定日期的所有推文資料。

    Returns:
        {
            "date": "2026-03-25",
            "posts": [...pipeline entries...],
            "flash_metas": [...meta dicts...],
            "total_posts": int,
            "signal_posts": int,
            "signals": {"TARIFF": 3, "BULLISH": 2, ...},
            "directions": {"UP": 1, "DOWN": 2, "NEUTRAL": 5},
        }
    """
    # 從 pipeline log 收集當天的 entries
    pipeline_file = BASE / "data" / "rss_pipeline_log.json"
    posts = []
    if pipeline_file.exists():
        all_entries = json.loads(pipeline_file.read_text())
        for entry in all_entries:
            # pub_time 格式："Wed, 25 Mar 2026 03:45:21 +0000"
            pub = entry.get("pub_time", "")
            if target_date.replace("-", "") in pub.replace(" ", "").replace(",", ""):
                posts.append(entry)
            # 也用 detected_at 比對（更可靠）
            elif entry.get("detected_at", "").startswith(target_date):
                if entry not in posts:
                    posts.append(entry)

    # 從 flash meta 檔案收集
    day_str = target_date.split("-")[-1]  # "25"
    month_dir = BASE / "articles" / target_date[:7]  # "articles/2026-03"
    flash_metas = []
    if month_dir.exists():
        for meta_file in sorted(month_dir.glob(f"{day_str}-flash-*-meta.json")):
            try:
                flash_metas.append(json.loads(meta_file.read_text()))
            except Exception:
                pass

    # 統計信號
    signal_counts = {}
    direction_counts = {"UP": 0, "DOWN": 0, "NEUTRAL": 0}
    signal_posts = 0

    for p in posts:
        sigs = p.get("signals", [])
        if sigs:
            signal_posts += 1
        for s in sigs:
            signal_counts[s] = signal_counts.get(s, 0) + 1
        d = p.get("direction", "NEUTRAL")
        direction_counts[d] = direction_counts.get(d, 0) + 1

    return {
        "date": target_date,
        "posts": posts,
        "flash_metas": flash_metas,
        "total_posts": len(posts),
        "signal_posts": signal_posts,
        "signals": signal_counts,
        "directions": direction_counts,
    }


def build_thread_texts(data: dict) -> list[dict]:
    """組三語 Thread 文案。

    Returns:
        [
            {"lang": "en", "text": "..."},
            {"lang": "zh", "text": "..."},
            {"lang": "ja", "text": "..."},
        ]
    """
    d = data["date"]
    total = data["total_posts"]
    sig_posts = data["signal_posts"]
    signals = data["signals"]
    directions = data["directions"]

    if total == 0:
        return []  # 今天沒推文，不發

    # 排序信號（出現次數多的在前）
    top_signals = sorted(signals.items(), key=lambda x: -x[1])[:5]
    sig_str = " | ".join(f"{s} ×{c}" for s, c in top_signals) if top_signals else "None detected"

    # 方向統計
    dir_parts = []
    for d_name, emoji in [("UP", "📈"), ("DOWN", "📉"), ("NEUTRAL", "➡️")]:
        count = directions.get(d_name, 0)
        if count > 0:
            dir_parts.append(f"{emoji}{count}")
    dir_str = " ".join(dir_parts)

    # 找今天最高信心度的推文
    top_post = None
    top_conf = 0
    for p in data["posts"]:
        conf = p.get("confidence") or 0
        if conf > top_conf:
            top_conf = conf
            top_post = p

    # --- 英文主推 ---
    en = f"📊 Trump Code Daily | {d}\n\n"
    en += f"🔍 {total} posts scanned"
    if sig_posts > 0:
        en += f" → {sig_posts} with market signals"
    en += f"\n\n{dir_str}\n"
    en += f"Signals: {sig_str}\n"
    if top_post and top_conf > 0.5:
        preview = top_post.get("content_preview", "")[:60]
        en += f"\n🔥 Top: \"{preview}...\"\n"
    en += f"\nFull reports → trumpcode.washinmura.jp"

    # --- 中文回覆 ---
    zh = f"🇹🇼 {d} 每日總結\n\n"
    zh += f"今日川普發了 {total} 則"
    if sig_posts > 0:
        zh += f"，{sig_posts} 則有市場信號"
    zh += f"\n{dir_str}\n"
    if top_signals:
        zh_sigs = "、".join(f"{s}({c}次)" for s, c in top_signals[:3])
        zh += f"關鍵信號：{zh_sigs}\n"
    zh += f"\n完整分析 → trumpcode.washinmura.jp"

    # --- 日文回覆 ---
    ja = f"🇯🇵 {d} デイリーまとめ\n\n"
    ja += f"本日のトランプ投稿：{total} 件"
    if sig_posts > 0:
        ja += f"（{sig_posts} 件に市場シグナル）"
    ja += f"\n{dir_str}\n"
    if top_signals:
        ja_sigs = "・".join(f"{s}({c}回)" for s, c in top_signals[:3])
        ja += f"主要シグナル：{ja_sigs}\n"
    ja += f"\n詳細分析 → trumpcode.washinmura.jp"

    return [
        {"lang": "en", "text": en},
        {"lang": "zh", "text": zh},
        {"lang": "ja", "text": ja},
    ]


def post_daily_thread(target_date: str = None, dry_run: bool = False) -> dict:
    """收集當日資料 → 組文案 → 發三語 Thread。"""
    if not target_date:
        target_date = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    log(f"📊 每日總結：{target_date}")

    # 收集資料
    data = collect_day_data(target_date)
    log(f"   推文 {data['total_posts']} 則，信號 {data['signal_posts']} 則")

    if data["total_posts"] == 0:
        log("   今天沒有推文，跳過")
        return {"ok": False, "error": "No posts today"}

    # 組文案
    texts = build_thread_texts(data)
    for t in texts:
        log(f"   [{t['lang']}] {len(t['text'])} chars")

    if dry_run:
        for t in texts:
            print(f"\n=== {t['lang'].upper()} ===")
            print(t["text"])
        return {"ok": True, "dry_run": True}

    # 發推
    from x_poster import post_tweet

    # 主推（英文）
    main = post_tweet(texts[0]["text"])
    if not main.get("ok"):
        log(f"   ❌ 主推失敗: {main.get('error', '')[:80]}")
        return main

    results = [{"lang": "en", "tweet_id": main["tweet_id"], "url": main["url"]}]
    main_id = main["tweet_id"]
    log(f"   🐦 EN: {main['url']}")

    # 回覆（中文、日文）
    for t in texts[1:]:
        time.sleep(random.uniform(3, 8))
        r = post_tweet(t["text"], reply_to=main_id)
        if r.get("ok"):
            results.append({"lang": t["lang"], "tweet_id": r["tweet_id"], "url": r["url"]})
            log(f"   🐦 {t['lang'].upper()}: {r['url']}")
        else:
            log(f"   ⚠️ {t['lang'].upper()} 失敗: {r.get('error', '')[:60]}")

    log(f"   ✅ Thread {len(results)}/3 則發出")
    return {"ok": True, "tweets": results, "main_url": main["url"]}


if __name__ == "__main__":
    dry_run = "--dry-run" in sys.argv
    target = None
    for arg in sys.argv[1:]:
        if arg.startswith("20") and len(arg) == 10:
            target = arg

    result = post_daily_thread(target_date=target, dry_run=dry_run)
    if not dry_run:
        print(json.dumps(result, ensure_ascii=False, indent=2))
