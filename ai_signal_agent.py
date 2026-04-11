#!/usr/bin/env python3
"""
川普密碼 — AI 信號 Agent

用本機的 Claude Opus（Claude Code）當大腦，不走 API、不花額外的錢。

運作方式：
  1. 管線跑完 → 呼叫 prepare_briefing() → 產出「簡報包」
  2. Claude Code（Opus）讀簡報包 → 直接分析 → 寫回結果
  3. 下一輪管線讀結果 → 調整規則和信號

兩種觸發方式：
  A. 自動：管線產出簡報 → `claude -p "$(cat data/opus_briefing.txt)"` → 寫回
  B. 手動：tkman 對 Claude Code 說「幫我看一下川普密碼」→ 我讀簡報包分析

沒有 Claude Code 在線時：
  → 簡報包存著等，下次開 Claude Code 時補算
  → 關鍵字引擎照跑不受影響（graceful degradation）
"""

from __future__ import annotations

import json
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

BASE = Path(__file__).parent
DATA = BASE / "data"
TODAY = datetime.now(timezone.utc).strftime('%Y-%m-%d')
NOW = datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')

# 檔案路徑
BRIEFING_FILE = DATA / "opus_briefing.txt"       # 給 Opus 看的人話簡報
BRIEFING_JSON = DATA / "opus_briefing.json"      # 結構化版本
AI_RESULT_FILE = DATA / "opus_analysis.json"     # Opus 寫回的分析結果
AI_SIGNALS_FILE = DATA / "ai_signals.json"       # AI 分類的信號
PENDING_FILE = DATA / "opus_pending.json"        # 還沒被 Opus 處理的簡報


def log(msg: str) -> None:
    print(f"[AI Agent] {msg}", flush=True)


# =====================================================================
# ① 準備簡報包（管線呼叫）
# =====================================================================

def prepare_briefing(
    today_posts: list[dict] | None = None,
    today_features: dict | None = None,
    keyword_signals: list[str] | None = None,
    triggered_rules: list[dict] | None = None,
) -> dict[str, Any]:
    """
    收集所有框架數據，產出一份完整的「簡報包」給 Opus。

    這個函數被 daily_pipeline 在最後呼叫。
    產出的簡報存成兩種格式：
      - opus_briefing.txt（人話版，Opus 直接讀）
      - opus_briefing.json（結構化版，程式讀）
    """
    log("準備 Opus 簡報包...")

    briefing: dict[str, Any] = {
        'date': TODAY,
        'prepared_at': NOW,
        'status': 'PENDING',  # Opus 處理完改成 DONE
    }

    # --- 今日推文摘要 ---
    if today_posts:
        briefing['today_posts'] = {
            'count': len(today_posts),
            'latest': today_posts[-1]['content'][:200] if today_posts else '',
            'earliest_time': today_posts[0]['created_at'] if today_posts else '',
            'latest_time': today_posts[-1]['created_at'] if today_posts else '',
            'sample': [
                {'time': p['created_at'][11:16], 'text': p['content'][:300]}
                for p in today_posts[-10:]  # 最新 10 篇完整給 Opus 看
            ],
        }

    # --- 關鍵字信號 ---
    if keyword_signals:
        briefing['keyword_signals'] = keyword_signals

    # --- 今日特徵 ---
    if today_features:
        briefing['today_features'] = today_features

    # --- 觸發的規則 ---
    if triggered_rules:
        briefing['triggered_rules'] = {
            'total': len(triggered_rules),
            'long': sum(1 for r in triggered_rules if r.get('direction') == 'LONG'),
            'short': sum(1 for r in triggered_rules if r.get('direction') == 'SHORT'),
            'sample': triggered_rules[:10],
        }

    # --- 模型績效（從 predictions_log）---
    predictions_file = DATA / "predictions_log.json"
    if predictions_file.exists():
        with open(predictions_file, encoding='utf-8') as f:
            predictions = json.load(f)

        verified = [p for p in predictions if p.get('status') == 'VERIFIED']
        model_stats = defaultdict(lambda: {'correct': 0, 'wrong': 0, 'total': 0, 'returns': []})
        for p in verified:
            mid = p.get('model_id', '?')
            model_stats[mid]['total'] += 1
            model_stats[mid]['returns'].append(p.get('actual_return', 0))
            if p.get('correct'):
                model_stats[mid]['correct'] += 1
            else:
                model_stats[mid]['wrong'] += 1

        briefing['model_performance'] = {
            mid: {
                'name': _get_model_name(mid, predictions),
                'win_rate': round(s['correct'] / s['total'] * 100, 1) if s['total'] > 0 else 0,
                'avg_return': round(sum(s['returns']) / len(s['returns']), 3) if s['returns'] else 0,
                'total_trades': s['total'],
            }
            for mid, s in sorted(model_stats.items())
        }

        # 最近 5 筆錯誤
        recent_wrong = [p for p in verified if not p.get('correct')][-5:]
        briefing['recent_wrong'] = [
            {
                'model': p.get('model_id', '?'),
                'date': p.get('date_signal', '?'),
                'direction': p.get('direction', '?'),
                'actual_return': p.get('actual_return', 0),
            }
            for p in recent_wrong
        ]

    # --- 學習引擎狀態 ---
    learning_file = DATA / "learning_report.json"
    if learning_file.exists():
        with open(learning_file, encoding='utf-8') as f:
            lr = json.load(f)
        briefing['learning_summary'] = lr.get('adjustments', {}).get('summary', {})

    # --- 進化引擎狀態 ---
    evo_file = DATA / "evolution_log.json"
    if evo_file.exists():
        with open(evo_file, encoding='utf-8') as f:
            el = json.load(f)
        if el:
            briefing['evolution_latest'] = el[-1]

    # --- 信號信心度 ---
    sc_file = DATA / "signal_confidence.json"
    if sc_file.exists():
        with open(sc_file, encoding='utf-8') as f:
            briefing['signal_confidence'] = json.load(f)

    # --- 預測市場 ---
    pm_file = DATA / "prediction_market_scan.json"
    if pm_file.exists():
        with open(pm_file, encoding='utf-8') as f:
            briefing['prediction_market'] = json.load(f)

    # === 存檔 ===

    # JSON 版
    with open(BRIEFING_JSON, 'w', encoding='utf-8') as f:
        json.dump(briefing, f, ensure_ascii=False, indent=2)

    # 人話版（給 Opus 直接讀的 prompt）
    human_text = _format_human_briefing(briefing)
    with open(BRIEFING_FILE, 'w', encoding='utf-8') as f:
        f.write(human_text)

    # 加入待處理清單
    pending: list[dict] = []
    if PENDING_FILE.exists():
        with open(PENDING_FILE, encoding='utf-8') as f:
            pending = json.load(f)

    pending.append({
        'date': TODAY,
        'prepared_at': NOW,
        'status': 'PENDING',
    })
    with open(PENDING_FILE, 'w', encoding='utf-8') as f:
        json.dump(pending, f, ensure_ascii=False, indent=2)

    log(f"✅ 簡報包準備完成 → {BRIEFING_FILE.name}")
    log(f"   等 Opus 上線分析（手動或 claude -p）")

    return briefing


