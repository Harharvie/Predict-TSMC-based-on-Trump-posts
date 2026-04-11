#!/usr/bin/env python3
"""
川普密碼 分析 #10 — 台積電2330版本：密碼換碼偵測 + 台股連動
追蹤川普發文風格變化對台積電2330的影響：什麼時候換了說法、換了節奏
如果密碼會換，那「偵測到他換密碼」本身就是最強的信號
"""

import json
import re
from collections import defaultdict, Counter
from datetime import datetime, timedelta
from pathlib import Path

BASE = Path(__file__).parent

def main():
    # 載入川普貼文資料
    with open(BASE / "clean_president.json", 'r', encoding='utf-8') as f:
        posts = json.load(f)

    originals = sorted(
        [p for p in posts if p['has_text'] and not p['is_retweet']],
        key=lambda p: p['created_at']
    )

    DATA = BASE / "data"

    # 載入台積電2330資料 (取代原本的S&P500)
    print("📈 載入台積電2330市場資料...")
    with open(DATA / "market_2330TW.json", 'r', encoding='utf-8') as f:
        tsmc_data = json.load(f)
    tsmc_by_date = {r['date']: r for r in tsmc_data}
    print(f"   成功載入 {len(tsmc_by_date)} 個交易日資料")

    print("=" * 90)
    print("🔄 分析 #10: 台積電2330 密碼換碼偵測")
    print(f"   追蹤 {len(originals)} 篇貼文對2330的風格演化影響")
    print("=" * 90)

    # === 1. 台積電相關口頭禪演化追蹤 ===
    print(f"\n{'='*90}")
    print("📊 1. 台積電相關口頭禪出現/消失時間線")
    print("=" * 90)

    # 針對台積電/半導體/科技戰相關的關鍵詞
    tsmc_catchphrases = [
        'taiwan', 'semiconductor', 'chip', 'chips', 'tsmc',
        'foundry', 'advanced chip', 'microchip', 'silicon',
        'intel', 'nvidia', 'amd', 'qualcomm',
        'china taiwan', 'taiwan strait', 'trade war',
        'technology war', 'supply chain', 'critical technology'
    ]

    monthly_phrases = defaultdict(lambda: defaultdict(int))
    for p in originals:
        month = p['created_at'][:7]
        cl = p['content'].lower()
        for phrase in tsmc_catchphrases:
            if phrase in cl:
                monthly_phrases[phrase][month] += 1

    months = sorted(set(p['created_at'][:7] for p in originals))

    print(f"\n  台積電關鍵詞月度變化（✦=新出現 ✗=消失 數字=次數）：")
    for phrase in tsmc_catchphrases:
        counts = [monthly_phrases[phrase].get(m, 0) for m in months]
        if sum(counts) < 2:  # 降低門檻，捕捉更多信號
            continue

        first_seen = next((m for m, c in zip(months, counts) if c > 0), '?')
        last_seen = next((m for m, c in reversed(list(zip(months, counts))) if c > 0), '?')

        first_half = sum(counts[:len(counts)//2])
        second_half = sum(counts[len(counts)//2:])
        trend = "📈增加" if second_half > first_half * 1.3 else ("📉減少" if second_half < first_half * 0.7 else "➡️穩定")

        bar = ''.join([f"{c:>2d}" if c > 0 else ' ·' for c in counts])
        print(f"\n  「{phrase}」")
        print(f"     首見:{first_seen} 末見:{last_seen} 趨勢:{trend} 總計:{sum(counts)}")
        print(f"     {' '.join(m[-2:] for m in months)}")
        print(f"     {bar}")

    # === 2. 台積電相關新詞彙首次出現 ===
    print(f"\n{'='*90}")
    print("📊 2. 台積電關鍵信號詞首次出現時間")
    print("=" * 90)

    tsmc_keywords = [
        'taiwan semiconductor', 'tsmc', 'foundry', '3nm', '2nm', '5nm',
        'advanced packaging', 'cowo', 'chip war', 'semiconductor war',
        'taiwan chip', 'taiwan production', 'fab', 'wafer',
        'nvidia chip', 'ai chip', 'h100', 'h20', 'blackwell',
        'trade restriction', 'export control', 'entity list'
    ]

    keyword_first_appearance = {}
    keyword_monthly = defaultdict(lambda: defaultdict(int))

    for p in originals:
        cl = p['content'].lower()
        month = p['created_at'][:7]
        for kw in tsmc_keywords:
            if kw in cl:
                keyword_monthly[kw][month] += 1
                if kw not in keyword_first_appearance:
                    keyword_first_appearance[kw] = p['created_at'][:10]

    sorted_kw = sorted(keyword_first_appearance.items(), key=lambda x: x[1])
    print(f"\n  {'關鍵字':30s} | {'首次出現':12s} | {'出現頻率'}")
    for kw, first_date in sorted_kw:
        counts = [keyword_monthly[kw].get(m, 0) for m in months]
        total = sum(counts)
        if total < 3:
            continue
        print(f"  {kw:30s} | {first_date:12s} | {total:3d}次")

    # === 3. 台積電相關發文 vs 2330隔日表現 ===
    print(f"\n{'='*90}")
    print("📊 3. 台積電關鍵詞發文日 vs 2330隔日表現")
    print("=" * 90)

    def next_trading_day(date_str):
        """找到下一個交易日"""
        dt = datetime.strptime(date_str, '%Y-%m-%d')
        for i in range(1, 10):  # 最多找10天後
            d = (dt + timedelta(days=i)).strftime('%Y-%m-%d')
            if d in tsmc_by_date:
                return d
        return None

    # 建立每日關鍵詞特徵
    daily_features = defaultdict(lambda: {'posts': 0, 'tsmc_mentions': 0, 'trade_war': 0})

    for p in originals:
        date = p['created_at'][:10]
        daily_features[date]['posts'] += 1
        cl = p['content'].lower()

        # 台積電相關
        if any(kw in cl for kw in ['taiwan', 'semiconductor', 'chip', 'tsmc', 'foundry']):
            daily_features[date]['tsmc_mentions'] += 1

        # 貿易戰相關
        if any(kw in cl for kw in ['trade war', 'tariff', 'china', 'export control']):
            daily_features[date]['trade_war'] += 1

    # 計算隔日報酬
    tsmc_signal_days = {'tsmc': [], 'trade_war': [], 'normal': []}

    for date, features in daily_features.items():
        next_day = next_trading_day(date)
        if not next_day or next_day not in tsmc_by_date:
            continue

        tsmc = tsmc_by_date[next_day]
        ret = (tsmc['close'] - tsmc['open']) / tsmc['open'] * 100

        if features['tsmc_mentions'] > 0:
            tsmc_signal_days['tsmc'].append(ret)
        elif features['trade_war'] > 0:
            tsmc_signal_days['trade_war'].append(ret)
        else:
            tsmc_signal_days['normal'].append(ret)

    # 統計結果
    print(f"\n  2330隔日表現統計：")
    print(f"  台積電相關發文日 ({len(tsmc_signal_days['tsmc'])}天):")
    print(f"    平均報酬: {sum(tsmc_signal_days['tsmc'])/len(tsmc_signal_days['tsmc']):+.2f}%")
    print(f"    勝率: {sum(1 for r in tsmc_signal_days['tsmc'] if r > 0)/len(tsmc_signal_days['tsmc']):.0f}%")

    print(f"\n  貿易戰相關發文日 ({len(tsmc_signal_days['trade_war'])}天):")
    print(f"    平均報酬: {sum(tsmc_signal_days['trade_war'])/len(tsmc_signal_days['trade_war']):+.2f}%")
    print(f"    勝率: {sum(1 for r in tsmc_signal_days['trade_war'] if r > 0)/len(tsmc_signal_days['trade_war']):.0f}%")

    print(f"\n  一般發文日 ({len(tsmc_signal_days['normal'])}天):")
    print(f"    平均報酬: {sum(tsmc_signal_days['normal'])/len(tsmc_signal_days['normal']):+.2f}%")
    print(f"    勝率: {sum(1 for r in tsmc_signal_days['normal'] if r > 0)/len(tsmc_signal_days['normal']):.0f}%")

    # === 4. 發文風格 DNA vs 2330表現 ===
    print(f"\n{'='*90}")
    print("📊 4. 每月發文風格 DNA vs 2330月表現")
    print("=" * 90)

    monthly_dna = {}
    monthly_tsmc_ret = {}

    for month in months:
        month_posts = [p for p in originals if p['created_at'][:7] == month]
        if not month_posts:
            continue

        # 風格指紋 (同原版)
        total_chars = sum(len(p['content']) for p in month_posts)
        total_alpha = sum(sum(1 for c in p['content'] if c.isalpha()) for p in month_posts)
        total_upper = sum(sum(1 for c in p['content'] if c.isupper()) for p in month_posts)
        total_excl = sum(p['content'].count('!') for p in month_posts)
        avg_length = total_chars / len(month_posts)

        word_counts = Counter()
        stop_words = {'that', 'this', 'with', 'from', 'have', 'been', 'will', 'just',
                      'they', 'their', 'were', 'what', 'when', 'your', 'very', 'about'}
        for p in month_posts:
            words = re.findall(r'[a-z]{4,}', p['content'].lower())
            words = [w for w in words if w not in stop_words]
            word_counts.update(words)

        top_words = [w for w, _ in word_counts.most_common(15)]

        monthly_dna[month] = {
            'posts': len(month_posts),
            'avg_length': round(avg_length),
            'caps_ratio': round(total_upper / max(total_alpha, 1) * 100, 1),
            'excl_per_post': round(total_excl / len(month_posts), 2),
            'top_words': top_words,
        }

        # 當月2330表現
        month_days = [d for d in tsmc_by_date if d.startswith(month)]
        if month_days:
            rets = [(tsmc_by_date[d]['close'] - tsmc_by_date[d]['open']) / tsmc_by_date[d]['open'] * 100
                   for d in month_days]
            monthly_tsmc_ret[month] = {
                'days': len(month_days),
                'avg_ret': sum(rets)/len(rets),
                'win_rate': sum(1 for r in rets if r > 0)/len(rets)*100
            }

    # 顯示結果
    print(f"\n  {'月份':8s} | {'篇數':>4s} | {'2330日均報酬':>8s} | {'大寫率':>5s} | Top 3 關鍵字")
    for month in months:
        dna = monthly_dna.get(month)
        tsmc = monthly_tsmc_ret.get(month)
        if not dna:
            continue
        ret_str = f"{tsmc['avg_ret']:+.2f}%" if tsmc else "    -"
        top3 = ', '.join(dna['top_words'][:3])
        print(f"  {month:8s} | {dna['posts']:4d} | {ret_str:>8s} | {dna['caps_ratio']:5.1f}% | {top3}")

    # === 5. 存結果 ===
    results = {
        'monthly_dna': monthly_dna,
        'keyword_first_tsmc': keyword_first_appearance,
        'tsmc_signal_stats': tsmc_signal_days,
        'monthly_tsmc_returns': monthly_tsmc_ret
    }

    with open(DATA / 'results_10_tsmc_codechange.json', 'w', encoding='utf-8') as f:
        json.dump(results, f, ensure_ascii=False, indent=2)

    print(f"\n💾 結果存入 results_10_tsmc_codechange.json")
    print("\n✅ 分析完成！台積電2330密碼換碼偵測完毕")

if __name__ == '__main__':
    main()