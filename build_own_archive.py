#!/usr/bin/env python3
"""
川普密碼 — 建立自己的完整資料庫
從 trumpstruth.org 逐篇抓取所有推文，建立獨立於 CNN 的備份
同時和 CNN Archive 交叉比對，確保 100% 吻合

用法:
  python3 build_own_archive.py              # 全量建庫（首次，約 1-2 小時）
  python3 build_own_archive.py --update     # 只抓新的
  python3 build_own_archive.py --verify     # 比對 CNN 和自建庫的吻合率
"""

import json
import re
import sys
import time
import csv
import html
import urllib.request
import urllib.error
from datetime import datetime, timezone
from pathlib import Path

BASE = Path(__file__).parent
DATA = BASE / "data"
DATA.mkdir(exist_ok=True)

OWN_ARCHIVE = DATA / "own_archive.json"  # 我們自己的資料庫
VERIFY_REPORT = DATA / "verify_report.json"

def log(msg):
    print(f"[{datetime.now(timezone.utc).strftime('%H:%M:%S')}] {msg}", flush=True)


def fetch_single_post(status_id):
    """從 trumpstruth.org 抓單篇推文"""
    url = f"https://trumpstruth.org/statuses/{status_id}"
    try:
        req = urllib.request.Request(url, headers={
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36',
        })
        with urllib.request.urlopen(req, timeout=15) as resp:
            h = resp.read().decode('utf-8')

        # 內容
        contents = re.findall(
            r'<div class="status__content">\s*(.*?)\s*</div>', h, re.DOTALL
        )
        content = re.sub(r'<[^>]+>', '', contents[0]).strip() if contents else ''

        # 時間
        times = re.findall(
            r'(\w+ \d{1,2}, \d{4},?\s*\d{1,2}:\d{2}\s*[AP]M)', h
        )
        post_time = ''
        if times:
            try:
                raw_time = re.sub(r'\s+', ' ', times[0].strip()).replace(',', '')
                dt = datetime.strptime(raw_time, '%B %d %Y %I:%M %p')
                post_time = dt.strftime('%Y-%m-%dT%H:%M:%S.000Z')
            except ValueError:
                pass

        # 原始 Truth Social URL
        ts_url = ''
        ts_urls = re.findall(r'href="(https://truthsocial\.com/@[^"]+)"', h)
        if ts_urls:
            ts_url = ts_urls[0]

        # 是否是 RT
        is_rt = bool(re.search(r'class="status__reblog-indicator"', h))

        if content:
            return {
                'id': str(status_id),
                'created_at': post_time,
                'content': content,
                'url': ts_url or url,
                'source': 'own_archive',
                'is_retweet': is_rt,
            }
        return None

    except urllib.error.HTTPError as e:
        if e.code == 404:
            return None  # 不存在的 ID
        return None
    except Exception:
        return None


def build_full_archive():
    """全量建庫：從 ID 1 到最新"""
    log("🏗️ 建立自己的完整資料庫")

    # 載入已有的進度
    existing = {}
    if OWN_ARCHIVE.exists():
        with open(OWN_ARCHIVE, encoding='utf-8') as f:
            data = json.load(f)
            existing = {p['id']: p for p in data.get('posts', [])}
        log(f"   已有 {len(existing)} 篇，繼續抓")

    # 找最新 ID
    log("   探測最新 ID...")
    max_id = 37308  # 已知最新
    for test_id in range(37308, 40000):
        try:
            req = urllib.request.Request(
                f'https://trumpstruth.org/statuses/{test_id}',
                headers={'User-Agent': 'Mozilla/5.0'},
                method='HEAD'
            )
            urllib.request.urlopen(req, timeout=5)
            max_id = test_id
        except Exception:
            break

    log(f"   最新 ID: {max_id}")
    log(f"   需要抓: {max_id - len(existing)} 篇")

    # 逐篇抓取
    posts = dict(existing)  # 保留已有的
    batch_start = time.time()
    errors = 0
    skipped = 0

    for sid in range(1, max_id + 1):
        if str(sid) in posts:
            skipped += 1
            continue

        post = fetch_single_post(sid)
        if post:
            posts[str(sid)] = post
        else:
            errors += 1

        # 進度報告（每 100 篇）
        done = sid
        if done % 100 == 0:
            elapsed = time.time() - batch_start
            speed = (done - skipped) / max(elapsed, 1)
            remaining = (max_id - done) / max(speed, 0.1)
            log(f"   {done}/{max_id} ({done/max_id*100:.1f}%) | "
                f"已抓 {len(posts)} 篇 | 錯誤 {errors} | "
                f"速度 {speed:.1f}/秒 | 剩 ~{remaining/60:.0f} 分鐘")

            # 每 500 篇存一次 checkpoint
            if done % 500 == 0:
                _save_archive(posts)

        # 禮貌延遲：0.3 秒（不要打爆人家伺服器）
        time.sleep(0.3)

    _save_archive(posts)
    log(f"✅ 建庫完成: {len(posts)} 篇")
    return posts