def _get_model_name(model_id: str, predictions: list[dict]) -> str:
    """從 predictions 中找到模型的中文名。"""
    for p in predictions:
        if p.get('model_id') == model_id and p.get('model_name'):
            return p['model_name']
    return model_id


def _format_human_briefing(b: dict) -> str:
    """把結構化簡報轉成 Opus 看得舒服的人話格式。"""
    lines = []
    lines.append(f"# 川普密碼 Opus 簡報 — {b.get('date', TODAY)}")
    lines.append(f"準備時間: {b.get('prepared_at', NOW)}")
    lines.append("")

    # 今日推文
    posts = b.get('today_posts', {})
    if posts:
        lines.append(f"## 今日推文: {posts.get('count', 0)} 篇")
        lines.append(f"時間: {posts.get('earliest_time', '?')} ~ {posts.get('latest_time', '?')}")
        lines.append("")
        for p in posts.get('sample', []):
            lines.append(f"[{p.get('time', '?')}] {p.get('text', '')}")
            lines.append("")

    # 關鍵字信號
    kw = b.get('keyword_signals', [])
    if kw:
        lines.append(f"## 關鍵字偵測到的信號: {', '.join(kw)}")
        lines.append("")

    # 模型績效
    perf = b.get('model_performance', {})
    if perf:
        lines.append("## 模型績效排行")
        for mid, s in sorted(perf.items(), key=lambda x: -x[1].get('win_rate', 0)):
            lines.append(f"  {mid} ({s.get('name', '?')}): "
                         f"{s.get('win_rate', 0):.1f}% | "
                         f"報酬 {s.get('avg_return', 0):+.3f}% | "
                         f"{s.get('total_trades', 0)} 筆")
        lines.append("")

    # 最近錯誤
    wrong = b.get('recent_wrong', [])
    if wrong:
        lines.append("## 最近的錯誤預測（請分析原因）")
        for w in wrong:
            lines.append(f"  {w.get('model', '?')} | {w.get('date', '?')} | "
                         f"{w.get('direction', '?')} → 實際 {w.get('actual_return', 0):+.3f}%")
        lines.append("")

    # 學習和進化
    ls = b.get('learning_summary', {})
    if ls:
        lines.append(f"## 學習引擎上次動作: {ls.get('promoted', 0)} 升級 / "
                     f"{ls.get('demoted', 0)} 降級 / {ls.get('eliminated', 0)} 淘汰")
        lines.append("")

    ev = b.get('evolution_latest', {})
    if ev:
        lines.append(f"## 規則進化: 新增 {ev.get('total_new', 0)} 條規則")
        lines.append("")

    # 信號信心度
    sc = b.get('signal_confidence', {})
    if sc:
        lines.append("## 信號信心度")
        for sig, conf in sorted(sc.items()):
            lines.append(f"  {sig}: {conf}")
        lines.append("")

    # 指令
    lines.append("## 請 Opus 回答以下問題（JSON 格式寫入 data/opus_analysis.json）")
    lines.append("")
    lines.append("1. 今天的推文，你看到什麼關鍵字引擎漏掉的信號？")
    lines.append("2. 最近的錯誤預測，根本原因是什麼？")
    lines.append("3. Trump 的溝通模式最近有沒有變化？")
    lines.append("4. 你建議新增什麼規則？（具體到特徵組合+方向+持有天數）")
    lines.append("5. 哪些模型該淘汰？哪些該加權？")
    lines.append("6. 信號信心度要怎麼調？")
    lines.append("7. 整體系統健康度？下一步最重要的事是什麼？")

    return '\n'.join(lines)


