"""X (Twitter) 自動發推模組 — @trumpcodeai

川普發文 → 快報生成 → 自動發一則摘要推文到 @trumpcodeai。

用法：
  from x_poster import post_tweet, post_flash_summary
  post_tweet("Hello from Trump Code!")
  post_flash_summary(meta)  # 從快報 meta 自動組文案

不需要外部套件 — 用 Python 標準庫實作 OAuth 1.0a 簽名。
"""

import hashlib
import hmac
import json
import os
import time
import urllib.parse
import urllib.request
from base64 import b64encode
from datetime import datetime, timezone
from pathlib import Path


# === Key 讀取（從 .env 或環境變數）===

def _load_env():
    """從 .env 讀 key（LaunchAgent 環境可能沒有）。"""
    env_path = Path(__file__).parent / ".env"
    if env_path.exists():
        for line in env_path.read_text().splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                if k.strip() not in os.environ:
                    os.environ[k.strip()] = v.strip()

_load_env()

API_KEY = os.environ.get("X_API_KEY", "")
API_SECRET = os.environ.get("X_API_SECRET", "")
ACCESS_TOKEN = os.environ.get("X_ACCESS_TOKEN", "")
ACCESS_TOKEN_SECRET = os.environ.get("X_ACCESS_TOKEN_SECRET", "")


# === OAuth 1.0a 簽名（純標準庫）===

def _percent_encode(s: str) -> str:
    """RFC 3986 percent-encoding。"""
    return urllib.parse.quote(str(s), safe="")


def _oauth_signature(method: str, url: str, params: dict, body_params: dict = None) -> str:
    """產生 OAuth 1.0a HMAC-SHA1 簽名。"""
    # 合併所有參數（OAuth params + body params）
    all_params = dict(params)
    if body_params:
        all_params.update(body_params)

    # 按 key 排序，組成 parameter string
    param_str = "&".join(
        f"{_percent_encode(k)}={_percent_encode(v)}"
        for k, v in sorted(all_params.items())
    )

    # Signature Base String
    base_str = f"{method.upper()}&{_percent_encode(url)}&{_percent_encode(param_str)}"

    # Signing Key
    signing_key = f"{_percent_encode(API_SECRET)}&{_percent_encode(ACCESS_TOKEN_SECRET)}"

    # HMAC-SHA1
    sig = hmac.new(
        signing_key.encode("utf-8"),
        base_str.encode("utf-8"),
        hashlib.sha1,
    ).digest()

    return b64encode(sig).decode("utf-8")


def _oauth_header(method: str, url: str, body_params: dict = None) -> str:
    """產生完整的 OAuth Authorization header。"""
    oauth_params = {
        "oauth_consumer_key": API_KEY,
        "oauth_nonce": b64encode(os.urandom(32)).decode("utf-8").rstrip("="),
        "oauth_signature_method": "HMAC-SHA1",
        "oauth_timestamp": str(int(time.time())),
        "oauth_token": ACCESS_TOKEN,
        "oauth_version": "1.0",
    }

    # 計算簽名
    oauth_params["oauth_signature"] = _oauth_signature(method, url, oauth_params, body_params)

    # 組成 Authorization header
    auth_str = ", ".join(
        f'{_percent_encode(k)}="{_percent_encode(v)}"'
        for k, v in sorted(oauth_params.items())
    )

    return f"OAuth {auth_str}"


# === 發推速率限制 ===
# 血的教訓：2026-03-25 測試時 2 分鐘發 24 則 → 帳號被停
_tweet_timestamps = []  # 記錄最近發推的時間戳
_RATE_LIMIT_PER_HOUR = 15  # 每小時最多 15 則（含 Thread 回覆）
_RATE_LIMIT_PER_MIN = 3    # 每分鐘最多 3 則


def _check_rate_limit():
    """檢查是否超過發推速率。超過回傳錯誤訊息，正常回傳 None。"""
    now = time.time()
    # 清掉 1 小時前的記錄
    while _tweet_timestamps and _tweet_timestamps[0] < now - 3600:
        _tweet_timestamps.pop(0)

    # 每小時限制
    if len(_tweet_timestamps) >= _RATE_LIMIT_PER_HOUR:
        return f"速率限制：每小時最多 {_RATE_LIMIT_PER_HOUR} 則（目前 {len(_tweet_timestamps)} 則）"

    # 每分鐘限制
    recent_1min = sum(1 for t in _tweet_timestamps if t > now - 60)
    if recent_1min >= _RATE_LIMIT_PER_MIN:
        return f"速率限制：每分鐘最多 {_RATE_LIMIT_PER_MIN} 則（目前 {recent_1min} 則）"

    return None


# === 發推 ===

def post_tweet(text: str, reply_to: str = None) -> dict:
    """發一則推文到 @trumpcodeai。

    Args:
        text: 推文內容（最多 280 字元）
        reply_to: 回覆的推文 ID（用於建立 Thread）

    Returns:
        {"ok": True, "tweet_id": "...", "url": "..."} 或
        {"ok": False, "error": "..."}
    """
    if not all([API_KEY, API_SECRET, ACCESS_TOKEN, ACCESS_TOKEN_SECRET]):
        return {"ok": False, "error": "X API key 未設定（檢查 .env）"}

    # 速率保護（防止再被停號）
    rate_err = _check_rate_limit()
    if rate_err:
        return {"ok": False, "error": rate_err}

    # X API v2 發推 endpoint
    url = "https://api.x.com/2/tweets"
    payload = {"text": text[:280]}
    if reply_to:
        payload["reply"] = {"in_reply_to_tweet_id": reply_to}
    body = json.dumps(payload).encode("utf-8")

    auth = _oauth_header("POST", url)

    req = urllib.request.Request(
        url,
        data=body,
        headers={
            "Authorization": auth,
            "Content-Type": "application/json",
        },
        method="POST",
    )

    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read())
            tweet_id = data.get("data", {}).get("id", "")
            _tweet_timestamps.append(time.time())  # 記錄成功發推時間
            return {
                "ok": True,
                "tweet_id": tweet_id,
                "url": f"https://x.com/trumpcodeai/status/{tweet_id}",
            }
    except urllib.error.HTTPError as e:
        err = e.read().decode()[:300]
        return {"ok": False, "error": f"HTTP {e.code}: {err}"}
    except Exception as e:
        return {"ok": False, "error": str(e)}


