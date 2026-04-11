#!/usr/bin/env python3
"""
Musk Code — 過夜暴力搜索（完整版）
搜索範圍：2-combo, 3-combo, 4-combo × 多門檻 × TSLA + DOGE
預計跑 30 分鐘～2 小時。
"""
import json, time
from collections import defaultdict, Counter
from datetime import datetime, timedelta
from pathlib import Path

DATA = Path('/home/ubuntu/trump-code/data')
start_time = time.time()

def log(msg):
    elapsed = time.time() - start_time
    print(f"[{elapsed:.0f}s] {msg}", flush=True)

# ===== 載入 =====
log("載入推文...")
with open(DATA / 'musk_posts.json') as f:
    all_posts = json.load(f)['posts']

daily = defaultdict(list)
for p in all_posts:
    d = p.get('created_at','')[:10]
    if d >= '2020-01-01':
        daily[d].append(p)

sorted_dates = sorted(daily.keys())
log(f"{len(sorted_dates)} 天, {sum(len(v) for v in daily.values()):,} 篇")

# ===== TSLA + DOGE 數據 =====
log("下載市場數據...")
import yfinance as yf
import urllib.request

tsla_hist = yf.Ticker("TSLA").history(period="5y")
tsla_market = {}
prev = None
for date, row in tsla_hist.iterrows():
    d = date.strftime('%Y-%m-%d')
    close = row['Close']
    if prev and prev > 0:
        tsla_market[d] = round((close - prev) / prev * 100, 3)
    prev = close
log(f"TSLA: {len(tsla_market)} 交易日")

# DOGE
try:
    url = 'https://api.coingecko.com/api/v3/coins/dogecoin/market_chart?vs_currency=usd&days=max'
    req = urllib.request.Request(url, headers={'User-Agent': 'MuskCode/1.0'})
    with urllib.request.urlopen(req, timeout=30) as resp:
        doge_data = json.load(resp)
    doge_market = {}
    prev_p = None
    for ts, price in doge_data.get('prices', []):
        d = datetime.utcfromtimestamp(ts/1000).strftime('%Y-%m-%d')
        if prev_p and prev_p > 0:
            doge_market[d] = round((price - prev_p) / prev_p * 100, 3)
        prev_p = price
    log(f"DOGE: {len(doge_market)} 天")
except Exception as e:
    log(f"DOGE 失敗: {e}")
    doge_market = {}

# ===== 特徵計算 =====
log("計算特徵...")
stats = {}
for d in sorted_dates:
    posts = daily[d]
    n = len(posts)
    text = ' '.join(p['content'].lower() for p in posts)
    total_likes = sum(p.get('likes', 0) for p in posts)
    
    def ct(kws): return sum(1 for p in posts if any(w in p['content'].lower() for w in kws))
    
    stats[d] = {
        'n': n, 'likes': total_likes,
        'avg_len': sum(len(p['content']) for p in posts) / max(n,1),
        't_tesla': ct(['tesla','tsla','model','cybertruck','fsd','autopilot','roadster','optimus','gigafactory','supercharger','megapack','powerwall']),
        't_spacex': ct(['spacex','starship','falcon','starlink','mars','launch','orbit','rocket','booster']),
        't_doge': ct(['doge','dogecoin','🐕','shib']),
        't_crypto': ct(['bitcoin','btc','crypto','blockchain','eth','nft','web3','satoshi']),
        't_ai': ct(['grok','xai','openai','chatgpt','ai ','artificial intelligence','neural','agi','llm','machine learning']),
        't_politics': ct(['government','congress','vote','election','border','immigration','regulation','sec ','doge department','biden','trump','democrat','republican']),
        't_attack': ct(['fake','woke','censorship','propaganda','dei','legacy media','msm','mainstream','corrupt']),
        't_product': ct(['announce','launch','deliver','release','update','upgrade','version','new feature','unveil','reveal']),
        't_money': ct(['revenue','profit','earnings','valuation','market cap','stock','share','investor','billion','million']),
        't_personal': ct(['lol','lmao','haha','😂','🤣','meme','based','ratio','69','420']),
        't_positive': ct(['amazing','incredible','insane','revolutionary','awesome','love','great','best','beautiful','exciting']),
        't_negative': ct(['terrible','awful','disaster','worst','hate','stupid','broken','fail','sad','unfortunate']),
    }

