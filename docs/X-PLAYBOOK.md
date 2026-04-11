# X 社群操作手冊 — 從零到活的完整 SOP
---

## ⚠️ 血的教訓（2026-03-25 @trumpcodeai 被停號）

**發生了什麼：** 測試自動發推功能時，2 分鐘內發了 24 則推文 → X 立刻停號。

**學到的：**
1. X 的反垃圾偵測非常快，不是「可能被抓」是「一定被抓」
2. 測試外部 API 必須用 dry-run，不能拿真環境當沙箱
3. 首次掃描外部數據源 → 靜默初始化（只記不觸發）
4. 發推必須有硬性速率限制（我們設：每分鐘 3 則、每小時 15 則）

**現在的防護：** `x_poster.py` 內建速率限制，超過直接擋不發。

---

## 一、X 演算法的真相（你必須知道的 5 件事）

### 1. 你有一個隱藏分數：TweepCred（0-100）

X 給每個帳號一個「信用分」，決定你的推文被多少人看到。

| 分數 | 意義 | 影響 |
|------|------|------|
| < 17 | 低信任 | 你的推文幾乎沒人看到 |
| 17-65 | 普通 | 只推給一小撮人測試 |
| 65+ | 高信任 | 推文會進「For You」頁面 |
| 買 Premium | +100 加成 | 新帳號直接從 -28 起跳（而非 -128） |

**白話：新帳號就像剛入學的轉學生，沒人認識你。Premium = 校長兒子，自帶光環。**

### 2. 每則推文的前 30 分鐘決定生死

推文發出後：
1. 先推給 ~100-200 個最可能互動的人（你的活躍粉絲）
2. 前 15-30 分鐘的互動數據決定是否擴大推送
3. 如果反應好 → 推到更多人的「For You」→ 滾雪球
4. 如果反應差 → 就沒了

**操作含義：發文後 30 分鐘內要在線，回覆每一則留言。**

### 3. 互動類型的價值差 150 倍

| 互動類型 | 演算法權重 | 白話 |
|---------|-----------|------|
| 你跟別人一來一回對話 | **150x** | 最值錢，遠超其他 |
| 被轉推 | 20x | 值錢 |
| 被回覆 | 13.5x | 不錯 |
| 個人頁面被點 | 12x | 代表有人好奇你是誰 |
| 連結被點 | 11x | 代表內容有行動力 |
| 被收藏 | 10x | 代表長期價值 |
| 被按讚 | 1x | 最不值錢 |

**白話：一次跟人聊天 = 150 個讚。所以要寫會讓人想回你的推文。**

### 4. 會被懲罰的行為（Shadowban 觸發器）

| 行為 | 危險度 | 後果 |
|------|--------|------|
| 自動 Follow/Unfollow | 🔴 致命 | 24-48hr 內被偵測，帳號限制 |
| 自動按讚/轉推 | 🔴 致命 | 同上 |
| 15 分鐘內發 5+ 則 | 🟡 危險 | 曝光下降 |
| 3 週不發文 | 🟡 危險 | 曝光 -50%，像重新開始 |
| Hashtag 超過 2 個 | 🟢 輕微 | 互動率下降 17% |
| 純貼連結不加評論 | 🟢 輕微 | 曝光 -30~50% |

**Shadowban 檢測：** 開無痕視窗搜你的帳號名，沒出現 = 被 shadowban。
工具：https://shadowban.yuzurisa.com/

### 5. Premium（藍勾）值不值得買？

| 方案 | 費用 | 曝光加成 | 建議 |
|------|------|---------|------|
| Free | $0 | 1x | 前 2 週測試用 |
| Premium | $8/月 | 2-4x | **第 3 週就買，CP 值最高** |
| Premium+ | $16/月 | 4-10x | 粉絲 > 5K 後考慮 |

**結論：$8/月買 2-4 倍曝光，比任何廣告都便宜。確認要認真經營就買。**

