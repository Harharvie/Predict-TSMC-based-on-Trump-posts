#!/usr/bin/env python3
"""
川普密碼 — Kalshi API 客戶端

Kalshi = 美國 CFTC 監管的預測市場，第二大。
公開端點不需要 API key 就能讀市場數據和價格。

端點：
  GET /markets           搜尋/列出市場
  GET /market/{ticker}   單一市場詳情
  GET /market/{ticker}/orderbook   訂單簿（即時價格）
  GET /market/{ticker}/candlesticks  K線（歷史價格）
  GET /events            列出事件
  GET /events/{ticker}   單一事件
  GET /trades            所有交易紀錄

用法：
  from kalshi_client import fetch_trump_markets, get_market_price
  markets = fetch_trump_markets()
  price = get_market_price("TRUMPTARIFF-26MAR31-T60")
"""

from __future__ import annotations

import json
import time
import urllib.request
import urllib.error
import urllib.parse
from typing import Any

# === 設定 ===

BASE_URL = "https://api.elections.kalshi.com/trade-api/v2"
DEFAULT_TIMEOUT = 15
MAX_RETRIES = 3
RETRY_DELAY = 1.0
USER_AGENT = "TrumpCode-KalshiClient/1.0"


class KalshiAPIError(Exception):
    """Kalshi API 呼叫失敗。"""
    def __init__(self, message: str, status_code: int | None = None, url: str = ""):
        self.status_code = status_code
        self.url = url
        super().__init__(message)


def _request(
    path: str,
    params: dict[str, str] | None = None,
    timeout: int = DEFAULT_TIMEOUT,
) -> dict[str, Any]:
    """
    發送 GET 請求到 Kalshi API，附帶重試。
    公開端點不需要認證。
    """
    url = f"{BASE_URL}{path}"
    if params:
        url += '?' + urllib.parse.urlencode(params)

    headers = {
        "User-Agent": USER_AGENT,
        "Accept": "application/json",
    }
    req = urllib.request.Request(url, headers=headers, method="GET")
    last_error: Exception | None = None

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                raw = resp.read().decode('utf-8')
                parsed = json.loads(raw)
                if isinstance(parsed, list):
                    return {"data": parsed}
                return parsed

        except urllib.error.HTTPError as e:
            last_error = KalshiAPIError(
                f"HTTP {e.code}: {e.reason}", status_code=e.code, url=url
            )
            if 400 <= e.code < 500 and e.code != 429:
                raise last_error
        except urllib.error.URLError as e:
            last_error = KalshiAPIError(f"連線失敗: {e.reason}", url=url)
        except json.JSONDecodeError as e:
            last_error = KalshiAPIError(f"JSON 解析失敗: {e}", url=url)
        except TimeoutError:
            last_error = KalshiAPIError(f"逾時（{timeout}s）", url=url)

        if attempt < MAX_RETRIES:
            time.sleep(RETRY_DELAY * (2 ** (attempt - 1)))

    raise last_error  # type: ignore


# =====================================================================
# 市場查詢
# =====================================================================

def get_markets(
    status: str = "open",
    limit: int = 50,
    cursor: str | None = None,
) -> dict[str, Any]:
    """
    列出所有市場。

    Args:
        status: "open" / "closed" / "settled"
        limit: 每頁數量（最大 200）
        cursor: 分頁游標
    """
    params: dict[str, str] = {
        "status": status,
        "limit": str(min(limit, 200)),
    }
    if cursor:
        params["cursor"] = cursor
    return _request("/markets", params)


def get_market(ticker: str) -> dict[str, Any]:
    """取得單一市場詳情。"""
    return _request(f"/markets/{urllib.parse.quote(ticker)}")


def get_events(limit: int = 50) -> dict[str, Any]:
    """列出所有事件（每個事件下可能有多個市場）。"""
    return _request("/events", {"limit": str(min(limit, 200))})


def get_event(ticker: str) -> dict[str, Any]:
    """取得單一事件詳情。"""
    return _request(f"/events/{urllib.parse.quote(ticker)}")


# =====================================================================
# 價格查詢
# =====================================================================

def get_orderbook(ticker: str) -> dict[str, Any]:
    """
    取得市場的訂單簿（即時 bid/ask 價格）。

    回傳結構包含 yes 和 no 兩邊的掛單。
    價格是 0-100 美分（= 0%-100% 機率）。
    """
    return _request(f"/markets/{urllib.parse.quote(ticker)}/orderbook")


def get_market_price(ticker: str) -> dict[str, Any]:
    """
    取得市場的即時價格（從訂單簿推算）。

    回傳：
    {
        "ticker": str,
        "yes_price": float (0-1),   # Yes 方的最佳買價
        "no_price": float (0-1),    # No 方的最佳買價
        "spread": float,            # 價差
        "midpoint": float,          # 中間價 = 市場隱含機率
    }
    """
    try:
        book = get_orderbook(ticker)
    except KalshiAPIError:
        # 訂單簿可能為空，fallback 到市場詳情
        market = get_market(ticker)
        m = market.get('market', market)
        last = m.get('last_price', 50)  # Kalshi 用美分
        return {
            'ticker': ticker,
            'yes_price': last / 100,
            'no_price': (100 - last) / 100,
            'spread': None,
            'midpoint': last / 100,
            'source': 'last_price',
        }

    # 從訂單簿提取最佳價格
    yes_bids = book.get('orderbook', {}).get('yes', [])
    no_bids = book.get('orderbook', {}).get('no', [])

    yes_best = yes_bids[0][0] / 100 if yes_bids else 0.5  # [price_cents, quantity]
    no_best = no_bids[0][0] / 100 if no_bids else 0.5

    midpoint = (yes_best + (1 - no_best)) / 2

    return {
        'ticker': ticker,
        'yes_price': yes_best,
        'no_price': no_best,
        'spread': abs(yes_best - (1 - no_best)),
        'midpoint': round(midpoint, 4),
        'source': 'orderbook',
    }


