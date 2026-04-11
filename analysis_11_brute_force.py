#!/usr/bin/env python3
"""
川普密碼 分析 #11 — 暴力搜索 (PyTorch GPU 加速版)
把所有特徵的 2 條件、3 條件、4 條件組合全部跑一遍
前 10 個月找規則 → 最後 3 個月驗證 → 兩段都對的才是真密碼
使用 Tensor 平行運算將原本需要數十分鐘的回測縮短到數秒鐘。
"""

import json
import itertools
import time
from math import comb
from collections import defaultdict
from datetime import datetime, timedelta
from pathlib import Path

# 載入 PyTorch
try:
    import torch
except ImportError:
    print("❌ 找不到 PyTorch！請先執行: pip install torch 或 uv pip install torch")
    exit(1)

from utils import est_hour

BASE = Path(__file__).parent


def binomial_pvalue(wins: int, total: int, p0: float = 0.5) -> float:
    """
    二項檢定 p-value（單尾）
    H0: 勝率 = p0（隨機）
    H1: 勝率 > p0
    """
    pval = sum(
        comb(total, k) * (p0 ** k) * ((1 - p0) ** (total - k))
        for k in range(wins, total + 1)
    )
    return pval


def main():
    with open(BASE / "clean_president.json", 'r', encoding='utf-8') as f:
        posts = json.load(f)

    DATA = BASE / "data"

    with open(DATA / "market_SP500.json", 'r', encoding='utf-8') as f:
        sp500 = json.load(f)

    sp_by_date = {r['date']: r for r in sp500}

    originals = sorted(
        [p for p in posts if p['has_text'] and not p['is_retweet']],
        key=lambda p: p['created_at']
    )

    # === 每天算 20+ 個二元特徵 ===
    daily_posts = defaultdict(list)
    for p in originals:
        daily_posts[p['created_at'][:10]].append(p)

    sorted_dates = sorted(daily_posts.keys())

    def compute_features(date, idx):
        """計算某一天的所有二元特徵"""
        day_p = daily_posts.get(date, [])
        if not day_p:
            return None

        f = {}
        post_count = len(day_p)
        f['posts_high'] = post_count >= 20      # 高發文量
        f['posts_low'] = post_count <= 5        # 低發文量
        f['posts_very_high'] = post_count >= 35 # 極高

        tariff = 0; deal = 0; relief = 0; action = 0
        attack = 0; positive = 0; market_brag = 0
        china = 0; iran = 0; russia = 0
        pre_tariff = 0; pre_deal = 0; pre_relief = 0; pre_action = 0
        open_tariff = 0; open_deal = 0
        night_post = 0; sig_djt = 0; sig_potus = 0; sig_tyfa = 0
        total_excl = 0; total_caps = 0; total_alpha = 0
        total_len = 0

        for p in day_p:
            cl = p['content'].lower()
            c = p['content']
            h, m_val = est_hour(p['created_at'])
            is_pre = h < 9 or (h == 9 and m_val < 30)
            is_open = not is_pre and h < 16
            is_night = h < 5 or h >= 23

            this_tariff = any(w in cl for w in ['tariff', 'tariffs', 'duty'])
            this_deal = any(w in cl for w in ['deal', 'agreement', 'signed', 'negotiate'])
            this_relief = any(w in cl for w in ['pause', 'exempt', 'suspend', 'delay'])
            this_action = any(w in cl for w in ['immediately', 'hereby', 'executive order', 'just signed'])
            this_attack = any(w in cl for w in ['fake news', 'corrupt', 'fraud', 'witch hunt'])
            this_positive = any(w in cl for w in ['great', 'tremendous', 'incredible', 'historic', 'beautiful'])
            this_brag = any(w in cl for w in ['stock market', 'all time high', 'record high', 'dow'])
            this_china = any(w in cl for w in ['china', 'chinese', 'beijing'])
            this_iran = any(w in cl for w in ['iran', 'iranian'])
            this_russia = any(w in cl for w in ['russia', 'putin', 'ukraine'])

            if this_tariff: tariff += 1
            if this_deal: deal += 1
            if this_relief: relief += 1
            if this_action: action += 1
            if this_attack: attack += 1
            if this_positive: positive += 1
            if this_brag: market_brag += 1
            if this_china: china += 1
            if this_iran: iran += 1
            if this_russia: russia += 1

            if is_pre and this_tariff: pre_tariff += 1
            if is_pre and this_deal: pre_deal += 1
            if is_pre and this_relief: pre_relief += 1
            if is_pre and this_action: pre_action += 1
            if is_open and this_tariff: open_tariff += 1
            if is_open and this_deal: open_deal += 1
            if is_night: night_post += 1

            if 'President DJT' in c: sig_djt += 1
            if 'PRESIDENT OF THE UNITED STATES' in c: sig_potus += 1
            if 'Thank you for your attention' in c: sig_tyfa += 1

            total_excl += c.count('!')
            total_caps += sum(1 for ch in c if ch.isupper())
            total_alpha += sum(1 for ch in c if ch.isalpha())
            total_len += len(c)

        f['has_tariff'] = tariff >= 1
        f['tariff_heavy'] = tariff >= 3
        f['has_deal'] = deal >= 1
        f['deal_heavy'] = deal >= 2
        f['has_relief'] = relief >= 1
        f['has_action'] = action >= 1
        f['has_attack'] = attack >= 1
        f['attack_heavy'] = attack >= 3
        f['has_positive'] = positive >= 1
        f['positive_heavy'] = positive >= 3
        f['has_market_brag'] = market_brag >= 1
        f['brag_heavy'] = market_brag >= 2
        f['has_china'] = china >= 1
        f['has_iran'] = iran >= 1
        f['has_russia'] = russia >= 1
        f['pre_tariff'] = pre_tariff >= 1
        f['pre_deal'] = pre_deal >= 1
        f['pre_relief'] = pre_relief >= 1
        f['pre_action'] = pre_action >= 1
        f['open_tariff'] = open_tariff >= 1
        f['open_tariff_heavy'] = open_tariff >= 2
        f['open_deal'] = open_deal >= 1
        f['has_night_post'] = night_post >= 1
        f['sig_djt'] = sig_djt >= 1
        f['sig_potus'] = sig_potus >= 1
        f['sig_tyfa'] = sig_tyfa >= 1
        f['high_emotion'] = (total_caps / max(total_alpha, 1)) > 0.2
        f['lots_of_excl'] = total_excl >= 5
        f['long_posts'] = (total_len / max(post_count, 1)) > 400
        f['short_posts'] = (total_len / max(post_count, 1)) < 150

        if idx >= 3:
            prev_tariff = sum(1 for j in range(max(0,idx-3), idx)
                             if any('tariff' in p['content'].lower() for p in daily_posts.get(sorted_dates[j], [])))
            f['tariff_streak_3d'] = prev_tariff >= 3
            f['tariff_rising'] = prev_tariff >= 2 and tariff >= 1
        else:
            f['tariff_streak_3d'] = False
            f['tariff_rising'] = False

        f['deal_over_tariff'] = deal > tariff and deal >= 1
        f['tariff_only'] = tariff >= 1 and deal == 0
        f['deal_only'] = deal >= 1 and tariff == 0

        if idx >= 7:
            prev_avg = sum(len(daily_posts.get(sorted_dates[j], []))
                          for j in range(idx-7, idx)) / 7
            f['volume_spike'] = post_count > prev_avg * 2 if prev_avg > 0 else False
            f['volume_drop'] = post_count < prev_avg * 0.4 if prev_avg > 0 else False
        else:
            f['volume_spike'] = False
            f['volume_drop'] = False

        return f

    def next_trading_day(date_str):
        dt = datetime.strptime(date_str, '%Y-%m-%d')
        for i in range(1, 6):
            d = (dt + timedelta(days=i)).strftime('%Y-%m-%d')
            if d in sp_by_date:
                return d
        return None

    # === 計算所有天的特徵 ===
    print("📊 計算每日特徵中...")
    all_features = {}
    for idx, date in enumerate(sorted_dates):
        feat = compute_features(date, idx)
        if feat:
            all_features[date] = feat

    feature_names = sorted(list(all_features[sorted_dates[10]].keys()))
    print(f"   特徵數: {len(feature_names)} 個")
    print(f"   天數: {len(all_features)} 天")

    # === 分割：訓練 vs 驗證 ===
    _all_valid_dates = [d for d in sorted_dates if d in all_features and d in sp_by_date]
    _n_dates = len(_all_valid_dates)
    _cutoff_idx = int(_n_dates * 0.75)
    cutoff = _all_valid_dates[_cutoff_idx] if _n_dates > 0 else "2025-12-01"

    train_dates = _all_valid_dates[:_cutoff_idx]
    test_dates = _all_valid_dates[_cutoff_idx:]

    if len(test_dates) < 10:
        print("⚠️ 驗證集不足 10 天，結果不可靠")

    print(f"   訓練期: {train_dates[0]} ~ {train_dates[-1]} ({len(train_dates)} 天)")
    print(f"   驗證期: {test_dates[0]} ~ {test_dates[-1]} ({len(test_dates)} 天)")

    # === PyTorch GPU 環境準備 ===
    print(f"\n{'='*90}")
    print(f"🚀 初始化 PyTorch 張量與運算環境")
    print(f"{'='*90}")

    # 選擇運算設備 (NVIDIA / Apple Silicon MPS / CPU)
    device = torch.device('cuda' if torch.cuda.is_available() else 'mps' if torch.backends.mps.is_available() else 'cpu')
    print(f"   使用設備: {device}")

    # 1. 建立特徵矩陣 X: (N_dates, N_features) 的布林張量
    N = len(_all_valid_dates)
    K = len(feature_names)
    X = torch.zeros((N, K), dtype=torch.bool)
    
    for i, date in enumerate(_all_valid_dates):
        feat = all_features[date]
        for j, fname in enumerate(feature_names):
            X[i, j] = feat.get(fname, False)
            
    X = X.to(device)

    # 2. 建立回報率矩陣 R 與有效遮罩 V: (N_dates, 3)
    hold_options = [1, 2, 3]
    direction_options = ['LONG', 'SHORT']
    
    R = torch.zeros((N, len(hold_options)), dtype=torch.float32)
    V = torch.zeros((N, len(hold_options)), dtype=torch.bool)

    for i, date in enumerate(_all_valid_dates):
        entry_day = next_trading_day(date)
        if not entry_day or entry_day not in sp_by_date:
            continue
            
        entry_p = sp_by_date[entry_day]['open']
        for h_idx, hold in enumerate(hold_options):
            exit_day = entry_day
            for _ in range(hold):
                nd = next_trading_day(exit_day)
                if nd:
                    exit_day = nd
                    
            if exit_day in sp_by_date:
                exit_p = sp_by_date[exit_day]['close']
                R[i, h_idx] = (exit_p - entry_p) / entry_p * 100.0
                V[i, h_idx] = True

    R = R.to(device)
    V = V.to(device)

    # 3. 建立 Train / Test 布林遮罩
    train_mask = torch.zeros(N, dtype=torch.bool, device=device)
    train_mask[:_cutoff_idx] = True
    test_mask = torch.zeros(N, dtype=torch.bool, device=device)
    test_mask[_cutoff_idx:] = True

    # === 計算組合總數 ===
    n2 = comb(K, 2)
    n3 = comb(K, 3)
    n4 = comb(K, 4)
    total_combos = (n2 + n3 + n4) * len(hold_options) * len(direction_options)
    
    print(f"   2 條件: {n2} 組")
    print(f"   3 條件: {n3} 組")
    print(f"   4 條件: {n4} 組")
    print(f"   × {len(hold_options)} 持有天數 × {len(direction_options)} 方向")
    print(f"   總計: {total_combos:,} 組合")

    winners_train = []
    total_tested = 0

    print(f"\n🔄 啟動張量平行回測...\n")
    start_time = time.time()

    for n_cond in [2, 3, 4]:
        # 展開當前條件數的所有組合
        combos = list(itertools.combinations(range(K), n_cond))
        C = len(combos)
        if C == 0: continue
        
        # 準備組合指標: (C, n_cond)
        indices = torch.tensor(combos, device=device)
        
        # 利用廣播與花式索引一次抓出所有組合在每一天的狀態 -> (N, C, n_cond)
        X_combo = X[:, indices]
        
        # 當所有條件 (dim=2) 都為 True 時才觸發 -> (N, C)
        triggered = X_combo.all(dim=2)
        
        for h_idx, hold in enumerate(hold_options):
            # 取出特定 hold_day 的有效交易日遮罩 -> (N, 1)
            valid_h = V[:, h_idx].unsqueeze(1)
            
            # 分別建立訓練期與測試期的有效觸發矩陣 -> (N, C)
            train_valid = valid_h & train_mask.unsqueeze(1)
            train_triggered = triggered & train_valid
            train_trades = train_triggered.sum(dim=0)
            
            test_valid = valid_h & test_mask.unsqueeze(1)
            test_triggered = triggered & test_valid
            test_trades = test_triggered.sum(dim=0)
            
            # 過濾門檻：訓練期至少 10 筆交易
            min_trades_mask = train_trades >= 10
            
            for direction in direction_options:
                total_tested += C
                
                # 計算方向回報率
                R_h = R[:, h_idx] if direction == 'LONG' else -R[:, h_idx]
                R_h = R_h.unsqueeze(1) # (N, 1)
                
                # 訓練期績效計算 (所有組合平行運算)
                train_combo_returns = train_triggered * R_h
                train_total_ret = train_combo_returns.sum(dim=0)
                train_avg_ret = train_total_ret / train_trades.clamp(min=1)
                train_wins = (train_combo_returns > 0).sum(dim=0) # 大於 0 才算贏
                train_win_rate = (train_wins.float() / train_trades.clamp(min=1).float()) * 100.0
                
                # 測試期績效計算 (與訓練期一併算出，省下後續重新回測時間)
                test_combo_returns = test_triggered * R_h
                test_total_ret = test_combo_returns.sum(dim=0)
                test_avg_ret = test_total_ret / test_trades.clamp(min=1)
                test_wins = (test_combo_returns > 0).sum(dim=0)
                test_win_rate = (test_wins.float() / test_trades.clamp(min=1).float()) * 100.0
                
                # 初步篩選：訓練期勝率 >= 60% 且 平均回報 > 0.1%
                pass_mask = min_trades_mask & (train_win_rate >= 60.0) & (train_avg_ret > 0.1)
                pass_indices = torch.where(pass_mask)[0]
                
                # 將合格的少數結果轉回 CPU 進行 p-value 計算及存檔
                if len(pass_indices) > 0:
                    trades_cpu = train_trades[pass_indices].cpu().tolist()
                    wins_cpu = train_wins[pass_indices].cpu().tolist()
                    win_rate_cpu = train_win_rate[pass_indices].cpu().tolist()
                    avg_ret_cpu = train_avg_ret[pass_indices].cpu().tolist()
                    total_ret_cpu = train_total_ret[pass_indices].cpu().tolist()
                    
                    t_trades_cpu = test_trades[pass_indices].cpu().tolist()
                    t_wins_cpu = test_wins[pass_indices].cpu().tolist()
                    t_win_rate_cpu = test_win_rate[pass_indices].cpu().tolist()
                    t_avg_ret_cpu = test_avg_ret[pass_indices].cpu().tolist()
                    t_total_ret_cpu = test_total_ret[pass_indices].cpu().tolist()
                    
                    pass_indices_cpu = pass_indices.cpu().tolist()
                    
                    for i, c_idx in enumerate(pass_indices_cpu):
                        w_trades = trades_cpu[i]
                        w_wins = wins_cpu[i]
                        
                        pval = binomial_pvalue(w_wins, w_trades)
                        if pval < 0.05:
                            feature_combo = [feature_names[idx] for idx in combos[c_idx]]
                            winners_train.append({
                                'features': feature_combo,
                                'direction': direction,
                                'hold': hold,
                                'n_conditions': n_cond,
                                'train': {
                                    'trades': w_trades,
                                    'wins': w_wins,
                                    'win_rate': win_rate_cpu[i],
                                    'avg_return': avg_ret_cpu[i],
                                    'total_return': total_ret_cpu[i],
                                    'p_value': round(pval, 6),
                                },
                                'test': {
                                    'trades': t_trades_cpu[i],
                                    'wins': t_wins_cpu[i],
                                    'win_rate': t_win_rate_cpu[i],
                                    'avg_return': t_avg_ret_cpu[i],
                                    'total_return': t_total_ret_cpu[i],
                                }
                            })

    elapsed = time.time() - start_time
    print(f"✅ 平行回測完成！GPU 運算耗時: {elapsed:.2f} 秒")
    print(f"   總組合: {total_tested:,}")
    print(f"   訓練期過關: {len(winners_train)} 組 (勝率>60% & 平均報酬>0.1%)")

    # === 用驗證期檢驗 ===
    print(f"\n{'='*90}")
    print(f"🧪 驗證期檢驗 — 只有兩段都對的才是真密碼")
    print(f"{'='*90}")

    final_winners = []
    bonferroni_alpha = 0.05 / max(total_combos, 1)

    for w in winners_train:
        t = w['test']
        # 驗證期條件（這裡使用的是事前 GPU 平行運算好的結果）
        if t['trades'] >= 5 and t['win_rate'] >= 60.0 and t['avg_return'] > 0.1:
            test_pval = binomial_pvalue(t['wins'], t['trades'])
            t['p_value'] = round(test_pval, 6)
            w['test_p_value'] = round(test_pval, 6)
            w['bonferroni_significant'] = (w['train']['p_value'] < bonferroni_alpha)
            w['combined_win_rate'] = (w['train']['win_rate'] + t['win_rate']) / 2
            w['combined_avg_return'] = (w['train']['avg_return'] + t['avg_return']) / 2
            final_winners.append(w)

    # 按綜合表現排序
    final_winners.sort(key=lambda w: (-w['combined_win_rate'], -w['combined_avg_return']))

    print(f"\n   訓練期過關: {len(winners_train)} 組")
    print(f"   驗證期也過關: {len(final_winners)} 組 ← 真密碼候選")
    print(f"   淘汰率: {(1 - len(final_winners)/max(len(winners_train),1))*100:.1f}%")

    # === 打印 Top 30 ===
    print(f"\n{'='*90}")
    print(f"🏆 川普密碼 — 最終排行榜 Top 30（訓練+驗證都過關）")
    print(f"{'='*90}")
    print(f"  {'排名':>4s} | {'方向':>4s} | {'持有':>2s} | {'訓練勝率':>8s} | {'驗證勝率':>8s} | {'訓練報酬':>8s} | {'驗證報酬':>8s} | 條件組合")
    print(f"  {'-'*4}-+-{'-'*4}-+-{'-'*2}-+-{'-'*8}-+-{'-'*8}-+-{'-'*8}-+-{'-'*8}-+-{'-'*30}")

    for rank, w in enumerate(final_winners[:30], 1):
        dir_icon = "📈" if w['direction'] == 'LONG' else "📉"
        features_str = ' + '.join(w['features'])

        print(f"  {rank:4d} | {dir_icon}{w['direction']:>3s} | {w['hold']:2d}天 | "
              f"{w['train']['win_rate']:6.1f}% | {w['test']['win_rate']:6.1f}% | "
              f"{w['train']['avg_return']:+.3f}% | {w['test']['avg_return']:+.3f}% | "
              f"{features_str}")

    # === 按條件數分組統計 ===
    print(f"\n{'='*90}")
    print(f"📊 幾個條件最好？")
    print(f"{'='*90}")
    for n in [2, 3, 4]:
        group = [w for w in final_winners if w['n_conditions'] == n]
        if group:
            avg_wr = sum(w['combined_win_rate'] for w in group) / len(group)
            avg_ret = sum(w['combined_avg_return'] for w in group) / len(group)
            best = group[0]
            print(f"  {n} 條件: {len(group)} 組過關 | 平均勝率 {avg_wr:.1f}% | 平均報酬 {avg_ret:+.3f}%")
            print(f"    最佳: {' + '.join(best['features'])} ({best['direction']}, {best['hold']}天)")

    # === 找最常出現的特徵 ===
    print(f"\n{'='*90}")
    print(f"📊 哪些特徵最常出現在贏家組合？（真密碼的 DNA）")
    print(f"{'='*90}")
    feature_freq = defaultdict(int)
    for w in final_winners:
        for f_name in w['features']:
            feature_freq[f_name] += 1

    for fname, count in sorted(feature_freq.items(), key=lambda x: -x[1])[:20]:
        bar = '█' * min(count, 40)
        pct = count / max(len(final_winners), 1) * 100
        print(f"  {fname:25s} | {count:4d}次 ({pct:5.1f}%) {bar}")

    # 存結果
    bonferroni_count = sum(1 for w in final_winners if w.get('bonferroni_significant'))
    output = {
        'total_tested': total_tested,
        'train_passed': len(winners_train),
        'final_passed': len(final_winners),
        'bonferroni_alpha': bonferroni_alpha,
        'bonferroni_significant_count': bonferroni_count,
        'cutoff_date': cutoff,
        'top_30': [{
            'rank': i+1,
            'features': w['features'],
            'direction': w['direction'],
            'hold': w['hold'],
            'train_win_rate': round(w['train']['win_rate'], 1),
            'test_win_rate': round(w['test']['win_rate'], 1),
            'train_avg_return': round(w['train']['avg_return'], 3),
            'test_avg_return': round(w['test']['avg_return'], 3),
            'p_value': w['train'].get('p_value'),
            'test_p_value': w.get('test_p_value'),
            'bonferroni_significant': w.get('bonferroni_significant', False),
        } for i, w in enumerate(final_winners[:30])],
        'feature_frequency': dict(sorted(feature_freq.items(), key=lambda x: -x[1])[:20]),
    }

    with open(DATA / 'results_11_bruteforce.json', 'w', encoding='utf-8') as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    print(f"\n💾 結果存入 results_11_bruteforce.json")


if __name__ == '__main__':
    main()
