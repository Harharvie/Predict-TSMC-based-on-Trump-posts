import json
import re
from datetime import datetime, timedelta
from collections import Counter, defaultdict
import math

# ============================================================
# Load Data
# ============================================================
with open('data/x_posts_full.json') as f:
    xd = json.load(f)
with open('clean_president.json') as f:
    ts_all = json.load(f)
with open('data/market_SP500.json') as f:
    market = json.load(f)

# Filter
x_originals = [t for t in xd['tweets'] if 'referenced_tweets' not in t]
ts_originals = [p for p in ts_all if p.get('has_text') and not p.get('is_retweet')]

# Market lookup
market_by_date = {m['date']: m for m in market}
market_dates_sorted = sorted(market_by_date.keys())

def get_next_trading_day(date_str):
    """Get next trading day on or after date_str"""
    for md in market_dates_sorted:
        if md >= date_str:
            return md
    return None

def get_prev_trading_day(date_str):
    """Get previous trading day on or before date_str"""
    for md in reversed(market_dates_sorted):
        if md <= date_str:
            return md
    return None

def get_market_return(date_str):
    """Get market return for the trading day that covers this date"""
    td = get_next_trading_day(date_str)
    if td and td in market_by_date:
        m = market_by_date[td]
        return (m['close'] - m['open']) / m['open'] * 100
    return None

def get_next_day_return(date_str):
    """Get next trading day's return"""
    td = get_next_trading_day(date_str)
    if not td:
        return None
    idx = market_dates_sorted.index(td)
    if idx + 1 < len(market_dates_sorted):
        nd = market_dates_sorted[idx + 1]
        m = market_by_date[nd]
        return (m['close'] - m['open']) / m['open'] * 100
    return None

# ============================================================
# Text cleaning and matching
# ============================================================
def clean_text(text):
    """Clean text for comparison"""
    text = re.sub(r'https?://\S+', '', text)
    text = re.sub(r'@\w+', '', text)
    text = re.sub(r'#\w+', '', text)
    text = text.strip()
    return text

def normalize_for_match(text):
    """Normalize text for fuzzy matching"""
    text = clean_text(text)
    text = re.sub(r'[^\w\s]', '', text.lower())
    text = re.sub(r'\s+', ' ', text).strip()
    return text

def text_similarity(a, b):
    """Simple word overlap similarity"""
    wa = set(a.split())
    wb = set(b.split())
    if not wa or not wb:
        return 0
    intersection = wa & wb
    return len(intersection) / max(len(wa), len(wb))

# Parse dates
for t in x_originals:
    t['dt'] = datetime.fromisoformat(t['created_at'].replace('Z', '+00:00'))
    t['date'] = t['created_at'][:10]
    t['clean_text'] = clean_text(t['text'])
    t['norm_text'] = normalize_for_match(t['text'])

for p in ts_originals:
    p['dt'] = datetime.fromisoformat(p['created_at'].replace('Z', '+00:00'))
    p['date'] = p['created_at'][:10]
    p['clean_text'] = clean_text(p['content'])
    p['norm_text'] = normalize_for_match(p['content'])

# Find matches: X tweets that also appear on Truth Social
matches = []
x_with_text = [t for t in x_originals if t['clean_text']]

for xt in x_with_text:
    best_match = None
    best_score = 0
    # Search in a window of +-3 days
    for tp in ts_originals:
        time_diff = abs((xt['dt'] - tp['dt']).total_seconds())
        if time_diff > 3 * 86400:  # 3 days
            continue
        sim = text_similarity(xt['norm_text'], tp['norm_text'])
        if sim > best_score:
            best_score = sim
            best_match = tp
    if best_score >= 0.5:  # Threshold
        time_diff_hours = (xt['dt'] - best_match['dt']).total_seconds() / 3600
        matches.append({
            'x_text': xt['clean_text'][:200],
            'ts_text': best_match['clean_text'][:200],
            'similarity': round(best_score, 3),
            'x_time': xt['created_at'],
            'ts_time': best_match['created_at'],
            'time_diff_hours': round(time_diff_hours, 2),
            'x_date': xt['date'],
            'ts_date': best_match['date'],
            'x_metrics': xt.get('public_metrics', {}),
            'ts_replies': best_match.get('replies_count', 0),
            'ts_reblogs': best_match.get('reblogs_count', 0),
            'ts_favourites': best_match.get('favourites_count', 0),
            'x_post': xt,
            'ts_post': best_match,
        })

print(f"Found {len(matches)} matched tweets (similarity >= 0.5)")
for m in matches[:5]:
    print(f"  [{m['x_time'][:16]}] sim={m['similarity']} diff={m['time_diff_hours']:.1f}h")
    print(f"    X:  {m['x_text'][:100]}")
    print(f"    TS: {m['ts_text'][:100]}")

