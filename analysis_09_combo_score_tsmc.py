
#!/usr/bin/env python3
"""
川普密碼 分析 #9 — 多信號組合評分模型 (台積電2330專用版)
使用 market_2330TW.json 分析川普貼文對台積電影響
"""

import json
import re
import math
from collections import defaultdict
from datetime import datetime, timedelta
from pathlib import Path

BASE = Path(__file__).parent

def main():
    # 載入川普貼文資料
    with open(BASE / "clean_president.json", 'r', encoding='utf-8') as f:
        posts = json.load(f)

    DATA = BASE / "data"

    # 使用台積電資料
    with open(DATA / "market_2330TW.json", 'r', encoding='utf-8') as f:
        tsmc_data = json.load(f)

    # 建立日期索引
    tsmc_by_date = {r['date']: r for r in tsmc_data}

    # 篩選原始貼文
    originals = sorted(
        [p for p in posts if p['has_text'] and not p['is_retweet']],
        key=lambda p: p['created_at']
    )

    def next_td(date_str):
        """找下一個交易日"""
        dt = datetime.strptime(date_str, '%Y-%m-%d')
        for i in range(1, 10):  # 台股可能連假較長
            d = (dt + timedelta(days=i)).strftime('%Y-%m-%d')
            if d in tsmc_by_date:
                return d
        return None

    print("=" * 80)
    print("🧮 分析 #9: 川普貼文對台積電(2330.TW)多信號組合評分")
    print("=" * 80)

    # === 每天算分 ===
    daily_scores = {}
    daily_posts = defaultdict(list)

    # 按日期分組貼文
    for p in originals:
        daily_posts[p['created_at'][:10]].append(p)

    sorted_dates = sorted(daily_posts.keys())

    for idx, date in enumerate(sorted_dates):
        day_p = daily_posts[date]
        score = 0  # -100（極度看空）到 +100（極度看多）
        components = {}

        # --- 維度 1: 台積電/台灣/半導體相關度 (-20 ~ +20) ---
        tsmc_count = 0
        taiwan_count = 0
        semi_count = 0
        tariff_count = 0
        deal_count = 0

        for p in day_p:
            cl = p['content'].lower()
            # 台積電直接提及
            if any(w in cl for w in ['tsmc', '台積電', '2330']):
                tsmc_count += 2
            # 台灣相關
            if any(w in cl for w in ['taiwan', '台灣']):
                taiwan_count += 1
            # 半導體產業
            if any(w in cl for w in ['semiconductor', 'chip', '半導體', '晶片']):
                semi_count += 1
            # 貿易政策
            if any(w in cl for w in ['tariff', 'tariffs', 'duty']):
                tariff_count += 1
            if any(w in cl for w in ['deal', 'agreement']):
                deal_count += 1

        relevance = tsmc_count + taiwan_count * 0.8 + semi_count * 0.6
        if relevance > 0:
            policy_balance = (deal_count - tariff_count) * 0.5
            dim1 = min(20, max(-20, relevance + policy_balance))
        else:
            dim1 = 0
        components['tsmc_relevance'] = round(dim1, 1)
        score += dim1

        # --- 維度 2: 情緒方向 (-15 ~ +15) ---
        positive_words = ['great', 'tremendous', 'beautiful', 'amazing', 'deal', 'agreement']
        negative_words = ['tariff', 'duty', 'ban', 'block', 'worst', 'disaster']
        pos_count = 0
        neg_count = 0

        for p in day_p:
            cl = p['content'].lower()
            pos_count += sum(1 for w in positive_words if w in cl)
            neg_count += sum(1 for w in negative_words if w in cl)

        if pos_count + neg_count > 0:
            sentiment = (pos_count - neg_count) / (pos_count + neg_count)
            dim2 = sentiment * 15
        else:
            dim2 = 0
        components['sentiment'] = round(dim2, 1)
        score += dim2

        # --- 維度 3: 發文量異常 (-10 ~ +10) ---
        prev_counts = []
        for j in range(max(0, idx-7), idx):
            prev_counts.append(len(daily_posts.get(sorted_dates[j], [])))
        avg_prev = sum(prev_counts) / max(len(prev_counts), 1)
        today_count = len(day_p)

        if avg_prev > 0:
            volume_ratio = today_count / avg_prev
            if volume_ratio > 2:
                dim3 = -8  # 爆量通常負面
            elif volume_ratio > 1.5:
                dim3 = -4
            elif volume_ratio < 0.5:
                dim3 = 2
            else:
                dim3 = 5
        else:
            dim3 = 0
        components['volume'] = round(dim3, 1)
        score += dim3

        # --- 維度 4: 盤前信號 (-15 ~ +15) ---
        pre_tsmc = 0
        pre_tariff = 0
        pre_deal = 0
        for p in day_p:
            h, m = map(int, p['created_at'][11:16].split(':'))
            # 台股盤前 (假設 UTC+8 凌晨2-6點)
            if h < 6:
                cl = p['content'].lower()
                if any(w in cl for w in ['tsmc', 'taiwan', '2330']):
                    pre_tsmc += 2
                if any(w in cl for w in ['tariff']):
                    pre_tariff += 1
                if any(w in cl for w in ['deal']):
                    pre_deal += 1

        dim4 = pre_tsmc * 3 + pre_deal * 5 - pre_tariff * 4
        dim4 = max(-15, min(15, dim4))
        components['pre_market'] = round(dim4, 1)
        score += dim4

        # --- 維度 5: 權威性 (-5 ~ +10) ---
        formal = 0
        for p in day_p:
            c = p['content']
            if 'PRESIDENT' in c.upper():
                formal += 3
            elif any(sig in c for sig in ['DJT', 'Trump']):
                formal += 1
        dim5 = min(10, formal)
        components['authority'] = dim5
        score += dim5

        # --- 維度 6: 大寫強度 (-5 ~ +5) ---
        caps_total = 0
        alpha_total = 0
        for p in day_p:
            caps_total += sum(1 for c in p['content'] if c.isupper())
            alpha_total += sum(1 for c in p['content'] if c.isalpha())
        caps_ratio = caps_total / max(alpha_total, 1)
        if caps_ratio > 0.3:
            dim6 = -5
        elif caps_ratio > 0.2:
            dim6 = -2
        else:
            dim6 = 3
        components['caps_intensity'] = dim6
        score += dim6

        daily_scores[date] = {
            'score': round(score, 1),
            'components': components,
            'post_count': today_count,
            'tsmc_mentions': tsmc_count,
            'taiwan_mentions': taiwan_count,
        }

    # === 回測結果 ===
    print(f"\n📊 台積電每日川普信號分數統計:")
    scores_list = [(d, s) for d, s in daily_scores.items()]
    scores_values = [s['score'] for _, s in scores_list]

    print(f"   範圍: {min(scores_values):+.1f} ~ {max(scores_values):+.1f}")
    print(f"   平均: {sum(scores_values)/len(scores_values):+.1f}")

    # 分組分析
    print(f"\n📈 分數區間 vs 隔日台積電表現:")
    print(f"   {'區間':20s} | {'天數':>4s} | {'隔日漲跌':>8s} | {'勝率':>6s}")
    print(f"   {'-'*20} | {'-'*4} | {'-'*8} | {'-'*6}")

    buckets = [
        ('🔴 極負面 (<-10)', lambda s: s < -10),
        ('🟠 負面 (-10~0)', lambda s: -10 <= s < 0),
        ('🟡 中性 (0~10)', lambda s: 0 <= s < 10),
        ('🟢 正面 (10~20)', lambda s: 10 <= s < 20),
        ('🔵 極正面 (≥20)', lambda s: s >= 20),
    ]

    for bucket_name, bucket_fn in buckets:
        days = [(d, s) for d, s in scores_list if bucket_fn(s['score'])]
        if not days:
            continue

        returns = []
        for d, s in days:
            ntd = next_td(d)
            if ntd and ntd in tsmc_by_date:
                tsmc = tsmc_by_date[ntd]
                ret = (tsmc['close'] - tsmc['open']) / tsmc['open'] * 100
                returns.append(ret)

        if returns:
            avg_ret = sum(returns) / len(returns)
            win_rate = sum(1 for r in returns if r > 0) / len(returns) * 100
            print(f"   {bucket_name:20s} | {len(days):4d} | {avg_ret:+7.2f}% | {win_rate:5.1f}%")

    # === 交易策略回測 ===
    print(f"\n{'='*80}")
    print("📊 台積電交易策略回測 (基準資金 $10萬)")
    print("=" * 80)

    # 統一參數為 (d, s, ps) -> date, score_dict, prev_score_dict
    strategies = {
        'A: 高分(>15)買進隔日': {
            'trigger': lambda d, s, ps: s['score'] > 15, 
            'hold': 1
        },
        'B: 低分(<-10)放空隔日': {
            'trigger': lambda d, s, ps: s['score'] < -10, 
            'hold': 1
        },
        'C: 正面轉折(前<0今>12)': {
            'trigger': lambda d, s, ps: s['score'] > 12 and ps is not None and ps['score'] < 0, 
            'hold': 2
        },
    }

    for strat_name, strat in strategies.items():
        trades = []
        prev_score = None

        for date in sorted_dates:
            if date not in daily_scores:
                continue
            s = daily_scores[date]

            if strat['trigger'](date, s, prev_score):
                entry_day = next_td(date)
                if entry_day and entry_day in tsmc_by_date:
                    exit_day = entry_day
                    for _ in range(strat['hold']):
                        nd = next_td(exit_day)
                        if nd and nd in tsmc_by_date:
                            exit_day = nd
                        else:
                            break

                    if exit_day in tsmc_by_date:
                        entry_p = tsmc_by_date[entry_day]['open']
                        exit_p = tsmc_by_date[exit_day]['close']
                        ret = (exit_p - entry_p) / entry_p * 100

                        trades.append({
                            'entry': entry_day,
                            'exit': exit_day,
                            'return': ret,
                            'score': s['score']
                        })
            prev_score = s

        if trades:
            wins = sum(1 for t in trades if t['return'] > 0)
            avg_ret = sum(t['return'] for t in trades) / len(trades)
            total_ret = sum(t['return'] for t in trades)

            capital = 100000
            for t in trades:
                capital *= (1 + t['return'] / 100)

            print(f"\n  📋 {strat_name}")
            print(f"     交易次數: {len(trades)} | 勝率: {wins/len(trades)*100:.1f}%")
            print(f"     平均報酬: {avg_ret:+.2f}% | 累積報酬: {total_ret:+.1f}%")
            print(f"     $10萬 → ${capital:,.0f}")

    # === 最近30天 ===
    print(f"\n{'='*80}")
    print("📊 最近30天川普對台積電信號:")
    print("=" * 80)
    print(f"  {'日期':12s} | {'分數':>6s} | {'柱狀':25s} | {'TSMC提及':>3s} | {'台股表現'}")

    for date in sorted_dates[-30:]:
        s = daily_scores[date]
        score = s['score']

        # 柱狀圖
        if score >= 0:
            bar = '█' * min(int(score), 25)
        else:
            bar = '▓' * min(int(abs(score)), 25)

        tsmc_today = tsmc_by_date.get(date)
        tsmc_ret = ""
        if tsmc_today:
            ret = (tsmc_today['close'] - tsmc_today['open']) / tsmc_today['open'] * 100
            tsmc_ret = f"{ret:+.1f}%"

        print(f"  {date:12s} | {score:+6.1f} | {bar:25s} | {s['tsmc_mentions']:>2d} | {tsmc_ret:>6s}")

    # 存檔
    results = {'daily_scores': daily_scores}
    with open(DATA / 'result_09_combo_score_tsmc.json', 'w', encoding='utf-8') as f:
        json.dump(results, f, ensure_ascii=False, indent=2)

    print(f"\n💾 結果存入 result_09_combo_score_tsmc.json")
    print(f"✅ 分析完成！")

if __name__ == '__main__':
    main()