# 滾動平均
def rolling(key, window=7):
    avgs = {}
    for i, d in enumerate(sorted_dates):
        vals = [stats[sorted_dates[j]][key] for j in range(max(0,i-window), i) if sorted_dates[j] in stats]
        avgs[d] = sum(vals) / max(len(vals), 1)
    return avgs

r_n = rolling('n')
r_likes = rolling('likes')

features = {}
for d in sorted_dates:
    s = stats[d]
    f = {}
    avg_n = r_n.get(d, s['n']); avg_likes = r_likes.get(d, s['likes'])
    n = max(s['n'], 1)
    
    # 量
    if avg_n > 0:
        f['vol_spike_50'] = s['n'] > avg_n * 1.5
        f['vol_spike_100'] = s['n'] > avg_n * 2.0
        f['vol_drop_50'] = s['n'] < avg_n * 0.5
        f['vol_drop_75'] = s['n'] < avg_n * 0.25
    if avg_likes > 0:
        f['eng_spike'] = s['likes'] > avg_likes * 2
        f['eng_drop'] = s['likes'] < avg_likes * 0.3
    
    # 話題佔比
    for topic in ['tesla','spacex','doge','crypto','ai','politics','attack','product','money','personal','positive','negative']:
        pct = s.get(f't_{topic}', 0) / n
        f[f'{topic}_dominant'] = pct > 0.30
        f[f'{topic}_heavy'] = pct > 0.50
        f[f'{topic}_absent'] = pct == 0
        f[f'{topic}_minor'] = 0 < pct < 0.10
    
    # 組合
    f['tesla_focus'] = s['t_tesla']/n > 0.3 and s['t_spacex']/n < 0.1
    f['doge_pump'] = s['t_doge']/n > 0.05
    f['crypto_day'] = (s['t_crypto'] + s['t_doge'])/n > 0.15
    f['attack_day'] = s['t_attack']/n > 0.15
    f['product_day'] = s['t_product']/n > 0.1
    f['money_talk'] = s['t_money']/n > 0.05
    f['meme_lord'] = s['t_personal']/n > 0.3
    f['serious_day'] = s['t_personal']/n < 0.05 and s['n'] > 10
    f['quiet_day'] = s['n'] < 5
    f['hyper_day'] = s['n'] > 50
    f['short_tweets'] = s['avg_len'] < 60
    f['long_tweets'] = s['avg_len'] > 200
    f['multi_topic'] = sum(1 for t in ['tesla','spacex','crypto','ai','politics'] if s[f't_{t}']/n > 0.1) >= 3
    f['positive_day'] = s['t_positive']/n > 0.2
    f['negative_day'] = s['t_negative']/n > 0.05
    f['bullish_combo'] = s['t_positive']/n > 0.15 and s['t_tesla']/n > 0.1
    f['bearish_combo'] = s['t_negative']/n > 0.05 or (s['t_tesla']/n == 0 and s['n'] > 20)
    
    features[d] = f

nd = len(features)
fc = Counter()
for f in features.values():
    for k,v in f.items():
        if v: fc[k] += 1
useful = sorted([k for k,c in fc.items() if 5 <= c <= nd-5])
log(f"有用特徵: {len(useful)} 個")

