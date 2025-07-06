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
from keep_alive import keep_alive
keep_alive()

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

# 載入 .env 檔案中的環境變數
load_dotenv()
DISCORD_TOKEN = os.getenv('DISCORD_TOKEN')
GEMINI_API_KEY = os.getenv('GEMINI_API_KEY')
FIREBASE_CREDENTIALS_JSON = os.getenv('FIREBASE_CREDENTIALS_JSON')

# 檢查 Token 和 API Key 是否成功載入
if not DISCORD_TOKEN or not GEMINI_API_KEY:
    print("錯誤：請在 .env 檔案中設定 DISCORD_TOKEN 和 GEMINI_API_KEY")
    exit()

# --- 初始化 Firebase ---
try:
    if FIREBASE_CREDENTIALS_JSON:
        firebase_creds_dict = json.loads(FIREBASE_CREDENTIALS_JSON)
        cred = credentials.Certificate(firebase_creds_dict)
        firebase_admin.initialize_app(cred)
        db = firestore.client()
        print("Firebase 初始化成功")
    else:
        print("錯誤：找不到 FIREBASE_CREDENTIALS_JSON 環境變數")
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

def format_character_profile(persona: dict) -> str:
    profile_lines = ["# Character Profile"]
    for key, value in persona.items():
        # 將 key 轉為首字母大寫 + 替換底線
        key_formatted = key.replace("_", " ").capitalize()

        # 如果是 list，就 join 起來
        if isinstance(value, list):
            value = ", ".join(value)
        elif value is None or value == "":
            continue  # 跳過空值

        profile_lines.append(f"- {key_formatted}: {value}")

    return "\n".join(profile_lines)

# --- Bot 事件處理 ---
@client.event
async def on_ready():
    print(f'Bot 已成功登入為 {client.user}')
    #await client.change_presence(activity=discord.Game(name="叔叔幫你準備早餐好嗎？"))

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
                    
                    if message.guild.me.nick != target_nick:
                        try:
                            await message.guild.me.edit(nick=target_nick)
                        except discord.Forbidden:
                            print("Bot 沒有權限更改暱稱")
                            await message.channel.send("我沒辦法更改暱稱，可能因為權限不足，請確認我在伺服器的角色設定。")

                    channel_id = message.channel.id
                    history = conversation_histories.get(channel_id, [])

                    formatted_history = "\n".join(
                        f"{user_name if msg['role'] == 'user' else bot_name}: {msg['parts'][0]}"
                        for msg in history
                    )
                    
                    system_prompt = f"""

                    # Character Profile
                    {format_character_profile(persona)}

                    # 過去的對話紀錄
                    {formatted_history}

                    # 對話情境
                    你是「{user_name}」生活已久的照顧者，彼此關係親密且曖昧不明。你必須根據以上角色檔案和過去的對話紀錄回應，絕不可脫離角色。
                    ---
                    {user_name}: 「{user_prompt}」
                    {bot_name}:
                    """

                    # 建立包含歷史的聊天 session
                    chat_session = gemini_model.start_chat(history=history)

                    # 定義生成設定，限制最大輸出 Token 數量
                    generation_config = genai_types.GenerationConfig(
                        max_output_tokens=persona.get('max_output_tokens', 1024),
                        temperature=persona.get('temperature', 0.9),
                        top_p=persona.get('top_p', 1),
                        top_k=persona.get('top_k', 40)
                    )
                    
                    # 定義安全設定
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

                    model_reply = None
                    # 安全處理 Gemini 回應
                    try:
                        if not response.candidates:
                            print("Gemini 沒有回應候選內容")
                        elif not response.candidates[0].content.parts:
                            finish_reason = response.candidates[0].finish_reason
                            print(f"Gemini 回應為空，finish_reason: {finish_reason}")
                        else:
                            model_reply = response.text
                    except Exception as e:
                        print(f"Gemini 回應解析失敗：{e}")
                        print(traceback.format_exc())

                    # 加入對話歷史
                    if model_reply:
                        history.append({'role': 'user', 'parts': [user_prompt]})
                        history.append({'role': 'model', 'parts': [model_reply]})

                        if len(history) > 5:
                            history = history[-5:]

                        conversation_histories[channel_id] = history

                        await message.reply(model_reply, mention_author=False)
                        print(f"✅ 成功回應 {message.author.display_name}：{model_reply[:20]}...")
                    else:
                        print("未產生 model_reply，跳過回覆。")
                    
            except Exception as e:
                await message.reply("抱歉，我的思緒好像有些混亂⋯⋯可以請妳再說一次嗎？", mention_author=False)
                print(f"錯誤細節：{e}")
                print(traceback.format_exc())
                    
# --- 啟動 Bot ---
client.run(DISCORD_TOKEN)