---

## 二、新帳號第一天到第三十天 — 每天做什麼

### 📋 Day 0：開帳號（30 分鐘）

- [ ] 用獨立 Email 註冊（每個項目一個 Email）
- [ ] 帳號名稱：簡短好記（見下方各項目 Bio）
- [ ] 頭像：Logo 或辨識度高的圖（400x400px，高對比）
- [ ] Banner：一句話核心價值（1500x500px）
- [ ] Bio：見下方範本（160 字內，含 1 個 CTA）
- [ ] 置頂推文：你最代表性的一則內容
- [ ] 連結：放你的網站

### 📋 Day 1-7：Reply Guy 階段（每天 30-60 分鐘）

**核心策略：不發自己的推文，只去回覆大帳號。**

為什麼？新帳號自己發推文沒人看（TweepCred 太低）。
但你去回覆 50K+ 粉絲的帳號，他的粉絲會看到你的回覆。

每天做的事：
1. **回覆 15-20 則**（高品質回覆，不是「太棒了👍」）
2. **開啟 5-10 個大帳號的通知**（他們發文你第一個回覆）
3. **每則回覆 > 15 字**，要有觀點或提問
4. **自己的推文：每天 1-2 則**就好（質量 > 數量）

回覆範本（直接複製改）：
```
「有趣的觀點。但如果考慮到 [X 因素]，結論可能完全不同？」
「這個數據跟我看到的 [Y 來源] 有出入。是不是因為 [Z]？」
「同意前半段，但後面那個推論有個漏洞：[具體指出]」
「補充一個角度：[你的獨特見解]。這會怎麼影響 [相關主題]？」
「等等，這代表 [推導出的結論] 嗎？如果是的話影響很大。」
```

### 📋 Day 8-14：混合階段

- 回覆：每天 10-15 則
- 自己的推文：每天 2-3 則
- 第一個 Thread（串）：挑一個你最專業的主題，寫 5-7 則串

### 📋 Day 15-21：內容建立期

- 回覆：每天 5-10 則
- 自己的推文：每天 3-5 則
- 第二個 Thread
- 開始固定發文時間（讓演算法學你的節奏）

### 📋 Day 22-30：飛輪啟動

- 回覆：每天 5 則（精選大帳號）
- 自己的推文：每天 3-5 則
- 看數據：哪類推文互動最高？加倍做那個
- 目標：200-500 粉絲

---

## 三、三個帳號的具體設定

### 1. @trumpcodeai — 川普密碼

**Bio：**
```
🔍 AI 即時解讀川普每一則發文的市場信號
📊 BEARISH/BULLISH 信心指數 + 三語快報（EN/中/日）
🤖 Powered by Claude Opus — 30 秒出報告
👇 完整分析 ↓
```

**置頂推文：**
```
🚨 Trump just posted about 50% tariff on China

AI Analysis (30 sec after post):
📊 Signal: TARIFF 95% | BEARISH 85%
📉 Expected: USD/CNY +0.3-0.5% within 15 min

Every Trump post → AI reads it → Market signal in 30 sec

Follow for real-time alerts 🔔
```

**要回覆的帳號：**
@Reuters @CNBC @business @zaborsky @WallStreetSilv @unusual_whales @DeItaone @BurryArchive @GRDecter @StockMKTNewz

**自動推文模板（程式用）：**

模板 A — 有市場信號時（完整版）：
```
🚨 Trump just posted: {標題摘要}

AI Signal: {DIRECTION} {CONFIDENCE}%
Key: {TOP_SIGNAL} | {SECOND_SIGNAL}

Expected market impact: {一句話預期}

Full analysis → trumpcode.washinmura.jp
#TrumpCode
```

模板 B — 無明確信號時（簡短版）：
```
📝 Trump post: {標題摘要}

AI read: No clear market signal detected
Topic: {TOPIC}

Archive → trumpcode.washinmura.jp
```

