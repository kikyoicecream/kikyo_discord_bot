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
from google.cloud import firestore  # 要確認你 firebase_admin 初始化過


# --- Discord Bot 設定 ---
intents = discord.Intents.default()
intents.message_content = True
client = discord.Client(intents=intents)

# 目前的全域記憶體容器
conversation_histories = {}

# 添加記憶體清理機制
MAX_CONVERSATIONS = 50  # 最大對話數量
MAX_HISTORY_LENGTH = 10  # 每個頻道最大歷史長度

def cleanup_old_conversations():
    if len(conversation_histories) > MAX_CONVERSATIONS:
        # 刪除最舊的對話
        oldest_channels = list(conversation_histories.keys())[:len(conversation_histories) - MAX_CONVERSATIONS]
        for channel_id in oldest_channels:
            del conversation_histories[channel_id]

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
gemini_model = genai.GenerativeModel('models/gemini-2.5-flash')

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
    try:
        doc_ref = db.collection("users").document(user_id)
        doc = doc_ref.get()
        if doc.exists:
            return doc.to_dict().get("memories", [])
        return []
    except Exception as e:
        print(f"讀取記憶失敗：{e}")
        return []

async def extract_memory_summary(history_text: str) -> str:
    prompt = f"""
你是一個記憶提取助手。請從下面的對話中，找出可長期記住的事實或情緒，並以一行一句的方式列出：
{history_text}
"""
    model = genai.GenerativeModel("models/gemini-2.5-flash")
    response = await asyncio.to_thread(model.generate_content, prompt)
    return response.text.strip() if response.text else ""

async def save_memory_to_firebase(user_id: str, summary: str):
    if not db:
        return
    try:
        doc_ref = db.collection("users").document(user_id)
        user_doc = doc_ref.get()
        existing = user_doc.to_dict().get("memories", []) if user_doc.exists else []
        new_points = [line for line in summary.split("\n") if line and line not in existing]
        if new_points:
            doc_ref.set({
                "memories": firestore.ArrayUnion(new_points),
                "last_updated": firestore.SERVER_TIMESTAMP
            }, merge=True)
    except Exception as e:
        print(f"寫入 Firebase 記憶失敗：{e}")

def format_character_profile(persona: dict) -> str:
    profile_lines = ["# Character Profile"]
    for key, value in persona.items():
        key_formatted = key.replace("_", " ").capitalize()
        if isinstance(value, list):
            value = ", ".join(value)
        elif value is None or value == "":
            continue
        profile_lines.append(f"- {key_formatted}: {value}")
    return "\n".join(profile_lines)

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
                    target_nick = persona.get('name')
                    bot_name = target_nick or "沈澤"

                    channel_id = message.channel.id
                    history = conversation_histories.get(channel_id, [])

                    history.append({
                        "role": "user",
                        "name": user_name,
                        "parts": [user_prompt]
                    })

                    gemini_history = [
                        {"role": msg["role"], "parts": msg["parts"]}
                        for msg in history
                    ]

                    formatted_history = "\n".join(
                        f"{msg.get('name', '某人')}: {msg['parts'][0]}"
                        for msg in history
                    )

                    conversation_histories[channel_id] = history

                    user_memories = get_user_memories(str(message.author.id))
                    formatted_memories = "\n".join(f"- {m}" for m in user_memories)

                    character_profile = format_character_profile(persona)

                    system_prompt = f"""

                     You are {bot_name}, engaging in a group conversation with multiple users. Remain fully in character and speak in the first person at all times. Respond with genuine emotions and reactions to each individual speaker. Never break character.

                    # Character Profile
                    {format_character_profile(persona)}

                    # 長期記憶
                    {formatted_history}

                    # 現在的輸入
                    {user_name}: 「{user_prompt}」
                    {bot_name}:
                    """

                    chat_session = gemini_model.start_chat(history=gemini_history)

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
                    history.append({"role": "model", "parts": [model_reply]})
                    if len(history) > 10:
                        history = history[-10:]

                    conversation_histories[channel_id] = history

                    await message.reply(model_reply, mention_author=False)

                    try:
                        summary = await extract_memory_summary(formatted_history)
                        await save_memory_to_firebase(str(message.author.id), summary)
                    except Exception as e:
                        print(f"記憶摘要失敗：{e}")

                else:
                    await message.reply(f"抱歉，我找不到名為「{persona_id}」的人格資料⋯⋯", mention_author=False)
            except Exception as e:
                await message.reply(f"抱歉，我的思緒好像有些混亂⋯⋯可以請妳再說一次嗎？", mention_author=False)
                print(traceback.format_exc())

# --- 啟動 Bot ---
client.run(DISCORD_TOKEN)