<div align="center">

# Trump Posts Market Signal Detector
</div>
川普是全球唯一能用一則社群貼文撼動市場的人。這個專案透過暴力搜尋，找出他發文行為與股市走勢的統計規律。

- 分析 **5591 則 Truth Social 貼文**（三來源交叉驗證）
- 暴力搜尋 **3,150 萬種模型組合**
- **551 條存活規則**通過訓練/測試集雙驗證
- **566 筆預測驗收命中率 61.3%**（z=5.39, p<0.05）



## 核心發現

### S&P 500 分析
|  | 發現 | 數據依據 | 市場影響 |
|---|------|----------|----------|
| 1 | **盤前 RELIEF = 最強買入訊號** | 2025/4/9：S&P +9.52% | 平均 +1.12% |
| 2 | **TARIFF → 放空正確率僅 30%** | 熔斷器分析 | 自動反轉做多 |
| 3 | **中國訊號只在 Truth Social** | 203 篇 TS / X 零篇 | 權重提升 1.5 倍 |
| 4 | **Truth Social 比 X 早 6.2 小時** | 38/39 篇吻合 | 6 小時套利窗口 |
| 5 | **純關稅日最危險** | 4/3：-4.84%，4/4：-5.97% | 平均 -1.057% |
| 6 | **4 訊號組合最高獲利** | 12 次出現，66.7% 上漲 | 平均 +2.792% |
| 7 | **沉默日八成看多** | 零貼文日分析 | 平均 +0.409% |
| 8 | **深夜關稅反指標** | 62% 預測錯 → 反向操作 62% 正確 | 自動反轉 |

### 台積電 (2330.TW) 分析
| 時段 (台灣時間) | 篇數 | 當日 2330 | 隔日 2330 |
|----------------|------|-----------|-----------|
| 🌅 **盤前 (08-09)** | 238 | **+0.099% 📈** | -0.047% |
| ☀️ **盤中 (09-13:30)** | 901 | +0.074% | -0.055% |
| 🌆 **盤後 (13:30-15)** | 52 | **+0.605% 📈** | **+0.825% 📈** |
| 🌙 **非交易時段** | 4233 | +0.073% | -0.026% |

**時段 × 關鍵詞組合**：

| 組合 | 篇數 | 當日 2330 | 隔日 2330 |
|------|------|-----------|-----------|
| **盤前+TARIFF** | 14 | **+0.555% 📈** | **+0.430% 📈** |
| **盤前+DEAL** | 11 | **+0.545% 📈** | +0.159% |
| **盤前+CHINA_TAIWAN** | 4 | -0.194% ➡️ | **+1.330% 📈** |

deal指出現'deal', 'agreement', 'negotiate', 'talks', 'signed'這些詞語

### 2. 關鍵詞 → 隔日平均報酬

| 關鍵詞 | 出現篇數 | 隔日 2330 平均報酬 |
|--------|----------|-------------------|
| **has_taiwan** | 1 | **-1.1204% 💥** |
| **has_tsmc** | 1 | **-2.7054% 💥** |
| **has_chip** | 18 | **+0.458% 📈** |
| **has_tariff** | 127 | **+0.2536% 📈** |
| **has_tariff_semis** | 14 | **+0.3164% 📈** |
| **has_china** | 75 | **+0.5544% 📈** |

### 3. 大漲/大跌前一天信號差異

| 特徵 | 大漲前一天 (>1%) | 大跌前一天 (<-1%) | 差異 |
|------|------------------|-------------------|------|
| **發文量** | 11.7 篇 | **12.2 篇** | 大跌前較高 |
| **大寫率** | 12.6% | **14.2%** | 大跌前較高 |
| **驚嘆號** | 13.0 個 | **16.2 個** | 大跌前較高 |
| **平均文長** | 367 字 | **423 字** | 大跌前較高 |

**情緒信號分數統計**：範圍 **-8.6 ~ +40.5**，平均 **+19.7**。極正面 (≥20) 區間勝率 **44.5%**，並沒有較高勝率。


## 系統架構圖 (System Architecture)

```bash
trump-code/
├── chatbot_server.py             # Web server + all API endpoints
├── realtime_loop.py              # Real-time monitor (every 5 min)
├── daily_pipeline.py             # Daily pipeline (11 steps)
├── learning_engine.py            # Promote/demote/eliminate rules
├── rule_evolver.py               # Crossover/mutation/distill
├── circuit_breaker.py            # System health + auto-pause
├── event_detector.py             # Multi-day event patterns
├── dual_platform_signal.py       # Truth Social vs X analysis
├── polymarket_client.py          # Polymarket API client
├── kalshi_client.py              # Kalshi API client
├── arbitrage_engine.py           # Cross-platform arbitrage
├── mcp_server.py                 # MCP server (9 tools)
├── trump_code_cli.py             # CLI interface
├── trump_monitor.py              # Post monitor
├── analysis_01_caps.py           # CAPS code analysis
├── analysis_02_timing.py         # Posting time patterns
├── analysis_03_hidden.py         # Hidden messages (acrostic)
├── analysis_04_entities.py       # Country & people mentions
├── analysis_05_anomaly.py        # Anomaly detection
├── analysis_06_market.py         # Posts vs S&P 500
├── analysis_07_signal_sequence.py # Signal sequences
├── analysis_08_backtest.py       # Strategy backtesting
├── analysis_09_combo_score.py    # Multi-signal scoring
├── analysis_10_code_change.py    # Signature change detection
├── analysis_11_brute_force.py    # Brute-force rule search
├── analysis_12_big_moves.py      # Big move prediction
├── analysis_06_market_tsmc.py         # Posts vs TSMC
├── analysis_07_signal_sequence_tsmc.py # Signal sequences of TSMC
├── analysis_08_backtest_tsmc.py       # Strategy backtesting of TSMC
├── analysis_09_combo_score_tsmc.py    # Multi-signal scoring of TSMC
├── analysis_10_code_change_tsmc.py    # Signature change detection of TSMC
├── analysis_11_big_moves_tsmc.py      # Big move prediction of TSMC
├── data/                         # All data 
└── tests/                        # Test suite
```

## 快速開始

```bash
git clone https://github.com/Harharvie/Predict-TSMC-based-on-Trump-posts.git
cd Predict-TSMC-based-on-Trump-posts
pip install -r requirements.txt

# 今日訊號
python trump_code_cli.py signals

# S&P 500 分析
python analysis_06_market.py

# 台積電分析 (新增)
python analysis_06_market_tsmc.py
python analysis_09_combo_score_tsmc.py

# 暴力搜尋 (~25 分鐘)
python overnight_search.py

# 即時監控
python realtime_loop.py

# 儀表板 + 聊天機器人
export GEMINI_KEYS="key1,key2,key3"
python chatbot_server.py  # http://localhost:8888
```

## CLI 指令

```bash
python trump_code_cli.py signals   # 今日訊號
python trump_code_cli.py models    # 模型排行
python trump_code_cli.py predict   # 共識預測
python trump_code_cli.py health    # 系統狀態
```

## 開放資料

| 檔案 | 說明 |
|------|------|
| `trump_posts_all.json` | 7,400+ Truth Social 貼文 |
| `predictions_log.json` | 566 筆驗收預測 |
| `surviving_rules.json` | 551 條活躍規則 |
| `market_2330TW.json` | 台積電歷史資料 |


## 免責聲明

**僅供研究用途，不構成投資建議。** 過去規律不保證未來表現。相關性不等於因果。作者對任何損失不負責任。
