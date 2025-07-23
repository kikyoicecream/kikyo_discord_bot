# Kikyo Discord BOT

多角色 Discord Bot 系統，支援獨立的虛擬人物角色，每個角色都有專屬的 Discord Token 和記憶系統。具備 AI 群組對話追蹤功能，讓 BOT 能夠感知多使用者對話環境並自然地與所有參與者互動。

## ✨ 最新更新

- 🔒 **全域安全過濾器**：統一的 Gemini AI 安全過濾器設定
- 🧠 **改進的記憶系統**：分離永久記憶和動態記憶，更符合使用者偏好的記憶管理
- 👥 **增強的群組對話追蹤**：更自然的多人對話互動
- 🎯 **角色啟動器**：簡化的角色 Bot 管理系統
- 🔧 **簡化指令系統**：移除不必要的 sync 指令，優化指令權限
- 📝 **關鍵字查詢**：新增 `/{character}_keywords` 指令，方便查看角色關鍵字

## 快速開始

1. 複製 `.env.example` 為 `.env` 並填入您的設定
2. 安裝相依套件：`pip install -r requirements.txt`
3. 使用角色啟動器：`python3 main.py`

## 系統特色

- 🎭 **多角色支援**：每個角色都是獨立的 Discord Bot
- 🧠 **資料庫記憶**：使用 Firestore 儲存每個使用者的對話記憶
- 👥 **群組對話追蹤**：追蹤活躍使用者，支援多使用者群組對話
- 🔧 **靈活權限**：支援全域或個別 Bot 權限設定
- 🚀 **自動重啟**：Bot 異常時自動重啟功能
- 📱 **管理介面**：互動式多 Bot 管理系統
- 🔒 **安全過濾**：全域 Gemini AI 安全過濾器保護
- 🎯 **簡化指令**：精簡的斜線指令系統

## 檔案結構

```
Kikyo Discord BOT/
├── README.md                    # 主要說明文件
├── main.py                      # 主程式啟動器
├── requirements.txt             # Python 套件需求
├── characters.json              # 角色設定檔
├── core/                        # 核心系統
│   ├── character_bot.py         # 通用 Bot 模板
│   ├── character_registry_custom.py # 角色註冊系統
│   ├── memory.py                # 記憶管理系統（含全域安全設定）
│   ├── emoji_responses.py       # 表情符號回應系統
│   └── group_conversation_tracker.py # 群組對話追蹤系統
└── emoji_system/                # 表情符號設定
    ├── fan_chengxi_emoji.json   # 范丞㰕表情符號
    ├── gu_beichen_emoji.json    # 顧北辰表情符號
    └── shen_ze_emoji.json       # 沈澤表情符號
```

## 使用方式

### 推薦：使用主程式啟動器
```bash
# 啟動主程式
python3 main.py
```

主程式提供：
- 📋 **角色列表**：顯示所有可用角色
- ▶️ **一鍵啟動**：選擇角色後自動啟動
- 🔄 **自動重啟**：Bot 異常時自動重新啟動
- 📊 **狀態監控**：即時顯示 Bot 運行狀態

### 角色設定檔

編輯 `characters.json` 來管理角色：

```json
{
  "shen_ze": {
    "name": "沈澤",
    "token_env": "SHEN_ZE_TOKEN",
    "proactive_keywords": ["叔叔"],
    "gemini_config": {
      "temperature": 1.0,
      "top_k": 40,
      "top_p": 0.95
    },
    "enabled": true
  },
  "gu_beichen": {
    "name": "顧北辰",
    "token_env": "GU_BEICHEN_TOKEN",
    "proactive_keywords": ["顧北辰", "顧總", "辰辰"],
    "gemini_config": {
      "temperature": 1.0,
      "top_k": 40,
      "top_p": 0.9
    },
    "enabled": true
  }
}
```

## 環境設定

### 基本設定
在 `.env` 檔案中設定：

```env
# Discord Bot Tokens (每個角色需要獨立的 Token)
SHEN_ZE_TOKEN=your_shen_ze_bot_token_here
GU_BEICHEN_TOKEN=your_gu_beichen_bot_token_here
FAN_CHENGXI_TOKEN=your_fan_chengxi_bot_token_here

# Firebase 和 AI 設定
FIREBASE_CREDENTIALS_JSON={"type":"service_account","project_id":"your-project-id",...}
GOOGLE_API_KEY=your_gemini_api_key_here

# 權限設定
ALLOWED_GUILDS=123456789,987654321
ALLOWED_CHANNELS=111111111,222222222
BOT_OWNER_IDS=333333333,444444444
```