def update_archive():
    """增量更新：只抓新的"""
    log("🔄 增量更新")

    if not OWN_ARCHIVE.exists():
        log("   ⚠️ 資料庫不存在，需要先跑全量建庫")
        return build_full_archive()

    with open(OWN_ARCHIVE, encoding='utf-8') as f:
        data = json.load(f)
        posts = {p['id']: p for p in data.get('posts', [])}

    max_existing = max(int(pid) for pid in posts.keys())
    log(f"   現有最新 ID: {max_existing}")

    # 從最新 ID 往後抓
    new_count = 0
    consecutive_404 = 0

    for sid in range(max_existing + 1, max_existing + 500):
        post = fetch_single_post(sid)
        if post:
            posts[str(sid)] = post
            new_count += 1
            consecutive_404 = 0
        else:
            consecutive_404 += 1
            if consecutive_404 >= 10:
                break  # 連續 10 個 404 = 到頂了

        time.sleep(0.3)

    if new_count > 0:
        _save_archive(posts)
        log(f"   ✅ 新增 {new_count} 篇，總計 {len(posts)} 篇")
    else:
        log("   ℹ️ 沒有新推文")

    return posts


def _save_archive(posts_dict):
    """存檔"""
    sorted_posts = sorted(posts_dict.values(), key=lambda p: p.get('created_at', ''))
    data = {
        'updated_at': datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ'),
        'total_posts': len(sorted_posts),
        'source': 'trumpstruth.org (self-scraped)',
        'posts': sorted_posts,
    }
    with open(OWN_ARCHIVE, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def verify_against_cnn():
    """比對自建庫 vs CNN Archive，逐篇驗證吻合率"""
    log("🔍 交叉比對: 自建庫 vs CNN Archive")

    # 載入自建庫
    if not OWN_ARCHIVE.exists():
        log("   ❌ 自建庫不存在，請先跑 build_own_archive.py")
        return

    with open(OWN_ARCHIVE, encoding='utf-8') as f:
        own_data = json.load(f)
    own_posts = own_data.get('posts', [])
    log(f"   自建庫: {len(own_posts)} 篇")

    # 下載 CNN Archive
    log("   下載 CNN Archive...")
    try:
        req = urllib.request.Request(
            "https://ix.cnn.io/data/truth-social/truth_archive.csv",
            headers={'User-Agent': 'TrumpCode/1.0'}
        )
        with urllib.request.urlopen(req, timeout=60) as resp:
            raw = resp.read().decode('utf-8')

        reader = csv.DictReader(raw.splitlines())
        cnn_posts = []
        for row in reader:
            if not row.get('content') or not row.get('created_at'):
                continue
            content = row['content'].strip()
            try:
                content = content.encode('latin-1').decode('utf-8')
            except (UnicodeDecodeError, UnicodeEncodeError):
                pass
            content = html.unescape(content)
            if content:
                cnn_posts.append({
                    'created_at': row['created_at'],
                    'content': content,
                })
        log(f"   CNN Archive: {len(cnn_posts)} 篇")

    except Exception as e:
        log(f"   ❌ CNN 下載失敗: {e}")
        return

    # 建指紋索引（用前 80 字做匹配）
    cnn_fps = {}
    for p in cnn_posts:
        fp = re.sub(r'\s+', ' ', p['content'][:80].lower().strip())
        cnn_fps[fp] = p

    own_fps = {}
    for p in own_posts:
        fp = re.sub(r'\s+', ' ', p['content'][:80].lower().strip())
        own_fps[fp] = p

    # 比對
    matched = 0
    cnn_only = 0
    own_only = 0
    mismatches = []

    for fp, p in own_fps.items():
        if fp in cnn_fps:
            matched += 1
        else:
            own_only += 1
            if len(mismatches) < 10:
                mismatches.append({
                    'source': 'own_only',
                    'content': p['content'][:100],
                    'date': p.get('created_at', '?'),
                })

    for fp in cnn_fps:
        if fp not in own_fps:
            cnn_only += 1

    total = matched + cnn_only + own_only
    match_rate = matched / max(total, 1) * 100

    log(f"\n   📊 比對結果:")
    log(f"      吻合: {matched} 篇")
    log(f"      只在 CNN: {cnn_only} 篇")
    log(f"      只在自建庫: {own_only} 篇")
    log(f"      吻合率: {match_rate:.1f}%")

    verdict = 'PERFECT' if match_rate > 95 else ('GOOD' if match_rate > 80 else ('PARTIAL' if match_rate > 50 else 'INCONSISTENT'))
    log(f"      判定: {verdict}")

    report = {
        'timestamp': datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ'),
        'own_count': len(own_posts),
        'cnn_count': len(cnn_posts),
        'matched': matched,
        'cnn_only': cnn_only,
        'own_only': own_only,
        'match_rate': round(match_rate, 1),
        'verdict': verdict,
        'sample_mismatches': mismatches,
    }

    with open(VERIFY_REPORT, 'w', encoding='utf-8') as f:
        json.dump(report, f, ensure_ascii=False, indent=2)

    log(f"   💾 報告存入 {VERIFY_REPORT.name}")


def main():
    if '--update' in sys.argv:
        update_archive()
    elif '--verify' in sys.argv:
        verify_against_cnn()
    else:
        build_full_archive()
        verify_against_cnn()


if __name__ == '__main__':
    main()
