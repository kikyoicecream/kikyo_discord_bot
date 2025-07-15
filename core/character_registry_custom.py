import os
import asyncio
import re
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
                    print(f"成功註冊角色: {character_id}")
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
    
    def get_character_setting(self, character_id: str, setting_key: str, default_value=None):
        """獲取角色設定"""
        if character_id in self.characters:
            return self.characters[character_id].get(setting_key, default_value)
        return default_value
    
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
        
        # 檢查是否切換角色
        match = re.search(r'persona\s*:\s*(\w+)', user_prompt, re.IGNORECASE)
        if match:
            persona_id = match.group(1).lower()
            user_prompt = re.sub(r'persona\s*:\s*\w+\s*', '', user_prompt, flags=re.IGNORECASE).strip()
        else:
            persona_id = character_id
        
        if not user_prompt:
            async with message.channel.typing():
                await message.reply("「想說什麼？我在聽。」", mention_author=False)
            return True
        
        async with message.channel.typing():
            try:
                # 獲取角色設定
                character_name = self.get_character_setting(persona_id, 'name', persona_id) or persona_id
                character_persona = self.get_character_setting(persona_id, 'persona', '') or ''
                
                # 使用 memory.py 中的功能獲取用戶記憶
                user_memories = memory.get_character_user_memories(persona_id, str(message.author.id))
                
                # 使用 memory.py 中的功能生成回應
                response = await memory.generate_character_response(
                    str(character_name), 
                    str(character_persona), 
                    user_memories, 
                    user_prompt, 
                    message.author.display_name
                )
                
                # 使用 memory.py 中的功能保存記憶
                memory_content = f"{message.author.display_name} 說：{user_prompt}"
                memory.save_character_user_memory(persona_id, str(message.author.id), memory_content)
                
                # 發送回應
                await message.reply(response, mention_author=False)
                
            except Exception as e:
                print(f"處理訊息時發生錯誤: {e}")
                await message.reply("「抱歉，我現在有點累...」", mention_author=False)
        
        return True 