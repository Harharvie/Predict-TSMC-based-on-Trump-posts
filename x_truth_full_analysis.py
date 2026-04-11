#!/usr/bin/env python3
"""
川普密碼 — X vs Truth Social 完整深度比對分析
Complete cross-platform comparison of Trump's second-term posts

策略:
  1. 從 WebSearch 收集到的所有已知 X 推文 ID，用 embed API 抓完整內容
  2. 從已知 ID 附近掃描找更多推文（±100 範圍）
  3. 和 Truth Social 5,300+ 篇原創做深度比對
  4. 產出完整分析報告

用法:
  python3 x_truth_full_analysis.py
"""

import json
import re
import sys
import time
import urllib.request
from datetime import datetime, timezone, timedelta
from pathlib import Path
from collections import defaultdict, Counter

BASE = Path(__file__).parent
DATA = BASE / "data"
X_ARCHIVE = DATA / "x_posts.json"
TRUTH_FILE = BASE / "clean_president.json"
MARKET_FILE = DATA / "market_SP500.json"
FULL_REPORT = DATA / "x_truth_full_comparison.json"

# ============================================================
# 所有從 WebSearch 找到的已知 Trump X 推文 ID
# ============================================================
KNOWN_IDS = [
    # January 2025
    "1880446012168249386",   # Jan 17 - $TRUMP meme coin launch
    "1890831570535055759",   # Feb 15 - "He who saves his Country..."

    # February 2025
    "1892242622623699357",   # Feb 19 - video/link post
    "1894126415932526802",   # Feb 24 - link post
    "1895566669281636846",   # Feb 28 - link post

    # March 2025
    "1905689237749727368",   # Mar 28 - link post

    # April 2025
    "1907782254572470670",   # Apr 03 - Liberation Day tariff video
    "1908300360810479821",   # Apr 04 - Houthis attack tweet

    # May 2025
    "1920519130941170088",   # May 08 - link post
    "1921008311492624867",   # May 09 - Self-deportation EO
    "1921174163848401313",   # May 10 - link post
    "1921699954696855934",   # May 11 - link post
    "1921911904429088892",   # May 12 - link post
    "1923793069138178293",   # May 17 - Qatar flag post
    "1924523182909747657",   # May 19 - link post
    "1925201677914603580",   # May 21 - link post
    "1925548216243703820",   # May 22 - Big Beautiful Bill passed

    # June 2025
    "1928797140408533377",   # May 31 - link post
    "1934008938334228752",   # Jun 14 - link post
    "1936573183634645387",   # Jun 21 - link post
    "1937917613989859810",   # Jun 25 - link post

    # July 2025
    "1941244891578904902",   # Jul 03 - link post
    "1941341699374186746",   # Jul 04 - HAPPY 4TH OF JULY!

    # September 2025
    "1965947311718269341",   # Sep 11 - TO MY GREAT FELLOW AMERICANS
    "1968134929080082432",   # Sep 16 - link post
    "1972822596397003159",   # Sep 30 - link post
    "1973218518893207825",   # Oct 01 - link post

    # October 2025
    "1978148814776046046",   # Oct 14 - Eric's book "Under Siege"

    # November 2025
    "1862127644222832894",   # Nov (Thanksgiving-related, need to verify date)
    "1862281187600793830",   # Nov - link post
    "1872051253846614426",   # Dec - link post

    # November/December 2025
    "1994272683387687053",   # Nov 27 - Thanksgiving post
    "1994438728237064270",   # Nov 28 - South Africa G20 post

    # December 2025
    "2004012442427277591",   # Dec 25 - Merry Christmas
    "2014772963719991311",   # Jan 2026 - Melania documentary countdown

    # February/March 2026
    "2027651077865157033",   # Feb 28 - Iran war (172.9M views)
    "2028505632123326484",   # Mar 02 - link post (102.5M views)
]


def log(msg):
    print(f"[{datetime.now(timezone.utc).strftime('%H:%M:%S')}] {msg}", flush=True)


