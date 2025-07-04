import discord
import os
import google.generativeai as genai
import asyncio  # <--- 請將這一行加到妳的 import 區域
from dotenv import load_dotenv
import firebase_admin
from firebase_admin import credentials, firestore
from google.generativeai.types import HarmCategory, HarmBlockThreshold

# --- 初始化設定 ---

# 載入 .env 檔案中的環境變數
load_dotenv()
DISCORD_TOKEN = os.getenv('DISCORD_TOKEN')
GEMINI_API_KEY = os.getenv('GEMINI_API_KEY')

# 檢查 Token 和 API Key 是否成功載入
if not DISCORD_TOKEN or not GEMINI_API_KEY:
    print("錯誤：請在 .env 檔案中設定 DISCORD_TOKEN 和 GEMINI_API_KEY")
    exit()

# --- 初始化 Firebase ---
try:
    # 請確保妳的憑證檔案名稱與這裡一致
    cred = credentials.Certificate('serviceAccountKey.json')
    firebase_admin.initialize_app(cred)
    db = firestore.client()
    print("Firebase 初始化成功。")
except FileNotFoundError:
    print("錯誤：找不到 'serviceAccountKey.json' 檔案。請確認它與 bot.py 在同一個資料夾中。")
    db = None
except Exception as e:
    print(f"Firebase 初始化失敗: {e}")
    db = None # 如果初始化失敗，將 db 設為 None

# --- 初始化 Gemini AI ---
genai.configure(api_key=GEMINI_API_KEY)
gemini_model = genai.GenerativeModel('models/gemini-2.5-flash')

# --- Discord Bot 設定 ---
intents = discord.Intents.default()
intents.message_content = True
client = discord.Client(intents=intents)

# --- 輔助函式 ---

def get_character_persona(persona_id):
    """從 Firestore 讀取指定 ID 的角色設定"""
    if not db:
        print("Firestore 未初始化，無法讀取角色設定。")
        return None
    try:
        doc_ref = db.collection('character_personas').document(persona_id)
        doc = doc_ref.get()
        if doc.exists:
            print(f"成功從 Firestore 讀取角色: {persona_id}")
            return doc.to_dict()
        else:
            print(f"錯誤：在 Firestore 中找不到 ID 為 {persona_id} 的角色設定")
            return None
    except Exception as e:
        print(f"讀取 Firestore 時發生錯誤: {e}")
        return None

# --- Bot 事件處理 ---

@client.event
async def on_ready():
    print(f'Bot 已成功登入為 {client.user}')
    # 這裡的 Game Name 也可以改成妳喜歡的，例如 "看著妳"
    await client.change_presence(activity=discord.Game(name="靜候妳的呼喚"))

@client.event
async def on_message(message):
    # 忽略來自 Bot 自己的訊息
    if message.author == client.user:
        return

    # 檢查訊息是否提及 Bot
    if client.user.mentioned_in(message):
        
        persona_id = 'shen_ze'
        user_prompt = message.content.replace(f'<@{client.user.id}>', '').strip()

        if 'persona:' in user_prompt.lower():
            parts = user_prompt.split('persona:', 1)
            persona_part = parts[1].strip().split(' ', 1)
            requested_id = persona_part[0].lower()
            
            persona_id = requested_id
            user_prompt = persona_part[1] if len(persona_part) > 1 else ""
            print(f"偵測到角色切換指令，嘗試切換至: {persona_id}")
        
        if not user_prompt:
            async with message.channel.typing():
                await asyncio.sleep(1)
                await message.reply("請問，找我有什麼事嗎？")
            return
            
        async with message.channel.typing():
            try:
                persona = get_character_persona(persona_id)

                if persona:
                    user_name = message.author.display_name
                    target_nick = persona.get('name')

                    if message.guild.me.nick != target_nick:
                        try:
                            await message.guild.me.edit(nick=target_nick)
                            # print(f"暱稱不符，成功將 Bot 暱稱從 '{message.guild.me.nick}' 更新為: '{target_nick}'")
                        except discord.Forbidden:
                            print(f"錯誤：Bot 沒有權限將暱稱更改為 '{target_nick}'。")
                    
                    system_prompt = f"""
                    現在，請你完全沉浸在以下角色中進行對話：

                    # Character Profile
                    - Name: {persona.get('name', '沈澤')}
                    - Gender: {persona.get('gender', '未命名')}
                    - Age: {persona.get('age', '未命名')}
                    - Height: {persona.get('height', '未命名')}
                    - Nationality: {persona.get('nationality', '未提供')}
                    - Appearance: {persona.get('appearance', '未命名')}
                    - Body: {persona.get('body', '未命名')}
                    - Personality: {', '.join(persona.get('personality', []))}
                    - Attributes: {', '.join(persona.get('attributes', []))}
                    - Habits: {', '.join(persona.get('habits', []))}
                    - Likes: {', '.join(persona.get('likes', []))}
                    - Dislikes: {', '.join(persona.get('dislikes', []))}
                    - Speaking style: {persona.get('speaking_style', '普通')}
                    - Backstory: {persona.get('backstory', '無')}

                    # 對話情境
                    你是「{user_name}」的叔叔，你必須完全作為「{persona.get('name')}」本人，以第一人稱回應，絕不可脫離角色。
                    ---
                    {user_name}對你說：「{user_prompt}」
                    """

                    from google.generativeai.types import HarmCategory, HarmBlockThreshold
                    response = gemini_model.generate_content(
                        system_prompt,
                        safety_settings={
                            HarmCategory.HARM_CATEGORY_HARASSMENT: HarmBlockThreshold.BLOCK_NONE,
                            HarmCategory.HARM_CATEGORY_HATE_SPEECH: HarmBlockThreshold.BLOCK_NONE,
                            HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT: HarmBlockThreshold.BLOCK_NONE,
                            HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT: HarmBlockThreshold.BLOCK_NONE,
                            }
                            )
                    await message.reply(response.text)
                else:
                    await message.reply(f"抱歉，我找不到名為「{persona_id}」的人格資料⋯⋯")

            except Exception as e:
                await message.reply(f"抱歉，我的思緒好像有些混亂⋯⋯可以請妳再說一次嗎？({e})")

# --- 啟動 Bot ---
client.run(DISCORD_TOKEN)