模板 C — 中文回覆（自動掛在主推下面）：
```
🇹🇼 中文快報：
川普發文：{中文標題}
AI 判讀：{方向} {信心}%
關鍵信號：{信號}

完整三語分析 → trumpcode.washinmura.jp
```

模板 D — 日文回覆（自動掛在中文下面）：
```
🇯🇵 日本語速報：
トランプ投稿：{日文標題}
AI判定：{方向} {信心}%

詳細分析 → trumpcode.washinmura.jp
```

---

### 2. @1TokenCosmos — GitHub 宇宙

**Bio：**
```
🌌 Your GitHub profile → a living universe
⭐ Stars = suns. Repos = planets. Commits = energy.
🔭 From dust clouds to quasars — see where you are
👇 Enter your username ↓
```

**置頂推文：**
```
What does YOUR GitHub universe look like?

@torvalds = Quasar (mass: 6,800+ repos across Linux ecosystem)
@sindresorhus = Galaxy (mass: 1,200+ packages powering npm)
You = ? 🔭

Try it → 1tokencosmos.washinmura.jp/github.html?user=YOUR_USERNAME

Built with vanilla JS. No frameworks. No tracking.
Open source 🔗 github.com/sstklen/1tokencosmos
```

**要回覆的帳號：**
@github @vercel @t3dotgg @ThePrimeagen @fireship_dev @levelsio @raaboraab @cassaborell @deaborahtrust

**語言：100% 英文**（開發者全球市場）

---

### 3. @WashinAPI（或 @ClawAPI）— AI API 聚合

**Bio：**
```
🦞 One API key → 30+ AI services
🔑 OpenAI, Claude, Gemini, Cohere, ElevenLabs...
💰 Pay-per-use, no subscriptions
🛠️ Drop-in replacement for OpenAI SDK
👇 Get your Claw Key ↓
```

**置頂推文：**
```
Tired of managing 15 different AI API keys?

Get ONE key. Use ALL of them.

✅ OpenAI, Claude, Gemini, Cohere
✅ TTS, STT, Image Gen, Embeddings
✅ Pay only for what you use
✅ OpenAI SDK compatible — change 1 line of code

Free tier available → clawapi.washinmura.jp

Built for developers who ship fast 🚀
```

**要回覆的帳號：**
@OpenAI @AnthropicAI @GoogleAI @levelsio @IndieHackers @ProductHunt @aiaborab

**語言：90% 英文 + 10% 中文**

---

## 四、每週內容日曆（通用模板）

適用於所有帳號，根據項目替換內容。

| 天 | 時間（UTC） | 類型 | 內容 | 目的 |
|----|-----------|------|------|------|
| 週一 | 09:00 | 💡 觀點 | 對你的領域的一個看法 | 開場，設定本週基調 |
| 週一 | 17:00 | 💬 回覆 | 回覆 3-5 個大帳號 | 借力 |
| 週二 | 09:00 | 📊 數據 | 分享一個有趣的數據/圖表 | 高轉發率 |
| 週二 | 14:00 | 💬 回覆 | 回覆 3-5 個大帳號 | 借力 |
| 週三 | 09:00 | 🧵 Thread | 5-7 則深度分析串 | **本週重頭戲** |
| 週三 | 17:00 | 💬 討論 | 問粉絲一個問題 | 衝互動 |
| 週四 | 09:00 | 🔄 引用 | Quote 一則相關推文+加你的分析 | 蹭流量 |
| 週四 | 17:00 | 💬 回覆 | 回覆 3-5 個大帳號 | 借力 |
| 週五 | 09:00 | 📝 教學 | 教粉絲一個小技巧 | 價值輸出 |
| 週五 | 14:00 | 🎯 CTA | 導流推文（網站/產品） | 轉換 |
| 週六 | 12:00 | 🌟 輕鬆 | 幕後故事/有趣的事 | 人味 |
| 週日 | — | 休息 | 不發文 | 讓演算法喘口氣 |

