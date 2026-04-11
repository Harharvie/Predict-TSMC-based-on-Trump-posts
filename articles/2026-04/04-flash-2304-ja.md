這則推文的內容是空的（沒有文字），無法產出速報。

可能原因：
1. 抓取時推文已被刪除或編輯
2. 推文只有圖片/影片，文字部分為空
3. API 回傳異常

要我檢查一下抓取邏輯，看是不是 parser 漏掉了內容？

---
**📋 出典・分析手法**
- 原文：Truth Social
- リンク：https://truthsocial.com/@realDonaldTrump/116318327451670661
- 投稿日時：Mon, 30 Mar 2026 13:20:22 +0000
- 分析エンジン：Trump Code AI（Claude Opus / Gemini Flash）
- シグナル検出：7,400件以上の投稿から検証済み551ルール（z=5.39）
- 手法：NLPキーワード分類 → LLM因果推論 → 信頼度スコアリング
- データセット：trumpcode.washinmura.jp/api/data
- オープンソース：github.com/sstklen/trump-code
