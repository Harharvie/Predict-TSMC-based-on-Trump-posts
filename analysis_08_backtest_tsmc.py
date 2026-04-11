#!/usr/bin/env python3
"""
川普密碼 分析 #8 — 台積電回測驗證 (2330.TW)
使用 market_2330TW.json 資料，測試川普貼文對台積電影響
對照組：同期 Buy & Hold 台積電
"""

import json
import re
from collections import defaultdict
from datetime import datetime, timedelta
from pathlib import Path
from utils import est_hour  # 假設 utils.py 存在

BASE = Path(__file__).parent


def main():
    # 載入川普貼文資料
    with open(BASE / "clean_president.json", 'r', encoding='utf-8') as f:
        posts = json.load(f)

    DATA = BASE / "data"

    # 使用台積電資料替代美股
    with open(DATA / "market_2330TW.json", 'r', encoding='utf-8') as f:
        tsmc_data = json.load(f)

    # 建立日期索引
    tsmc_by_date = {r['date']: r for r in tsmc_data}

    originals = sorted(
        [p for p in posts if p['has_text'] and not p['is_retweet']],
        key=lambda p: p['created_at']
    )

    # === 工具函數 ===
    def classify_post(content):
        cl = content.lower()
        signals = set()
        if any(w in cl for w in ['tariff', 'tariffs', 'duty', 'duties', 'reciprocal']):
            signals.add('TARIFF')
        if any(w in cl for w in ['deal', 'agreement', 'negotiate', 'talks', 'signed']):
            signals.add('DEAL')
        if any(w in cl for w in ['pause', 'delay', 'exempt', 'exception', 'reduce', 'suspend', 'postpone']):
            signals.add('RELIEF')
        if any(w in cl for w in ['stock market', 'all time high', 'record high', 'dow', 'nasdaq', 'market up']):
            signals.add('MARKET_BRAG')
        if any(w in cl for w in ['china', 'chinese', 'beijing']):
            signals.add('CHINA')
        if any(w in cl for w in ['immediately', 'effective', 'hereby', 'i have directed', 'executive order', 'just signed']):
            signals.add('ACTION')
        # 台積電相關關鍵詞
        if any(w in cl for w in ['semiconductor', 'chip', 'chips', 'tsmc', 'taiwan', 'taiwanese']):
            signals.add('TSMC')
        return signals

    def market_session(utc_str):
        """美東時間交易時段判斷 (台股用 UTC+8 交易時段需調整)"""
        h, m = est_hour(utc_str)
        if h < 9 or (h == 9 and m < 30):
            return 'PRE_MARKET'
        elif h < 16:
            return 'MARKET_OPEN'
        elif h < 20:
            return 'AFTER_HOURS'
        else:
            return 'OVERNIGHT'

    def next_trading_day(date_str, market=None):
        if market is None:
            market = tsmc_by_date
        dt = datetime.strptime(date_str, '%Y-%m-%d')
        for i in range(1, 10):  # 台股週末較長，搜尋範圍加大
            d = (dt + timedelta(days=i)).strftime('%Y-%m-%d')
            if d in market:
                return d
        return None

    def trading_day_offset(date_str, offset, market=None):
        """取得 N 個交易日後的日期"""
        if market is None:
            market = tsmc_by_date
        d = date_str
        for _ in range(abs(offset)):
            if offset > 0:
                d = next_trading_day(d, market)
            else:
                # 往前找交易日 (簡化版)
                dt = datetime.strptime(d, '%Y-%m-%d')
                for i in range(1, 10):
                    prev_d = (dt - timedelta(days=i)).strftime('%Y-%m-%d')
                    if prev_d in market:
                        d = prev_d
                        break
            if not d:
                return None
        return d

    # === 每日信號彙整 ===
    daily_signals = defaultdict(lambda: {
        'tariff': 0, 'deal': 0, 'relief': 0, 'market_brag': 0,
        'action': 0, 'china': 0, 'tsmc': 0, 'posts': 0,
        'pre_tariff': 0, 'pre_deal': 0, 'pre_relief': 0,
        'open_tariff': 0, 'open_deal': 0,
        'pre_close_tariff': 0, 'pre_close_deal': 0, 'pre_close_relief': 0,
        'pre_close_market_brag': 0, 'pre_close_action': 0, 'pre_close_tsmc': 0,
        'pre_action': 0,
    })

    for p in originals:
        date = p['created_at'][:10]
        signals = classify_post(p['content'])
        session = market_session(p['created_at'])
        d = daily_signals[date]
        d['posts'] += 1

        for sig in signals:
            sig_lower = sig.lower()
            d[sig_lower] = d.get(sig_lower, 0) + 1
            if session == 'PRE_MARKET':
                d[f'pre_{sig_lower}'] = d.get(f'pre_{sig_lower}', 0) + 1
                d[f'pre_close_{sig_lower}'] = d.get(f'pre_close_{sig_lower}', 0) + 1
            elif session == 'MARKET_OPEN':
                d[f'open_{sig_lower}'] = d.get(f'open_{sig_lower}', 0) + 1
                d[f'pre_close_{sig_lower}'] = d.get(f'pre_close_{sig_lower}', 0) + 1

    print("=" * 90)
    print("📊 川普密碼回測 — 台積電 2330.TW (使用 market_2330TW.json)")
    print("=" * 90)

    # === Buy & Hold 基準 ===
    first_day = tsmc_data[0]
    last_day = tsmc_data[-1]
    bh_return = (last_day['close'] - first_day['open']) / first_day['open'] * 100
    print(f"\n📈 基準: Buy & Hold 台積電 2330.TW")
    print(f"   期間: {first_day['date']} ~ {last_day['date']}")
    print(f"   起點(open): {first_day['open']:,.0f} → 終點(close): {last_day['close']:,.0f}")
    print(f"   報酬率: {bh_return:+.2f}%")
    print(f"   交易日: {len(tsmc_data)} 天")
    print(f"\n   ⚠️  前視偏差修正: 只用盤前(PRE_MARKET)+盤中(MARKET_OPEN)推文")
    print(f"      盤後/夜間推文不計入信號，避免前視偏差")

    # === 回測框架 ===
    class Trade:
        def __init__(self, rule, date, direction, entry_price, reason):
            self.rule = rule
            self.entry_date = date
            self.direction = direction  # 'LONG' or 'SHORT'
            self.entry_price = entry_price
            self.reason = reason
            self.exit_date = None
            self.exit_price = None
            self.return_pct = None
            self.hold_days = None

        def close(self, exit_date, exit_price):
            self.exit_date = exit_date
            self.exit_price = exit_price
            if self.direction == 'LONG':
                self.return_pct = (exit_price - self.entry_price) / self.entry_price * 100
            else:
                self.return_pct = (self.entry_price - exit_price) / self.entry_price * 100
            d1 = datetime.strptime(self.entry_date, '%Y-%m-%d')
            d2 = datetime.strptime(self.exit_date, '%Y-%m-%d')
            self.hold_days = (d2 - d1).days

    def run_rule(rule_name, trigger_fn, direction, hold_days_target, market=None):
        if market is None:
            market = tsmc_by_date
        trades = []
        sorted_dates = sorted(daily_signals.keys())

        for i, date in enumerate(sorted_dates):
            if date not in market:
                td = next_trading_day(date, market)
                if not td:
                    continue
            else:
                td = date

            sig = daily_signals[date]
            pre_close_view = {k.replace('pre_close_', ''): v for k, v in sig.items() if k.startswith('pre_close_')}
            context = {
                'date': date,
                'today': daily_signals[date],
                'today_pre_close': pre_close_view,
                'prev_3': [daily_signals[sorted_dates[j]] for j in range(max(0,i-3), i)],
                'prev_7': [daily_signals[sorted_dates[j]] for j in range(max(0,i-7), i)],
            }

            if trigger_fn(context):
                entry_day = next_trading_day(td, market)
                if not entry_day or entry_day not in market:
                    continue

                entry_price = market[entry_day]['open']

                exit_day = entry_day
                for _ in range(hold_days_target):
                    nd = next_trading_day(exit_day, market)
                    if nd:
                        exit_day = nd
                    else:
                        break

                if exit_day not in market:
                    continue

                exit_price = market[exit_day]['close']

                trade = Trade(rule_name, entry_day, direction, entry_price, f"{date} signal")
                trade.close(exit_day, exit_price)
                trades.append(trade)

        return trades

    def print_rule_results(rule_name, trades, description):
        if not trades:
            print(f"\n  ❌ {rule_name}: 沒有觸發")
            return None

        wins = [t for t in trades if t.return_pct > 0]
        losses = [t for t in trades if t.return_pct <= 0]
        returns = [t.return_pct for t in trades]

        total_return = sum(returns)
        avg_return = total_return / len(returns)
        win_rate = len(wins) / len(trades) * 100
        avg_win = sum(t.return_pct for t in wins) / len(wins) if wins else 0
        avg_loss = sum(t.return_pct for t in losses) / len(losses) if losses else 0
        max_win = max(returns)
        max_loss = min(returns)
        avg_hold = sum(t.hold_days for t in trades) / len(trades)

        capital = 10000
        cumulative = capital
        peak = capital
        max_drawdown = 0
        for t in trades:
            cumulative *= (1 + t.return_pct / 100)
            peak = max(peak, cumulative)
            dd = (peak - cumulative) / peak * 100
            max_drawdown = max(max_drawdown, dd)

        final_value = cumulative

        print(f"\n  {'='*85}")
        print(f"  📋 規則: {rule_name}")
        print(f"  📝 {description}")
        print(f"  {'='*85}")
        print(f"  交易次數:  {len(trades):5d}")
        print(f"  勝率:      {win_rate:5.1f}%  ({len(wins)}勝 {len(losses)}負)")
        print(f"  平均報酬:  {avg_return:+.3f}% / 次")
        print(f"  累積報酬:  {total_return:+.2f}%")
        print(f"  平均持有:  {avg_hold:.1f} 天")
        print(f"  平均勝:    {avg_win:+.3f}%")
        print(f"  平均負:    {avg_loss:+.3f}%")
        print(f"  最大單筆勝: {max_win:+.2f}%")
        print(f"  最大單筆負: {max_loss:+.2f}%")
        profit_loss_ratio = abs(avg_win / avg_loss) if avg_loss != 0 else 999
        print(f"  盈虧比:    {profit_loss_ratio:.2f}")
        print(f"  最大回撤:  {max_drawdown:.2f}%")
        print(f"  NT$10萬 →  NT${final_value:,.0f}  ({(final_value/capital-1)*100:+.1f}%)")

        print(f"\n  📋 交易明細:")
        print(f"  {'入場':12s} | {'出場':12s} | {'入場價':>12s} | {'出場價':>12s} | {'報酬':>8s} | {'累積':>12s}")
        cum = capital
        for t in trades:
            cum *= (1 + t.return_pct / 100)
            arrow = "✅" if t.return_pct > 0 else "❌"
            print(f"  {t.entry_date:12s} | {t.exit_date:12s} | {t.entry_price:>12,.0f} | {t.exit_price:>12,.0f} | {t.return_pct:+.2f}% {arrow} | NT${cum:>10,.0f}")

        return {
            'trades': len(trades),
            'win_rate': round(win_rate, 1),
            'avg_return': round(avg_return, 3),
            'total_return': round(total_return, 2),
            'max_drawdown': round(max_drawdown, 2),
            'final_value': round(final_value, 0),
        }

    # 規則 1: 盤前暫緩信號 → 買入1天
    def rule1_trigger(ctx):
        return ctx['today'].get('pre_relief', 0) >= 1

    trades_r1 = run_rule('R1', rule1_trigger, 'LONG', 1)
    r1 = print_rule_results(
        "規則1: 盤前RELIEF → 台積電買入1天",
        trades_r1,
        "川普開盤前說「暫緩/豁免」→ 台積電隔日開盤買、收盤賣"
    )

    # 規則 2: 盤中關稅信號密集 → 台積電做空1天
    def rule2_trigger(ctx):
        return ctx['today'].get('open_tariff', 0) >= 2

    trades_r2 = run_rule('R2', rule2_trigger, 'SHORT', 1)
    r2 = print_rule_results(
        "規則2: 盤中TARIFF×2 → 台積電做空1天",
        trades_r2,
        "川普交易時間提關稅 ≥2 次 → 台積電隔日開盤做空、收盤平倉"
    )

    # 規則 3: 提到台灣/半導體 → 台積電買入1天
    def rule3_trigger(ctx):
        return ctx['today_pre_close'].get('tsmc', 0) >= 1

    trades_r3 = run_rule('R3', rule3_trigger, 'LONG', 1)
    r3 = print_rule_results(
        "規則3: 提到台灣/半導體 → 台積電買入1天",
        trades_r3,
        "川普提到台灣/半導體/晶片 → 台積電隔日開盤買入、收盤賣出"
    )

    # 規則 4: 中國+關稅組合 → 台積電做空2天
    def rule4_trigger(ctx):
        t = ctx['today_pre_close']
        return t.get('china', 0) >= 1 and t.get('tariff', 0) >= 1

    trades_r4 = run_rule('R4', rule4_trigger, 'SHORT', 2)
    r4 = print_rule_results(
        "規則4: 中國+TARIFF → 台積電做空2天",
        trades_r4,
        "川普同時提到中國+關稅 → 台積電做空，持有2個交易日"
    )

    # 組合策略：規則 1+3 同時運行
    print(f"\n{'='*90}")
    print("🏆 組合策略回測：規則 1+3 同時運行 (台積電)")
    print("   各規則獨立觸發，不重複入場（同一天只觸一次）")
    print("=" * 90)

    all_trades = []
    used_dates = set()

    for trades, priority in [(trades_r1, 1), (trades_r3, 3)]:
        for t in trades:
            if t.entry_date not in used_dates:
                all_trades.append(t)
                used_dates.add(t.entry_date)

    all_trades.sort(key=lambda t: t.entry_date)

    if all_trades:
        capital = 100000  # 台幣 10 萬
        cumulative = capital
        peak = capital
        max_dd = 0
        wins = sum(1 for t in all_trades if t.return_pct > 0)

        for t in all_trades:
            cumulative *= (1 + t.return_pct / 100)
            peak = max(peak, cumulative)
            dd = (peak - cumulative) / peak * 100
            max_dd = max(max_dd, dd)

        total_ret = sum(t.return_pct for t in all_trades)
        avg_ret = total_ret / len(all_trades)

        print(f"  交易次數:     {len(all_trades)}")
        print(f"  勝率:         {wins/len(all_trades)*100:.1f}%")
        print(f"  平均報酬:     {avg_ret:+.3f}% / 次")
        print(f"  累積報酬:     {total_ret:+.2f}%")
        print(f"  最大回撤:     {max_dd:.2f}%")
        print(f"  NT$10萬 →     NT${cumulative:,.0f}")
        print(f"  vs Buy&Hold:  {bh_return:+.2f}%")

    # 總結表格
    print(f"\n{'='*90}")
    print("📊 台積電 2330.TW 川普密碼回測總結")
    print("=" * 90)
    print(f"  {'規則':40s} | {'次數':>4s} | {'勝率':>5s} | {'平均':>8s} | {'NT$10萬→':>12s}")
    print(f"  {'-'*40}-+-{'-'*4}-+-{'-'*5}-+-{'-'*8}-+-{'-'*12}")

    all_results = [
        ('R1: 盤前RELIEF→買1天', r1),
        ('R2: 盤中TARIFF×2→空1天', r2),
        ('R3: 台灣/半導體→買1天', r3),
        ('R4: 中國+TARIFF→空2天', r4),
    ]

    for name, result in all_results:
        if result:
            print(f"  {name:40s} | {result['trades']:4d} | {result['win_rate']:4.1f}% | {result['avg_return']:+.3f}% | NT${result['final_value']:>10,.0f}")
        else:
            print(f"  {name:40s} | {'N/A':>4s} |  {'N/A':>4s} |   {'N/A':>6s} |     {'N/A':>8s}")

    print(f"  {'-'*40}-+-{'-'*4}-+-{'-'*5}-+-{'-'*8}-+-{'-'*12}")
    print(f"  {'Buy & Hold 台積電 (對照組)':40s} | {len(tsmc_data):4d} | {'N/A':>5s} | {'N/A':>8s} | NT${100000*(1+bh_return/100):>10,.0f}")

    # 存結果
    summary = {'buy_hold_return_tsmc': round(bh_return, 2)}
    for name, result in all_results:
        if result:
            summary[name] = result

    with open(DATA / 'results_08_backtest_tsmc.json', 'w', encoding='utf-8') as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)

    print(f"\n💾 詳細結果存入 results_08_backtest_tsmc.json")
    print(f"\n✅ 台積電回測完成！")


if __name__ == '__main__':
    main()
