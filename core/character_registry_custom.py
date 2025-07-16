import os
import asyncio
import json
from typing import Dict, Optional, List
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
import firebase_admin
from firebase_admin import firestore
import google.generativeai.types as genai_types
from google.generativeai.types import HarmCategory, HarmBlockThreshold
from core import memory

class CharacterRegistry:
    """簡化的角色註冊器 - 管理多個角色的設定和記憶"""
    
    def __init__(self):
        self.characters: Dict[str, dict] = {}
        self.conversation_histories: Dict[str, Dict[int, list]] = {}
        self.active_users: Dict[str, Dict[int, Dict[str, dict]]] = {}
        self.db = None
        self._initialize_firebase()
    
    def _initialize_firebase(self):
        """初始化 Firebase"""
        try:
            # 檢查是否已經初始化過
            if firebase_admin._apps:
                self.db = firestore.client()
                print("Firebase 已初始化，重用現有連接")
                return
                
            firebase_creds_json = os.getenv('FIREBASE_CREDENTIALS_JSON')
            if firebase_creds_json:
                firebase_creds_dict = json.loads(firebase_creds_json)
                cred = firebase_admin.credentials.Certificate(firebase_creds_dict)
                firebase_admin.initialize_app(cred)
                self.db = firestore.client()
                print("Firebase 初始化成功")
            else:
                print("錯誤：找不到 FIREBASE_CREDENTIALS_JSON")
        except Exception as e:
            print(f"Firebase 初始化失敗: {e}")
            # 如果初始化失敗，嘗試使用現有的連接
            try:
                self.db = firestore.client()
                print("使用現有的 Firebase 連接")
            except:
                self.db = None
    
    def register_character(self, character_id: str):
        """註冊角色並從 Firestore 載入設定"""
        if not self.db:
            print(f"Firestore 未初始化，無法註冊角色 {character_id}")
            return False
        
        try:
            # 從 character_id/profile 讀取角色設定
            doc_ref = self.db.collection(character_id).document('profile')
            doc = doc_ref.get()
            
            if doc.exists:
                character_data = doc.to_dict()
                if character_data:  # 確保不是 None
                    self.characters[character_id] = character_data
                    self.conversation_histories[character_id] = {}
                    self.active_users[character_id] = {}
                    return True
                else:
                    print(f"角色 {character_id} 的設定資料為空")
                    return False
            else:
                print(f"錯誤：在 Firestore 中找不到 {character_id}/profile")
                return False
        except Exception as e:
            print(f"註冊角色 {character_id} 失敗: {e}")
            return False
    
    def _format_character_data(self, character_data: dict) -> str:
        """將角色資料格式化為字串供 AI 使用"""
        if not character_data:
            return "角色資料未載入"
        
        # 直接將整個 profile 轉換為 JSON 格式
        import json
        try:
            formatted_data = json.dumps(character_data, ensure_ascii=False, indent=2)
            print(f"🔧 格式化角色資料 for {character_data.get('name', '未知')}:")
            print(f"   欄位數量: {len(character_data)}")
            print(f"   總長度: {len(formatted_data)} 字符")
            return formatted_data
        except Exception as e:
            print(f"❌ 格式化角色資料失敗: {e}")
            return str(character_data)

    def get_character_setting(self, character_id: str, setting_key: str, default_value=None):
        """獲取角色設定"""
        if character_id not in self.characters:
            return default_value
            
        character_data = self.characters[character_id]
        
        # 如果請求的是 persona，但資料中沒有，則使用 backstory
        if setting_key == 'persona' and 'persona' not in character_data:
            backstory = character_data.get('backstory', '')
            if backstory:
                print(f"🔧 使用 backstory 作為 {character_data.get('name', '未知')} 的 persona")
                return backstory
        
        return character_data.get(setting_key, default_value)
    
    async def handle_message(self, message, character_id, client, proactive_keywords=None):
        """處理角色訊息"""
        # 檢查是否需要回應
        mentioned = client.user.mentioned_in(message)
        contains_keyword = False
        
        if proactive_keywords:
            contains_keyword = any(keyword.lower() in message.content.lower() for keyword in proactive_keywords)
        
        if not mentioned and not contains_keyword:
            return False
        
        user_prompt = message.content
        if mentioned:
            user_prompt = user_prompt.replace(f'<@{client.user.id}>', '').strip()
        
        # 直接使用當前角色 ID（移除角色切換功能）
        persona_id = character_id
        
        if not user_prompt:
            async with message.channel.typing():
                await message.reply("「想說什麼？我在聽。」", mention_author=False)
            return True
        
        async with message.channel.typing():
            try:
                # 獲取完整的角色資料
                character_data = self.characters.get(persona_id, {})
                if not character_data:
                    await message.reply("「抱歉，我的設定資料似乎有問題...」", mention_author=False)
                    return True
                
                # 提取需要的資訊
                user_name = message.author.display_name
                user_id = str(message.author.id)
                channel_id = message.channel.id
                target_nick = character_data.get('name', persona_id)
                bot_name = target_nick or persona_id
                
                # 追蹤使用者活動（新增）
                try:
                    from core.group_conversation_tracker import track_user_activity
                    track_user_activity(character_id, channel_id, message.author.id, user_name, user_prompt)
                except Exception as e:
                    print(f"追蹤使用者活動時發生錯誤: {e}")
                
                # 格式化角色描述供 AI 使用
                character_persona = self._format_character_data(character_data)
                
                # 使用 memory.py 中的功能獲取使用者記憶
                user_memories = memory.get_character_user_memory(persona_id, user_id)
                
                # 使用 memory.py 中的功能生成回應（包含群組上下文）
                response = await memory.generate_character_response(
                    bot_name, 
                    character_persona, 
                    user_memories, 
                    user_prompt, 
                    user_name,
                    channel_id,
                    character_id
                )
                
                # 使用 memory.py 中的功能保存記憶
                memory_content = f"{user_name} 說：{user_prompt}"
                save_success = await memory.save_character_user_memory(persona_id, user_id, memory_content, user_name)
                if not save_success:
                    print(f"⚠️ 記憶保存失敗：{persona_id} - {user_id}")
                
                # 發送回應
                await message.reply(response, mention_author=False)
                
                # 追蹤BOT自己的回應（新增）
                try:
                    from core.group_conversation_tracker import track_bot_response
                    track_bot_response(character_id, channel_id, bot_name, response)
                except Exception as e:
                    print(f"追蹤BOT回應時發生錯誤: {e}")
                
            except Exception as e:
                print(f"處理訊息時發生錯誤: {e}")
                await message.reply("「抱歉，我現在有點累...」", mention_author=False)
        
        return True 