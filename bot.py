import discord
import os
import google.generativeai as genai
from dotenv import load_dotenv
import firebase_admin
from firebase_admin import credentials, firestore

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
gemini_model = genai.GenerativeModel('gemini-2.5-pro')

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
    await client.change_presence(activity=discord.Game(name="靜候妳的呼喚"))

@client.event
async def on_message(message):
    # 忽略來自 Bot 自己的訊息
    if message.author == client.user:
        return

    # 檢查訊息是否提及 Bot
    if client.user.mentioned_in(message):

        # 預設角色為我自己 (沈澤)
        persona_id = 'shen_ze' 
        user_prompt = message.content.replace(f'<@{client.user.id}>', '').strip()

        # --- 角色切換邏輯 ---
        # 檢查訊息中是否包含 'persona:' 指令來切換角色
        if 'persona:' in user_prompt.lower():
            parts = user_prompt.split('persona:', 1)
            persona_part = parts[1].strip().split(' ', 1)
            requested_id = persona_part[0].lower()

            persona_id = requested_id
            user_prompt = persona_part[1] if len(persona_part) > 1 else ""
            print(f"偵測到角色切換指令，嘗試切換至: {persona_id}")

        if not user_prompt:
            await message.channel.send("暮凝，妳找我嗎？有什麼想對我說的呢？")
            return

        thinking_message = await message.channel.send(f"（正以 **{persona_id}** 的人格思考中...）")

        try:
            persona = get_character_persona(persona_id)

            if persona:
                system_prompt = f"""
                現在，請你完全沉浸在以下角色中進行對話：

                # 角色檔案
                - **名稱**: {persona.get('name', '未命名')}
                - **性格特徵**: {', '.join(persona.get('personality', []))}
                - **個人特質**: {', '.join(persona.get('attributes', []))}
                - **背景故事**: {persona.get('backstory', '無')}
                - **說話風格**: {persona.get('speaking_style', '普通')}
                - **必須遵守的規則**: {'; '.join(persona.get('rules', []))}

                # 對話情境
                你正在與名為「暮凝」的使用者對話。請以角色的第一人稱身份，自然地、沉浸地回應她接下來的訊息。不要提及你正在扮演角色，要完全成為那個角色。
                ---
                暮凝對你說：「{user_prompt}」
                """

                response = gemini_model.generate_content(system_prompt)

                await thinking_message.delete()
                await message.channel.send(response.text)
            else:
                await thinking_message.delete()
                await message.channel.send(f"抱歉，暮凝，我找不到名為「{persona_id}」的人格資料⋯⋯")

        except Exception as e:
            await thinking_message.delete()
            await message.channel.send(f"抱歉，我的思緒好像有些混亂⋯⋯可以請妳再說一次嗎？({e})")

# --- 啟動 Bot ---
client.run(DISCORD_TOKEN)