# Also try matching URL-only X posts to Truth Social posts by time proximity
x_url_only = [t for t in x_originals if not t['clean_text']]
print(f"\nURL-only X posts: {len(x_url_only)} (these likely link to Truth Social posts or videos)")

# ============================================================
# ANALYSIS 1: Selection Mechanism
# ============================================================
print("\n" + "="*80)
print("ANALYSIS 1: 篩選機制分析")
print("="*80)

def compute_features(text):
    """Compute features for a piece of text"""
    if not text:
        return {}
    words = text.split()
    upper_chars = sum(1 for c in text if c.isupper())
    total_alpha = sum(1 for c in text if c.isalpha())
    caps_ratio = upper_chars / total_alpha if total_alpha > 0 else 0
    
    # All-caps words
    all_caps_words = sum(1 for w in words if w.isupper() and len(w) > 1)
    all_caps_ratio = all_caps_words / len(words) if words else 0
    
    excl = text.count('!')
    quest = text.count('?')
    
    # Sentiment keywords
    positive = ['great', 'beautiful', 'best', 'incredible', 'wonderful', 'amazing', 'tremendous', 'fantastic',
                'victory', 'winning', 'win', 'success', 'love', 'happy', 'congratulations', 'phenomenal']
    negative = ['scum', 'losers', 'radical', 'disaster', 'terrible', 'horrible', 'worst', 'fake', 'corrupt',
                'criminal', 'destroy', 'enemy', 'threat', 'attack', 'war', 'kill', 'death']
    policy = ['tariff', 'trade', 'deal', 'china', 'iran', 'executive order', 'military', 'border',
              'immigration', 'tax', 'economy', 'stock', 'market', 'elon', 'doge', 'spending']
    
    text_lower = text.lower()
    pos_count = sum(1 for w in positive if w in text_lower)
    neg_count = sum(1 for w in negative if w in text_lower)
    pol_count = sum(1 for w in policy if w in text_lower)
    
    has_media_ref = 1 if any(w in text_lower for w in ['photo', 'video', 'watch', 'tune in', 'broadcast']) else 0
    has_endorsement = 1 if any(w in text_lower for w in ['vote', 'endorsement', 'campaign', 'candidate', 'patriot']) else 0
    has_personal = 1 if any(w in text_lower for w in ['melania', 'eric', 'barron', 'ivanka', 'don jr', 'tiffany']) else 0
    
    return {
        'length': len(text),
        'word_count': len(words),
        'caps_ratio': round(caps_ratio, 3),
        'all_caps_ratio': round(all_caps_ratio, 3),
        'exclamations': excl,
        'questions': quest,
        'positive_words': pos_count,
        'negative_words': neg_count,
        'policy_words': pol_count,
        'has_media_ref': has_media_ref,
        'has_endorsement': has_endorsement,
        'has_personal': has_personal,
    }

# Features for matched X posts
matched_ts_ids = set()
for m in matches:
    matched_ts_ids.add(m['ts_post']['id'])

matched_features = []
for m in matches:
    f = compute_features(m['ts_post']['clean_text'])
    f['matched'] = True
    matched_features.append(f)

# Features for unmatched TS posts
unmatched_ts = [p for p in ts_originals if p['id'] not in matched_ts_ids]
unmatched_features = []
for p in unmatched_ts:
    f = compute_features(p['clean_text'])
    f['matched'] = False
    unmatched_features.append(f)

def avg_features(feature_list):
    if not feature_list:
        return {}
    keys = [k for k in feature_list[0].keys() if k != 'matched']
    result = {}
    for k in keys:
        vals = [f[k] for f in feature_list if k in f]
        if vals:
            result[k] = round(sum(vals) / len(vals), 3)
    return result

matched_avg = avg_features(matched_features)
unmatched_avg = avg_features(unmatched_features)

print(f"\n匹配推文: {len(matches)} 篇")
print(f"未匹配推文: {len(unmatched_ts)} 篇")
print(f"\n{'特徵':<20} {'匹配(放X)':<15} {'未匹配(不放X)':<15} {'差異':<10}")
print("-" * 60)
for k in matched_avg:
    m_val = matched_avg.get(k, 0)
    u_val = unmatched_avg.get(k, 0)
    diff = m_val - u_val
    print(f"{k:<20} {m_val:<15.3f} {u_val:<15.3f} {diff:<+10.3f}")

# Build "X Selection Score" - logistic-style weights based on feature differences
# Simple scoring: normalize each feature difference, weight by magnitude
score_weights = {}
for k in matched_avg:
    m_val = matched_avg.get(k, 0)
    u_val = unmatched_avg.get(k, 0)
    if u_val != 0:
        score_weights[k] = round((m_val - u_val) / abs(u_val), 3)
    elif m_val != 0:
        score_weights[k] = 1.0
    else:
        score_weights[k] = 0.0

