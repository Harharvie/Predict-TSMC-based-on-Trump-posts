#!/usr/bin/env python3
"""
川普密碼 — X vs Truth Social 落差分析器
比較他在 X 和 Truth Social 上發的文，找出「落差」

核心假設：
  Truth Social = 講真話給自己人（內部信號）
  X = 對外向大眾放話（公開訊息）
  落差 = 他選擇不讓全世界看到的 = 密碼

方法：
  1. 從 X embed API 抓他第二任所有 X 推文（不需 API key）
  2. 和 Truth Social 比對
  3. 找出「只在 Truth Social、沒有放到 X」的推文
  4. 分析這些「隱藏推文」的特徵

用法:
  python3 x_truth_gap.py             # 完整比對
  python3 x_truth_gap.py --scan      # 掃描他最新的 X 推文
"""

import json
import re
import sys
import time
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from collections import defaultdict

BASE = Path(__file__).parent
DATA = BASE / "data"
X_ARCHIVE = DATA / "x_posts.json"
GAP_REPORT = DATA / "x_truth_gap.json"


def log(msg):
    print(f"[{datetime.now(timezone.utc).strftime('%H:%M:%S')}] {msg}", flush=True)


def fetch_x_post(tweet_id):
    """用 X embed API 抓單篇推文（公開，不需 API key）"""
    try:
        url = f'https://cdn.syndication.twimg.com/tweet-result?id={tweet_id}&token=0'
        req = urllib.request.Request(url, headers={
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)',
        })
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode('utf-8'))

        return {
            'id': tweet_id,
            'created_at': data.get('created_at', ''),
            'text': data.get('text', ''),
            'lang': data.get('lang', ''),
            'favorite_count': data.get('favorite_count', 0),
            'conversation_count': data.get('conversation_count', 0),
            'source': 'x',
        }
    except Exception:
        return None


def scan_x_timeline():
    """
    掃描 Trump 在 X 上的推文
    策略：從已知推文 ID 附近掃描，找出所有推文
    X 的推文 ID 是遞增的 snowflake ID
    """
    log("🔍 掃描 Trump 的 X 推文...")

    # 已知的推文 ID（從搜尋結果收集）
    known_ids = [
        '1892242622623699357',  # 2025-02-19
        '1907782254572470670',  # 2025-04-03
        '1936573183634645387',  # 2025-06-21
        '1965947311718269341',  # 2025-09-10
        '1972822596397003159',  # 2025-09-29
        '1973218518893207825',  # 2025-10-01
        '2004012442427277591',  # 2025-12-25
    ]

    # 載入已有的
    existing = {}
    if X_ARCHIVE.exists():
        with open(X_ARCHIVE, encoding='utf-8') as f:
            data = json.load(f)
            existing = {p['id']: p for p in data.get('posts', [])}

    # 先抓已知的
    for tid in known_ids:
        if tid not in existing:
            post = fetch_x_post(tid)
            if post and post['text']:
                existing[tid] = post
                log(f"   ✅ {post['created_at'][:16]} | {post['text'][:60]}...")
            time.sleep(0.5)

    # 從已知 ID 附近搜索（向前向後掃）
    # X snowflake ID 大約每秒 +4096
    # 一天 ≈ 4096 * 86400 ≈ 353M
    # 一個月 ≈ 10.6B

    sorted_ids = sorted(int(i) for i in existing.keys())

    if sorted_ids:
        log(f"   已有 {len(sorted_ids)} 篇，掃描附近...")

        # 在每個已知 ID 前後小範圍掃描
        scan_count = 0
        found = 0

        for known_id in sorted_ids:
            # 往前掃 20 個 ID
            for offset in range(-20, 21):
                test_id = str(known_id + offset)
                if test_id in existing:
                    continue

                post = fetch_x_post(test_id)
                scan_count += 1

                if post and post['text']:
                    existing[test_id] = post
                    found += 1
                    log(f"   🆕 {post['created_at'][:16]} | {post['text'][:60]}...")

                time.sleep(0.3)

                # 節制：每個 known_id 最多掃 40 個
                if scan_count > 40 * len(sorted_ids):
                    break

        log(f"   掃描 {scan_count} 個 ID，新發現 {found} 篇")

    # 存檔
    posts = sorted(existing.values(), key=lambda p: p.get('created_at', ''))
    with open(X_ARCHIVE, 'w', encoding='utf-8') as f:
        json.dump({
            'updated_at': datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ'),
            'total_posts': len(posts),
            'posts': posts,
        }, f, ensure_ascii=False, indent=2)

    log(f"   💾 X 推文庫: {len(posts)} 篇")
    return posts


