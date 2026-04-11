#!/usr/bin/env python3
"""
川普密碼 — 共用工具模組
統一時區轉換、關鍵字匹配、情緒分數等核心函數
"""

import json
import os
import re
import tempfile
from datetime import datetime, timezone, timedelta
from functools import lru_cache
from pathlib import Path
from zoneinfo import ZoneInfo

# 美東時區（自動處理 EST/EDT 夏令時間）
ET = ZoneInfo("America/New_York")


# ============================================================
# 時區轉換（修正 DST bug）
# ============================================================

def to_eastern(utc_str: str) -> datetime:
    """UTC 字串轉美東時間（自動處理 EST/EDT）"""
    dt = datetime.fromisoformat(utc_str.replace('Z', '+00:00'))
    return dt.astimezone(ET)


def est_hour(utc_str: str) -> tuple:
    """回傳美東 (hour, minute)，自動處理夏令時"""
    et = to_eastern(utc_str)
    return et.hour, et.minute


def market_session(utc_str: str) -> str:
    """判斷美股交易時段"""
    h, m = est_hour(utc_str)
    if h < 4:
        return 'OVERNIGHT'
    elif h < 9 or (h == 9 and m < 30):
        return 'PRE_MARKET'
    elif h < 16:
        return 'MARKET_OPEN'
    elif h < 20:
        return 'AFTER_HOURS'
    else:
        return 'OVERNIGHT'


# ============================================================
# 關鍵字匹配（字詞邊界，避免子字串誤判）
# ============================================================

@lru_cache(maxsize=256)
def _make_pattern(words: tuple) -> re.Pattern:
    """編譯字詞邊界正規表達式（快取）"""
    escaped = [re.escape(w) for w in words]
    return re.compile(r'\b(?:' + '|'.join(escaped) + r')\b', re.IGNORECASE)


def count_keywords(text: str, keywords: list) -> int:
    """用字詞邊界匹配計算關鍵字出現次數"""
    pattern = _make_pattern(tuple(keywords))
    return len(pattern.findall(text))


def has_keywords(text: str, keywords: list) -> bool:
    """文本中是否包含任一關鍵字（字詞邊界匹配）"""
    pattern = _make_pattern(tuple(keywords))
    return bool(pattern.search(text))


# ============================================================
# 情緒分數（統一版本）
# ============================================================

STRONG_WORDS = frozenset([
    'never', 'always', 'worst', 'best', 'greatest', 'terrible',
    'incredible', 'tremendous', 'massive', 'total', 'complete',
    'absolute', 'disaster', 'perfect', 'beautiful', 'horrible',
    'amazing', 'fantastic', 'disgrace', 'pathetic', 'historic',
    'unprecedented', 'radical', 'corrupt', 'crooked', 'fake'
])


def emotion_score(content: str) -> float:
    """計算單篇貼文的情緒強度 (0-100)"""
    score = 0.0
    text = content

    # 大寫字比例（最高 30 分）
    upper = sum(1 for c in text if c.isupper())
    alpha = sum(1 for c in text if c.isalpha())
    caps_ratio = upper / max(alpha, 1)
    score += caps_ratio * 30

    # 驚嘆號密度（最高 25 分）
    excl = text.count('!')
    excl_density = excl / max(len(text), 1) * 100
    score += min(excl_density * 10, 25)

    # 強烈詞彙 — 使用字詞邊界匹配（最高 25 分）
    word_count = len(re.findall(r'\b\w+\b', text.lower()))
    strong_count = count_keywords(text, list(STRONG_WORDS))
    score += min(strong_count / max(word_count, 1) * 500, 25)

    # 全大寫連續詞（最高 20 分）
    caps_words = len(re.findall(r'\b[A-Z]{3,}\b', text))
    score += min(caps_words * 2, 20)

    return min(round(score, 1), 100)


# ============================================================
# 下一個交易日
# ============================================================

def safe_json_write(path, data) -> None:
    """原子寫入 JSON — 先寫暫存檔再 os.replace，中斷不損壞原檔"""
    path = Path(path)
    tmp_fd, tmp_path = tempfile.mkstemp(dir=path.parent, suffix='.tmp')
    try:
        with os.fdopen(tmp_fd, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        os.replace(tmp_path, path)
    except Exception:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
        raise


def next_trading_day(date_str: str, market_data: dict, max_days: int = 10) -> str:
    """找 date_str 之後的下一個交易日，最多往後找 max_days 天"""
    d = datetime.strptime(date_str, '%Y-%m-%d')
    for i in range(1, max_days + 1):
        candidate = (d + timedelta(days=i)).strftime('%Y-%m-%d')
        if candidate in market_data:
            return candidate
    return None
