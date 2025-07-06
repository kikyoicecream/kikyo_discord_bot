import discord
import os
import google.generativeai as genai
import asyncio
from dotenv import load_dotenv
import firebase_admin
from firebase_admin import credentials, firestore
from google.generativeai.types import HarmCategory, HarmBlockThreshold
import json
import google.generativeai.types as genai_types
import re
import traceback
from datetime import datetime, timedelta

# --- Discord Bot 設定 ---
intents = discord.Intents.default()
intents.message_content = True
client = discord.Client(intents=intents)

# 對話歷史和活躍用戶追蹤
conversation_histories = {}
active_users = {}  # 追蹤每個頻道的活躍用戶

# 記憶體管理
MAX_CONVERSATIONS = 50
MAX_HISTORY_LENGTH = 15  # 增加到15條以便更好處理群聊
ACTIVE_USER_TIMEOUT = 300  # 5分鐘後認為用戶不活躍

def cleanup_old_conversations():
    if len(conversation_histories) > MAX_CONVERSATIONS:
        oldest_channels = list(conversation_histories.keys())[:len(conversation_histories) - MAX_CONVERSATIONS]
        for channel_id in oldest_channels:
            del conversation_histories[channel_id]
            if channel_id in active_users:
                del active_users[channel_id]

def update_active_users(channel_id: int, user_id: str, user_name: str):
    """更新頻道中的活躍用戶列表"""
    if channel_id not in active_users:
        active_users[channel_id] = {}
    
    active_users[channel_id][user_id] = {
        'name': user_name,
        'last_active': datetime.now()
    }
    
    # 清理不活躍的用戶
    cutoff_time = datetime.now() - timedelta(seconds=ACTIVE_USER_TIMEOUT)
    active_users[channel_id] = {
        uid: info for uid, info in active_users[channel_id].items()
        if info['last_active'] > cutoff_time
    }

def get_active_users_list(channel_id: int) -> list:
    """獲取頻道中的活躍用戶列表"""
    if channel_id not in active_users:
        return []
    
    cutoff_time = datetime.now() - timedelta(seconds=ACTIVE_USER_TIMEOUT)
    return [
        info['name'] for uid, info in active_users[channel_id].items()
        if info['last_active'] > cutoff_time
    ]

# --- 初始化設定 ---
load_dotenv()
DISCORD_TOKEN = os.getenv('DISCORD_TOKEN')
GEMINI_API_KEY = os.getenv('GEMINI_API_KEY')
FIREBASE_CREDENTIALS_JSON = os.getenv('FIREBASE_CREDENTIALS_JSON')

if not DISCORD_TOKEN or not GEMINI_API_KEY:
    print("錯誤：請在 .env 檔案中設定 DISCORD_TOKEN 和 GEMINI_API_KEY")
    exit()

# --- 初始化 Firebase ---
try:
    firebase_creds_json = os.getenv('FIREBASE_CREDENTIALS_JSON')
    if firebase_creds_json:
        firebase_creds_dict = json.loads(firebase_creds_json)
        cred = credentials.Certificate(firebase_creds_dict)
        firebase_admin.initialize_app(cred)
        db = firestore.client()
        print("Firebase 初始化成功 (來自 Secret)。")
    else:
        print("錯誤：找不到 FIREBASE_CREDENTIALS_JSON 這個 Secret。")
        db = None
except Exception as e:
    print(f"Firebase 初始化失敗: {e}")
    db = None

# --- 初始化 Gemini AI ---
genai.configure(api_key=GEMINI_API_KEY)
gemini_model = genai.GenerativeModel('models/gemini-2.0-flash')

# --- 輔助函式 ---
def get_character_persona(persona_id):
    if not db:
        print("Firestore 未初始化，無法讀取角色設定。")
        return None
    try:
        doc_ref = db.collection('character_personas').document(persona_id)
        doc = doc_ref.get()
        if doc.exists:
            return doc.to_dict()
        else:
            print(f"錯誤：在 Firestore 中找不到 ID 為 {persona_id} 的角色設定")
            return None
    except Exception as e:
        print(f"讀取 Firestore 時發生錯誤: {e}")
        return None

def get_user_memories(user_id: str):
    """從 Firebase 讀取用戶的長期記憶"""
    if not db:
        return []
    try:
        doc_ref = db.collection("users").document(user_id)
        doc = doc_ref.get()
        if doc.exists:
            return doc.to_dict().get("memories", [])
        return []
    except Exception as e:
        print(f"讀取記憶失敗：{e}")
        return []

def get_multiple_user_memories(user_ids: list) -> dict:
    """批量獲取多個用戶的記憶"""
    if not db:
        return {}
    
    memories = {}
    for user_id in user_ids:
        try:
            doc_ref = db.collection("users").document(user_id)
            doc = doc_ref.get()
            if doc.exists:
                user_memories = doc.to_dict().get("memories", [])
                if user_memories:
                    memories[user_id] = user_memories
        except Exception as e:
            print(f"讀取用戶 {user_id} 記憶失敗：{e}")
    
    return memories

