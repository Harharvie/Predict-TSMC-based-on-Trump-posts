#!/usr/bin/env python3
"""
川普密碼 分析 #11 — 台積電大跌大漲分析 (>1% 波動)
使用 market_2330TW.json，重新定義「命中」= 預測到大漲(>1%)或大跌(<-1%)

⚡ 優化版：使用 bitmask 向量化加速暴力搜索
"""

import json
import re
from itertools import combinations
from collections import defaultdict, Counter
from datetime import datetime, timedelta
from pathlib import Path

BASE = Path(__file__).parent

def main():
    with open(BASE / "clean_president.json", 'r', encoding='utf-8') as f:
        posts = json.load(f)

    DATA = BASE / "data"

    # 使用台積電資料
    with open(DATA / "market_2330TW.json", 'r', encoding='utf-8') as f:
        tsmc = json.load(f)

    tsmc_by_date = {r['date']: r for r in tsmc}

    originals = sorted(
        [p for p in posts if p['has_text'] and not p.get('is_retweet', False)],
        key=lambda p: p['created_at']
    )

    daily_posts = defaultdict(list)
    for p in originals:
        daily_posts[p['created_at'][:10]].append(p)
    sorted_dates = sorted(daily_posts.keys())

    def next_td(date_str, market=None):
        if market is None:
            market = tsmc_by_date
        dt = datetime.strptime(date_str, '%Y-%m-%d')
        for i in range(1, 6):
            d = (dt + timedelta(days=i)).strftime('%Y-%m-%d')
            if d in market:
                return d
        return None

    print("=" * 90)
    print("🎯 分析 #12: 台積電 2330.TW 大跌大漲（日波動 >1%）")
    print("=" * 90)

    # === 找出台積電所有大波動日 ===
    big_up = []    # >1%
    big_down = []  # <-1%
    huge_up = []   # >2%
    huge_down = [] # <-2%
    normal = []    # -1% ~ +1%

    for ts in tsmc:
        ret = (ts['close'] - ts['open']) / ts['open'] * 100
        ts['return'] = ret
        if ret > 2:
            huge_up.append(ts)
        elif ret > 1:
            big_up.append(ts)
        elif ret < -2:
            huge_down.append(ts)
        elif ret < -1:
            big_down.append(ts)
        else:
            normal.append(ts)

    print(f"\n📊 台積電 2330.TW 日波動分布:")
    print(f"   暴漲 >2%:   {len(huge_up):3d} 天 ({len(huge_up)/len(tsmc)*100:.1f}%)")
    print(f"   大漲 1~2%:  {len(big_up):3d} 天 ({len(big_up)/len(tsmc)*100:.1f}%)")
    print(f"   正常 ±1%:   {len(normal):3d} 天 ({len(normal)/len(tsmc)*100:.1f}%)")
    print(f"   大跌 1~2%:  {len(big_down):3d} 天 ({len(big_down)/len(tsmc)*100:.1f}%)")
    print(f"   暴跌 >2%:   {len(huge_down):3d} 天 ({len(huge_down)/len(tsmc)*100:.1f}%)")

    all_big = huge_up + big_up + huge_down + big_down
    print(f"\n   台積電大波動天數: {len(all_big)} / {len(tsmc)} ({len(all_big)/len(tsmc)*100:.1f}%)")

    # === 大波動日的前一天，Trump 發了什麼？===
    print(f"\n{'='*90}")
    print("📊 台積電大波動日 vs 前一天的推文特徵")
    print("=" * 90)

    def prev_td(date_str):
        dt = datetime.strptime(date_str, '%Y-%m-%d')
        for i in range(1, 6):
            d = (dt - timedelta(days=i)).strftime('%Y-%m-%d')
            if d in tsmc_by_date:
                return d
        return None

    def day_features(date):
        """提取一天的推文特徵"""
        day_p = daily_posts.get(date, [])
        if not day_p:
            return None

        f = {}
        n = len(day_p)
        f['post_count'] = n

        all_text = ' '.join(p['content'].lower() for p in day_p)
        all_content = ' '.join(p['content'] for p in day_p)

        # 台積電 / 半導體相關關鍵字
        f['semiconductor'] = sum(1 for w in ['chip', 'semiconductor', 'tsmc', 'intel', 'nvidia'] if w in all_text)
        f['taiwan'] = sum(1 for w in ['taiwan', 'taipei'] if w in all_text)
        f['china'] = 1 if any(w in all_text for w in ['china', 'chinese', 'beijing']) else 0
        f['tariff'] = sum(1 for w in ['tariff', 'tariffs', 'duty'] if w in all_text)
        f['deal'] = sum(1 for w in ['deal', 'agreement', 'negotiate', 'signed'] if w in all_text)
        f['supply_chain'] = sum(1 for w in ['supply', 'chain', 'manufacture'] if w in all_text)

        # 情緒與風格
        f['attack'] = sum(1 for w in ['fake news', 'corrupt', 'fraud', 'disgrace'] if w in all_text)
        f['positive'] = sum(1 for w in ['great', 'tremendous', 'incredible', 'beautiful'] if w in all_text)
        f['action'] = sum(1 for w in ['immediately', 'executive order', 'just signed'] if w in all_text)

        # 大寫率、驚嘆號
        caps = sum(1 for c in all_content if c.isupper())
        alpha = sum(1 for c in all_content if c.isalpha())
        f['caps_ratio'] = round(caps / max(alpha, 1) * 100, 1)
        f['excl'] = all_content.count('!')

        f['avg_len'] = round(sum(len(p['content']) for p in day_p) / n)
        f['sentiment'] = f['positive'] - f['attack']

        return f

    # 分析大漲日 vs 大跌日的前一天特徵差異
    print(f"\n📈 台積電大漲日（>1%）前一天 vs 📉 大跌日（<-1%）前一天:")
    print(f"{'='*90}")

    up_features = []
    down_features = []

    for ts in huge_up + big_up:
        prev = prev_td(ts['date'])
        if prev:
            feat = day_features(prev)
            if feat:
                up_features.append(feat)

    for ts in huge_down + big_down:
        prev = prev_td(ts['date'])
        if prev:
            feat = day_features(prev)
            if feat:
                down_features.append(feat)

    def avg_feat(features, key):
        vals = [f[key] for f in features if key in f]
        return sum(vals) / max(len(vals), 1)

    print(f"\n  {'特徵':20s} | {'大漲前一天':>10s} | {'大跌前一天':>10s} | {'差異':>10s} | 解讀")
    print(f"  {'-'*20}-+-{'-'*10}-+-{'-'*10}-+-{'-'*10}-+-{'-'*30}")

    features_to_compare = [
        ('post_count', '發文量', '篇'),
        ('semiconductor', '半導體', '次'),
        ('taiwan', '台灣', ''),
        ('china', '中國', ''),
        ('tariff', '關稅', '次'),
        ('deal', '交易', '次'),
        ('supply_chain', '供應鏈', '次'),
        ('attack', '攻擊用詞', '次'),
        ('positive', '正面用詞', '次'),
        ('caps_ratio', '大寫率', '%'),
        ('excl', '驚嘆號', '個'),
        ('avg_len', '平均文長', '字'),
        ('sentiment', '情緒淨值', ''),
    ]

    for key, label, unit in features_to_compare:
        up_avg = avg_feat(up_features, key)
        down_avg = avg_feat(down_features, key)
        diff = up_avg - down_avg

        # 解讀
        if abs(diff) < 0.01:
            interpretation = "無差異"
        elif key == 'tariff' and diff < -0.5:
            interpretation = "⚡ 關稅越多→越容易大跌"
        elif key == 'semiconductor' and diff > 0.3:
            interpretation = "⚡ 半導體越多→越容易大漲"
        elif key == 'china' and diff < -0.1:
            interpretation = "⚡ 中國相關→大跌機率高"
        elif abs(diff) > 0.3:
            interpretation = f"{'大漲前較高' if diff > 0 else '大跌前較高'}"
        else:
            interpretation = "差異不大"

        print(f"  {label:20s} | {up_avg:>9.1f}{unit} | {down_avg:>9.1f}{unit} | {diff:>+9.2f} | {interpretation}")

    # === 大波動預測模型（針對台積電）===
    print(f"\n{'='*90}")
    print("📊 台積電大波動預測暴力搜索")
    print("   目標：用前一天推文預測「明天台積電是大漲日還是大跌日」")
    print("=" * 90)

    # 為每個交易日標記：大漲/大跌/普通
    day_labels = {}
    for ts in tsmc:
        ret = ts['return']
        if ret > 1:
            day_labels[ts['date']] = 'BIG_UP'
        elif ret < -1:
            day_labels[ts['date']] = 'BIG_DOWN'
        else:
            day_labels[ts['date']] = 'NORMAL'

    # 台積電相關關鍵字
    KEYWORDS = [
        'chip', 'semiconductor', 'tsmc', 'intel', 'nvidia', 'amd', 'taiwan', 'taipei',
        'china', 'chinese', 'beijing', 'tariff', 'tariffs', 'duty', 'trade',
        'deal', 'agreement', 'supply', 'manufacture', 'fab', 'foundry',
        'great', 'tremendous', 'incredible', 'fake', 'corrupt', 'disgrace',
        'stock market', 'record', 'immediately', 'executive order',
    ]

    # 預先為每個日期生成文字快取
    _text_cache = {}
    for date in sorted_dates:
        day_p = daily_posts.get(date, [])
        if day_p:
            _text_cache[date] = ' '.join(p['content'].lower() for p in day_p)

    def compute_binary_features(date, idx):
        day_p = daily_posts.get(date, [])
        if not day_p:
            return None

        f = {}
        n = len(day_p)
        all_text = _text_cache.get(date, '')
        all_content = ' '.join(p['content'] for p in day_p)

        # 發文量
        f['posts_high'] = n >= 20
        f['posts_very_high'] = n >= 35
        f['posts_low'] = n <= 5

        # 大寫率、驚嘆號
        caps = sum(1 for c in all_content if c.isupper())
        alpha = sum(1 for c in all_content if c.isalpha())
        cr = caps / max(alpha, 1)
        f['caps_high'] = cr > 0.18
        f['caps_very_high'] = cr > 0.25

        excl = all_content.count('!')
        f['excl_heavy'] = excl >= 5

        # 台積電關鍵特徵
        f['taiwan_related'] = any(w in all_text for w in ['taiwan', 'taipei'])
        f['china_taiwan'] = 'china' in all_text and 'taiwan' in all_text
        f['semiconductor'] = any(w in all_text for w in ['chip', 'semiconductor', 'tsmc'])
        f['trade_war'] = any(w in all_text for w in ['tariff', 'tariffs']) and 'china' in all_text

        for kw in KEYWORDS:
            kw_clean = kw.replace(' ', '_')
            count = all_text.count(kw)
            if count >= 1:
                f[f'kw_{kw_clean}'] = True
            if count >= 2:
                f[f'kw_{kw_clean}_heavy'] = True

        return {k: v for k, v in f.items() if v is True}

    # 計算所有天的特徵
    log_features = {}
    for idx, date in enumerate(sorted_dates):
        feat = compute_binary_features(date, idx)
        if feat:
            log_features[date] = feat

    # 有效特徵
    feat_counts = Counter()
    for feat in log_features.values():
        feat_counts.update(feat.keys())
    useful = sorted([f for f, c in feat_counts.items() if 3 <= c <= 100])
    print(f"   台積電相關有效特徵: {len(useful)} 個")

    # 分割訓練/測試
    _all_valid = [d for d in sorted_dates if d in log_features]
    n_dates = len(_all_valid)
    cutoff_idx = int(n_dates * 0.75)
    cutoff = _all_valid[cutoff_idx] if n_dates > 0 else "2025-12-01"
    train_dates = _all_valid[:cutoff_idx]
    test_dates = _all_valid[cutoff_idx:]

    print(f"   訓練集: {len(train_dates)} 天, 測試集: {len(test_dates)} 天")

    # =========================================================
    # ⚡ bitmask 向量化暴力搜索
    # =========================================================
    print(f"\n🔨 台積電大波動搜索中（bitmask 加速）...")

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
        feat_mask = {f: 0 for f in feature_names}
        target_up = 0
        target_down = 0
        valid = 0

        for i, d in enumerate(dates):
            bit = 1 << i
            feat = features_dict.get(d, {})
            for fname in feat:
                if fname in feat_mask:
                    feat_mask[fname] |= bit

            lbl = next_labels.get(d)
            if lbl is not None:
                valid |= bit
                if lbl == 'BIG_UP':
                    target_up |= bit
                elif lbl == 'BIG_DOWN':
                    target_down |= bit

        return feat_mask, {'BIG_UP': target_up, 'BIG_DOWN': target_down}, valid

    tr_feat_mask, tr_target, tr_valid = build_masks(
        train_dates, train_next, useful, log_features
    )
    te_feat_mask, te_target, te_valid = build_masks(
        test_dates, test_next, useful, log_features
    )

    winners = []
    tested = 0

    tr_single = [tr_feat_mask[useful[i]] for i in range(n_feat)]
    te_single = [te_feat_mask[useful[i]] for i in range(n_feat)]

    # 2-combo 搜索
    for i in range(n_feat):
        tr_i = tr_single[i]
        te_i = te_single[i]
        for j in range(i + 1, n_feat):
            tr_match = tr_i & tr_single[j]
            tr_total = tr_match.bit_count()
            if tr_total < 3:
                tested += 2
                continue

            te_match = te_i & te_single[j]

            feature_combo = [useful[i], useful[j]]
            for target in ('BIG_UP', 'BIG_DOWN'):
                tested += 1
                tr_hits = (tr_match & tr_target[target]).bit_count()
                train_rate = tr_hits / tr_total * 100
                if train_rate < 50:
                    continue

                te_total = te_match.bit_count()
                if te_total < 2:
                    continue

                te_hits = (te_match & te_target[target]).bit_count()
                test_rate = te_hits / te_total * 100
                if test_rate >= 40:
                    winners.append({
                        'features': feature_combo,
                        'target': target,
                        'train_total': tr_total,
                        'train_hits': tr_hits,
                        'train_rate': round(train_rate, 1),
                        'test_total': te_total,
                        'test_hits': te_hits,
                        'test_rate': round(test_rate, 1),
                        'combined': round((train_rate + test_rate) / 2, 1),
                    })

    print(f"   完成！測試 {tested:,} 組，候選 {len(winners)} 組")

    # 結果排序與展示
    up_winners = sorted([w for w in winners if w['target'] == 'BIG_UP'],
                        key=lambda w: -w['combined'])
    down_winners = sorted([w for w in winners if w['target'] == 'BIG_DOWN'],
                          key=lambda w: -w['combined'])

    print(f"\n{'='*90}")
    print(f"🚀 Top 10: 台積電預測大漲（隔天 >1%）的信號組合")
    print(f"{'='*90}")
    print(f"  {'#':>3s} | {'訓練':>10s} | {'驗證':>10s} | 條件")
    for i, w in enumerate(up_winners[:10], 1):
        feats = ' + '.join(w['features'])
        print(f"  {i:3d} | {w['train_hits']}/{w['train_total']} ({w['train_rate']:.0f}%) | {w['test_hits']}/{w['test_total']} ({w['test_rate']:.0f}%) | {feats}")

    print(f"\n{'='*90}")
    print(f"💥 Top 10: 台積電預測大跌（隔天 <-1%）的信號組合")
    print(f"{'='*90}")
    print(f"  {'#':>3s} | {'訓練':>10s} | {'驗證':>10s} | 條件")
    for i, w in enumerate(down_winners[:10], 1):
        feats = ' + '.join(w['features'])
        print(f"  {i:3d} | {w['train_hits']}/{w['train_total']} ({w['train_rate']:.0f}%) | {w['test_hits']}/{w['test_total']} ({w['test_rate']:.0f}%) | {feats}")

    # 大波動日列表
    print(f"\n{'='*90}")
    print(f"📋 台積電每個大波動日的前一天推文信號")
    print(f"{'='*90}")

    all_big_days = sorted(huge_up + big_up + huge_down + big_down, key=lambda x: x['date'])

    print(f"  {'日期':12s} | {'2330':>8s} | {'前天篇數':>6s} | {'半導體':>4s} | {'台灣':>4s} | {'中國':>4s} | {'關稅':>4s} | {'前天摘要'}")
    print(f"  {'-'*12}-+-{'-'*8}-+-{'-'*6}-+-{'-'*4}-+-{'-'*4}-+-{'-'*4}-+-{'-'*4}-+-{'-'*40}")

    for ts in all_big_days:
        prev = prev_td(ts['date'])
        feat = day_features(prev) if prev else None

        if feat:
            sample = daily_posts.get(prev, [{}])
            first_content = sample[0].get('content', '')[:40] if sample else ''
            arrow = "🚀" if ts['return'] > 0 else "💥"
            print(f"  {ts['date']:12s} | {ts['return']:+.2f}% {arrow} | {feat['post_count']:>5d} | "
                  f"{feat.get('semiconductor',0):>3d} | {feat.get('taiwan',0):>3d} | "
                  f"{feat.get('china',0):>3d} | {feat.get('tariff',0):>3d} | {first_content}")

    # 存結果
    output = {
        'tsmc_big_move_stats': {
            'huge_up': len(huge_up), 'big_up': len(big_up),
            'huge_down': len(huge_down), 'big_down': len(big_down),
            'normal': len(normal),
        },
        'up_rules': up_winners[:30],
        'down_rules': down_winners[:30],
        'big_move_days': [{'date': d['date'], 'return': d['return']} for d in all_big_days],
    }
    with open(DATA / 'results_12_tsmc_bigmoves.json', 'w', encoding='utf-8') as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    print(f"\n💾 台積電分析結果存入 results_12_tsmc_bigmoves.json")
    print(f"   總結：找到 {len(up_winners)} 組大漲信號，{len(down_winners)} 組大跌信號")

if __name__ == '__main__':
    main()