def post_flash_summary(meta: dict) -> dict:
    """從快報 meta 自動組文案並發推（單則版，向下相容）。"""
    return post_flash_thread(meta)


def post_flash_thread(meta: dict) -> dict:
    """發三語 Thread：主推英文 → 回覆中文 → 回覆日文。

    Thread 結構：
      主推（EN）：🚨 Trump posted: {摘要} + AI Signal + 連結
      ↳ 回覆 1（ZH）：中文快報摘要
      ↳ 回覆 2（JA）：日文快報摘要

    Returns:
        {"ok": True, "tweets": [{"lang": "en", "tweet_id": "...", "url": "..."}, ...]}
    """
    direction = meta.get("direction", "NEUTRAL")
    signals = meta.get("signals", "")
    content = meta.get("post_content", "")[:80]
    date = meta.get("date", "")
    confidence = meta.get("confidence", 0)
    articles = meta.get("articles", {})

    dir_emoji = {"UP": "📈", "DOWN": "📉", "NEUTRAL": "➡️"}.get(direction, "➡️")

    # --- 主推（英文）---
    en_text = f"🚨 Trump posted: {content}"
    if len(content) >= 78:
        en_text += "..."
    en_text += f"\n\n{dir_emoji} {direction}"
    if signals:
        en_text += f" | {signals}"
    if confidence and confidence > 0:
        en_text += f" ({int(confidence * 100)}%)"
    en_text += f"\n\nFull analysis ↓\ntrumpcode.washinmura.jp"

    main = post_tweet(en_text)
    if not main.get("ok"):
        return main

    results = [{"lang": "en", "tweet_id": main["tweet_id"], "url": main["url"]}]
    main_id = main["tweet_id"]

    # --- 回覆（中文）---
    zh_article = articles.get("zh", {})
    if zh_article.get("status") == "ok":
        zh_len = zh_article.get("length", 0)
        zh_text = f"🇹🇼 中文快報：\n川普發文：{content[:40]}"
        zh_text += f"\nAI 判讀：{dir_emoji} {direction}"
        if signals:
            zh_text += f" | {signals}"
        zh_text += f"\n完整 {zh_len} 字分析 → trumpcode.washinmura.jp"

        # 隨機延遲 3-8 秒，避免機械感
        import random
        time.sleep(random.uniform(3, 8))
        zh_r = post_tweet(zh_text, reply_to=main_id)
        if zh_r.get("ok"):
            results.append({"lang": "zh", "tweet_id": zh_r["tweet_id"], "url": zh_r["url"]})

    # --- 回覆（日文）---
    ja_article = articles.get("ja", {})
    if ja_article.get("status") == "ok":
        ja_len = ja_article.get("length", 0)
        ja_text = f"🇯🇵 日本語速報：\nトランプ投稿：{content[:40]}"
        ja_text += f"\nAI判定：{dir_emoji} {direction}"
        if signals:
            ja_text += f" | {signals}"
        ja_text += f"\n全文 {ja_len} 字 → trumpcode.washinmura.jp"

        import random
        time.sleep(random.uniform(3, 8))
        ja_r = post_tweet(ja_text, reply_to=main_id)
        if ja_r.get("ok"):
            results.append({"lang": "ja", "tweet_id": ja_r["tweet_id"], "url": ja_r["url"]})

    return {"ok": True, "tweets": results, "main_url": main["url"]}


def post_daily_summary(date: str, posts_count: int, signals: list = None) -> dict:
    """每日日報發推摘要。

    格式：
    📊 Trump Code | Daily {date}
    {N} posts analyzed in 3 languages
    {信號列表}
    🔗 trumpcode.washinmura.jp/daily.html?date={date}
    """
    sig_str = ", ".join(signals) if signals else "No major signals"

    text = (
        f"📊 Trump Code | Daily {date}\n"
        f"{posts_count} posts analyzed in zh/en/ja\n"
        f"Signals: {sig_str}\n\n"
        f"🔗 trumpcode.washinmura.jp/daily.html?date={date}"
    )

    return post_tweet(text)


# === CLI 測試 ===

if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1 and sys.argv[1] == "test":
        # 測試推文（會真的發出去）
        result = post_tweet("🧪 Trump Code system test. Ignore this tweet.")
        print(json.dumps(result, ensure_ascii=False, indent=2))
    elif len(sys.argv) > 1 and sys.argv[1] == "status":
        print(f"API_KEY: {'✅' if API_KEY else '❌'} {API_KEY[:8]}..." if API_KEY else "❌ 未設定")
        print(f"API_SECRET: {'✅' if API_SECRET else '❌'}")
        print(f"ACCESS_TOKEN: {'✅' if ACCESS_TOKEN else '❌'}")
        print(f"ACCESS_TOKEN_SECRET: {'✅' if ACCESS_TOKEN_SECRET else '❌'}")
    else:
        print("用法: python3 x_poster.py status  — 查 key 狀態")
        print("      python3 x_poster.py test    — 發測試推文")
