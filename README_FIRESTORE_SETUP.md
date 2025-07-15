# Firestore 設定說明

## 你的 Firestore 結構

根據你的需求，Firestore 結構如下：

```
your-project/
├── shen_ze/                    # 沈澤角色
│   ├── profile/                # 角色設定文件
│   └── users memory/           # 使用者記憶子集合
│         ├── discord_user_id_1 # 使用者1的記憶
│         ├── discord_user_id_2 # 使用者2的記憶
│         └── discord_user_id_3 # 使用者3的記憶
└── other_character/            # 其他角色
     ├── profile/               # 角色設定文件
     └── users memory/          # 使用者記憶子集合
           ├── discord_user_id_1
           ├── discord_user_id_2
           └── discord_user_id_3
```

## 設定步驟

### 1. 建立角色設定文件

在 Firestore 中建立以下文件：

**文件路徑**: `shen_ze/profile`
**文件內容**:
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

### 2. 建立使用者記憶結構

**集合路徑**: `shen_ze/users memory/users`
**文件 ID**: Discord 使用者的 ID (例如: `123456789012345678`)
**文件內容**:
```json
{
  "memories": [
    "喜歡看動漫",
    "住在台北",
    "正在學習程式設計"
  ],
  "last_updated": "2024-01-01T00:00:00Z",
  "user_name": "使用者暱稱"
}
```

### 3. 環境變數設定

在 `.env` 檔案中設定：

```env
# Discord Bot Token
DISCORD_TOKEN=your_discord_bot_token

# Firebase 憑證 (JSON 格式)
FIREBASE_CREDENTIALS_JSON={"type": "service_account", "project_id": "your-project", ...}

# Gemini API Key
GEMINI_API_KEY=your_gemini_api_key

# 允許的伺服器和頻道
ALLOWED_GUILDS=123456789012345678,987654321098765432
ALLOWED_CHANNELS=123456789012345678,987654321098765432

# Bot 擁有者 ID
BOT_OWNER_IDS=123456789012345678
```

## 如何新增新角色

### 1. 建立角色設定

在 Firestore 中建立新的角色文件：

**文件路徑**: `new_character/profile`
**文件內容**:
```json
{
  "name": "新角色名稱",
  "personality": "角色性格描述",
  "background": "角色背景故事",
  "speaking_style": "說話風格",
  "interests": ["興趣1", "興趣2"],
  "relationships": "與其他角色的關係"
}
```

### 2. 建立使用者記憶集合

**集合路徑**: `new_character/users memory/users`

### 3. 在 bot.py 中註冊角色

修改 `bot.py` 中的 `register_all_characters()` 函式：

```python
def register_all_characters():
    """註冊所有可用的角色"""
    characters_to_register = [
        "shen_ze",
        "new_character",  # 新增你的角色
    ]
    
    for character_id in characters_to_register:
        success = character_registry.register_character(character_id)
        if success:
            print(f"✅ 成功註冊角色: {character_id}")
        else:
            print(f"❌ 註冊角色失敗: {character_id}")
```

### 4. 建立角色處理器

在 `bots/` 資料夾中建立 `new_character.py`：

```python
from core.character_handler import handle_character_message

# --- 角色專屬設定 ---
CHARACTER_ID = "new_character"
PROACTIVE_KEYWORDS = ["關鍵字1", "關鍵字2"]

def setup_new_character_handlers(client, character_registry, ALLOWED_GUILD_IDS, ALLOWED_CHANNEL_IDS):
    """設定新角色的處理器"""
    
    @client.event
    async def on_message(message):
        if message.author == client.user:
            return

        # 安全措施：只允許特定伺服器和頻道
        if message.guild is not None:
            if ALLOWED_GUILD_IDS and message.guild.id not in ALLOWED_GUILD_IDS:
                return
            if ALLOWED_CHANNEL_IDS and message.channel.id not in ALLOWED_CHANNEL_IDS:
                return
        else:
            return # 不允許私訊

        # 使用通用的角色處理函式
        await handle_character_message(
            message=message,
            character_id=CHARACTER_ID,
            character_registry=character_registry,
            client=client,
            proactive_keywords=PROACTIVE_KEYWORDS
        )
```

### 5. 在 bot.py 中設定處理器

```python
# --- 導入角色處理器 ---
from bots.shen_ze import setup_shen_ze_handlers
from bots.new_character import setup_new_character_handlers  # 新增

# --- 設定角色處理器 ---
setup_shen_ze_handlers(client, character_registry, ALLOWED_GUILD_IDS, ALLOWED_CHANNEL_IDS)
setup_new_character_handlers(client, character_registry, ALLOWED_GUILD_IDS, ALLOWED_CHANNEL_IDS)  # 新增
```

## 資料結構說明

### 角色設定 (profile)
- **name**: 角色名稱
- **personality**: 角色性格
- **background**: 背景故事
- **speaking_style**: 說話風格
- **interests**: 興趣愛好 (陣列)
- **relationships**: 與其他角色的關係

### 使用者記憶 (users memory/users)
- **memories**: 記憶列表 (陣列)
- **last_updated**: 最後更新時間
- **user_name**: 使用者暱稱

## 注意事項

1. **文件 ID**: 使用者記憶的文件 ID 必須是 Discord 使用者的 ID
2. **集合名稱**: 必須完全符合 `users memory` (包含空格)
3. **子集合**: 使用者記憶必須在 `users` 子集合中
4. **權限設定**: 確保 Firebase 安全規則允許讀寫操作

## 故障排除

### 角色設定讀取失敗
- 檢查 `character_id/profile` 文件是否存在
- 確認文件內容格式正確
- 檢查 Firebase 連線狀態

### 記憶無法儲存
- 確認 `character_id/users memory/users` 集合存在
- 檢查使用者 ID 格式正確
- 確認 Firebase 權限設定

### 角色無法回應
- 確認角色已在 `bot.py` 中註冊
- 檢查角色處理器是否正確設定
- 確認關鍵字設定正確 