async def extract_memory_summary(new_messages: list, current_user_name: str) -> str:
    """從新的對話消息中提取關於當前用戶的記憶摘要"""
    if not new_messages:
        return ""
    
    # 過濾出當前用戶的消息
    user_messages = [
        msg for msg in new_messages 
        if msg.get('name') == current_user_name and msg.get('role') == 'user'
    ]
    
    if not user_messages:
        return ""
    
    # 格式化對話內容，包含上下文
    messages_text = "\n".join([
        f"{msg.get('name', '某人')}: {msg['parts'][0]}"
        for msg in new_messages
    ])
    
    prompt = f"""
你是一個記憶提取助手。請從下面的群組對話中，找出關於 {current_user_name} 的重要資訊，包括：個人偏好、興趣愛好、重要的生活事件或經歷、情感狀態或性格特徵、與其他用戶的關係或互動、其他值得長期記住的事實。

對話內容：
{messages_text}

請只提取關於 {current_user_name} 的資訊，以簡潔的句子列出，每行一個重點，不要使用數字編號或任何格式符號。
如果沒有值得記住的重要資訊，請回覆「無」。

範例格式：
喜歡看動漫
住在台北
最近在學習程式設計
與其他用戶關係良好
"""
    
    try:
        model = genai.GenerativeModel("models/gemini-2.0-flash")
        response = await asyncio.to_thread(model.generate_content, prompt)
        result = response.text.strip() if response.text else ""
        
        # 額外清理：移除可能的數字編號
        if result and result != "無":
            lines = result.split('\n')
            cleaned_lines = []
            for line in lines:
                # 移除行首的數字編號（如 "1. ", "2. " 等）
                cleaned_line = re.sub(r'^\d+\.\s*', '', line.strip())
                # 移除行首的破折號或其他符號
                cleaned_line = re.sub(r'^[-•*]\s*', '', cleaned_line)
                if cleaned_line:
                    cleaned_lines.append(cleaned_line)
            result = '\n'.join(cleaned_lines)
        
        return result if result != "無" else ""
    except Exception as e:
        print(f"記憶摘要提取失敗：{e}")
        return ""

async def save_memory_to_firebase(user_id: str, summary: str):
    """將新的記憶摘要保存到 Firebase"""
    if not db or not summary:
        return
    try:
        doc_ref = db.collection("users").document(user_id)
        user_doc = doc_ref.get()
        existing = user_doc.to_dict().get("memories", []) if user_doc.exists else []
        
        new_points = [line.strip() for line in summary.split("\n") if line.strip()]
        
        unique_new_points = []
        for point in new_points:
            if not any(point.lower() in existing_memory.lower() for existing_memory in existing):
                unique_new_points.append(point)
        
        if unique_new_points:
            all_memories = existing + unique_new_points
            if len(all_memories) > 50:
                all_memories = all_memories[-50:]
            
            doc_ref.set({
                "memories": all_memories,
                "last_updated": firestore.SERVER_TIMESTAMP
            }, merge=True)
            print(f"已為用戶 {user_id} 保存 {len(unique_new_points)} 條新記憶")
    except Exception as e:
        print(f"寫入 Firebase 記憶失敗：{e}")

def format_character_profile(persona: dict) -> str:
    """格式化角色資料"""
    profile_lines = []
    for key, value in persona.items():
        key_formatted = key.replace("_", " ").capitalize()
        if isinstance(value, list):
            value = ", ".join(value)
        elif value is None or value == "":
            continue
        profile_lines.append(f"- {key_formatted}: {value}")
    return "\n".join(profile_lines)

def format_group_memories(memories_dict: dict, active_users_dict: dict) -> str:
    """格式化群組中活躍用戶的記憶"""
    if not memories_dict:
        return "目前沒有關於其他用戶的記憶記錄"
    
    formatted_memories = []
    for user_id, memories in memories_dict.items():
        # 找到用戶名稱
        user_name = "未知用戶"
        for uid, info in active_users_dict.items():
            if uid == user_id:
                user_name = info['name']
                break
        
        if memories:
            formatted_memories.append(f"關於 {user_name}:")
            for memory in memories[-5:]:  # 只顯示最近5條記憶
                formatted_memories.append(f"  - {memory}")
    
    return "\n".join(formatted_memories) if formatted_memories else "目前沒有關於其他用戶的記憶記錄"

# --- Bot 事件處理 ---
@client.event
async def on_ready():
    print(f'Bot 已成功登入為 {client.user}')

