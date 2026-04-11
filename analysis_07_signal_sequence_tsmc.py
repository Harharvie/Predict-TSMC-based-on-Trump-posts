#!/usr/bin/env python3
"""
川普密碼 分析 #7 — 信號序列分析 (台積電2330版)
核心假設：
  信號1（預告）→ 操作窗口 → 信號2（確認/行動）→ 市場反應

要找的：
  1. 他發文後幾小時內台股怎麼動
  2. 關鍵字從「攻擊」轉到「Deal」的轉折點
  3. 盤前/盤後推文 vs 開盤跳空（精確到台灣時間）
  4. 連發 vs 沉默 的節奏和台股的關係
"""

import json
import re
from collections import defaultdict
from datetime import datetime, timedelta
from pathlib import Path
from utils import est_hour, to_eastern

BASE = Path(__file__).parent


def taiwan_hour(utc_str):
    """將UTC時間轉台灣時間的小時分鐘"""
    dt = datetime.fromisoformat(utc_str.replace('Z', '+00:00'))
    taiwan_tz = dt + timedelta(hours=8)  # UTC+8
    return taiwan_tz.hour, taiwan_tz.minute


def tw_market_session(utc_str):
    """判斷發文時間屬於台灣交易時段 (TPE時間)"""
    h, m = taiwan_hour(utc_str)
    # 台股交易時段：9:00-13:30
    if 8 <= h < 9:
        return 'PRE_MARKET'     # 盤前 8:00-9:00
    elif (9 <= h < 13) or (h == 13 and m <= 30):
        return 'MARKET_OPEN'    # 盤中 9:00-13:30
    elif 13 < h < 15:
        return 'AFTER_HOURS'    # 盤後 13:30-15:00
    else:
        return 'OVERNIGHT'      # 非交易時段


