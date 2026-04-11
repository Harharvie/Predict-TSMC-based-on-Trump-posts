#!/usr/bin/env python3
"""
川普密碼 — 事件偵測器（Event Detector）

不是看一篇推文，是看連續幾天的模式。
大資金需要運作時間 → 大事前一定有醞釀。

從歷史數據發現的醞釀模式：
  1.「關稅轟炸」模式：連續 3+ 天關稅信號 ≥2 → 大跌即將到來
  2.「轟炸→RELIEF」模式：關稅轟炸後突然出現 RELIEF → 大漲反轉
  3.「爆量→沉默」模式：發文量暴增 → 突然沉默 → 大波動
  4.「升溫」模式：關稅信號逐日遞增 → 正在醞釀

數據根據：288 個交易日，8 個大事日的分析。
大事前 3 天的關稅信號 = 平常日的 2.7 倍。
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

BASE = Path(__file__).parent
DATA = BASE / "data"

NOW = datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
TODAY = datetime.now(timezone.utc).strftime('%Y-%m-%d')

EVENT_ALERTS_FILE = DATA / "event_alerts.json"


def log(msg: str) -> None:
    print(f"[事件偵測] {msg}", flush=True)


# =====================================================================
# 醞釀模式定義（從歷史數據歸納）
# =====================================================================

PATTERNS = {
    'TARIFF_BARRAGE': {
        'name': '關稅轟炸',
        'name_en': 'Tariff Barrage',
        'description': '連續 3+ 天出現 2+ 次關稅信號 → 大跌風險高',
        'check': '_check_tariff_barrage',
        'severity': 'HIGH',
        'expected_direction': 'DOWN',
        'historical_examples': ['2025-04-03 (-4.84%)', '2025-04-04 (-5.97%)', '2025-03-10 (-2.70%)'],
    },
    'BARRAGE_TO_RELIEF': {
        'name': '轟炸→寬減轉折',
        'name_en': 'Barrage → Relief Reversal',
        'description': '關稅轟炸後突然出現 RELIEF 信號 → 大漲反轉',
        'check': '_check_barrage_to_relief',
        'severity': 'HIGH',
        'expected_direction': 'UP',
        'historical_examples': ['2025-04-09 (+9.52%)'],
    },
    'VOLUME_SPIKE_SILENCE': {
        'name': '爆量→沉默',
        'name_en': 'Volume Spike → Silence',
        'description': '發文量暴增（30+篇）後突然沉默（<5 篇）→ 大波動',
        'check': '_check_volume_spike_silence',
        'severity': 'MEDIUM',
        'expected_direction': 'VOLATILE',
        'historical_examples': ['2025-03-10 (131篇→大跌)'],
    },
    'ESCALATION': {
        'name': '關稅升溫',
        'name_en': 'Tariff Escalation',
        'description': '關稅信號逐日遞增（1→2→3+）→ 正在醞釀大動作',
        'check': '_check_escalation',
        'severity': 'MEDIUM',
        'expected_direction': 'DOWN',
        'historical_examples': ['2025-04-01~03 (7→3→2 關稅信號 → 04 大跌)'],
    },
    'DEAL_SURGE': {
        'name': 'Deal 密集',
        'name_en': 'Deal Surge',
        'description': '連續 2+ 天出現 3+ 次 Deal 信號 → 可能在談判，正面',
        'check': '_check_deal_surge',
        'severity': 'MEDIUM',
        'expected_direction': 'UP',
        'historical_examples': ['2025-05-08~12 (Deal 5→2→3 → +3.26%)'],
    },
}


# =====================================================================
# 模式偵測函數
# =====================================================================

def _get_recent_signals(days: int = 5) -> list[dict]:
    """取得最近 N 天的信號摘要。"""
    predictions_file = DATA / "predictions_log.json"
    if not predictions_file.exists():
        return []

    with open(predictions_file, encoding='utf-8') as f:
        predictions = json.load(f)

    # 按日期分組取最新
    by_date: dict[str, dict] = {}
    for p in predictions:
        date = p.get('date_signal', '')
        if date and date not in by_date:
            by_date[date] = p.get('day_summary', {})
            by_date[date]['date'] = date

    sorted_dates = sorted(by_date.keys(), reverse=True)
    return [by_date[d] for d in sorted_dates[:days]]


def _check_tariff_barrage(recent: list[dict]) -> dict | None:
    """連續 3+ 天出現 2+ 次關稅信號。"""
    if len(recent) < 3:
        return None

    # 最近 5 天中，有多少天關稅 ≥ 2
    tariff_days = 0
    consecutive = 0
    max_consecutive = 0

    for day in recent[:5]:
        tariff = day.get('tariff', 0)
        if tariff >= 2:
            tariff_days += 1
            consecutive += 1
            max_consecutive = max(max_consecutive, consecutive)
        else:
            consecutive = 0

    if max_consecutive >= 3:
        total_tariff = sum(d.get('tariff', 0) for d in recent[:5])
        return {
            'consecutive_days': max_consecutive,
            'total_tariff_signals': total_tariff,
            'confidence': min(0.95, 0.6 + 0.1 * (max_consecutive - 3)),
            'detail': f"連續 {max_consecutive} 天關稅信號 ≥2，總計 {total_tariff} 次",
        }
    return None


def _check_barrage_to_relief(recent: list[dict]) -> dict | None:
    """關稅轟炸後出現 RELIEF。"""
    if len(recent) < 2:
        return None

    today = recent[0]
    prev_days = recent[1:5]

    # 今天有 RELIEF
    if today.get('relief', 0) == 0:
        return None

    # 前面有關稅轟炸
    tariff_before = sum(d.get('tariff', 0) for d in prev_days)
    tariff_days = sum(1 for d in prev_days if d.get('tariff', 0) >= 2)

    if tariff_days >= 2 and tariff_before >= 4:
        return {
            'relief_today': today.get('relief', 0),
            'tariff_before': tariff_before,
            'tariff_days': tariff_days,
            'confidence': min(0.95, 0.7 + 0.05 * tariff_before),
            'detail': f"前 {tariff_days} 天共 {tariff_before} 次關稅信號，今天出現 RELIEF {today['relief']} 次 → 轉折！",
        }
    return None


def _check_volume_spike_silence(recent: list[dict]) -> dict | None:
    """發文量暴增後沉默。"""
    if len(recent) < 3:
        return None

    today = recent[0]
    yesterday = recent[1]

    # 今天沉默（<5 篇）
    if today.get('post_count', 10) >= 8:
        return None

    # 前 1-3 天有爆量（≥30 篇）
    spike_day = None
    for d in recent[1:4]:
        if d.get('post_count', 0) >= 30:
            spike_day = d
            break

    if spike_day:
        return {
            'spike_posts': spike_day.get('post_count', 0),
            'spike_date': spike_day.get('date', '?'),
            'today_posts': today.get('post_count', 0),
            'confidence': 0.65,
            'detail': f"{spike_day.get('date','?')} 發了 {spike_day['post_count']} 篇，今天只有 {today['post_count']} 篇 → 沉默前的暴風雨？",
        }
    return None


def _check_escalation(recent: list[dict]) -> dict | None:
    """關稅信號逐日遞增。"""
    if len(recent) < 3:
        return None

    # 倒過來看（從舊到新）
    last_3 = list(reversed(recent[:3]))
    tariffs = [d.get('tariff', 0) for d in last_3]

    # 遞增
    if tariffs[0] >= 1 and tariffs[1] > tariffs[0] and tariffs[2] > tariffs[1]:
        return {
            'tariff_sequence': tariffs,
            'confidence': 0.60,
            'detail': f"關稅信號 {tariffs[0]}→{tariffs[1]}→{tariffs[2]}，持續升溫中",
        }
    return None


def _check_deal_surge(recent: list[dict]) -> dict | None:
    """Deal 信號密集。"""
    if len(recent) < 2:
        return None

    deal_days = sum(1 for d in recent[:3] if d.get('deal', 0) >= 2)
    total_deal = sum(d.get('deal', 0) for d in recent[:3])

    if deal_days >= 2 and total_deal >= 5:
        return {
            'deal_days': deal_days,
            'total_deal': total_deal,
            'confidence': 0.60,
            'detail': f"最近 3 天有 {deal_days} 天 Deal ≥2，總計 {total_deal} 次 → 正在談判",
        }
    return None


# =====================================================================
# 主偵測
# =====================================================================

CHECKERS = {
    'TARIFF_BARRAGE': _check_tariff_barrage,
    'BARRAGE_TO_RELIEF': _check_barrage_to_relief,
    'VOLUME_SPIKE_SILENCE': _check_volume_spike_silence,
    'ESCALATION': _check_escalation,
    'DEAL_SURGE': _check_deal_surge,
}


def detect_events() -> list[dict]:
    """
    掃描最近 5 天的信號，偵測醞釀中的事件模式。
    回傳觸發的警報列表。
    """
    log(f"掃描最近 5 天的信號模式...")
    recent = _get_recent_signals(days=5)

    if len(recent) < 2:
        log("   數據不足（需要至少 2 天）")
        return []

    log(f"   最近 {len(recent)} 天的信號:")
    for d in recent:
        tariff = d.get('tariff', 0)
        deal = d.get('deal', 0)
        relief = d.get('relief', 0)
        posts = d.get('post_count', 0)
        log(f"   {d.get('date', '?')}: {posts} 篇 | T={tariff} D={deal} R={relief}")

    alerts = []
    for pattern_id, checker in CHECKERS.items():
        result = checker(recent)
        if result:
            pattern = PATTERNS[pattern_id]
            alert = {
                'pattern': pattern_id,
                'name': pattern['name'],
                'name_en': pattern['name_en'],
                'severity': pattern['severity'],
                'expected_direction': pattern['expected_direction'],
                'confidence': result['confidence'],
                'detail': result['detail'],
                'detected_at': NOW,
                'historical': pattern['historical_examples'],
            }
            alerts.append(alert)

            icon = '🔴' if pattern['severity'] == 'HIGH' else '🟡'
            dir_icon = {'UP': '📈', 'DOWN': '📉', 'VOLATILE': '⚡'}.get(pattern['expected_direction'], '?')
            log(f"\n   {icon} {pattern['name']} ({pattern['name_en']})")
            log(f"      {dir_icon} 預期: {pattern['expected_direction']} | 信心: {result['confidence']:.0%}")
            log(f"      {result['detail']}")
            log(f"      歷史案例: {', '.join(pattern['historical_examples'])}")

    # 存檔
    all_alerts: list[dict] = []
    if EVENT_ALERTS_FILE.exists():
        with open(EVENT_ALERTS_FILE, encoding='utf-8') as f:
            all_alerts = json.load(f)

    all_alerts.extend(alerts)
    all_alerts = all_alerts[-100:]  # 保留最近 100 條

    with open(EVENT_ALERTS_FILE, 'w', encoding='utf-8') as f:
        json.dump(all_alerts, f, ensure_ascii=False, indent=2)

    if not alerts:
        log("   ✅ 目前沒有偵測到醞釀中的事件模式")
    else:
        log(f"\n   ⚠️ 偵測到 {len(alerts)} 個醞釀模式！")

    return alerts


if __name__ == '__main__':
    alerts = detect_events()
    if alerts:
        print(json.dumps(alerts, ensure_ascii=False, indent=2))
