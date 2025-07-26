# Kikyo Discord BOT

多角色 Discord Bot 系統，支援獨立的虛擬人物角色，每個角色都有專屬的 Discord Token 和記憶系統。具備 AI 群組對話追蹤功能，讓 BOT 能夠感知多使用者對話環境並自然地與所有參與者互動。

## 🚀 快速開始

完整安裝文件：https://hackmd.io/@kikyoicecream/H1lydGdree

## 🎯 系統特色

- 🎭 **多角色支援**：同時 Host 多個 BOT，模組化新增角色
- 🧠 **Firestore 記憶系統**：使用 Firestore 儲存每個使用者的對話記憶
- 👥 **群組對話追蹤**：追蹤活躍使用者，支援多使用者群組對話
- ✨ **表情符號回應**：依照使用者對話內容，觸發表情符號回應
- 🔧 **雲端配置管理**：所有角色設定、權限、表情符號機率都儲存在 Firestore
- 🚀 **自動重啟**：Bot 異常時自動重啟功能
- 🔒 **安全過濾**：全域 Gemini AI 安全過濾器保護
- 🎯 **斜線指令**：keyword、memory、restart 三種斜線指令，每個 BOT 都有獨立的指令
- ⚡ **簡化結構**：所有核心檔案都在根目錄，易於維護

## 📁 專案結構

```
Kikyo Discord BOT/
├── main.py                    # 主程式 - 多 Bot 啟動器
├── character_bot.py           # 角色 Bot 核心邏輯
├── character_registry_custom.py  # 角色註冊與設定管理
├── emoji_responses.py         # 表情符號回應系統
├── memory.py                  # Firestore 記憶管理
├── group_conversation_tracker.py  # 群組對話追蹤
├── requirements.txt           # Python 依賴套件
├── README.md                  # 專案說明文件
└── .gitignore                 # Git 忽略檔案設定
```

## 🗄️ Firestore 資料庫結構

```
your-project/
├── {character_id}/
│   ├── profile/               # 角色設定檔
│   ├── users/                 # 使用者記憶（單一文件）
│   │   └── {user_id}: []      # 使用者 ID 對應記憶陣列
│   ├── emoji_system/          # 表情符號管理器
│   │   ├── general_emojis: []
│   │   ├── trigger_emojis: {}
│   │   ├── trigger_keywords: {}
│   │   ├── general_probability: 0.3
│   │   └── server_probability: 0.2
│   └── system/                # 系統配置
│       ├── name: "{character_id}"
│       ├── token_env: "{CHARACTER_ID}_TOKEN"
│       ├── proactive_keywords: []
│       ├── temperature: 1.0
│       ├── top_k: 40
│       ├── top_p: 0.9
│       ├── enabled: true
│       ├── allowed_guilds: []
│       └── allowed_channels: []
```

## 🧠 記憶系統

- **自動記憶**：每次對話後自動使用 AI 提取重要資訊
- **智慧統整**：動態記憶超過 15 則時，自動統整成摘要
- **角色隔離**：每個角色的記憶完全獨立
- **使用者隔離**：每個使用者的記憶分別儲存在單一文件中

## 👥 群組對話追蹤功能

### 功能概述
- **活躍使用者追蹤**：記錄哪些使用者正在與 BOT 對話
- **群組對話上下文**：了解整個對話的脈絡
- **主動提及其他使用者**：BOT 可以自然地提及其他活躍使用者
- **AI 對話摘要**：生成群組對話的摘要
- **BOT 回應追蹤**：記錄 BOT 自己的發言，確保對話連續性

## 🎭 斜線指令系統

### 可用指令

每個角色都有以下斜線指令：

#### `/{character_prefix}_restart`
- **功能**：重新啟動 Bot
- **範例**：`/shen_ze_restart`、`/gu_beichen_restart`

#### `/{character_prefix}_keywords`
- **功能**：顯示角色的主動關鍵字
- **範例**：`/shen_ze_keywords`、`/gu_beichen_keywords`
- **顯示內容**：角色名稱和對應的關鍵字列表

#### `/{character_prefix}_memories`
- **功能**：顯示角色與使用者的記憶內容
- **範例**：`/shen_ze_memories`、`/gu_beichen_memories`

## ⚙️ 配置管理

### 環境變數設定
在 `.env` 檔案中設定以下環境變數：

```bash
# Discord Bot Token 設定（全大寫）
(CHARACTER_ID)_TOKEN=

# 範例：
# SHEN_ZE_TOKEN=
# GU_BEICHEN_TOKEN=
# FAN_CHENGXI_TOKEN=

# Google Gemini API 設定
GOOGLE_API_KEY=

# Firebase 金鑰，必須把所有內容放在同一行
FIREBASE_CREDENTIALS_JSON={"type": "service_account","project_id": ... ,"universe_domain": "googleapis.com"}
```

### Firestore 配置
- **角色設定**：在 `/{character_id}/profile/` 中設定角色資料
- **系統配置**：在 `/{character_id}/system/` 中設定 Bot 參數
- **表情符號**：在 `/{character_id}/emoji_system/` 中設定表情符號和機率
- **權限控制**：在 `/{character_id}/system/` 中設定 `allowed_guilds` 和 `allowed_channels`

## 🔧 開發說明

### 程式碼特色
- **模組化設計**：核心功能分離，易於維護
- **雲端配置**：所有設定都儲存在 Firestore，無需修改程式碼
- **錯誤處理**：完整的異常處理機制
- **日誌記錄**：詳細的運行日誌
- **簡化結構**：移除 core 資料夾，所有檔案都在根目錄

## 📋 環境需求

- **Python 3.9+**
- **Discord.py >= 2.3.0**
- **Firebase Admin SDK >= 6.0.0**
- **Google Generative AI == 0.8.3**
- **其他相依套件**請參考 `requirements.txt`

## 授權
此專案僅供個人使用和學習目的。