# ===== 搜索函數 =====
def search(market_data, asset_name, thresholds):
    all_winners = []
    
    for thresh in thresholds:
        day_labels = {}
        for d, ch in market_data.items():
            if ch > thresh: day_labels[d] = 'BIG_UP'
            elif ch < -thresh: day_labels[d] = 'BIG_DOWN'
            else: day_labels[d] = 'NORMAL'
        
        bu = sum(1 for v in day_labels.values() if v=='BIG_UP')
        bd = sum(1 for v in day_labels.values() if v=='BIG_DOWN')
        log(f"\n{'='*60}")
        log(f"🔍 {asset_name} ±{thresh}%: {bu} 漲 + {bd} 跌")
        
        td_set = set(market_data.keys())
        def next_td(d):
            dt = datetime.strptime(d, '%Y-%m-%d')
            for i in range(1,5):
                nd = (dt + timedelta(days=i)).strftime('%Y-%m-%d')
                if nd in td_set: return nd
            return None
        
        valid = [d for d in sorted_dates if d in features and features[d]]
        cutoff = int(len(valid) * 0.75)
        train, test = valid[:cutoff], valid[cutoff:]
        
        n_feat = len(useful)
        def build_masks(dates):
            fm = {f: 0 for f in useful}
            tup, tdn = 0, 0
            nxt = {d: next_td(d) for d in dates}
            for i, d in enumerate(dates):
                bit = 1 << i
                for fname in features.get(d, {}):
                    if fname in fm and features[d][fname]: fm[fname] |= bit
                nd = nxt.get(d)
                if nd and nd in day_labels:
                    if day_labels[nd] == 'BIG_UP': tup |= bit
                    elif day_labels[nd] == 'BIG_DOWN': tdn |= bit
            return fm, {'BIG_UP': tup, 'BIG_DOWN': tdn}
        
        tr_fm, tr_tgt = build_masks(train)
        te_fm, te_tgt = build_masks(test)
        popcount = lambda x: bin(x).count('1')
        tr_s = [tr_fm[useful[i]] for i in range(n_feat)]
        te_s = [te_fm[useful[i]] for i in range(n_feat)]
        
        winners = []
        tested = 0
        
        # 2-combo
        for i in range(n_feat):
            for j in range(i+1, n_feat):
                trm = tr_s[i] & tr_s[j]; trt = popcount(trm)
                if trt < 3: tested += 2; continue
                tem = te_s[i] & te_s[j]
                for tgt in ('BIG_UP','BIG_DOWN'):
                    tested += 1
                    trh = popcount(trm & tr_tgt[tgt])
                    if trt == 0: continue
                    tr_rate = trh/trt*100
                    if tr_rate < 45: continue
                    tet = popcount(tem)
                    if tet < 2: continue
                    teh = popcount(tem & te_tgt[tgt])
                    te_rate = teh/tet*100
                    if te_rate >= 35:
                        winners.append({'features':[useful[i],useful[j]],'target':tgt,'asset':asset_name,'threshold':thresh,'train':f'{trh}/{trt}','train_rate':round(tr_rate,1),'test':f'{teh}/{tet}','test_rate':round(te_rate,1),'combined':round((tr_rate+te_rate)/2,1)})
        
        log(f"  2-combo: {tested:,} → {len(winners)} 候選")
        
        # 3-combo
        t3 = 0
        for i in range(n_feat):
            for j in range(i+1, n_feat):
                trij = tr_s[i] & tr_s[j]
                if popcount(trij) < 3: t3 += (n_feat-j-1)*2; continue
                teij = te_s[i] & te_s[j]
                for k in range(j+1, n_feat):
                    trm = trij & tr_s[k]; trt = popcount(trm)
                    if trt < 3: t3 += 2; continue
                    tem = teij & te_s[k]
                    for tgt in ('BIG_UP','BIG_DOWN'):
                        t3 += 1
                        trh = popcount(trm & tr_tgt[tgt])
                        if trt == 0: continue
                        tr_rate = trh/trt*100
                        if tr_rate < 45: continue
                        tet = popcount(tem)
                        if tet < 2: continue
                        teh = popcount(tem & te_tgt[tgt])
                        te_rate = teh/tet*100
                        if te_rate >= 35:
                            winners.append({'features':[useful[i],useful[j],useful[k]],'target':tgt,'asset':asset_name,'threshold':thresh,'train':f'{trh}/{trt}','train_rate':round(tr_rate,1),'test':f'{teh}/{tet}','test_rate':round(te_rate,1),'combined':round((tr_rate+te_rate)/2,1)})
        
        tested += t3
        log(f"  3-combo: {t3:,} → 累計 {len(winners)} 候選")
        
        # 4-combo（只在有足夠特徵時跑）
        if n_feat <= 60:
            t4 = 0
            for i in range(n_feat):
                for j in range(i+1, n_feat):
                    trij = tr_s[i] & tr_s[j]
                    if popcount(trij) < 4: continue
                    teij = te_s[i] & te_s[j]
                    for k in range(j+1, n_feat):
                        trk = trij & tr_s[k]
                        if popcount(trk) < 4: continue
                        tek = teij & te_s[k]
                        for l in range(k+1, n_feat):
                            trm = trk & tr_s[l]; trt = popcount(trm)
                            if trt < 3: t4 += 2; continue
                            tem = tek & te_s[l]
                            for tgt in ('BIG_UP','BIG_DOWN'):
                                t4 += 1
                                trh = popcount(trm & tr_tgt[tgt])
                                if trt == 0: continue
                                tr_rate = trh/trt*100
                                if tr_rate < 50: continue
                                tet = popcount(tem)
                                if tet < 2: continue
                                teh = popcount(tem & te_tgt[tgt])
                                te_rate = teh/tet*100
                                if te_rate >= 40:
                                    winners.append({'features':[useful[i],useful[j],useful[k],useful[l]],'target':tgt,'asset':asset_name,'threshold':thresh,'train':f'{trh}/{trt}','train_rate':round(tr_rate,1),'test':f'{teh}/{tet}','test_rate':round(te_rate,1),'combined':round((tr_rate+te_rate)/2,1)})
            
            tested += t4
            log(f"  4-combo: {t4:,} → 累計 {len(winners)} 候選")
        
        log(f"  ✅ 總計 {tested:,} 組, {len(winners)} 候選")
        all_winners.extend(winners)
    
    return all_winners

