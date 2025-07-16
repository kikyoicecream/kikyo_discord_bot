# Kikyo Discord BOT 系統

多角色 Discord Bot 系統，支援獨立的虛擬人物角色，每個角色都有專屬的 Discord Token 和記憶系統。具備智能群組對話追蹤功能，讓 BOT 能夠感知多使用者對話環境並自然地與所有參與者互動。

## 快速開始

1. 複製 `env_example.txt` 為 `.env` 並填入您的設定
2. 安裝相依套件：`pip install -r requirements.txt`
3. 使用多 Bot 啟動器：`python3 multi_bot_launcher.py`

## 系統特色

- 🎭 **多角色支援**：每個角色都是獨立的 Discord Bot
- 🧠 **智能記憶**：使用 Firestore 儲存每個使用者的對話記憶
- 👥 **群組對話追蹤**：追蹤活躍使用者，支援多使用者群組對話
- 🔧 **靈活權限**：支援全域或個別 Bot 權限設定
- 🚀 **自動重啟**：Bot 異常時自動重啟功能
- 📱 **管理介面**：互動式多 Bot 管理系統

## 角色介紹

### 沈澤 (`shen_ze`)
- 溫和的大叔角色，退休教師
- 關鍵字：`沈澤`, `shen_ze`, `沈`, `澤`, `叔叔`
- 性格：親切照顧人，經常稱呼對方為「孩子」或「年輕人」

### 顧北辰 (`gu_beichen`)
- 冷酷的角色
- 關鍵字：`顧北辰`, `gu_beichen`, `顧`, `北辰`, `beichen`

## 檔案結構

```
Kikyo Discord BOT/
├── README.md                    # 主要說明文件
├── multi_bot_launcher.py        # 多 Bot 啟動器
├── bot.py                       # 單一 Bot 啟動器（舊版）
├── requirements.txt             # Python 套件需求
├── mypy.ini                     # 型別檢查設定
├── env_example.txt              # 環境變數範例
├── bots/                        # 各角色 Bot 檔案
│   ├── shen_ze.py              # 沈澤 Bot
│   └── gu_beichen.py           # 顧北辰 Bot
└── core/                        # 核心系統
    ├── character_bot.py        # 通用 Bot 模板
    ├── character_registry_custom.py # 角色註冊系統
    ├── memory.py               # 記憶管理系統
    └── group_conversation_tracker.py # 群組對話追蹤系統
```

## 使用方式

### 啟動單一 Bot
```bash
# 啟動沈澤 Bot
python3 bots/shen_ze.py

# 啟動顧北辰 Bot
python3 bots/gu_beichen.py
```

### 啟動多個 Bot
```bash
# 使用管理介面
python3 multi_bot_launcher.py
```

## 環境設定

### 基本設定
在 `.env` 檔案中設定：

```env
# Discord Bot Tokens (每個角色需要獨立的 Token)
SHEN_ZE_TOKEN=your_shen_ze_bot_token_here
GU_BEICHEN_TOKEN=your_gu_beichen_bot_token_here

# Firebase 和 AI 設定
FIREBASE_CREDENTIALS_JSON={"type":"service_account","project_id":"your-project-id",...}
GEMINI_API_KEY=your_gemini_api_key_here

# 權限設定
ALLOWED_GUILDS=123456789,987654321
ALLOWED_CHANNELS=111111111,222222222
BOT_OWNER_IDS=333333333,444444444
```

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

**權限優先順序**：
1. 個別 Bot 設定 (例如 `SHEN_ZE_ALLOWED_GUILDS`)
2. 全域設定 (例如 `ALLOWED_GUILDS`)
3. 如果都沒有設定，Bot 將無法運作

#### 如何獲取 Discord ID

1. **開啟開發者模式**：Discord 設定 → 進階 → 開發者模式
2. **獲取伺服器 ID**：右鍵點擊伺服器名稱 → 複製伺服器 ID
3. **獲取頻道 ID**：右鍵點擊頻道名稱 → 複製頻道 ID
4. **獲取使用者 ID**：右鍵點擊使用者名稱 → 複製使用者 ID

## Firestore 設定

### 資料庫結構
```
your-project/
├── shen_ze/                    # 沈澤角色
│   ├── profile/                # 角色設定
│   ├── users/                  # 使用者資料
│   │   └── memory/             # 記憶集合
│   │       └── discord_user_id/ # 使用者記憶
│   │           ├── memories: ["記憶1", "記憶2", ...]
│   │           └── last_updated: timestamp
│   └── group_context/          # 群組對話上下文
│       └── channels/           # 頻道集合
│           └── channel_id/     # 頻道對話記錄
│               ├── active_users: [使用者資料]
│               ├── recent_context: [對話記錄]
│               └── summary: "對話摘要"
└── gu_beichen/                 # 顧北辰角色
    ├── profile/                # 角色設定
    ├── users/                  # 使用者資料
    └── group_context/          # 群組對話上下文
```

### 角色設定範例
在 Firestore 中建立角色設定文件：

**文件路徑**: `shen_ze/profile`
```json
{
  "name": "沈澤",
  "personality": "溫和的大叔，喜歡照顧人，說話風格親切",
  "background": "沈澤是一個經驗豐富的大叔，喜歡幫助年輕人解決問題",
  "speaking_style": "使用親切的語氣，經常稱呼對方為「孩子」或「年輕人」",
  "interests": ["照顧他人", "分享經驗", "聆聽故事"],
  "relationships": "對所有使用者都像長輩一樣關懷",
  "age": "45歲",
  "occupation": "退休教師"
}
```

