
import json
import os
from collections import defaultdict
from datetime import datetime, timedelta
from pathlib import Path


BASE = Path(__file__).parent
DATA = BASE / "data"


def get_next_trading_day(date_str, market_data):
    dt = datetime.strptime(date_str, '%Y-%m-%d')
    for i in range(1, 6):
        next_d = (dt + timedelta(days=i)).strftime('%Y-%m-%d')
        if next_d in market_data:
            return next_d
    return None


def day_return(date_str, market_data):
    if date_str not in market_data:
        return None
    sorted_dates = sorted(market_data.keys())
    idx = sorted_dates.index(date_str)
    if idx == 0:
        d = market_data[date_str]
        return (d['close'] - d['open']) / d['open'] * 100
    prev_date = sorted_dates[idx - 1]
    prev_close = market_data[prev_date]['close']
    today_close = market_data[date_str]['close']
    return (today_close - prev_close) / prev_close * 100


def next_day_return(date_str, market_data):
    next_d = get_next_trading_day(date_str, market_data)
    if not next_d:
        return None
    return day_return(next_d, market_data)


def overnight_gap(date_str, market_data):
    if date_str not in market_data:
        return None
    next_d = get_next_trading_day(date_str, market_data)
    if not next_d:
        return None
    today_close = market_data[date_str]['close']
    next_open = market_data[next_d]['open']
    return (next_open - today_close) / today_close * 100


def main():
    # 檢查必要檔案
    clean_file = BASE / "clean_president.json"
    market_file = DATA / "market_2330TW.json"
    
    print(f"檢查檔案：")
    print(f"  clean_president.json: {'✅' if clean_file.exists() else '❌'} {clean_file}")
    print(f"  market_2330TW.json:  {'✅' if market_file.exists() else '❌'} {market_file}")
    
    if not clean_file.exists():
        print("❌ 請確認 clean_president.json 在 /content/trump-code/ 下")
        return
    if not market_file.exists():
        print("❌ 請先執行上面的 copy 指令")
        return
    
    with open(clean_file, 'r', encoding='utf-8') as f:
        posts = json.load(f)
    
    with open(market_file, 'r', encoding='utf-8') as f:
        px = json.load(f)

    px_by_date = {r['date']: r for r in px}
    originals = [p for p in posts if p['has_text'] and not p['is_retweet']]

    daily = defaultdict(lambda: {
        'post_count': 0,
        'has_taiwan': False,
        'has_tsmc': False,
        'has_chip': False,
        'has_tariff': False,
        'has_tariff_semis': False,
        'has_china': False
    })

    for p in originals:
        date = p['created_at'][:10]
        text = p['content'].lower()
        d = daily[date]
        d['post_count'] += 1

        if any(w in text for w in ['taiwan', 'taiwanese', 'taipei']):
            d['has_taiwan'] = True
        if any(w in text for w in ['tsmc', 'taiwan semiconductor', 'semiconductor manufacturing']):
            d['has_tsmc'] = True
        if any(w in text for w in ['chip', 'chips', 'semiconductor', 'semiconductors', 'foundry', 'fab', 'fabs']):
            d['has_chip'] = True
        if any(w in text for w in ['tariff', 'tariffs', 'duty', 'duties']):
            d['has_tariff'] = True
        if any(w in text for w in ['china', 'chinese', 'beijing']):
            d['has_china'] = True
        if d['has_tariff'] and (d['has_taiwan'] or d['has_tsmc'] or d['has_chip']):
            d['has_tariff_semis'] = True

    event_rows = []
    for d, feat in daily.items():
        if d in px_by_date:
            event_rows.append({
                'date': d,
                **feat,
                'ret0': day_return(d, px_by_date),
                'ret1': next_day_return(d, px_by_date),
                'gap1': overnight_gap(d, px_by_date),
            })

    event_rows = sorted(event_rows, key=lambda x: x['date'])

    print("\n事件天數:", len(event_rows))

    feature_stats = {}
    for key in ['has_taiwan', 'has_tsmc', 'has_chip', 'has_tariff', 'has_tariff_semis', 'has_china']:
        same_day_vals = [r['ret0'] for r in event_rows if r[key] and r['ret0'] is not None]
        next_day_vals = [r['ret1'] for r in event_rows if r[key] and r['ret1'] is not None]
        gap_vals = [r['gap1'] for r in event_rows if r[key] and r['gap1'] is not None]

        feature_stats[key] = {
            'days': len([r for r in event_rows if r[key]]),
            'same_day_n': len(same_day_vals),
            'same_day_avg': round(sum(same_day_vals) / len(same_day_vals), 4) if same_day_vals else None,
            'next_day_n': len(next_day_vals),
            'next_day_avg': round(sum(next_day_vals) / len(next_day_vals), 4) if next_day_vals else None,
            'overnight_gap_n': len(gap_vals),
            'overnight_gap_avg': round(sum(gap_vals) / len(gap_vals), 4) if gap_vals else None,
        }

        if next_day_vals:
            print(key, "N=", len(next_day_vals), "avg next-day=", round(sum(next_day_vals) / len(next_day_vals), 4))

    # ============================================================
    # 存結果摘要
    # ============================================================
    results = {
        'summary': {
            'event_days': len(event_rows),
            'matched_market_days': len(event_rows),
            'original_posts': len(originals),
        },
        'feature_stats': feature_stats,
        # ... 其他結果
    }

    os.makedirs(DATA, exist_ok=True)
    with open(DATA / 'results_06_tsmc.json', 'w', encoding='utf-8') as f:
        json.dump(results, f, ensure_ascii=False, indent=2)

    print(f"\n💾 詳細結果存入 {DATA / 'results_06_tsmc.json'}")

if __name__ == '__main__':
    main()