# ===== 開跑！=====
log("=" * 60)
log("🚀 MUSK CODE 過夜暴力搜索 開始")
log("=" * 60)

all_results = []

# TSLA: 多門檻
tsla_results = search(tsla_market, 'TSLA', [1.5, 2.0, 3.0, 5.0])
all_results.extend(tsla_results)

# DOGE: 多門檻
if doge_market:
    doge_results = search(doge_market, 'DOGE', [3.0, 5.0, 10.0])
    all_results.extend(doge_results)

# 排序
all_results.sort(key=lambda w: w['combined'], reverse=True)

elapsed = time.time() - start_time
log(f"\n{'='*60}")
log(f"🏁 完成！耗時 {elapsed/60:.1f} 分鐘")
log(f"   總候選: {len(all_results)} 組")
log(f"   TSLA: {sum(1 for r in all_results if r['asset']=='TSLA')} 組")
log(f"   DOGE: {sum(1 for r in all_results if r['asset']=='DOGE')} 組")

# Top 20
if all_results:
    log(f"\n🏆 TOP 20:")
    for i, w in enumerate(all_results[:20]):
        icon = '🚀' if w['target'] == 'BIG_UP' else '💥'
        log(f"  {i+1}. {icon} [{w['asset']} ±{w['threshold']}%] {' + '.join(w['features'])}")
        log(f"     → {w['target']} | 訓練: {w['train']}={w['train_rate']}% | 驗證: {w['test']}={w['test_rate']}% | 綜合: {w['combined']}%")

# 存檔
output = {
    'run_at': datetime.utcnow().isoformat() + 'Z',
    'elapsed_minutes': round(elapsed/60, 1),
    'total_posts': sum(len(v) for v in daily.values()),
    'total_features': len(useful),
    'feature_list': useful,
    'total_candidates': len(all_results),
    'candidates': all_results,
}
out_file = DATA / 'results_musk_overnight.json'
with open(out_file, 'w') as f:
    json.dump(output, f, ensure_ascii=False, indent=2)
log(f"💾 {out_file}")