# =====================================================================
# ② Opus 分析結果寫回（Opus 呼叫）
# =====================================================================

def save_analysis(analysis: dict[str, Any]) -> None:
    """
    Opus 分析完後，把結果寫回 data/opus_analysis.json。
    這個函數由 Opus（Claude Code）在分析完後呼叫。
    """
    analysis['analyzed_at'] = NOW
    analysis['analyzed_by'] = 'claude-opus-local'

    with open(AI_RESULT_FILE, 'w', encoding='utf-8') as f:
        json.dump(analysis, f, ensure_ascii=False, indent=2)

    # 更新 pending 狀態
    if PENDING_FILE.exists():
        with open(PENDING_FILE, encoding='utf-8') as f:
            pending = json.load(f)
        for p in pending:
            if p.get('status') == 'PENDING':
                p['status'] = 'DONE'
                p['analyzed_at'] = NOW
        with open(PENDING_FILE, 'w', encoding='utf-8') as f:
            json.dump(pending, f, ensure_ascii=False, indent=2)

    log(f"✅ Opus 分析結果已寫入 {AI_RESULT_FILE.name}")


# =====================================================================
# ③ 讀取 Opus 分析結果（學習引擎呼叫）
# =====================================================================

def get_opus_insights() -> dict[str, Any] | None:
    """
    讀取 Opus 最新的分析結果。
    學習引擎呼叫這個函數，把 Opus 的建議納入調整。
    """
    if not AI_RESULT_FILE.exists():
        return None

    with open(AI_RESULT_FILE, encoding='utf-8') as f:
        result = json.load(f)

    # 只用今天或昨天的分析（太舊就不用了）
    analyzed_date = result.get('analyzed_at', '')[:10]
    if analyzed_date < TODAY:
        # 超過一天的分析只參考不決策
        result['stale'] = True

    return result


# =====================================================================
# ④ 有多少簡報還沒被處理？
# =====================================================================

def pending_count() -> int:
    """回傳還沒被 Opus 處理的簡報數量。"""
    if not PENDING_FILE.exists():
        return 0
    with open(PENDING_FILE, encoding='utf-8') as f:
        pending = json.load(f)
    return sum(1 for p in pending if p.get('status') == 'PENDING')


# =====================================================================
# CLI
# =====================================================================

if __name__ == '__main__':
    import sys

    if len(sys.argv) < 2:
        print("川普密碼 AI Agent")
        print("=" * 50)
        print(f"待處理簡報: {pending_count()} 份")
        print()
        print("用法:")
        print("  python3 ai_signal_agent.py briefing   — 產出 Opus 簡報包")
        print("  python3 ai_signal_agent.py status     — 查看待處理狀態")
        print("  python3 ai_signal_agent.py read       — 印出最新簡報（給 Opus 看）")
        print()
        print("在 Claude Code 裡:")
        print('  讓 Opus 讀簡報 → Read /tmp/trump-code/data/opus_briefing.txt')
        print('  分析完後 → 呼叫 save_analysis({...}) 寫回結果')
        sys.exit(0)

    cmd = sys.argv[1]

    if cmd == 'briefing':
        prepare_briefing()

    elif cmd == 'status':
        n = pending_count()
        print(f"待處理: {n} 份簡報")
        if BRIEFING_FILE.exists():
            import os
            mtime = os.path.getmtime(BRIEFING_FILE)
            dt = datetime.fromtimestamp(mtime, tz=timezone.utc)
            print(f"最新簡報: {dt.strftime('%Y-%m-%d %H:%M')} UTC")
        if AI_RESULT_FILE.exists():
            with open(AI_RESULT_FILE, encoding='utf-8') as f:
                result = json.load(f)
            print(f"最新分析: {result.get('analyzed_at', '?')}")

    elif cmd == 'read':
        if BRIEFING_FILE.exists():
            with open(BRIEFING_FILE, encoding='utf-8') as f:
                print(f.read())
        else:
            print("還沒有簡報包。先跑 `python3 ai_signal_agent.py briefing`")

    else:
        print(f"未知指令: {cmd}")