## 群組對話追蹤功能

### 功能概述
系統具備完整的群組對話追蹤功能，讓 BOT 能夠：

1. **追蹤活躍使用者**：記錄哪些使用者正在與 BOT 對話
2. **群組對話上下文**：了解整個對話的脈絡
3. **主動提及其他使用者**：BOT 可以自然地提及其他活躍使用者
4. **智能對話摘要**：生成群組對話的摘要

### 技術架構
- **核心模組**：`core/group_conversation_tracker.py`
- **資料結構**：支援多角色、多頻道的獨立追蹤
- **BOT回應追蹤**：記錄BOT自己的發言，確保對話連續性
- **持久化儲存**：重要資料保存到 Firestore
- **智能清理**：自動清理過期活動記錄

### 使用範例

#### 多使用者群組對話
```
小明：大家好！今天天氣真好
小華：嗨！我在這裡
小美：大家好！我是新來的
小明：歡迎小美！

沈澤：「看到大家都很活躍呢！小明，你提到天氣很好，確實是個適合聊天的日子。小華，你也在這裡，我們可以一起歡迎小美。小美，歡迎加入我們的對話！」
```

#### 智能提及其他使用者
```
小明：有人想討論電影嗎？
小華：我喜歡科幻片
小美：我比較喜歡愛情片

沈澤：「電影話題很有趣呢！小明，你開啟了這個話題。小華喜歡科幻片，小美偏好愛情片，大家的品味都很不一樣。要不要分享一下最近看過的好電影？」
```

#### 對話連續性（BOT回應追蹤）
```
小明：沈澤叔叔，你覺得今天適合做什麼？
沈澤：「小華，今天天氣這麼好，很適合出去走走或者在家裡做些輕鬆的事情呢。」

小明：沈澤叔叔，你剛才說適合出去走走，有什麼建議嗎？
沈澤：「小明，你還記得我剛才說的話呢！我建議可以去公園散步，或者找個咖啡廳坐坐。」

小美：沈澤，你提到的咖啡廳聽起來不錯
沈澤：「小美，你也對咖啡廳感興趣嗎？我可以推薦幾個不錯的地方。」
```

### 管理功能
- **查看活躍使用者**：使用 `/active_users` 指令
- **對話摘要**：自動生成群組對話摘要
- **使用者統計**：顯示使用者訊息數和最後活動時間

## 如何新增新角色

### 1. 建立角色 Bot 檔案

```python
#!/usr/bin/env python3
"""
新角色 Discord Bot
"""
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.character_bot import run_character_bot_with_restart

# --- 角色專屬設定 ---
CHARACTER_ID = "new_character"
TOKEN_ENV_VAR = "NEW_CHARACTER_TOKEN"
PROACTIVE_KEYWORDS = ["新角色", "關鍵字1", "關鍵字2"]

def main():
    """啟動新角色 Bot"""
    print("🎭 新角色 Discord Bot")
    print("=" * 50)
    
    run_character_bot_with_restart(CHARACTER_ID, TOKEN_ENV_VAR, PROACTIVE_KEYWORDS)

if __name__ == "__main__":
    main()
```

### 2. 設定環境變數
在 `.env` 檔案中新增：
```env
NEW_CHARACTER_TOKEN=your_new_character_bot_token_here
```

### 3. 建立 Firestore 角色設定
在 Firestore 中建立 `new_character/profile` 文件。

### 4. 更新多 Bot 啟動器
修改 `multi_bot_launcher.py` 中的 `AVAILABLE_BOTS` 列表。

## 系統功能

### 記憶管理
- **自動記憶**：系統會自動記錄使用者的對話內容
- **記憶整理**：當記憶超過 15 則時，自動使用 AI 整理成摘要
- **角色隔離**：每個角色的記憶完全獨立

### 對話觸發
- **提及觸發**：`@Bot 你好`
- **關鍵字觸發**：`沈澤叔叔，今天天氣如何？`

### 群組對話功能
- **活躍使用者追蹤**：自動記錄參與對話的使用者
- **群組上下文**：BOT 了解整個對話脈絡
- **BOT回應追蹤**：記錄BOT自己的發言，確保對話連續性
- **智能提及**：BOT 可以自然地提及其他活躍使用者
- **對話摘要**：生成群組對話的智能摘要

### 管理命令
- `/restart` - 重啟 Bot
- `/info` - 顯示角色資訊
- `/memory_stats` - 顯示記憶統計
- `/active_users` - 顯示活躍使用者（僅限擁有者）

## 故障排除

### 角色無法回應
1. 檢查 Discord Token 是否正確
2. 確認 Firestore 中有對應的角色設定
3. 檢查伺服器和頻道權限設定
4. 確認關鍵字設定正確

### 記憶無法儲存
1. 確認 Firebase 連線正常
2. 檢查 Firestore 權限設定
3. 查看錯誤日誌

### Bot 無法啟動
1. 檢查環境變數設定
2. 確認所有相依套件已安裝
3. 檢查 Python 版本 (需要 3.9+)

## 環境需求

- Python 3.9+
- Discord.py
- Firebase Admin SDK
- Google Generative AI
- 其他相依套件請參考 `requirements.txt`

## 授權

此專案僅供個人使用和學習目的。 