### 🔒 全域安全過濾器設定

系統已內建全域 Gemini AI 安全過濾器，預設設定為：

```python
# 在 core/memory.py 中的全域設定
SAFETY_SETTINGS = [
    {"category": HarmCategory.HARM_CATEGORY_HARASSMENT, "threshold": HarmBlockThreshold.BLOCK_NONE},
    {"category": HarmCategory.HARM_CATEGORY_HATE_SPEECH, "threshold": HarmBlockThreshold.BLOCK_NONE},
    {"category": HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT, "threshold": HarmBlockThreshold.BLOCK_NONE},
    {"category": HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT, "threshold": HarmBlockThreshold.BLOCK_NONE},
]
```

**安全等級說明：**
- `BLOCK_NONE`：完全關閉過濾（當前設定）
- `BLOCK_ONLY_HIGH`：只阻擋高風險內容
- `BLOCK_MEDIUM_AND_ABOVE`：阻擋中等以上風險（建議設定）
- `BLOCK_LOW_AND_ABOVE`：阻擋低風險以上（嚴格）

**修改安全設定：**
編輯 `core/memory.py` 中的 `SAFETY_SETTINGS` 變數即可。

### 權限設定指南

#### 方式1：全域設定（所有 Bot 共用相同權限）
```env
# 所有 Bot 都使用這些設定
ALLOWED_GUILDS=您的伺服器ID
ALLOWED_CHANNELS=您的頻道ID1,您的頻道ID2
BOT_OWNER_IDS=您的使用者ID
```

#### 方式2：個別 Bot 權限設定
```env
# 沈澤 Bot 專屬權限
SHEN_ZE_ALLOWED_GUILDS=學習群組ID
SHEN_ZE_ALLOWED_CHANNELS=學習頻道ID

# 顧北辰 Bot 專屬權限
GU_BEICHEN_ALLOWED_GUILDS=遊戲群組ID
GU_BEICHEN_ALLOWED_CHANNELS=遊戲頻道ID
```

## 🧠 記憶系統

### 記憶分類
系統將記憶分為兩類：

1. **永久記憶**：手動添加的重要資訊，永不刪除
2. **動態記憶**：自動生成的對話記憶，會被統整

### 記憶管理機制
- **自動記憶**：每次對話後自動使用 AI 提取重要資訊
- **智慧統整**：動態記憶超過 15 則時，自動統整成摘要
- **角色隔離**：每個角色的記憶完全獨立
- **使用者隔離**：每個使用者的記憶分別儲存

### Firestore 資料結構
```
your-project/
├── character_id/
│   ├── profile/ # 角色設定
│   ├── users/ # 參與對話的人
│   │   └── memories/
│   │       └── user_id/
│   │           ├── permanent_memories: []
│   │           ├── dynamic_memories: []
│   │           └── last_updated: timestamp
│   └── emoji_system/ # 表情符號管理器
│       ├── emoji_map

```

## 👥 群組對話追蹤功能

### 功能概述
- **活躍使用者追蹤**：記錄哪些使用者正在與 BOT 對話
- **群組對話上下文**：了解整個對話的脈絡
- **主動提及其他使用者**：BOT 可以自然地提及其他活躍使用者
- **AI 對話摘要**：生成群組對話的摘要
- **BOT 回應追蹤**：記錄 BOT 自己的發言，確保對話連續性

### 使用範例

#### 多使用者群組對話
```
小明：大家好！今天天氣真好
小華：嗨！我在這裡
小美：大家好！我是新來的

沈澤：「看到大家都很活躍呢！小明，你提到天氣很好，確實是個適合聊天的日子。小華，你也在這裡，我們可以一起歡迎小美。小美，歡迎加入我們的對話！」
```

## 🎭 斜線指令系統

### 可用指令

每個角色都有以下斜線指令：

#### `/{character_prefix}_restart`
- **功能**：重新啟動 Bot
- **權限**：所有使用者都可以使用
- **範例**：`/shen_ze_restart`、`/gu_beichen_restart`

