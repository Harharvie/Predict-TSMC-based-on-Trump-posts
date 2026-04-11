#!/usr/bin/env python3
"""
Musk Code — Elon Musk 版暴力搜索原型

同樣的方法論：推文特徵 → 暴力搜索組合 → 預測 $TSLA / $DOGE
跟 Trump Code 完全相同的引擎，只是換了人物和關鍵字。
"""

import json
import csv
from datetime import datetime, timedelta
from pathlib import Path
from collections import defaultdict
from itertools import combinations

BASE = Path(__file__).parent
DATA = BASE / "data"

# =====================================================================
# ① 載入推文
# =====================================================================

def load_musk_posts(filepath: str = None) -> list[dict]:
    """載入 Musk 推文。支援 JSON 或 CSV。"""
    if filepath is None:
        # 嘗試常見路徑
        for p in [DATA / "musk_posts.json", DATA / "musk_tweets.json", DATA / "musk_tweets.csv"]:
            if p.exists():
                filepath = str(p)
                break
    
    if filepath is None:
        print("❌ 找不到 Musk 推文檔案！")
        print("   請放到 data/musk_posts.json 或 data/musk_tweets.csv")
        return []
    
    filepath = Path(filepath)
    posts = []
    
    if filepath.suffix == '.json':
        with open(filepath, encoding='utf-8') as f:
            data = json.load(f)
        if isinstance(data, list):
            posts = data
        elif isinstance(data, dict):
            posts = data.get('posts', data.get('tweets', data.get('data', [])))
    
    elif filepath.suffix == '.csv':
        with open(filepath, encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                content = row.get('text', row.get('content', row.get('tweet', '')))
                date = row.get('date', row.get('created_at', row.get('datetime', '')))
                if content and date:
                    posts.append({'content': content, 'created_at': date})
    
    print(f"📥 載入 {len(posts)} 篇 Musk 推文 from {filepath.name}")
    return posts


# =====================================================================
# ② 載入市場數據
# =====================================================================

def load_market_data() -> dict:
    """載入 TSLA + DOGE 每日價格。"""
    try:
        import yfinance as yf
    except ImportError:
        print("❌ 需要 yfinance: pip3 install yfinance")
        return {}
    
    print("📈 下載 TSLA 歷史數據...")
    tsla = yf.Ticker("TSLA")
    hist = tsla.history(period="2y")
    
    market = {}
    prev_close = None
    for date, row in hist.iterrows():
        d = date.strftime('%Y-%m-%d')
        close = row['Close']
        if prev_close and prev_close > 0:
            change = (close - prev_close) / prev_close * 100
            market[d] = {
                'tsla_close': round(close, 2),
                'tsla_change': round(change, 3),
            }
        prev_close = close
    
    print(f"   TSLA: {len(market)} 交易日")
    
    # DOGE（CoinGecko 90 天歷史）
    try:
        import urllib.request
        url = 'https://api.coingecko.com/api/v3/coins/dogecoin/market_chart?vs_currency=usd&days=365'
        req = urllib.request.Request(url, headers={'User-Agent': 'MuskCode/1.0'})
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.load(resp)
        
        prices = data.get('prices', [])
        prev_price = None
        for ts, price in prices:
            d = datetime.utcfromtimestamp(ts / 1000).strftime('%Y-%m-%d')
            if d in market and prev_price and prev_price > 0:
                change = (price - prev_price) / prev_price * 100
                market[d]['doge_price'] = round(price, 6)
                market[d]['doge_change'] = round(change, 3)
            prev_price = price
        
        doge_days = sum(1 for m in market.values() if 'doge_change' in m)
        print(f"   DOGE: {doge_days} 天有數據")
    except Exception as e:
        print(f"   ⚠️ DOGE 數據失敗: {e}")
    
    return market


# =====================================================================
# ③ Musk 專用特徵提取
# =====================================================================

MUSK_KEYWORDS = {
    # Tesla 相關
    'TESLA_PRODUCT': ['model', 'cybertruck', 'roadster', 'semi', 'megapack', 'powerwall', 'supercharger', 'fsd', 'autopilot', 'optimus'],
    'TESLA_GOOD': ['record', 'deliveries', 'production', 'milestone', 'incredible', 'amazing', 'insane'],
    'TESLA_BAD': ['recall', 'delay', 'lawsuit', 'investigation', 'fire', 'crash', 'defect'],
    
    # SpaceX
    'SPACEX': ['spacex', 'starship', 'falcon', 'starlink', 'launch', 'landing', 'mars', 'orbit'],
    
    # 加密貨幣
    'CRYPTO_BULL': ['doge', 'dogecoin', 'bitcoin', 'btc', 'crypto', 'moon', 'hodl', 'diamond hands', '🚀', '💎'],
    'CRYPTO_BEAR': ['sell', 'dump', 'crash', 'regulation', 'sec', 'ban'],
    
    # AI / xAI
    'AI': ['grok', 'xai', 'artificial intelligence', 'ai', 'agi', 'neural', 'training'],
    
    # 政治 / 衝突
    'POLITICAL': ['government', 'regulation', 'sec', 'congress', 'biden', 'trump', 'election', 'vote', 'doge department'],
    'ATTACK': ['media', 'fake', 'woke', 'propaganda', 'corrupt', 'censorship', 'legacy media'],
    
    # 個人 / 迷因
    'MEME': ['lol', 'lmao', '😂', '🤣', 'meme', 'based', 'ratio'],
    'PHILOSOPHICAL': ['civilization', 'humanity', 'consciousness', 'multiplanetary', 'extinction', 'population'],
    
    # 市場相關
    'MARKET': ['stock', 'share', 'investor', 'short', 'squeeze', 'valuation', 'market cap'],
}

def compute_musk_features(posts_on_day: list[dict]) -> dict:
    """計算某天 Musk 推文的二元特徵。"""
    if not posts_on_day:
        return {}
    
    f = {}
    n = len(posts_on_day)
    all_text = ' '.join(p.get('content', '').lower() for p in posts_on_day)
    
    # 推文數量
    f['posts_high'] = n >= 10
    f['posts_medium'] = 3 <= n < 10
    f['posts_low'] = n <= 2
    f['posts_zero'] = n == 0  # 沉默
    
    # 關鍵字特徵
    for sig_type, keywords in MUSK_KEYWORDS.items():
        matched = [kw for kw in keywords if kw in all_text]
        f[sig_type.lower()] = len(matched) > 0
        f[f'{sig_type.lower()}_strong'] = len(matched) >= 3
    
    # 情緒特徵
    caps_ratio = sum(1 for c in all_text if c.isupper()) / max(sum(1 for c in all_text if c.isalpha()), 1)
    excl_count = all_text.count('!')
    emoji_count = sum(1 for c in all_text if ord(c) > 0x1F600)
    
    f['high_energy'] = caps_ratio > 0.15 or excl_count > 5
    f['emoji_heavy'] = emoji_count > 3
    f['short_tweets'] = all(len(p.get('content', '')) < 50 for p in posts_on_day)
    f['long_tweets'] = any(len(p.get('content', '')) > 280 for p in posts_on_day)
    
    # 時間特徵
    hours = []
    for p in posts_on_day:
        try:
            dt = datetime.fromisoformat(p['created_at'].replace('Z', '+00:00'))
            hours.append(dt.hour)
        except (ValueError, KeyError):
            pass
    
    if hours:
        f['late_night'] = any(0 <= h < 6 for h in hours)  # 深夜推文
        f['early_morning'] = any(5 <= h < 9 for h in hours)
        f['market_hours'] = any(14 <= h < 21 for h in hours)  # UTC 14-21 = US market
    
    return f


# =====================================================================
# ④ 暴力搜索（跟 Trump Code 完全相同的邏輯）
# =====================================================================

def brute_force_search(daily_features: dict, market: dict, sorted_dates: list, target_asset: str = 'tsla'):
    """
    暴力搜索：前一天的推文特徵 → 今天 TSLA/DOGE 的大漲或大跌？
    """
    change_key = f'{target_asset}_change'
    
    # 定義大漲/大跌門檻
    if target_asset == 'tsla':
        BIG_THRESHOLD = 3.0  # TSLA 波動大，用 3%
    else:
        BIG_THRESHOLD = 5.0  # DOGE 波動更大，用 5%
    
    # 標記每天的 label
    day_labels = {}
    for d in sorted_dates:
        if d in market and change_key in market[d]:
            change = market[d][change_key]
            if change > BIG_THRESHOLD:
                day_labels[d] = 'BIG_UP'
            elif change < -BIG_THRESHOLD:
                day_labels[d] = 'BIG_DOWN'
            else:
                day_labels[d] = 'NORMAL'
    
    big_up = sum(1 for v in day_labels.values() if v == 'BIG_UP')
    big_down = sum(1 for v in day_labels.values() if v == 'BIG_DOWN')
    total = len(day_labels)
    print(f"\n📊 {target_asset.upper()} 大波動 (±{BIG_THRESHOLD}%)")
    print(f"   大漲: {big_up} 天 | 大跌: {big_down} 天 | 正常: {total - big_up - big_down} 天 | 共 {total} 天")
    
    # 找有用的特徵（至少出現 5 天）
    all_features = set()
    for feat in daily_features.values():
        all_features.update(k for k, v in feat.items() if v)
    
    feature_counts = defaultdict(int)
    for feat in daily_features.values():
        for k, v in feat.items():
            if v:
                feature_counts[k] += 1
    
    useful = [f for f in sorted(all_features) if 5 <= feature_counts[f] <= total - 5]
    print(f"   有用特徵: {len(useful)} 個（出現 5~{total-5} 天）")
    
    if len(useful) < 2:
        print("   ⚠️ 特徵太少，無法搜索")
        return []
    
    # 交易日查找
    trading_dates = sorted(day_labels.keys())
    td_set = set(trading_dates)
    
    def next_td(d):
        dt = datetime.strptime(d, '%Y-%m-%d')
        for i in range(1, 5):
            nd = (dt + timedelta(days=i)).strftime('%Y-%m-%d')
            if nd in td_set:
                return nd
        return None
    
    # 訓練/測試切分（80/20）
    valid_dates = [d for d in sorted_dates if d in daily_features and daily_features[d]]
    cutoff = int(len(valid_dates) * 0.8)
    train_dates = valid_dates[:cutoff]
    test_dates = valid_dates[cutoff:]
    print(f"   訓練: {len(train_dates)} 天 | 測試: {len(test_dates)} 天")
    
    # Bitmask 暴力搜索（from PR #7）
    print(f"\n🔨 搜索中（bitmask 加速）...")
    
    n_feat = len(useful)
    
    def _precompute_next_labels(dates):
        result = {}
        for d in dates:
            ntd = next_td(d)
            if ntd and ntd in day_labels:
                result[d] = day_labels[ntd]
            else:
                result[d] = None
        return result
    
    train_next = _precompute_next_labels(train_dates)
    test_next = _precompute_next_labels(test_dates)
    
    def build_masks(dates, next_labels, feature_names, features_dict):
        feat_mask = {f_name: 0 for f_name in feature_names}
        target_up = 0
        target_down = 0
        valid = 0
        
        for i, d in enumerate(dates):
            bit = 1 << i
            feat = features_dict.get(d, {})
            for fname in feat:
                if fname in feat_mask and feat[fname]:
                    feat_mask[fname] |= bit
            
            lbl = next_labels.get(d)
            if lbl is not None:
                valid |= bit
                if lbl == 'BIG_UP':
                    target_up |= bit
                elif lbl == 'BIG_DOWN':
                    target_down |= bit
        
        return feat_mask, {'BIG_UP': target_up, 'BIG_DOWN': target_down}, valid
    
    tr_feat_mask, tr_target, tr_valid = build_masks(train_dates, train_next, useful, daily_features)
    te_feat_mask, te_target, te_valid = build_masks(test_dates, test_next, useful, daily_features)
    
    popcount = lambda x: bin(x).count('1')  # Python 3.9 相容
    
    winners = []
    tested = 0
    
    tr_single = [tr_feat_mask[useful[i]] for i in range(n_feat)]
    te_single = [te_feat_mask[useful[i]] for i in range(n_feat)]
    
    # 2-combo
    for i in range(n_feat):
        tr_i = tr_single[i]
        te_i = te_single[i]
        for j in range(i + 1, n_feat):
            tr_match = tr_i & tr_single[j]
            tr_total = popcount(tr_match)
            if tr_total < 3:
                tested += 2
                continue
            
            te_match = te_i & te_single[j]
            feature_combo = [useful[i], useful[j]]
            
            for target in ('BIG_UP', 'BIG_DOWN'):
                tested += 1
                tr_hits = popcount(tr_match & tr_target[target])
                train_rate = tr_hits / tr_total * 100
                if train_rate < 50:
                    continue
                
                te_total = popcount(te_match)
                if te_total < 2:
                    continue
                
                te_hits = popcount(te_match & te_target[target])
                test_rate = te_hits / te_total * 100
                if test_rate >= 40:
                    winners.append({
                        'features': feature_combo,
                        'target': target,
                        'asset': target_asset,
                        'train_total': tr_total,
                        'train_hits': tr_hits,
                        'train_rate': round(train_rate, 1),
                        'test_total': te_total,
                        'test_hits': te_hits,
                        'test_rate': round(test_rate, 1),
                        'combined': round((train_rate + test_rate) / 2, 1),
                    })
    
    print(f"   2-combo: {tested:,} 組，候選 {len(winners)}")
    
    # 3-combo
    tested_3 = 0
    for i in range(n_feat):
        tr_i = tr_single[i]
        te_i = te_single[i]
        for j in range(i + 1, n_feat):
            tr_ij = tr_i & tr_single[j]
            if popcount(tr_ij) < 3:
                tested_3 += (n_feat - j - 1) * 2
                continue
            te_ij = te_i & te_single[j]
            for k in range(j + 1, n_feat):
                tr_match = tr_ij & tr_single[k]
                tr_total = popcount(tr_match)
                if tr_total < 3:
                    tested_3 += 2
                    continue
                
                te_match = te_ij & te_single[k]
                feature_combo = [useful[i], useful[j], useful[k]]
                
                for target in ('BIG_UP', 'BIG_DOWN'):
                    tested_3 += 1
                    tr_hits = popcount(tr_match & tr_target[target])
                    train_rate = tr_hits / tr_total * 100
                    if train_rate < 50:
                        continue
                    
                    te_total = popcount(te_match)
                    if te_total < 2:
                        continue
                    
                    te_hits = popcount(te_match & te_target[target])
                    test_rate = te_hits / te_total * 100
                    if test_rate >= 40:
                        winners.append({
                            'features': feature_combo,
                            'target': target,
                            'asset': target_asset,
                            'train_total': tr_total,
                            'train_hits': tr_hits,
                            'train_rate': round(train_rate, 1),
                            'test_total': te_total,
                            'test_hits': te_hits,
                            'test_rate': round(test_rate, 1),
                            'combined': round((train_rate + test_rate) / 2, 1),
                        })
    
    tested += tested_3
    print(f"   3-combo: {tested_3:,} 組")
    print(f"\n✅ 完成！測試 {tested:,} 組 → 候選 {len(winners)} 組")
    
    if winners:
        winners.sort(key=lambda w: w['combined'], reverse=True)
        print(f"\n🏆 Top 10 預測規則 ({target_asset.upper()}):")
        for i, w in enumerate(winners[:10]):
            icon = '🚀' if w['target'] == 'BIG_UP' else '💥'
            print(f"   {i+1}. {icon} {' + '.join(w['features'])} → {w['target']}")
            print(f"      訓練: {w['train_hits']}/{w['train_total']} = {w['train_rate']}%")
            print(f"      驗證: {w['test_hits']}/{w['test_total']} = {w['test_rate']}%")
            print(f"      綜合: {w['combined']}%")
    
    return winners


# =====================================================================
# ⑤ 主程式
# =====================================================================

def main():
    print("=" * 70)
    print("🚀 MUSK CODE — Elon Musk 推文 × 市場影響力暴力搜索")
    print("   同引擎，換人物。Let's see what the data says.")
    print("=" * 70)
    
    # 載入推文
    posts = load_musk_posts()
    if not posts:
        return
    
    # 按日分組
    daily_posts = defaultdict(list)
    for p in posts:
        date = (p.get('created_at', '') or '')[:10]
        if date >= '2024-01-01':
            daily_posts[date].append(p)
    
    sorted_dates = sorted(daily_posts.keys())
    print(f"📅 {sorted_dates[0]} ~ {sorted_dates[-1]} ({len(sorted_dates)} 天有推文)")
    
    # 載入市場數據
    market = load_market_data()
    if not market:
        return
    
    # 計算每天的特徵
    print(f"\n🔬 計算每日推文特徵...")
    daily_features = {}
    for date in sorted_dates:
        daily_features[date] = compute_musk_features(daily_posts[date])
    
    # 暴力搜索
    all_winners = []
    
    # TSLA
    tsla_winners = brute_force_search(daily_features, market, sorted_dates, 'tsla')
    all_winners.extend(tsla_winners)
    
    # DOGE（如果有數據）
    if any('doge_change' in m for m in market.values()):
        doge_winners = brute_force_search(daily_features, market, sorted_dates, 'doge')
        all_winners.extend(doge_winners)
    
    # 存結果
    output = {
        'total_posts': sum(len(v) for v in daily_posts.values()),
        'date_range': {'start': sorted_dates[0], 'end': sorted_dates[-1]},
        'tsla_winners': [w for w in all_winners if w['asset'] == 'tsla'],
        'doge_winners': [w for w in all_winners if w['asset'] == 'doge'],
    }
    
    out_file = DATA / "results_musk_prototype.json"
    with open(out_file, 'w', encoding='utf-8') as f:
        json.dump(output, f, ensure_ascii=False, indent=2)
    
    print(f"\n💾 結果存入 {out_file}")
    print(f"   TSLA 候選: {len(output['tsla_winners'])} 組")
    print(f"   DOGE 候選: {len(output['doge_winners'])} 組")


if __name__ == '__main__':
    main()