def get_candlesticks(
    ticker: str,
    period: str = "1d",
) -> dict[str, Any]:
    """
    取得市場的 K 線（歷史價格）。

    Args:
        ticker: 市場 ticker
        period: "1m" / "1h" / "1d"
    """
    params = {"period_interval": _map_period(period)}
    return _request(f"/markets/{urllib.parse.quote(ticker)}/candlesticks", params)


def _map_period(p: str) -> str:
    """把簡寫轉成 Kalshi 的格式。"""
    mapping = {"1m": "1", "1h": "60", "1d": "1440"}
    return mapping.get(p, "1440")


# =====================================================================
# Trump 相關市場搜尋
# =====================================================================

TRUMP_KEYWORDS = [
    'trump', 'tariff', 'trade', 'executive order', 'president',
    'gop', 'republican', 'immigration', 'border',
]


def fetch_trump_markets(limit: int = 100) -> list[dict]:
    """
    搜尋所有 Trump 相關的 Kalshi 市場。

    Kalshi 沒有關鍵字搜尋 API，所以：
    1. 拉所有 open 市場
    2. 用關鍵字過濾 title/subtitle

    Args:
        limit: 拉幾個市場來掃（越多越全但越慢）

    Returns:
        Trump 相關市場列表。
    """
    all_markets: list[dict] = []
    cursor = None

    # 分頁拉取
    for _ in range(3):  # 最多拉 3 頁
        result = get_markets(status="open", limit=min(limit, 200), cursor=cursor)
        markets = result.get('markets', [])
        all_markets.extend(markets)

        cursor = result.get('cursor')
        if not cursor or len(markets) < 100:
            break

    # 過濾 Trump 相關
    trump_markets = []
    for m in all_markets:
        title = (m.get('title', '') + ' ' + m.get('subtitle', '')).lower()
        if any(kw in title for kw in TRUMP_KEYWORDS):
            trump_markets.append(m)

    return trump_markets


# =====================================================================
# 跨平台套利偵測（Polymarket vs Kalshi）
# =====================================================================

def find_cross_platform_arb(
    poly_markets: list[dict],
    kalshi_markets: list[dict],
    threshold: float = 0.05,
) -> list[dict]:
    """
    找 Polymarket vs Kalshi 同一事件的價差套利機會。

    Args:
        poly_markets: Polymarket 市場列表（含 question, price）
        kalshi_markets: Kalshi 市場列表（含 title, last_price）
        threshold: 價差超過多少才算套利機會（預設 5%）

    Returns:
        套利機會列表。
    """
    opportunities = []

    # 對每個 Kalshi 市場，找 Polymarket 中的相似市場
    for km in kalshi_markets:
        k_title = km.get('title', '').lower()
        k_price = km.get('last_price', 50) / 100  # Kalshi 用美分

        for pm in poly_markets:
            p_question = pm.get('question', '').lower()

            # 簡單文字匹配（同一個事件）
            # 算共有的關鍵字數量
            k_words = set(k_title.split())
            p_words = set(p_question.split())
            common = k_words & p_words - {'the', 'a', 'an', 'will', 'by', 'in', 'on', 'of', 'to', 'be'}

            if len(common) < 3:
                continue  # 共同字太少，可能不是同一個事件

            p_price = float(pm.get('outcomePrices', '["0.5"]')[0]) if isinstance(pm.get('outcomePrices'), str) else 0.5

            # 計算價差
            spread = abs(p_price - k_price)
            if spread >= threshold:
                opportunities.append({
                    'kalshi_title': km.get('title', '?'),
                    'kalshi_ticker': km.get('ticker', '?'),
                    'kalshi_price': round(k_price, 3),
                    'polymarket_question': pm.get('question', '?'),
                    'polymarket_price': round(p_price, 3),
                    'spread': round(spread, 3),
                    'spread_pct': round(spread * 100, 1),
                    'arb_direction': 'buy_kalshi_sell_poly' if k_price < p_price else 'buy_poly_sell_kalshi',
                    'common_words': sorted(common),
                })

    opportunities.sort(key=lambda x: x['spread'], reverse=True)
    return opportunities


# =====================================================================
# Demo
# =====================================================================

if __name__ == '__main__':
    print("=== Kalshi 川普市場查詢 Demo ===\n")

    # 1. 搜尋 Trump 相關市場
    print("[1] 搜尋 Trump 相關市場...")
    try:
        markets = fetch_trump_markets(limit=200)
        print(f"  找到 {len(markets)} 個相關市場\n")

        for i, m in enumerate(markets[:10], 1):
            ticker = m.get('ticker', '?')
            title = m.get('title', '?')
            last = m.get('last_price', '?')
            volume = m.get('volume', 0)
            print(f"  {i}. [{ticker}]")
            print(f"     {title}")
            print(f"     價格: {last}¢ | 交易量: {volume}")
            print()

        # 2. 取第一個市場的價格
        if markets:
            ticker = markets[0].get('ticker', '')
            if ticker:
                print(f"[2] 取得 {ticker} 的即時價格...")
                try:
                    price = get_market_price(ticker)
                    print(f"  Yes: {price['yes_price']:.1%}")
                    print(f"  No:  {price['no_price']:.1%}")
                    print(f"  中間價: {price['midpoint']:.1%}")
                except KalshiAPIError as e:
                    print(f"  價格查詢失敗: {e}")

    except KalshiAPIError as e:
        print(f"  API 錯誤: {e}")

    print("\n=== Demo 結束 ===")