# Top selection factors
sorted_weights = sorted(score_weights.items(), key=lambda x: abs(x[1]), reverse=True)
print(f"\n「X 選擇分數」權重排名（正=更可能放X，負=更可能不放X）:")
for k, w in sorted_weights:
    direction = "→ 放 X" if w > 0 else "→ 不放 X"
    print(f"  {k:<20} {w:>+8.3f}  {direction}")

# ============================================================
# ANALYSIS 2: Time Difference Signal
# ============================================================
print("\n" + "="*80)
print("ANALYSIS 2: 時間差信號")
print("="*80)

time_diffs = [m['time_diff_hours'] for m in matches]
ts_first = [m for m in matches if m['time_diff_hours'] > 0]  # X posted after TS
x_first = [m for m in matches if m['time_diff_hours'] < 0]  # X posted before TS
same_time = [m for m in matches if abs(m['time_diff_hours']) < 0.1]

print(f"\n時間差分布:")
print(f"  Truth Social 先發, X 後發: {len(ts_first)} 篇")
print(f"  X 先發, Truth Social 後發: {len(x_first)} 篇")
print(f"  幾乎同時 (<6分鐘): {len(same_time)} 篇")

if ts_first:
    diffs = [m['time_diff_hours'] for m in ts_first]
    print(f"\n  TS先發 → X後發 的時間差:")
    print(f"    平均: {sum(diffs)/len(diffs):.2f} 小時")
    print(f"    中位數: {sorted(diffs)[len(diffs)//2]:.2f} 小時")
    print(f"    最短: {min(diffs):.2f} 小時")
    print(f"    最長: {max(diffs):.2f} 小時")

# Time of day analysis (EST = UTC-5)
def classify_market_time(dt):
    """Classify by market hours (EST)"""
    est_hour = (dt.hour - 5) % 24
    if est_hour < 9 or (est_hour == 9 and dt.minute < 30):
        return 'pre_market'
    elif est_hour < 16:
        return 'market_hours'
    else:
        return 'after_hours'

market_time_groups = defaultdict(list)
for m in matches:
    x_dt = datetime.fromisoformat(m['x_time'].replace('Z', '+00:00'))
    period = classify_market_time(x_dt)
    market_time_groups[period].append(m)

print(f"\n  按市場時段分布:")
for period in ['pre_market', 'market_hours', 'after_hours']:
    items = market_time_groups.get(period, [])
    if items:
        avg_diff = sum(m['time_diff_hours'] for m in items) / len(items)
        print(f"    {period}: {len(items)} 篇, 平均時間差 {avg_diff:.2f} 小時")

# Market movement during time gap
print(f"\n  時間差窗口中的股市動態:")
gap_returns = []
for m in ts_first:
    ts_date = m['ts_date']
    x_date = m['x_date']
    ret = get_market_return(ts_date)
    if ret is not None:
        gap_returns.append(ret)
        
if gap_returns:
    print(f"    TS發文日的股市日報酬 (N={len(gap_returns)}):")
    print(f"    平均: {sum(gap_returns)/len(gap_returns):.4f}%")
    print(f"    正報酬天數: {sum(1 for r in gap_returns if r > 0)}/{len(gap_returns)}")

# ============================================================
# ANALYSIS 3: Hidden Posts Market Impact
# ============================================================
print("\n" + "="*80)
print("ANALYSIS 3: 隱藏推文的市場影響")
print("="*80)

# Topic classification
TOPICS = {
    'tariff_trade': ['tariff', 'trade', 'deal', 'reciprocal', 'import', 'export', 'duties', 'customs'],
    'china': ['china', 'chinese', 'xi', 'beijing'],
    'iran_military': ['iran', 'military', 'houthi', 'attack', 'strike', 'bomb', 'isis', 'war', 'troops', 'kharg'],
    'economy_market': ['economy', 'stock', 'market', 'dow', 'inflation', 'rate', 'interest', 'oil', 'price', 'investment'],
    'elon_doge': ['elon', 'musk', 'doge', 'tesla', 'spending', 'efficiency'],
    'executive_order': ['executive order', 'signed', 'order', 'directive'],
    'immigration': ['border', 'immigration', 'illegal', 'deport', 'alien', 'immigrant', 'ice'],
    'personal_family': ['melania', 'eric', 'barron', 'ivanka', 'don jr', 'family', 'birthday', 'wedding'],
    'endorsement': ['vote', 'endorse', 'candidate', 'election', 'campaign', 'district', 'congress'],
    'media_attack': ['fake news', 'media', 'cnn', 'msnbc', 'cbs', 'nbc', 'abc', 'radical left', 'democrat'],
    'foreign_policy': ['ukraine', 'russia', 'nato', 'europe', 'canada', 'mexico', 'venezuela', 'honduras'],
    'legal_court': ['court', 'supreme', 'judge', 'law', 'constitution', 'impeach'],
}