#### `/{character_prefix}_keywords`
- **功能**：顯示角色的主動關鍵字
- **權限**：所有使用者都可以使用
- **範例**：`/shen_ze_keywords`、`/gu_beichen_keywords`
- **顯示內容**：角色名稱和對應的關鍵字列表

#### `/{character_prefix}_memory`
- **功能**：顯示角色與使用者的記憶內容
- **權限**：所有使用者都可以使用
- **範例**：`/shen_ze_memory`、`/gu_beichen_memory`

### 指令範例

```
/shen_ze_keywords
👤 沈澤
**主動關鍵字：**叔叔

/gu_beichen_keywords  
👤 顧北辰
**主動關鍵字：**顧北辰、顧總、辰辰

/fan_chengxi_keywords
👤 范丞㰕
**主動關鍵字：**范丞㰕、丞㰕、寶寶、小㰕、狗狗、寶貝
```

## 如何新增新角色

### 1. 更新角色設定檔
編輯 `characters.json`：

```json
{
  "new_character": {
    "name": "新角色",
    "token_env": "NEW_CHARACTER_TOKEN",
    "proactive_keywords": ["新角色", "關鍵字1", "關鍵字2"],
    "gemini_config": {
      "temperature": 1.0,
      "top_k": 40,
      "top_p": 0.9
    },
    "enabled": true
  }
}
```

### 2. 設定環境變數
在 `.env` 檔案中新增：
```env
NEW_CHARACTER_TOKEN=your_new_character_bot_token_here
```

### 3. 建立 Firestore 角色設定
在 Firestore 中建立 `new_character/profile` 文件：

```json
{
  "name": "新角色",
  "personality": "角色性格描述",
  "background": "角色背景故事",
  "speaking_style": "說話風格",
  "interests": ["興趣1", "興趣2"],
  "age": "年齡",
  "occupation": "職業"
}
```

### 4. 使用主程式啟動器
運行 `python3 main.py`，新角色會自動出現在列表中。

## 故障排除

### 角色無法回應
1. ✅ 檢查 Discord Token 是否正確
2. ✅ 確認 Firestore 中有對應的角色設定
3. ✅ 檢查伺服器和頻道權限設定
4. ✅ 確認關鍵字設定正確

### 記憶無法儲存
1. ✅ 確認 Firebase 連線正常
2. ✅ 檢查 Firestore 權限設定
3. ✅ 查看錯誤日誌
4. ✅ 檢查 `GOOGLE_API_KEY` 是否正確設定

### Bot 無法啟動
1. ✅ 檢查環境變數設定
2. ✅ 確認所有相依套件已安裝：`pip install -r requirements.txt`
3. ✅ 檢查 Python 版本 (需要 3.9+)
4. ✅ 確認 `characters.json` 格式正確

### Gemini API 相關問題
1. ✅ 檢查 `GOOGLE_API_KEY` 是否正確
2. ✅ 確認 API 配額是否足夠
3. ✅ 檢查網路連線
4. ✅ 查看安全過濾器設定是否適當

### 指令無法使用
1. ✅ 確認 Bot 已成功登入並同步指令
2. ✅ 檢查 Bot 在伺服器中的權限
3. ✅ 確認指令名稱正確（例如：`/shen_ze_keywords`）
4. ✅ 檢查 Bot 是否在正確的伺服器和頻道中

## 環境需求

- **Python 3.9+**
- **Discord.py >= 2.3.0**
- **Firebase Admin SDK >= 6.0.0**
- **Google Generative AI == 0.8.3**
- **其他相依套件**請參考 `requirements.txt`

## 🔧 開發說明

### 程式碼結構
- **模組化設計**：核心功能分離，易於維護
- **全域配置**：統一的 AI 安全設定
- **錯誤處理**：完整的異常處理機制
- **日誌記錄**：詳細的運行日誌

### 自動部署
專案包含 GitHub Actions 配置，支援自動重啟部署。

## 授權

此專案僅供個人使用和學習目的。

---

## 📞 支援

如果您遇到問題或有建議，請：
1. 檢查本 README 的故障排除部分
2. 查看程式碼中的註解和錯誤訊息
3. 確認環境設定是否正確

**祝您使用愉快！** 🎉 