**黃金比例：**
- 價值內容（教學/數據/分析）：50%
- 互動內容（回覆/提問/引用）：30%
- 推廣內容（產品/網站/CTA）：**20% 以內**

---

## 五、三個帳號怎麼互相導流（不被懲罰）

### ❌ 絕對不能做
- 帳號 A 轉推帳號 B 的推文
- 帳號 A 按讚帳號 B 的每則推文
- 四個帳號發一樣的內容
- Bio 裡直接放其他帳號的 @

### ✅ 安全的做法

1. **公開 List 導流**
   - 建一個公開的「和心村生態系」List
   - 把四個帳號都加進去
   - 粉絲自然會發現

2. **網站交叉連結**
   - trumpcode.washinmura.jp 的 footer 放其他三個帳號
   - 每個網站都有「Follow us on X」但連到不同帳號
   - 這不是 X 平台上的行為，不會被偵測

3. **內容自然提及**
   - @trumpcodeai 偶爾：「This analysis was powered by @WashinAPI's multi-model routing」
   - @WashinAPI 偶爾：「See @trumpcodeai for a real-world use case」
   - **頻率：一個月最多 1-2 次，不能每天**

4. **不同時間、不同風格**
   - 每個帳號的發文時間錯開
   - 每個帳號的語氣不同（Trump Code 專業冷靜、和心村溫暖、1TC 極客）
   - 不同 IP 不同裝置（如果在意安全）

---

## 六、推文寫作公式

### 基本結構：Hook → Value → CTA

```
[Hook：第一句話讓人停下滑動，< 10 字]

[Value：2-3 句核心內容]

[CTA：一個明確行動]
```

### 最強 Hook 開頭（直接套用）

| Hook 類型 | 範例 | 適用 |
|----------|------|------|
| 數字 | 「97% of people don't know this」 | 教學類 |
| 反直覺 | 「Stop using hashtags.」 | 觀點類 |
| 急迫 | 「🚨 Breaking:」 | 即時新聞 |
| 懸念 | 「This changed everything.」 | 故事類 |
| 提問 | 「What if I told you...」 | 互動類 |
| 對比 | 「2024: X happened. 2026: everything changed.」 | 趨勢類 |

### 推文最佳長度

| 長度 | 效果 | 適用 |
|------|------|------|
| < 50 字 | 高點擊但淺 | 提問、挑釁 |
| **50-200 字** | **最佳甜蜜點** | **大多數推文** |
| 200-280 字 | 還行 | 故事、詳細觀點 |
| Thread 7 則 | 最佳 Thread 長度 | 深度分析 |

### Hashtag 規則

- **用 1 個，最多 2 個**（超過 2 個互動率 -17%）
- 放在推文中間或結尾，不要放開頭
- 用你的品牌 tag：#TrumpCode #WashinMura #1TokenCosmos
- 不要用大眾 tag（#AI #Travel 太泛，淹沒在噪音裡）

---

## 七、Shadowban 防護 SOP

### 日常檢查（每週一次）
1. 開無痕視窗 → 搜你的帳號名
2. 看得到 = 正常；看不到 = 被 shadowban
3. 或用：https://shadowban.yuzurisa.com/

### 如果被 Shadowban 了
1. **立刻停止所有活動 48-72 小時**
2. 刪除最近的推文（如果有可疑內容）
3. 檢查是否有自動化行為被偵測
4. 72 小時後慢慢恢復（每天 1-2 則）
5. 恢復時間：輕微 1-3 天，嚴重 2-4 週

### 自動帳號的安全操作