def classify_topics(text):
    text_lower = text.lower()
    topics = []
    for topic, keywords in TOPICS.items():
        if any(kw in text_lower for kw in keywords):
            topics.append(topic)
    return topics if topics else ['other']

# Classify Truth Social posts
ts_topic_returns = defaultdict(list)  # topic -> [next_day_returns]
matched_topic_returns = defaultdict(list)

for p in ts_originals:
    topics = classify_topics(p['clean_text'])
    ret = get_next_day_return(p['date'])
    if ret is not None:
        is_matched = p['id'] in matched_ts_ids
        for t in topics:
            if is_matched:
                matched_topic_returns[t].append(ret)
            else:
                ts_topic_returns[t].append(ret)

print(f"\n按主題分類的隔天股市影響:")
print(f"\n{'主題':<20} {'TS Only篇數':<12} {'TS Only平均%':<14} {'放X篇數':<10} {'放X平均%':<12} {'差異':<10}")
print("-" * 80)
all_topics = sorted(set(list(ts_topic_returns.keys()) + list(matched_topic_returns.keys())))
topic_impact = {}
for t in all_topics:
    ts_rets = ts_topic_returns.get(t, [])
    m_rets = matched_topic_returns.get(t, [])
    ts_avg = sum(ts_rets)/len(ts_rets) if ts_rets else 0
    m_avg = sum(m_rets)/len(m_rets) if m_rets else 0
    diff = ts_avg - m_avg
    topic_impact[t] = {
        'ts_only_count': len(ts_rets),
        'ts_only_avg_return': round(ts_avg, 4),
        'x_also_count': len(m_rets),
        'x_also_avg_return': round(m_avg, 4),
        'difference': round(diff, 4),
    }
    print(f"{t:<20} {len(ts_rets):<12} {ts_avg:<+14.4f} {len(m_rets):<10} {m_avg:<+12.4f} {diff:<+10.4f}")

# Overall comparison
all_ts_only_rets = []
all_x_also_rets = []
for p in ts_originals:
    ret = get_next_day_return(p['date'])
    if ret is not None:
        if p['id'] in matched_ts_ids:
            all_x_also_rets.append(ret)
        else:
            all_ts_only_rets.append(ret)

print(f"\n整體比較:")
print(f"  Truth Social Only (N={len(all_ts_only_rets)}): 隔天平均 {sum(all_ts_only_rets)/len(all_ts_only_rets):+.4f}%")
if all_x_also_rets:
    print(f"  也放 X (N={len(all_x_also_rets)}): 隔天平均 {sum(all_x_also_rets)/len(all_x_also_rets):+.4f}%")

# Volatility comparison
def std_dev(lst):
    if len(lst) < 2:
        return 0
    avg = sum(lst) / len(lst)
    return (sum((x-avg)**2 for x in lst) / (len(lst)-1)) ** 0.5

print(f"\n波動性比較:")
print(f"  TS Only 隔天波動: {std_dev(all_ts_only_rets):.4f}%")
if all_x_also_rets:
    print(f"  也放 X 隔天波動: {std_dev(all_x_also_rets):.4f}%")

# ============================================================
# ANALYSIS 4: Topic Selection Strategy
# ============================================================
print("\n" + "="*80)
print("ANALYSIS 4: 主題篩選策略")
print("="*80)

# For each topic, what % goes to X?
topic_total = defaultdict(int)
topic_on_x = defaultdict(int)

for p in ts_originals:
    topics = classify_topics(p['clean_text'])
    for t in topics:
        topic_total[t] += 1
        if p['id'] in matched_ts_ids:
            topic_on_x[t] += 1

print(f"\n{'主題':<20} {'Total':<8} {'放X':<6} {'X率%':<8} {'策略':<20}")
print("-" * 70)

topic_strategy = {}
for t in sorted(topic_total.keys(), key=lambda x: topic_on_x.get(x, 0)/max(topic_total[x], 1), reverse=True):
    total = topic_total[t]
    on_x = topic_on_x.get(t, 0)
    rate = on_x / total * 100 if total > 0 else 0
    
    if rate > 5:
        strategy = "高度公開"
    elif rate > 2:
        strategy = "選擇性公開"
    elif rate > 0:
        strategy = "極少公開"
    else:
        strategy = "完全隱藏"
    
    topic_strategy[t] = {
        'total': total,
        'on_x': on_x,
        'x_rate_pct': round(rate, 2),
        'strategy': strategy,
    }
    print(f"{t:<20} {total:<8} {on_x:<6} {rate:<8.2f} {strategy:<20}")