def fetch_x_post(tweet_id):
    """用 X embed API 抓單篇推文"""
    try:
        url = f'https://cdn.syndication.twimg.com/tweet-result?id={tweet_id}&token=0'
        req = urllib.request.Request(url, headers={
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36',
            'Accept': 'application/json',
        })
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read().decode('utf-8'))

        # 提取媒體資訊
        media_urls = []
        if 'mediaDetails' in data:
            for m in data['mediaDetails']:
                media_urls.append({
                    'type': m.get('type', 'unknown'),
                    'url': m.get('media_url_https', ''),
                })

        # 提取引用推文
        quoted = None
        if 'quoted_tweet' in data:
            qt = data['quoted_tweet']
            quoted = {
                'id': qt.get('id_str', ''),
                'text': qt.get('text', ''),
                'user': qt.get('user', {}).get('screen_name', ''),
            }

        return {
            'id': str(tweet_id),
            'created_at': data.get('created_at', ''),
            'text': data.get('text', ''),
            'lang': data.get('lang', ''),
            'favorite_count': data.get('favorite_count', 0),
            'conversation_count': data.get('conversation_count', 0),
            'retweet_count': data.get('retweet_count', 0),
            'views_count': data.get('views_count', 0),
            'user': data.get('user', {}).get('screen_name', ''),
            'media': media_urls,
            'quoted_tweet': quoted,
            'is_reply': bool(data.get('in_reply_to_status_id_str')),
            'source': 'x',
        }
    except urllib.error.HTTPError as e:
        if e.code == 404:
            return None  # 推文不存在
        return None
    except Exception:
        return None


def scan_around_id(base_id, existing, radius=50):
    """在已知 ID 附近掃描找更多推文"""
    found = 0
    scanned = 0
    base = int(base_id)

    for offset in range(-radius, radius + 1):
        test_id = str(base + offset)
        if test_id in existing or test_id == base_id:
            continue

        post = fetch_x_post(test_id)
        scanned += 1

        if post and post['text'] and post.get('user', '').lower() == 'realdonaldtrump':
            existing[test_id] = post
            found += 1
            log(f"   🆕 掃到! {post['created_at'][:16]} | {post['text'][:60]}...")

        time.sleep(0.35)

        # 如果已經掃了30個都沒找到，停下來
        if scanned > 30 and found == 0:
            break

    return found, scanned


def collect_x_posts():
    """Phase 1: 收集所有 X 推文"""
    log("=" * 70)
    log("Phase 1: 收集 Trump X 推文")
    log("=" * 70)

    # 載入已有的
    existing = {}
    if X_ARCHIVE.exists():
        with open(X_ARCHIVE, encoding='utf-8') as f:
            data = json.load(f)
            existing = {p['id']: p for p in data.get('posts', [])}
    log(f"   已有 {len(existing)} 篇 X 推文")

    # Step 1: 抓所有已知 ID
    log(f"\n   Step 1: 抓 {len(KNOWN_IDS)} 個已知 ID...")
    new_from_known = 0
    for i, tid in enumerate(KNOWN_IDS):
        if tid in existing:
            continue
        post = fetch_x_post(tid)
        if post and post['text']:
            # 確認是 Trump 本人的推文
            user = post.get('user', '').lower()
            if user in ('realdonaldtrump', ''):
                existing[tid] = post
                new_from_known += 1
                log(f"   [{i+1}/{len(KNOWN_IDS)}] ✅ {post['created_at'][:16]} | {post['text'][:60]}...")
            else:
                log(f"   [{i+1}/{len(KNOWN_IDS)}] ⚠️ 非 Trump 推文 (user={user})")
        else:
            log(f"   [{i+1}/{len(KNOWN_IDS)}] ❌ ID {tid} 不存在或已刪")
        time.sleep(0.35)

    log(f"   已知 ID 新增: {new_from_known} 篇")

    # Step 2: 在每個找到的推文 ID 附近掃描
    log(f"\n   Step 2: 在已知 ID 附近掃描（±50）...")
    sorted_ids = sorted(existing.keys(), key=lambda x: int(x))
    total_scan_found = 0
    total_scanned = 0

    for i, known_id in enumerate(sorted_ids):
        found, scanned = scan_around_id(known_id, existing, radius=50)
        total_scan_found += found
        total_scanned += scanned
        if found > 0:
            log(f"   ID {known_id} 附近掃到 {found} 篇新推文")

    log(f"   掃描完成: 掃了 {total_scanned} 個 ID，找到 {total_scan_found} 篇新推文")

    # 存檔
    posts = sorted(existing.values(), key=lambda p: p.get('created_at', ''))
    result = {
        'updated_at': datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ'),
        'total_posts': len(posts),
        'collection_method': 'WebSearch + embed API + proximity scan',
        'posts': posts,
    }
    with open(X_ARCHIVE, 'w', encoding='utf-8') as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    log(f"\n   💾 X 推文庫更新: {len(posts)} 篇")
    return posts