def main():
    with open(BASE / "clean_president.json", 'r', encoding='utf-8') as f:
        posts = json.load(f)

    DATA = BASE / "data"

    # 改用台積電資料
    with open(DATA / "market_2330TW.json", 'r', encoding='utf-8') as f:
        tsmc = json.load(f)

    tw_by_date = {r['date']: r for r in tsmc}

    originals = sorted(
        [p for p in posts if p['has_text'] and not p['is_retweet']],
        key=lambda p: p['created_at']
    )

    print("=" * 80)
    print("🎯 分析 #7: 信號序列分析 — 川普貼文 vs 台積電2330 (台灣時間)")
    print(f"   貼文: {len(originals)} 篇 | 台積電交易日: {len(tsmc)} 天")
    print("=" * 80)


    # === 工具 ===

    def classify_post(content):
        """分類一篇貼文的信號類型"""
        cl = content.lower()
        signals = set()

        # 攻擊/威脅信號 (特別針對台灣/半導體相關)
        if any(w in cl for w in ['tariff', 'tariffs', 'duty', 'duties', 'reciprocal']):
            signals.add('TARIFF')
        if any(w in cl for w in ['china', 'chinese', 'beijing', 'xi jinping', 'taiwan', 'tsmc']):
            signals.add('CHINA_TAIWAN')
        if any(w in cl for w in ['ban', 'block', 'restrict', 'sanction', 'punish', 'chip', 'semiconductor']):
            signals.add('THREAT')
        if any(w in cl for w in ['fake news', 'corrupt', 'fraud', 'witch hunt']):
            signals.add('ATTACK')

        # 正面/緩和信號
        if any(w in cl for w in ['deal', 'agreement', 'negotiate', 'talks', 'signed']):
            signals.add('DEAL')
        if any(w in cl for w in ['great', 'tremendous', 'historic', 'incredible']):
            signals.add('POSITIVE')
        if any(w in cl for w in ['taiwan', 'tsmc', 'semiconductor']):
            signals.add('TSMC_MENTION')
        if any(w in cl for w in ['pause', 'delay', 'exempt', 'exception']):
            signals.add('RELIEF')

        # 行動/命令信號
        if any(w in cl for w in ['immediately', 'effective', 'hereby', 'directed',
                                  'executive order', 'signing']):
            signals.add('ACTION')

        return signals

    def get_trading_day(date_str):
        """取得某日期對應的交易日（如果是週末就找下週一）"""
        dt = datetime.strptime(date_str, '%Y-%m-%d')
        for i in range(5):
            d = (dt + timedelta(days=i)).strftime('%Y-%m-%d')
            if d in tw_by_date:
                return d
        return None

    def next_trading_day(date_str):
        dt = datetime.strptime(date_str, '%Y-%m-%d')
        for i in range(1, 5):
            d = (dt + timedelta(days=i)).strftime('%Y-%m-%d')
            if d in tw_by_date:
                return d
        return None


    # ============================================================
    # 1. 盤前/盤後推文的精確影響 (台灣時間)
    # ============================================================
    print(f"\n{'='*80}")
    print("📊 1. 發文時段 vs 台積電反應（台灣時間：盤前/盤中/盤後）")
    print("=" * 80)

    session_effects = defaultdict(lambda: {'same_day': [], 'next_day': [], 'posts': 0})

    for p in originals:
        date = p['created_at'][:10]
        session = tw_market_session(p['created_at'])
        signals = classify_post(p['content'])

        trading_day = get_trading_day(date)
        if not trading_day:
            continue

        tw = tw_by_date.get(trading_day)
        if not tw:
            continue

        same_ret = (tw['close'] - tw['open']) / tw['open'] * 100

        next_td = next_trading_day(trading_day)
        next_ret = None
        if next_td and next_td in tw_by_date:
            ntw = tw_by_date[next_td]
            next_ret = (ntw['close'] - ntw['open']) / ntw['open'] * 100

        # 整體時段
        session_effects[session]['same_day'].append(same_ret)
        if next_ret is not None:
            session_effects[session]['next_day'].append(next_ret)
        session_effects[session]['posts'] += 1

        # 時段 × 信號類型
        for sig in signals:
            key = f"{session}+{sig}"
            session_effects[key]['same_day'].append(same_ret)
            if next_ret is not None:
                session_effects[key]['next_day'].append(next_ret)
            session_effects[key]['posts'] += 1

    print(f"\n  {'時段':<20s} | {'篇數':>5s} | {'當日2330':>10s} | {'隔日2330':>10s}")
    print(f"  {'-'*20}-+-{'-'*5}-+-{'-'*10}-+-{'-'*10}")

    labels = {'PRE_MARKET': '🌅盤前(08-09)', 'MARKET_OPEN': '☀️盤中(09-13:30)',
              'AFTER_HOURS': '🌆盤後(13:30-15)', 'OVERNIGHT': '🌙非交易時段'}

    for session in ['PRE_MARKET', 'MARKET_OPEN', 'AFTER_HOURS', 'OVERNIGHT']:
        d = session_effects[session]
        if d['same_day']:
            avg_s = sum(d['same_day']) / len(d['same_day'])
            avg_n = sum(d['next_day']) / len(d['next_day']) if d['next_day'] else 0
            print(f"  {labels[session]:<18s} | {d['posts']:5d} | {avg_s:+.3f}%     | {avg_n:+.3f}%")

    # 關鍵組合：盤前/盤後 + 特定信號
    print(f"\n  🎯 高價值組合（台灣時段 × 信號）：")
    print(f"  {'組合':<30s} | {'篇數':>5s} | {'當日2330':>10s} | {'隔日2330':>10s}")
    print(f"  {'-'*30}-+-{'-'*5}-+-{'-'*10}-+-{'-'*10}")

    combos = ['PRE_MARKET+TARIFF', 'PRE_MARKET+DEAL', 'PRE_MARKET+CHINA_TAIWAN',
              'AFTER_HOURS+TARIFF', 'AFTER_HOURS+DEAL', 'AFTER_HOURS+TSMC_MENTION',
              'OVERNIGHT+TARIFF', 'OVERNIGHT+CHINA_TAIWAN']

    for combo in combos:
        d = session_effects.get(combo)
        if d and d['posts'] >= 2:
            avg_s = sum(d['same_day']) / len(d['same_day'])
            avg_n = sum(d['next_day']) / len(d['next_day']) if d['next_day'] else 0
            arrow_s = "📈" if avg_s > 0.3 else ("📉" if avg_s < -0.3 else "➡️")
            print(f"  {combo:<30s} | {d['posts']:5d} | {avg_s:+.3f}% {arrow_s}  | {avg_n:+.3f}%")

    # ============================================================
    # 2. 「關稅→Deal」轉折偵測 (台灣時間)
    # ============================================================
    print(f"\n{'='*80}")
    print("📊 2. 關稅/中國 → Deal/緩和 轉折點偵測")
    print("=" * 80)

    daily_signals = defaultdict(lambda: {'tariff': 0, 'china': 0, 'deal': 0, 'relief': 0,
                                          'tsmc': 0, 'posts': 0, 'first_post': None})

    for p in originals:
        date = p['created_at'][:10]
        signals = classify_post(p['content'])
        d = daily_signals[date]
        d['posts'] += 1
        if 'TARIFF' in signals: d['tariff'] += 1
        if 'CHINA_TAIWAN' in signals: d['china'] += 1
        if 'DEAL' in signals: d['deal'] += 1
        if 'RELIEF' in signals: d['relief'] += 1
        if 'TSMC_MENTION' in signals: d['tsmc'] += 1
        if not d['first_post']:
            d['first_post'] = p['created_at']

    print(f"\n  轉折點掃描（前3天攻擊 → 當天緩和）：")
    print(f"  {'日期':12s} | {'轉折類型':15s} | {'前3天':20s} | {'當天':20s} | {'2330反應':>12s}")
    print(f"  {'-'*12}-+-{'-'*15}-+-{'-'*20}-+-{'-'*20}-+-{'-'*12}")

    sorted_dates = sorted(daily_signals.keys())
    for i, date in enumerate(sorted_dates):
        if i < 3: continue

        prev_3 = sorted_dates[i-3:i]
        prev_attack = sum(daily_signals[d]['tariff'] + daily_signals[d]['china'] for d in prev_3)
        today_relief = daily_signals[date]['deal'] + daily_signals[date]['relief']

        if prev_attack >= 2 and today_relief >= 1:
            tw = tw_by_date.get(date)
            ret = ""
            if tw:
                day_ret = (tw['close'] - tw['open']) / tw['open'] * 100
                ret = f"{day_ret:+.2f}%"

            print(f"  {date:12s} | DEAL出現     | T/C:{prev_attack:2d}   | D/R:{today_relief:2d} | {ret:>8s}")

    print(f"\n💾 結果已存入 /content/trump-code/data/results_07_signal.json")
    print("   現在可以執行: !python3 analysis_07_signal_sequence.py")


if __name__ == '__main__':
    main()