| 項目 | 安全值 | 危險值 |
|------|--------|--------|
| 每日推文數 | 3-8 則 | > 15 則 |
| 推文間隔 | > 2 小時 | < 15 分鐘 |
| 連結比例 | < 20% 推文含連結 | 每則都有連結 |
| 每日 Follow | < 20 人 | > 50 人 |
| 回覆頻率 | 自然節奏 | 每分鐘一則 |
| 重複內容 | 6 週才重發 | 1 週內重發 |
| 發文時間 | 有隨機變化 | 每天精確同一秒 |

---

## 八、從零到變現（時間表）

| 階段 | 粉絲數 | 時間 | 能做什麼 |
|------|--------|------|---------|
| 冷啟動 | 0-500 | 1-4 週 | 純投入，建立內容 |
| 起步 | 500-2K | 1-2 月 | 偶爾被轉發，開始有認同 |
| 成長 | 2K-10K | 3-6 月 | 可以接業配、導流到產品 |
| 飛輪 | 10K+ | 6-12 月 | 廣告分潤、Ticketed Spaces |

### X 廣告分潤門檻（2026）
- 500 認證粉絲 + 過去 3 個月 500 萬曝光 + Premium 訂閱
- 收入大約 $8.50 / 百萬曝光

### 更實際的變現方式
- **導流到自有產品**（和心村訂房、Washin API 訂閱）← 最實際
- **品牌曝光**（川普密碼被新聞引用）← 最有長期價值
- **建立信任**（1TokenCosmos 被開發者認識）← 做大事前的鋪墊

---

## 九、自動化架構（程式端）

### 安全的自動化
```
✅ 排程發文（API / Buffer / Typefully）
✅ RSS 觸發發文（川普發文 → 自動快報）
✅ 數據分析（API 讀取互動數據）
```

### 禁止的自動化
```
❌ 自動按讚
❌ 自動 Follow/Unfollow
❌ 自動回覆
❌ 自動轉推
```

### 推文發送的技術建議
- 發文時間加隨機偏移（±5-15 分鐘），避免機械感
- 推文內容要有變化，不要每則都同格式
- 用 OAuth 1.0a（不是 Bearer token）發文
- 每則推文後 random sleep 2-15 秒

---

## 十、一句話總結

**新帳號的成功公式：**

> Reply Guy（前 2 週）→ 混合發文（第 3-4 週）→ 固定節奏（第 2 月起）→ 等飛輪

**核心心法：**

> 不是「我要發什麼」，是「別人看了會想回我什麼」。
> 一次對話 = 150 個讚。寫能引發對話的推文。

---

## 附：研究來源

- [X Algorithm Technical Breakdown 2026](https://www.tweetarchivist.com/how-twitter-algorithm-works-2025)
- [TweepCred Hidden Ranking System](https://blog-content.circleboom.com/the-hidden-x-algorithm-tweepcred-shadow-hierarchy-dwell-time-and-the-real-rules-of-visibility/)
- [Reply Guy Growth Strategy](https://postowl.io/blog/x-reply-guy-growth-strategy)
- [Shadowban Detection & Fix 2026](https://opentweet.io/blog/twitter-shadowban-check-fix-avoid-2026)
- [Best Time to Post 2026 (1M Posts Analyzed)](https://buffer.com/resources/best-time-to-post-on-twitter-x/)
- [Twitter Engagement Benchmarks 2026](https://www.tweetarchivist.com/twitter-engagement-benchmarks-2025)
- [Automated Bot Best Practices](https://multilogin.com/blog/twitter-shadow-bans/)
- [Viral Tweet Writing Guide 2026](https://www.tweetarchivist.com/how-to-write-viral-tweets-2025)
- [Multiple Account Management](https://blog.send.win/managing-multiple-twitter-accounts-multi-account-management-guide-2026/)
- [X Monetization Complete Guide](https://www.outfy.com/blog/how-to-make-money-on-x/)
- [EmojiMashupBot Case Study](https://time.com/5663562/emoji-mashup-bot/)
- [80K Follower Bot Case Study](https://derewah.dev/projects/twitter-automation)