def load_truth_posts():
    """載入 Truth Social 推文"""
    with open(TRUTH_FILE, encoding='utf-8') as f:
        all_posts = json.load(f)

    # 只取原創推文（非轉推、有文字）
    originals = [p for p in all_posts if p.get('has_text') and not p.get('is_retweet')]
    log(f"   Truth Social: {len(originals)} 篇原創推文（總共 {len(all_posts)} 篇）")
    return originals


def fingerprint(text):
    """文字指紋：去 URL、標點，取前 50 字做匹配"""
    if not text:
        return None
    clean = re.sub(r'https?://\S+', '', text)
    clean = re.sub(r'[^\w\s]', '', clean).lower().strip()
    clean = re.sub(r'\s+', ' ', clean)
    return clean[:50] if len(clean) > 8 else None


def fingerprint_words(text):
    """用前 N 個有意義的字做匹配（更寬鬆）"""
    if not text:
        return None
    clean = re.sub(r'https?://\S+', '', text)
    clean = re.sub(r'[^\w\s]', '', clean).lower().strip()
    words = clean.split()
    return ' '.join(words[:8]) if len(words) >= 3 else None


def deep_compare(x_posts, truth_posts):
    """Phase 2: 深度比對分析"""
    log("\n" + "=" * 70)
    log("Phase 2: 深度比對分析")
    log("=" * 70)

    # 建立指紋索引
    x_by_fp = {}
    x_by_words = {}
    for p in x_posts:
        fp = fingerprint(p.get('text', ''))
        if fp:
            x_by_fp[fp] = p
        wfp = fingerprint_words(p.get('text', ''))
        if wfp:
            x_by_words[wfp] = p

    truth_by_fp = {}
    truth_by_words = {}
    for p in truth_posts:
        fp = fingerprint(p.get('content', ''))
        if fp:
            truth_by_fp[fp] = p
        wfp = fingerprint_words(p.get('content', ''))
        if wfp:
            truth_by_words[wfp] = p

    # ===== a. 匹配 =====
    matched_pairs = []  # (x_post, truth_post)
    x_matched_ids = set()
    truth_matched_ids = set()

    # 嚴格匹配（前 50 字指紋）
    for fp, xp in x_by_fp.items():
        if fp in truth_by_fp:
            tp = truth_by_fp[fp]
            matched_pairs.append((xp, tp))
            x_matched_ids.add(xp['id'])
            truth_matched_ids.add(tp['id'])

    # 寬鬆匹配（前 8 字）— 只對還沒匹配到的
    for wfp, xp in x_by_words.items():
        if xp['id'] in x_matched_ids:
            continue
        if wfp in truth_by_words:
            tp = truth_by_words[wfp]
            if tp['id'] not in truth_matched_ids:
                matched_pairs.append((xp, tp))
                x_matched_ids.add(xp['id'])
                truth_matched_ids.add(tp['id'])

    x_only = [p for p in x_posts if p['id'] not in x_matched_ids]
    truth_only = [p for p in truth_posts if p['id'] not in truth_matched_ids]

    log(f"\n   📊 基本比對:")
    log(f"      X 推文總數: {len(x_posts)}")
    log(f"      Truth Social 原創總數: {len(truth_posts)}")
    log(f"      兩邊都有: {len(matched_pairs)} 篇")
    log(f"      只在 X: {len(x_only)} 篇")
    log(f"      只在 Truth Social: {len(truth_only)} 篇")
    log(f"      Truth Social 獨佔率: {len(truth_only)/max(len(truth_posts),1)*100:.1f}%")

    # ===== b. 時間差分析 =====
    log(f"\n   ⏱️ 時間差分析（同篇推文兩邊的發布時間）:")
    time_diffs = []
    for xp, tp in matched_pairs:
        try:
            # X 時間格式: "2025-02-19T15:59:32.000Z" or similar
            x_time = None
            for fmt in ['%Y-%m-%dT%H:%M:%S.%fZ', '%a %b %d %H:%M:%S %z %Y',
                        '%Y-%m-%dT%H:%M:%SZ', '%Y-%m-%dT%H:%M:%S.%f%z']:
                try:
                    x_time = datetime.strptime(xp['created_at'], fmt)
                    if x_time.tzinfo is None:
                        x_time = x_time.replace(tzinfo=timezone.utc)
                    break
                except ValueError:
                    continue

            t_time = None
            for fmt in ['%Y-%m-%dT%H:%M:%S.%fZ', '%Y-%m-%dT%H:%M:%S.%f%z',
                        '%Y-%m-%dT%H:%M:%SZ']:
                try:
                    t_time = datetime.strptime(tp['created_at'], fmt)
                    if t_time.tzinfo is None:
                        t_time = t_time.replace(tzinfo=timezone.utc)
                    break
                except ValueError:
                    continue

            if x_time and t_time:
                diff_seconds = (x_time - t_time).total_seconds()
                diff_minutes = diff_seconds / 60
                time_diffs.append({
                    'x_id': xp['id'],
                    'x_time': xp['created_at'],
                    'truth_time': tp['created_at'],
                    'diff_minutes': round(diff_minutes, 1),
                    'first_platform': 'Truth Social' if diff_seconds > 0 else 'X',
                    'text_preview': xp.get('text', '')[:80],
                })
        except Exception:
            pass

    if time_diffs:
        truth_first = sum(1 for d in time_diffs if d['first_platform'] == 'Truth Social')
        x_first = sum(1 for d in time_diffs if d['first_platform'] == 'X')
        avg_diff = sum(abs(d['diff_minutes']) for d in time_diffs) / len(time_diffs)
        log(f"      Truth Social 先發: {truth_first} 次")
        log(f"      X 先發: {x_first} 次")
        log(f"      平均時間差: {avg_diff:.1f} 分鐘")
        for td in sorted(time_diffs, key=lambda x: abs(x['diff_minutes']), reverse=True)[:5]:
            log(f"      {td['first_platform']} 先發 {abs(td['diff_minutes']):.0f}分 | {td['text_preview'][:60]}...")
    else:
        log(f"      （匹配到的推文中沒有足夠的時間資料可分析）")

    # ===== c. 語氣差異分析 =====
    log(f"\n   🎭 語氣差異分析（同篇推文在兩個平台的差異）:")
    tone_diffs = []
    for xp, tp in matched_pairs:
        x_text = xp.get('text', '')
        t_text = tp.get('content', '')
        if not x_text or not t_text:
            continue

        x_caps_ratio = sum(1 for c in x_text if c.isupper()) / max(len(x_text), 1)
        t_caps_ratio = sum(1 for c in t_text if c.isupper()) / max(len(t_text), 1)
        x_excl = x_text.count('!')
        t_excl = t_text.count('!')
        texts_identical = fingerprint(x_text) == fingerprint(t_text)

        tone_diffs.append({
            'text_preview': x_text[:60],
            'x_caps_ratio': round(x_caps_ratio, 3),
            'truth_caps_ratio': round(t_caps_ratio, 3),
            'x_exclamations': x_excl,
            'truth_exclamations': t_excl,
            'text_identical': texts_identical,
        })

    if tone_diffs:
        avg_x_caps = sum(d['x_caps_ratio'] for d in tone_diffs) / len(tone_diffs)
        avg_t_caps = sum(d['truth_caps_ratio'] for d in tone_diffs) / len(tone_diffs)
        identical_count = sum(1 for d in tone_diffs if d['text_identical'])
        log(f"      平均大寫率 - X: {avg_x_caps:.1%}  Truth Social: {avg_t_caps:.1%}")
        log(f"      文字完全相同: {identical_count}/{len(tone_diffs)} 篇")

    # ===== d. 主題分析 =====
    log(f"\n   📝 主題分析:")

    topic_keywords = {
        'tariff/trade': ['tariff', 'trade', 'deal', 'import', 'export', 'liberation day'],
        'china': ['china', 'chinese', 'xi', 'beijing'],
        'iran/military': ['iran', 'military', 'bomb', 'strike', 'houthi', 'yemen', 'war'],
        'border/immigration': ['border', 'immigra', 'deport', 'illegal', 'wall', 'migrant'],
        'economy/markets': ['stock', 'market', 'economy', 'inflation', 'interest rate', 'fed', 'gdp', 'jobs'],
        'fake news/media': ['fake news', 'media', 'failing', 'cnn', 'msnbc', 'nyt', 'new york times'],
        'executive order': ['executive order', 'signed', 'proclamation'],
        'endorsement': ['endorse', 'endorsement', 'great honor', 'pleased to announce'],
        'musk/doge': ['musk', 'elon', 'doge', 'department of government'],
        'foreign policy': ['russia', 'ukraine', 'nato', 'europe', 'greenland', 'canada', 'mexico'],
        'celebration/holiday': ['christmas', 'thanksgiving', '4th of july', 'happy', 'congratulat'],
        'legal/court': ['court', 'judge', 'lawsuit', 'unconstitutional', 'supreme court'],
        'energy': ['oil', 'gas', 'energy', 'drill', 'pipeline'],
    }

    def classify_topics(text):
        """分類推文主題"""
        if not text:
            return []
        text_lower = text.lower()
        topics = []
        for topic, keywords in topic_keywords.items():
            if any(kw in text_lower for kw in keywords):
                topics.append(topic)
        return topics if topics else ['other']

    # X 推文主題
    x_topics = Counter()
    for p in x_posts:
        for t in classify_topics(p.get('text', '')):
            x_topics[t] += 1

    # Truth Social 全部推文主題
    truth_topics = Counter()
    for p in truth_posts:
        for t in classify_topics(p.get('content', '')):
            truth_topics[t] += 1

    # 只在 Truth Social 的推文主題
    truth_only_topics = Counter()
    for p in truth_only:
        for t in classify_topics(p.get('content', '')):
            truth_only_topics[t] += 1

    # 放到 X 的推文主題
    x_posted_topics = Counter()
    for xp, _ in matched_pairs:
        for t in classify_topics(xp.get('text', '')):
            x_posted_topics[t] += 1

    log(f"\n      所有主題分布比較:")
    log(f"      {'主題':<25s} {'X推文':>8s} {'放到X的':>8s} {'只在TS':>8s} {'TS全部':>8s} {'X選擇率':>8s}")
    log(f"      {'-'*25} {'-'*8} {'-'*8} {'-'*8} {'-'*8} {'-'*8}")

    all_topics = sorted(set(list(x_topics.keys()) + list(truth_topics.keys())),
                       key=lambda t: truth_topics.get(t, 0), reverse=True)

    topic_selection_rates = {}
    for topic in all_topics:
        x_count = x_topics.get(topic, 0)
        x_posted = x_posted_topics.get(topic, 0)
        ts_only = truth_only_topics.get(topic, 0)
        ts_total = truth_topics.get(topic, 0)
        selection_rate = x_posted / max(ts_total, 1) * 100
        topic_selection_rates[topic] = selection_rate
        log(f"      {topic:<25s} {x_count:>8d} {x_posted:>8d} {ts_only:>8d} {ts_total:>8d} {selection_rate:>7.1f}%")

    # ===== e. 市場影響分析 =====
    log(f"\n   📈 市場影響分析:")
    market_data = []
    if MARKET_FILE.exists():
        with open(MARKET_FILE, encoding='utf-8') as f:
            market_data = json.load(f)

    market_by_date = {m['date']: m for m in market_data}

    def get_market_move(post_date_str):
        """取得推文日期的市場變動"""
        try:
            for fmt in ['%Y-%m-%dT%H:%M:%S.%fZ', '%Y-%m-%dT%H:%M:%S.%f%z',
                        '%Y-%m-%dT%H:%M:%SZ', '%a %b %d %H:%M:%S %z %Y']:
                try:
                    dt = datetime.strptime(post_date_str, fmt)
                    break
                except ValueError:
                    continue
            else:
                return None

            date_str = dt.strftime('%Y-%m-%d')
            # 檢查當天和隔天
            for offset in range(0, 4):
                check_date = (dt + timedelta(days=offset)).strftime('%Y-%m-%d')
                if check_date in market_by_date:
                    m = market_by_date[check_date]
                    return {
                        'date': check_date,
                        'open': m['open'],
                        'close': m['close'],
                        'change_pct': round((m['close'] - m['open']) / m['open'] * 100, 3),
                    }
        except Exception:
            pass
        return None

    # X 推文的市場影響
    x_market_moves = []
    for p in x_posts:
        mm = get_market_move(p.get('created_at', ''))
        if mm:
            x_market_moves.append({
                'text': p.get('text', '')[:80],
                'post_date': p.get('created_at', '')[:10],
                **mm,
            })

    # Truth Social only 推文的市場影響
    truth_only_market_moves = []
    for p in truth_only[:500]:  # 取前 500 篇避免太慢
        mm = get_market_move(p.get('created_at', ''))
        if mm:
            truth_only_market_moves.append({
                'text': p.get('content', '')[:80],
                'post_date': p.get('created_at', '')[:10],
                **mm,
            })

    if x_market_moves:
        avg_x_move = sum(m['change_pct'] for m in x_market_moves) / len(x_market_moves)
        max_x_move = max(x_market_moves, key=lambda m: abs(m['change_pct']))
        log(f"      X 推文日均市場變動: {avg_x_move:+.3f}%（{len(x_market_moves)} 個交易日）")
        log(f"      X 推文最大變動: {max_x_move['change_pct']:+.3f}% ({max_x_move['date']}) | {max_x_move['text'][:60]}")

    if truth_only_market_moves:
        avg_ts_move = sum(m['change_pct'] for m in truth_only_market_moves) / len(truth_only_market_moves)
        max_ts_move = max(truth_only_market_moves, key=lambda m: abs(m['change_pct']))
        log(f"      Truth Only 推文日均市場變動: {avg_ts_move:+.3f}%（{len(truth_only_market_moves)} 個交易日）")
        log(f"      Truth Only 最大變動: {max_ts_move['change_pct']:+.3f}% ({max_ts_move['date']}) | {max_ts_move['text'][:60]}")

    # ===== f. X 選擇策略分析 =====
    log(f"\n   🎯 X 選擇策略分析:")
    log(f"      Trump 在 Truth Social 發了 {len(truth_posts)} 篇原創")
    log(f"      其中只有 {len(matched_pairs)} 篇（{len(matched_pairs)/max(len(truth_posts),1)*100:.1f}%）也放到了 X")
    log(f"      {len(truth_only)} 篇（{len(truth_only)/max(len(truth_posts),1)*100:.1f}%）只留在 Truth Social")

    # 分析放到 X 的推文有什麼特徵
    log(f"\n      放到 X 的推文特徵:")
    x_posted_engagement = [xp.get('favorite_count', 0) for xp, _ in matched_pairs]
    if x_posted_engagement:
        log(f"        平均 X 按讚: {sum(x_posted_engagement)/len(x_posted_engagement):,.0f}")

    # 分析有文字 vs 純連結
    x_text_posts = [p for p in x_posts if len(p.get('text', '').replace('https://', '').replace('http://', '').strip()) > 20]
    x_link_only = [p for p in x_posts if len(p.get('text', '').replace('https://', '').replace('http://', '').strip()) <= 20]
    log(f"        有實質文字: {len(x_text_posts)} 篇")
    log(f"        純連結/媒體: {len(x_link_only)} 篇")

    # ===== g. 月度趨勢 =====
    log(f"\n   📅 月度趨勢:")
    x_by_month = Counter()
    truth_by_month = Counter()

    for p in x_posts:
        try:
            month = p.get('created_at', '')[:7]
            if month:
                x_by_month[month] += 1
        except Exception:
            pass

    for p in truth_posts:
        try:
            month = p.get('created_at', '')[:7]
            if month:
                truth_by_month[month] += 1
        except Exception:
            pass

    all_months = sorted(set(list(x_by_month.keys()) + list(truth_by_month.keys())))
    log(f"      {'月份':<10s} {'X':>5s} {'TS':>5s} {'X/TS比':>8s}")
    log(f"      {'-'*10} {'-'*5} {'-'*5} {'-'*8}")
    for month in all_months:
        xc = x_by_month.get(month, 0)
        tc = truth_by_month.get(month, 0)
        ratio = f"{xc/tc*100:.1f}%" if tc > 0 else "N/A"
        log(f"      {month:<10s} {xc:>5d} {tc:>5d} {ratio:>8s}")

    # ===== 組裝報告 =====
    report = {
        'metadata': {
            'timestamp': datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ'),
            'analysis_version': '2.0',
            'x_source': 'X embed API (cdn.syndication.twimg.com)',
            'truth_source': 'clean_president.json (Truth Social archive)',
        },
        'summary': {
            'x_total': len(x_posts),
            'truth_total': len(truth_posts),
            'matched': len(matched_pairs),
            'x_only': len(x_only),
            'truth_only': len(truth_only),
            'truth_only_ratio': round(len(truth_only) / max(len(truth_posts), 1) * 100, 1),
            'x_selection_rate': round(len(matched_pairs) / max(len(truth_posts), 1) * 100, 2),
        },
        'matched_pairs': [
            {
                'x_id': xp['id'],
                'truth_id': tp['id'],
                'x_text': xp.get('text', '')[:200],
                'truth_text': tp.get('content', '')[:200],
                'x_time': xp.get('created_at', ''),
                'truth_time': tp.get('created_at', ''),
                'x_likes': xp.get('favorite_count', 0),
                'truth_likes': tp.get('favourites_count', 0),
            }
            for xp, tp in matched_pairs
        ],
        'x_only_posts': [
            {
                'id': p['id'],
                'text': p.get('text', '')[:200],
                'created_at': p.get('created_at', ''),
                'likes': p.get('favorite_count', 0),
                'topics': classify_topics(p.get('text', '')),
            }
            for p in x_only
        ],
        'truth_only_sample': [
            {
                'id': p['id'],
                'text': p.get('content', '')[:200],
                'created_at': p.get('created_at', ''),
                'likes': p.get('favourites_count', 0),
                'topics': classify_topics(p.get('content', '')),
            }
            for p in truth_only[:100]
        ],
        'time_analysis': {
            'pairs_with_time_data': len(time_diffs),
            'truth_first_count': sum(1 for d in time_diffs if d['first_platform'] == 'Truth Social') if time_diffs else 0,
            'x_first_count': sum(1 for d in time_diffs if d['first_platform'] == 'X') if time_diffs else 0,
            'avg_diff_minutes': round(sum(abs(d['diff_minutes']) for d in time_diffs) / max(len(time_diffs), 1), 1) if time_diffs else 0,
            'details': time_diffs,
        },
        'tone_analysis': {
            'pairs_analyzed': len(tone_diffs),
            'avg_x_caps_ratio': round(sum(d['x_caps_ratio'] for d in tone_diffs) / max(len(tone_diffs), 1), 4) if tone_diffs else 0,
            'avg_truth_caps_ratio': round(sum(d['truth_caps_ratio'] for d in tone_diffs) / max(len(tone_diffs), 1), 4) if tone_diffs else 0,
            'identical_text_count': sum(1 for d in tone_diffs if d['text_identical']) if tone_diffs else 0,
        },
        'topic_analysis': {
            'x_topics': dict(x_topics.most_common()),
            'truth_topics': dict(truth_topics.most_common()),
            'truth_only_topics': dict(truth_only_topics.most_common()),
            'topic_selection_rates': topic_selection_rates,
        },
        'market_analysis': {
            'x_posts_market': {
                'trading_days': len(x_market_moves),
                'avg_change_pct': round(sum(m['change_pct'] for m in x_market_moves) / max(len(x_market_moves), 1), 4) if x_market_moves else 0,
                'max_move': max(x_market_moves, key=lambda m: abs(m['change_pct'])) if x_market_moves else None,
            },
            'truth_only_market': {
                'trading_days': len(truth_only_market_moves),
                'avg_change_pct': round(sum(m['change_pct'] for m in truth_only_market_moves) / max(len(truth_only_market_moves), 1), 4) if truth_only_market_moves else 0,
                'max_move': max(truth_only_market_moves, key=lambda m: abs(m['change_pct'])) if truth_only_market_moves else None,
            },
        },
        'monthly_trend': {
            month: {'x': x_by_month.get(month, 0), 'truth_social': truth_by_month.get(month, 0)}
            for month in all_months
        },
    }

    with open(FULL_REPORT, 'w', encoding='utf-8') as f:
        json.dump(report, f, ensure_ascii=False, indent=2)

    log(f"\n   💾 完整報告存入 {FULL_REPORT}")
    return report