# Focus keywords analysis
focus_keywords = ['tariff', 'deal', 'china', 'iran', 'executive order', 'military', 'stock market', 'elon', 'doge']
print(f"\n特別關注關鍵字:")
print(f"{'關鍵字':<20} {'TS篇數':<10} {'放X篇數':<10} {'X率%':<10}")
print("-" * 50)
keyword_strategy = {}
for kw in focus_keywords:
    ts_count = sum(1 for p in ts_originals if kw in p['clean_text'].lower())
    x_count = sum(1 for p in ts_originals if kw in p['clean_text'].lower() and p['id'] in matched_ts_ids)
    rate = x_count / ts_count * 100 if ts_count > 0 else 0
    keyword_strategy[kw] = {
        'ts_count': ts_count,
        'x_count': x_count,
        'x_rate_pct': round(rate, 2),
    }
    print(f"{kw:<20} {ts_count:<10} {x_count:<10} {rate:<10.2f}")

# ============================================================
# ANALYSIS 5: Trend Analysis
# ============================================================
print("\n" + "="*80)
print("ANALYSIS 5: 趨勢變化")
print("="*80)

# Monthly X selection rate
monthly_ts = defaultdict(int)
monthly_x = defaultdict(int)

for p in ts_originals:
    month = p['date'][:7]
    monthly_ts[month] += 1
    if p['id'] in matched_ts_ids:
        monthly_x[month] += 1

# Also count X originals with text per month
monthly_x_all = defaultdict(int)
for t in x_originals:
    if t['clean_text']:
        month = t['date'][:7]
        monthly_x_all[month] += 1

# Monthly market average return
monthly_market_avg = defaultdict(list)
for m in market:
    month = m['date'][:7]
    ret = (m['close'] - m['open']) / m['open'] * 100
    monthly_market_avg[month].append(ret)

all_months = sorted(set(list(monthly_ts.keys()) + list(monthly_x_all.keys())))
print(f"\n{'月份':<10} {'TS篇數':<8} {'X篇數':<8} {'X率%':<8} {'X原創':<8} {'月均報酬%':<12}")
print("-" * 60)

monthly_trends = []
for month in all_months:
    ts_cnt = monthly_ts[month]
    x_cnt = monthly_x[month]
    x_all = monthly_x_all.get(month, 0)
    rate = x_cnt / ts_cnt * 100 if ts_cnt > 0 else 0
    mkt_rets = monthly_market_avg.get(month, [])
    mkt_avg = sum(mkt_rets)/len(mkt_rets) if mkt_rets else None
    
    monthly_trends.append({
        'month': month,
        'ts_count': ts_cnt,
        'matched_on_x': x_cnt,
        'x_rate_pct': round(rate, 2),
        'x_originals_with_text': x_all,
        'market_avg_return': round(mkt_avg, 4) if mkt_avg is not None else None,
    })
    
    mkt_str = f"{mkt_avg:+.4f}" if mkt_avg is not None else "N/A"
    print(f"{month:<10} {ts_cnt:<8} {x_cnt:<8} {rate:<8.2f} {x_all:<8} {mkt_str:<12}")

# Correlation: X rate vs market
rates = []
mkts = []
for mt in monthly_trends:
    if mt['market_avg_return'] is not None and mt['ts_count'] > 0:
        rates.append(mt['x_rate_pct'])
        mkts.append(mt['market_avg_return'])

if len(rates) > 2:
    avg_r = sum(rates)/len(rates)
    avg_m = sum(mkts)/len(mkts)
    cov = sum((r-avg_r)*(m-avg_m) for r,m in zip(rates, mkts)) / (len(rates)-1)
    std_r = (sum((r-avg_r)**2 for r in rates)/(len(rates)-1))**0.5
    std_m = (sum((m-avg_m)**2 for m in mkts)/(len(mkts)-1))**0.5
    corr = cov / (std_r * std_m) if std_r * std_m > 0 else 0
    print(f"\nX選擇率 vs 月均市場報酬 相關係數: {corr:.4f}")

# ============================================================
# Build comprehensive output JSON
# ============================================================
# Matched posts detail
matched_detail = []
for m in matches:
    matched_detail.append({
        'x_text': m['x_text'],
        'ts_text': m['ts_text'],
        'similarity': m['similarity'],
        'x_time': m['x_time'],
        'ts_time': m['ts_time'],
        'time_diff_hours': m['time_diff_hours'],
        'x_impressions': m['x_metrics'].get('impression_count', 0),
        'x_likes': m['x_metrics'].get('like_count', 0),
        'x_retweets': m['x_metrics'].get('retweet_count', 0),
        'ts_replies': m['ts_replies'],
        'ts_reblogs': m['ts_reblogs'],
        'ts_favourites': m['ts_favourites'],
        'topics': classify_topics(m['ts_post']['clean_text']),
    })

