# 角色管理系統使用說明

## 概述

這個角色管理系統允許你管理多個 Discord Bot 角色，每個角色都有：
- 專屬的 Firestore 資料庫 collection
- 獨立的記憶管理
- 個別的對話歷史
- 專屬的關鍵字觸發

## 系統架構

```
core/
├── character_registry.py    # 角色註冊器
├── character_handler.py     # 通用角色處理函式
└── memory.py               # 原有的記憶模組

bots/
├── shen_ze.py              # 神澤角色
├── kikyo.py                # 桔梗角色
└── [其他角色].py           # 未來的新角色

bot.py                      # 主程式，整合所有角色
```

## 如何新增新角色

### 1. 在 Firestore 中建立角色設定

在 `character_personas` collection 中新增一個文件，ID 為角色名稱：

```json
{
  "name": "角色名稱",
  "personality": "角色性格描述",
  "background": "角色背景故事",
  "speaking_style": "說話風格",
  "interests": ["興趣1", "興趣2"],
  "relationships": "與其他角色的關係"
}
```

### 2. 建立角色檔案

在 `bots/` 資料夾中建立新的 Python 檔案，例如 `new_character.py`：

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

### 3. 在 bot.py 中註冊角色

修改 `bot.py` 中的 `register_all_characters()` 函式：

```python
def register_all_characters():
    """註冊所有可用的角色"""
    characters_to_register = [
        "shen_ze",
        "kikyo",
        "new_character",  # 新增你的角色
    ]
    
    for character_id in characters_to_register:
        success = character_registry.register_character(character_id)
        if success:
            print(f"✅ 成功註冊角色: {character_id}")
        else:
            print(f"❌ 註冊角色失敗: {character_id}")
```

然後在 bot.py 中導入並設定角色處理器：

```python
# --- 導入角色處理器 ---
from bots.shen_ze import setup_shen_ze_handlers
from bots.kikyo import setup_kikyo_handlers
from bots.new_character import setup_new_character_handlers  # 新增

# --- 設定角色處理器 ---
setup_shen_ze_handlers(client, character_registry, ALLOWED_GUILD_IDS, ALLOWED_CHANNEL_IDS)
setup_kikyo_handlers(client, character_registry, ALLOWED_GUILD_IDS, ALLOWED_CHANNEL_IDS)
setup_new_character_handlers(client, character_registry, ALLOWED_GUILD_IDS, ALLOWED_CHANNEL_IDS)  # 新增
```

## Firestore 資料結構

### 角色設定 (character_personas collection)
```
character_personas/
├── shen_ze/
│   ├── name: "神澤"
│   ├── personality: "性格描述"
│   └── ...
├── kikyo/
│   ├── name: "桔梗"
│   ├── personality: "性格描述"
│   └── ...
└── [其他角色]/
```

### 角色記憶 (各角色的專屬 collection)
```
shen_ze_memories/
├── user_id_1/
│   ├── memories: ["記憶1", "記憶2"]
│   ├── last_updated: timestamp
│   └── last_consolidated: timestamp
└── user_id_2/
    └── ...

kikyo_memories/
├── user_id_1/
│   ├── memories: ["記憶1", "記憶2"]
│   └── ...
└── user_id_2/
    └── ...
```

## 功能特色

### 1. 記憶隔離
- 每個角色的記憶完全獨立
- 不會互相干擾或混淆

### 2. 對話歷史分離
- 每個角色在每個頻道都有獨立的對話歷史
- 角色之間不會互相影響對話脈絡

### 3. 活躍使用者追蹤
- 每個角色獨立追蹤活躍使用者
- 可以根據不同角色的互動模式調整回應

### 4. 關鍵字觸發
- 每個角色可以設定專屬的關鍵字
- 支援提及 Bot 和關鍵字兩種觸發方式

### 5. 角色切換
- 使用 `persona: 角色名稱` 可以臨時切換角色
- 例如：`persona: kikyo 你好`

## 使用範例

### 觸發神澤角色
- 提及 Bot：`@Bot 你好`
- 關鍵字：`叔叔，今天天氣如何？`

### 觸發桔梗角色
- 提及 Bot：`@Bot 你好`
- 關鍵字：`桔梗姐姐，請幫我占卜`

### 臨時切換角色
- `persona: kikyo 你好，我是新來的`
- `persona: shen_ze 叔叔，我想請教你一件事`

## 注意事項

1. **角色設定**：確保在 Firestore 中有對應的角色設定
2. **記憶管理**：每個角色的記憶會自動整理和壓縮
3. **效能考量**：角色數量會影響記憶體使用量
4. **權限控制**：所有角色都遵循相同的伺服器和頻道限制

## 故障排除

### 角色註冊失敗
- 檢查 Firestore 中是否有對應的角色設定
- 確認角色 ID 拼寫正確
- 檢查 Firebase 連線狀態

### 記憶無法儲存
- 確認 Firebase 權限設定
- 檢查 collection 名稱是否正確
- 查看錯誤日誌

### 角色無法回應
- 確認關鍵字設定正確
- 檢查伺服器和頻道權限
- 確認角色處理器已正確設定 