def compare_platforms(x_posts, truth_posts):
    """比對 X vs Truth Social，找出落差"""
    log("📊 比對 X vs Truth Social...")

    # 建指紋（用前 60 字做模糊匹配）
    def fingerprint(text):
        # 去掉 URL、標點，只留文字
        clean = re.sub(r'https?://\S+', '', text)
        clean = re.sub(r'[^\w\s]', '', clean).lower().strip()
        return clean[:60] if len(clean) > 10 else None

    x_fps = {}
    for p in x_posts:
        fp = fingerprint(p.get('text', ''))
        if fp:
            x_fps[fp] = p

    truth_fps = {}
    for p in truth_posts:
        fp = fingerprint(p.get('content', ''))
        if fp:
            truth_fps[fp] = p

    # 比對
    both = 0           # 兩邊都有
    x_only = []        # 只在 X
    truth_only = []    # 只在 Truth Social（重點！）

    for fp, p in x_fps.items():
        if fp in truth_fps:
            both += 1
        else:
            x_only.append(p)

    for fp, p in truth_fps.items():
        if fp not in x_fps:
            truth_only.append(p)

    log(f"\n   📊 比對結果:")
    log(f"      兩邊都有: {both} 篇")
    log(f"      只在 X: {len(x_only)} 篇")
    log(f"      只在 Truth Social: {len(truth_only)} 篇 ← 這是密碼")

    # 分析 Truth Social 獨有推文的特徵
    if truth_only:
        log(f"\n   🔐 Truth Social 獨有推文分析:")

        # 關鍵字統計
        keywords = defaultdict(int)
        for p in truth_only:
            cl = p.get('content', '').lower()
            for kw in ['tariff', 'deal', 'china', 'iran', 'russia', 'border',
                       'fake news', 'executive order', 'stock market', 'military']:
                if kw in cl:
                    keywords[kw] += 1

        log(f"      關鍵字分布（只在 Truth Social 的推文）:")
        for kw, count in sorted(keywords.items(), key=lambda x: -x[1]):
            pct = count / len(truth_only) * 100
            log(f"        {kw:20s}: {count:4d} ({pct:.1f}%)")

    # 存報告
    report = {
        'timestamp': datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ'),
        'x_total': len(x_posts),
        'truth_total': len(truth_posts),
        'both_platforms': both,
        'x_only': len(x_only),
        'truth_only': len(truth_only),
        'truth_only_ratio': round(len(truth_only) / max(len(truth_posts), 1) * 100, 1),

        'summary': {
            'en': f"Gap Analysis: {both} posts on both platforms, {len(truth_only)} Truth Social exclusive ({len(truth_only)/max(len(truth_posts),1)*100:.0f}% hidden from X)",
            'zh': f"落差分析: {both} 篇兩邊都有，{len(truth_only)} 篇只在 Truth Social（{len(truth_only)/max(len(truth_posts),1)*100:.0f}% 沒放到 X）",
            'ja': f"ギャップ分析: {both}件が両方、{len(truth_only)}件がTruth Social限定（{len(truth_only)/max(len(truth_posts),1)*100:.0f}%がXに非公開）",
        },

        'x_only_sample': [{'text': p['text'][:120], 'date': p.get('created_at', '')[:16]} for p in x_only[:10]],
        'truth_only_sample': [{'text': p['content'][:120], 'date': p.get('created_at', '')[:16]} for p in truth_only[:20]],
    }

    with open(GAP_REPORT, 'w', encoding='utf-8') as f:
        json.dump(report, f, ensure_ascii=False, indent=2)

    log(f"   💾 報告存入 {GAP_REPORT.name}")
    return report


def main():
    log("=" * 70)
    log("🔐 川普密碼 — X vs Truth Social 落差分析")
    log("=" * 70)

    # 1. 掃描 X 推文
    x_posts = scan_x_timeline()

    # 2. 載入 Truth Social 推文
    truth_file = BASE / "clean_president.json"
    if not truth_file.exists():
        log("⚠️ 需要先跑 clean_data.py")
        return

    with open(truth_file, encoding='utf-8') as f:
        truth_all = json.load(f)

    truth_posts = [p for p in truth_all
                   if p.get('has_text') and not p.get('is_retweet')]

    log(f"   Truth Social: {len(truth_posts)} 篇原創")

    # 3. 比對
    report = compare_platforms(x_posts, truth_posts)

    # 4. 結論
    log(f"\n{'='*70}")
    log("📋 結論")
    log(f"{'='*70}")
    print(f"\n{report['summary']['zh']}")
    print(f"\n{report['summary']['en']}")
    print(f"\n{report['summary']['ja']}")


if __name__ == '__main__':
    main()