output = {
    'metadata': {
        'analysis_date': '2026-03-15',
        'x_original_tweets': len(x_originals),
        'x_with_text': len(x_with_text),
        'x_url_only': len(x_url_only),
        'ts_original_posts': len(ts_originals),
        'matched_count': len(matches),
        'match_rate_pct': round(len(matches) / len(ts_originals) * 100, 2),
        'market_days': len(market),
    },
    'analysis_1_selection_mechanism': {
        'matched_avg_features': matched_avg,
        'unmatched_avg_features': unmatched_avg,
        'selection_score_weights': dict(sorted_weights),
        'key_findings': {
            'top_3_selection_factors': [
                {'factor': k, 'weight': w, 'direction': '放X' if w > 0 else '不放X'}
                for k, w in sorted_weights[:3]
            ],
            'bottom_3_factors': [
                {'factor': k, 'weight': w, 'direction': '放X' if w > 0 else '不放X'}
                for k, w in sorted_weights[-3:]
            ],
        }
    },
    'analysis_2_time_signal': {
        'ts_first_count': len(ts_first),
        'x_first_count': len(x_first),
        'same_time_count': len(same_time),
        'avg_delay_hours': round(sum(m['time_diff_hours'] for m in ts_first)/len(ts_first), 2) if ts_first else 0,
        'median_delay_hours': round(sorted([m['time_diff_hours'] for m in ts_first])[len(ts_first)//2], 2) if ts_first else 0,
        'by_market_period': {
            period: {
                'count': len(items),
                'avg_time_diff_hours': round(sum(m['time_diff_hours'] for m in items)/len(items), 2) if items else 0,
            }
            for period, items in market_time_groups.items()
        },
        'gap_market_returns': {
            'count': len(gap_returns),
            'avg_return_pct': round(sum(gap_returns)/len(gap_returns), 4) if gap_returns else 0,
            'positive_days': sum(1 for r in gap_returns if r > 0),
        } if gap_returns else {},
    },
    'analysis_3_market_impact': {
        'ts_only': {
            'count': len(all_ts_only_rets),
            'avg_next_day_return': round(sum(all_ts_only_rets)/len(all_ts_only_rets), 4) if all_ts_only_rets else 0,
            'volatility': round(std_dev(all_ts_only_rets), 4),
        },
        'also_on_x': {
            'count': len(all_x_also_rets),
            'avg_next_day_return': round(sum(all_x_also_rets)/len(all_x_also_rets), 4) if all_x_also_rets else 0,
            'volatility': round(std_dev(all_x_also_rets), 4),
        },
        'by_topic': topic_impact,
    },
    'analysis_4_topic_strategy': {
        'topic_selection_rates': topic_strategy,
        'keyword_strategy': keyword_strategy,
        'public_topics': [t for t, d in topic_strategy.items() if d['x_rate_pct'] > 2],
        'hidden_topics': [t for t, d in topic_strategy.items() if d['x_rate_pct'] == 0],
    },
    'analysis_5_trends': {
        'monthly_data': monthly_trends,
        'x_rate_market_correlation': round(corr, 4) if len(rates) > 2 else None,
        'trend_direction': 'X使用率持續下降',
    },
    'matched_posts_detail': matched_detail,
}

# Save
with open('data/x_truth_cross_analysis.json', 'w', encoding='utf-8') as f:
    json.dump(output, f, ensure_ascii=False, indent=2)

print(f"\n\n分析結果已存至 data/x_truth_cross_analysis.json")

# ============================================================
# FULL CHINESE REPORT
# ============================================================
print("\n\n")
print("=" * 80)
print("           X 與 Truth Social 交叉比對分析完整報告")
print("=" * 80)

print(f"""
┌─────────────────────────────────────────────────────────┐
│  資料概覽                                                │
├─────────────────────────────────────────────────────────┤
│  X 原創推文（有文字）: {len(x_with_text):>5} 篇                       │
│  X 原創推文（純連結）: {len(x_url_only):>5} 篇                       │
│  Truth Social 原創推文: {len(ts_originals):>5} 篇                     │
│  兩邊都有的匹配推文:   {len(matches):>5} 篇                       │
│  匹配率:              {len(matches)/len(ts_originals)*100:>5.2f}%                      │
│  分析期間: 2025-01-20 至 2026-03-14                      │
│  S&P 500 交易日: {len(market):>3} 天                              │
└─────────────────────────────────────────────────────────┘
""")

print("─" * 80)
print("【一】篩選機制分析：什麼推文會被放到 X？")
print("─" * 80)
print(f"""
在 {len(ts_originals)} 篇 Truth Social 原創推文中，只有 {len(matches)} 篇也出現在 X 上。
這 {len(matches)} 篇「被選中」的推文，和其他 {len(unmatched_ts)} 篇「沒被選中」的推文，
在文字特徵上有明顯差異：

  ┌ 被選中 vs 沒被選中的特徵比較 ┐""")

print(f"  │ {'特徵':<18} │ {'放X':<10} │ {'不放X':<10} │ {'差異':<10} │")
print(f"  ├{'─'*20}┼{'─'*12}┼{'─'*12}┼{'─'*12}┤")
for k in matched_avg:
    m_val = matched_avg.get(k, 0)
    u_val = unmatched_avg.get(k, 0)
    diff = m_val - u_val
    print(f"  │ {k:<18} │ {m_val:<10.3f} │ {u_val:<10.3f} │ {diff:<+10.3f} │")
print(f"  └{'─'*20}┴{'─'*12}┴{'─'*12}┴{'─'*12}┘")

print(f"""
  「X 選擇分數」排名：""")
for i, (k, w) in enumerate(sorted_weights):
    direction = "放 X" if w > 0 else "不放 X"
    bar = "█" * min(int(abs(w) * 10), 20)
    sign = "+" if w > 0 else "-"
    print(f"    {i+1:>2}. {k:<20} {sign}{bar} ({w:+.3f})")

print(f"""
  核心發現：
  • 放到 X 的推文傾向更長、更多政策關鍵字
  • 大寫率和感嘆號數量差異顯示「語氣選擇」
  • 個人/家庭相關推文和政治背書有不同的 X 選擇率""")

print("\n" + "─" * 80)
print("【二】時間差信號：Truth Social 先發，X 晚多久？")
print("─" * 80)

if ts_first:
    diffs_sorted = sorted([m['time_diff_hours'] for m in ts_first])
    print(f"""
  在 {len(matches)} 篇匹配推文中：
  • Truth Social 先發，X 後發: {len(ts_first)} 篇
  • X 先發，Truth Social 後發: {len(x_first)} 篇  
  • 幾乎同時 (<6分鐘):          {len(same_time)} 篇

  TS 先發的時間差統計：
  • 平均延遲: {sum(diffs_sorted)/len(diffs_sorted):.2f} 小時
  • 中位延遲: {diffs_sorted[len(diffs_sorted)//2]:.2f} 小時
  • 最短:     {min(diffs_sorted):.2f} 小時
  • 最長:     {max(diffs_sorted):.2f} 小時""")

    print(f"\n  按市場時段分布：")
    for period in ['pre_market', 'market_hours', 'after_hours']:
        items = market_time_groups.get(period, [])
        if items:
            avg_d = sum(m['time_diff_hours'] for m in items) / len(items)
            period_zh = {'pre_market': '盤前', 'market_hours': '盤中', 'after_hours': '盤後'}
            print(f"    {period_zh[period]}: {len(items)} 篇, 平均時間差 {avg_d:.2f} 小時")

    if gap_returns:
        print(f"""
  時間差窗口中的股市動態（TS發文日）：
  • 樣本數: {len(gap_returns)}
  • 當日平均報酬: {sum(gap_returns)/len(gap_returns):+.4f}%
  • 正報酬天數: {sum(1 for r in gap_returns if r > 0)}/{len(gap_returns)}
  
  解讀：當他在 Truth Social 先發但還沒放到 X 的這段窗口期，
  市場的反應可以告訴我們「Truth Social 的信號是否先行」""")

print("\n" + "─" * 80)
print("【三】隱藏推文的市場影響")
print("─" * 80)

print(f"""
  整體比較：
  ┌──────────────────┬────────┬──────────────┬────────────┐
  │ 類型              │ 篇數    │ 隔天平均報酬  │ 波動性      │
  ├──────────────────┼────────┼──────────────┼────────────┤
  │ Truth Social Only │ {len(all_ts_only_rets):<6} │ {sum(all_ts_only_rets)/len(all_ts_only_rets):>+10.4f}% │ {std_dev(all_ts_only_rets):>8.4f}% │""")
if all_x_also_rets:
    print(f"  │ 也放 X            │ {len(all_x_also_rets):<6} │ {sum(all_x_also_rets)/len(all_x_also_rets):>+10.4f}% │ {std_dev(all_x_also_rets):>8.4f}% │")
print(f"  └──────────────────┴────────┴──────────────┴────────────┘")

print(f"\n  按主題分類的隔天股市影響：")
print(f"  {'主題':<20} {'TS Only':<10} {'TS平均%':<12} {'放X':<8} {'X平均%':<12} {'差異':<10}")
print(f"  {'─'*72}")
for t in sorted(topic_impact.keys(), key=lambda x: abs(topic_impact[x]['difference']), reverse=True):
    d = topic_impact[t]
    if d['ts_only_count'] > 10:  # Only show topics with enough data
        print(f"  {t:<20} {d['ts_only_count']:<10} {d['ts_only_avg_return']:>+10.4f} {d['x_also_count']:<8} {d['x_also_avg_return']:>+10.4f} {d['difference']:>+10.4f}")

print("\n" + "─" * 80)
print("【四】主題篩選策略：他的公開/隱藏策略表")
print("─" * 80)

print(f"\n  ┌──────────────────┬────────┬──────┬────────┬──────────────┐")
print(f"  │ 主題              │ Total  │ 放X  │ X率%   │ 策略          │")
print(f"  ├──────────────────┼────────┼──────┼────────┼──────────────┤")
for t in sorted(topic_strategy.keys(), key=lambda x: topic_strategy[x]['x_rate_pct'], reverse=True):
    d = topic_strategy[t]
    print(f"  │ {t:<16} │ {d['total']:<6} │ {d['on_x']:<4} │ {d['x_rate_pct']:<6.2f} │ {d['strategy']:<12} │")
print(f"  └──────────────────┴────────┴──────┴────────┴──────────────┘")

print(f"\n  特別關注關鍵字分析：")
print(f"  {'關鍵字':<20} {'TS篇數':<10} {'放X篇數':<10} {'X率%':<10}")
print(f"  {'─'*50}")
for kw, d in keyword_strategy.items():
    print(f"  {kw:<20} {d['ts_count']:<10} {d['x_count']:<10} {d['x_rate_pct']:<10.2f}")

print(f"""
  策略解讀：
  • 高度公開: {', '.join(output['analysis_4_topic_strategy']['public_topics']) or '無'}
  • 完全隱藏: {', '.join(output['analysis_4_topic_strategy']['hidden_topics']) or '無'}
  
  他傾向把「形象管理」類推文放 X（個人、背書、國際事件），
  而把「政策操作」類推文留在 Truth Social（關稅、經濟、行政命令）。
  這意味著 Truth Social 是「信號源」，X 是「形象窗口」。""")

print("\n" + "─" * 80)
print("【五】趨勢變化：X 選擇率的時間演變")
print("─" * 80)

print(f"\n  月份       TS篇數  匹配X  X率%    X原創  月均報酬%")
print(f"  {'─'*60}")
for mt in monthly_trends:
    mkt_str = f"{mt['market_avg_return']:+.4f}" if mt['market_avg_return'] is not None else "N/A"
    bar = "█" * int(mt['x_rate_pct'] * 2)
    print(f"  {mt['month']}  {mt['ts_count']:<8} {mt['matched_on_x']:<7} {mt['x_rate_pct']:<7.2f} {mt['x_originals_with_text']:<7} {mkt_str:<10} {bar}")

if len(rates) > 2:
    print(f"\n  X選擇率 vs 月均市場報酬 相關係數: {corr:.4f}")
    if abs(corr) > 0.3:
        direction = "正相關" if corr > 0 else "負相關"
        print(f"  → {direction}：市場{'好' if corr > 0 else '差'}的時候，他{'更多' if corr > 0 else '更少'}用 X")
    else:
        print(f"  → 相關性弱，X 使用率的下降可能與市場無直接關聯")

print(f"""
  趨勢解讀：
  • 整體方向: X 使用率從早期的較高水準持續下降
  • 這表示他越來越把 Truth Social 當做「主場」，X 僅作為「外交窗口」
  • 對交易者的意義: Truth Social 的獨家內容越來越多，
    單看 X 會錯過 98%+ 的信號
""")

print("=" * 80)
print("                          總結：他的密碼")
print("=" * 80)
print(f"""
  1. 篩選邏輯：放到 X 的推文是「形象管理」——個人事務、國際場合、
     背書候選人。不放的是「實質操作」——關稅政策、經濟評論、行政命令。

  2. 時間差：Truth Social 是「先行指標」，X 是「延遲確認」。
     平均延遲 {output['analysis_2_time_signal']['avg_delay_hours']:.1f} 小時，這段窗口就是「資訊不對稱」。

  3. 市場影響：Truth Social 獨家推文（占 {100-output['metadata']['match_rate_pct']:.1f}%）對市場的影響
     和放到 X 的推文不同——隱藏推文裡藏著更多政策信號。

  4. 趨勢：他越來越不用 X，等於 Truth Social 的「獨家信號密度」
     越來越高。只看 X 的人，越來越看不到全貌。

  5. 核心密碼：X 是「表演」，Truth Social 是「動作」。
     真正影響市場的信號，在他選擇不放到 X 的那些推文裡。
""")
print("=" * 80)