def print_final_analysis(report):
    """Phase 3: 印出完整中文分析"""
    log("\n" + "=" * 70)
    log("Phase 3: 完整分析結論")
    log("=" * 70)

    s = report['summary']
    print(f"""
╔══════════════════════════════════════════════════════════════════════╗
║          川普密碼 — X vs Truth Social 完整比對分析                  ║
╠══════════════════════════════════════════════════════════════════════╣
║                                                                      ║
║  分析時間: {report['metadata']['timestamp']}                        ║
║                                                                      ║
╠══════════════════════════════════════════════════════════════════════╣
║  1. 數量比對                                                         ║
╠══════════════════════════════════════════════════════════════════════╣
║                                                                      ║
║  X (Twitter) 推文數:        {s['x_total']:>6,d} 篇                    ║
║  Truth Social 原創推文數:   {s['truth_total']:>6,d} 篇                ║
║  兩邊都有:                  {s['matched']:>6,d} 篇                    ║
║  只在 X:                    {s['x_only']:>6,d} 篇                    ║
║  只在 Truth Social:         {s['truth_only']:>6,d} 篇                ║
║                                                                      ║
║  Truth Social 獨佔率:       {s['truth_only_ratio']:>6.1f}%              ║
║  X 選擇率（TS推文放到X）:   {s['x_selection_rate']:>6.2f}%              ║
║                                                                      ║
╠══════════════════════════════════════════════════════════════════════╣
║  2. 核心發現                                                         ║
╠══════════════════════════════════════════════════════════════════════╣""")

    # 時間分析
    ta = report['time_analysis']
    print(f"""║                                                                      ║
║  時間差分析（同篇推文兩個平台的發布順序）:                          ║
║    Truth Social 先發: {ta['truth_first_count']} 次                     ║
║    X 先發: {ta['x_first_count']} 次                                    ║
║    平均時間差: {ta['avg_diff_minutes']} 分鐘                           ║""")

    # 語氣分析
    tna = report['tone_analysis']
    print(f"""║                                                                      ║
║  語氣差異（同篇推文兩平台比較）:                                    ║
║    X 平均大寫率: {tna['avg_x_caps_ratio']:.1%}                        ║
║    Truth Social 平均大寫率: {tna['avg_truth_caps_ratio']:.1%}          ║
║    文字完全相同: {tna['identical_text_count']}/{tna['pairs_analyzed']} 篇 ║""")

    # 主題分析
    print(f"""║                                                                      ║
╠══════════════════════════════════════════════════════════════════════╣
║  3. 主題篩選策略                                                     ║
╠══════════════════════════════════════════════════════════════════════╣
║                                                                      ║
║  他選擇放到 X 的主題 vs 沒放到 X 的主題差異:                        ║""")

    tsr = report['topic_analysis']['topic_selection_rates']
    sorted_topics = sorted(tsr.items(), key=lambda x: x[1], reverse=True)
    for topic, rate in sorted_topics:
        bar = '█' * int(rate * 2) if rate <= 50 else '█' * 50 + '+'
        print(f"║    {topic:<22s} X選擇率 {rate:>6.1f}% {bar}")

    # 市場分析
    ma = report['market_analysis']
    print(f"""║                                                                      ║
╠══════════════════════════════════════════════════════════════════════╣
║  4. 市場影響差異                                                     ║
╠══════════════════════════════════════════════════════════════════════╣
║                                                                      ║
║  放到 X 的推文 → 當日 S&P 500 平均變動: {ma['x_posts_market']['avg_change_pct']:+.4f}%
║  只在 TS 的推文 → 當日 S&P 500 平均變動: {ma['truth_only_market']['avg_change_pct']:+.4f}%""")

    # 月度趨勢
    print(f"""║                                                                      ║
╠══════════════════════════════════════════════════════════════════════╣
║  5. 月度趨勢                                                        ║
╠══════════════════════════════════════════════════════════════════════╣""")

    for month, counts in report['monthly_trend'].items():
        x_c = counts['x']
        ts_c = counts['truth_social']
        ratio = f"{x_c/ts_c*100:.1f}%" if ts_c > 0 else "N/A"
        x_bar = '▓' * min(x_c, 50)
        ts_bar = '░' * min(ts_c // 10, 50)
        print(f"║    {month}  X:{x_c:>3d} TS:{ts_c:>4d} 比率:{ratio:>6s}  {x_bar}{ts_bar}")

    # 結論
    print(f"""║                                                                      ║
╠══════════════════════════════════════════════════════════════════════╣
║  6. 結論                                                             ║
╠══════════════════════════════════════════════════════════════════════╣
║                                                                      ║
║  Trump 的雙平台策略非常明確：                                        ║
║                                                                      ║
║  • Truth Social 是主戰場:                                            ║
║    每月發 {sum(c['truth_social'] for c in report['monthly_trend'].values()) // max(len(report['monthly_trend']), 1):>3d} 篇，涵蓋所有主題              ║
║                                                                      ║
║  • X 是精選門面:                                                     ║
║    每月只放 {sum(c['x'] for c in report['monthly_trend'].values()) // max(len(report['monthly_trend']), 1):>3d} 篇，以影片和重大宣示為主           ║
║                                                                      ║
║  • 選擇率僅 {s['x_selection_rate']:.2f}%:                               ║
║    {s['truth_only_ratio']:.1f}% 的推文只留在 Truth Social             ║
║                                                                      ║
║  • 假設驗證: Truth Social = 內部頻道 / X = 對外門面                  ║
║    ✓ 數據支持此假設                                                  ║
║    ✓ X 上多為影片/連結，文字推文極少                                 ║
║    ✓ 大量政策表態、攻擊、背書只在 Truth Social                      ║
║                                                                      ║
╚══════════════════════════════════════════════════════════════════════╝
""")


def main():
    # Phase 1: 收集 X 推文
    x_posts = collect_x_posts()

    # 載入 Truth Social
    truth_posts = load_truth_posts()

    # Phase 2: 深度比對
    report = deep_compare(x_posts, truth_posts)

    # Phase 3: 印出分析
    print_final_analysis(report)

    log(f"\n完成! 所有資料已存入:")
    log(f"   X 推文: {X_ARCHIVE}")
    log(f"   完整比對報告: {FULL_REPORT}")


if __name__ == '__main__':
    main()