@client.event
async def on_message(message):
    if message.author == client.user:
        return

    if client.user.mentioned_in(message):
        persona_id = 'shen_ze'
        user_prompt = message.content
        for mention in message.mentions:
            if mention == client.user:
                user_prompt = user_prompt.replace(f'<@{mention.id}>', '')
        user_prompt = user_prompt.strip()

        # 檢查是否指定了特定角色
        match = re.search(r'persona\s*:\s*(\w+)', user_prompt, re.IGNORECASE)
        if match:
            persona_id = match.group(1).lower()
            user_prompt = re.sub(r'persona\s*:\s*\w+\s*', '', user_prompt, flags=re.IGNORECASE).strip()

        if not user_prompt:
            async with message.channel.typing():
                await asyncio.sleep(1)
                await message.reply("請問，找我有什麼事嗎？", mention_author=False)
            return

        async with message.channel.typing():
            try:
                persona = get_character_persona(persona_id)
                if persona:
                    user_name = message.author.display_name
                    user_id = str(message.author.id)
                    channel_id = message.channel.id
                    target_nick = persona.get('name')
                    bot_name = target_nick or "沈澤"

                    # 更新活躍用戶
                    update_active_users(channel_id, user_id, user_name)
                    
                    # 獲取對話歷史
                    history = conversation_histories.get(channel_id, [])
                    history_length_before = len(history)

                    # 添加用戶消息
                    history.append({
                        "role": "user",
                        "name": user_name,
                        "user_id": user_id,  # 添加用戶ID
                        "parts": [user_prompt]
                    })

                    # 準備 Gemini 的對話歷史
                    gemini_history = [
                        {"role": msg["role"], "parts": msg["parts"]}
                        for msg in history
                    ]

                    # 獲取當前用戶的記憶
                    user_memories = get_user_memories(user_id)
                    current_user_memories = "\n".join(f"- {m}" for m in user_memories) if user_memories else "尚無記錄"

                    # 獲取群組中其他活躍用戶的記憶
                    active_users_in_channel = active_users.get(channel_id, {})
                    other_user_ids = [uid for uid in active_users_in_channel.keys() if uid != user_id]
                    group_memories = get_multiple_user_memories(other_user_ids)
                    formatted_group_memories = format_group_memories(group_memories, active_users_in_channel)

                    # 獲取活躍用戶列表
                    active_users_list = get_active_users_list(channel_id)
                    active_users_text = ", ".join(active_users_list) if active_users_list else "只有你"

                    # 格式化近期對話（顯示說話者）
                    recent_history = "\n".join([
                        f"[{msg.get('name', '某人')}]: {msg['parts'][0]}"
                        for msg in history[-8:]  # 顯示最近8條對話
                    ])

                    # 格式化角色資料
                    character_profile = format_character_profile(persona)

                    # 構建系統提示詞
                    system_prompt = f"""
你是 {bot_name}，正在參與一個群組對話。請始終保持角色設定，以第一人稱回應，展現真實的情感和反應。

## 角色設定
{character_profile}

## 群組對話情況
- 目前活躍的用戶: {active_users_text}
- 剛剛與你對話的是: {user_name}

## 關於 {user_name} 的長期記憶
{current_user_memories}

## 關於群組中其他用戶的記憶
{formatted_group_memories}

## 近期對話脈絡
{recent_history}

## 當前輸入
[{user_name}]: {user_prompt}

請以 {bot_name} 的身份回應，注意：
1. 要意識到這是群組對話，可能有多人參與
2. 可以根據記憶和對話內容自然地提及其他用戶
3. 回應要符合你的角色設定
4. 保持對話的連貫性和真實感
"""

                    # 開始對話
                    chat_session = gemini_model.start_chat(history=gemini_history[:-1])

                    generation_config = genai_types.GenerationConfig(max_output_tokens=1024)
                    safety_settings = [
                        {"category": HarmCategory.HARM_CATEGORY_HARASSMENT, "threshold": HarmBlockThreshold.BLOCK_NONE},
                        {"category": HarmCategory.HARM_CATEGORY_HATE_SPEECH, "threshold": HarmBlockThreshold.BLOCK_NONE},
                        {"category": HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT, "threshold": HarmBlockThreshold.BLOCK_NONE},
                        {"category": HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT, "threshold": HarmBlockThreshold.BLOCK_NONE},
                    ]

                    response = await asyncio.to_thread(
                        chat_session.send_message,
                        system_prompt,
                        generation_config=generation_config,
                        safety_settings=safety_settings
                    )

                    model_reply = response.text or "......"
                    
                    # 添加模型回應
                    history.append({
                        "role": "model", 
                        "parts": [model_reply]
                    })
                    
                    # 限制歷史長度
                    if len(history) > MAX_HISTORY_LENGTH:
                        history = history[-MAX_HISTORY_LENGTH:]

                    # 更新對話歷史
                    conversation_histories[channel_id] = history
                    cleanup_old_conversations()

                    # 回覆用戶
                    await message.reply(model_reply, mention_author=False)

                    # 記憶處理：只處理與當前用戶相關的記憶
                    try:
                        new_messages = history[history_length_before:]
                        if len(new_messages) >= 2:
                            summary = await extract_memory_summary(new_messages, user_name)
                            if summary:
                                await save_memory_to_firebase(user_id, summary)
                    except Exception as e:
                        print(f"記憶處理失敗：{e}")

                else:
                    await message.reply(f"抱歉，我找不到名為「{persona_id}」的人格資料⋯⋯", mention_author=False)
                    
            except Exception as e:
                await message.reply(f"抱歉，我的思緒好像有些混亂⋯⋯可以請妳再說一次嗎？", mention_author=False)
                print(f"處理消息時發生錯誤：{e}")
                print(traceback.format_exc())

# --- 啟動 Bot ---
if __name__ == "__main__":
    client.run(DISCORD_TOKEN)