#!/usr/bin/env python3
"""
記憶管理模組
負責角色的記憶存取和管理
"""

import json
import os
from datetime import datetime
from typing import Dict, List, Optional
from google.cloud import firestore
from google.oauth2 import service_account

class MemoryManager:
    """記憶管理器"""
    
    def __init__(self):
        self.db = self._init_firestore()
    
    def _init_firestore(self):
        """初始化 Firestore 連接"""
        try:
            # 從環境變數讀取 Firebase 憑證
            firebase_credentials = os.getenv("FIREBASE_CREDENTIALS_JSON")
            if not firebase_credentials:
                print("❌ 未找到 FIREBASE_CREDENTIALS_JSON 環境變數")
                return None
                
            credentials_dict = json.loads(firebase_credentials)
            credentials = service_account.Credentials.from_service_account_info(credentials_dict)
            
            db = firestore.Client(credentials=credentials, project=credentials_dict['project_id'])
            print("✅ Firestore 連接成功")
            return db
        except Exception as e:
            print(f"❌ Firestore 連接失敗: {e}")
            return None
    
    def save_character_user_memory(self, character_id: str, user_id: str, content: str):
        """保存角色與用戶的對話記憶"""
        if not self.db:
            return False
            
        try:
            doc_ref = self.db.collection('character_memories').document(f"{character_id}_{user_id}")
            
            # 獲取現有記憶
            doc = doc_ref.get()  # type: ignore
            if doc.exists:
                data = doc.to_dict()
                memories = data.get('memories', []) if data else []
            else:
                memories = []
            
            # 添加新記憶
            memory_entry = {
                'content': content,
                'timestamp': firestore.SERVER_TIMESTAMP,
                'character_id': character_id,
                'user_id': user_id
            }
            
            memories.append(memory_entry)
            
            # 保持最近 50 條記憶
            if len(memories) > 50:
                memories = memories[-50:]
            
            # 保存到 Firestore
            doc_ref.set({
                'character_id': character_id,
                'user_id': user_id,
                'memories': memories,
                'last_updated': firestore.SERVER_TIMESTAMP
            })
            
            return True
            
        except Exception as e:
            print(f"保存記憶時發生錯誤: {e}")
            return False
    
    def get_character_user_memory(self, character_id: str, user_id: str, limit: int = 10) -> List[Dict]:
        """獲取角色與用戶的對話記憶"""
        if not self.db:
            return []
            
        try:
            doc_ref = self.db.collection('character_memories').document(f"{character_id}_{user_id}")
            doc = doc_ref.get()  # type: ignore
            
            if doc.exists:
                data = doc.to_dict()
                memories = data.get('memories', []) if data else []
                
                # 返回最近的記憶
                return memories[-limit:] if memories else []
            else:
                return []
                
        except Exception as e:
            print(f"獲取記憶時發生錯誤: {e}")
            return []

# 全域記憶管理器實例
_memory_manager = MemoryManager()

def save_character_user_memory(character_id: str, user_id: str, content: str):
    """保存角色與用戶的對話記憶"""
    return _memory_manager.save_character_user_memory(character_id, user_id, content)

def get_character_user_memory(character_id: str, user_id: str, limit: int = 10) -> List[Dict]:
    """獲取角色與用戶的對話記憶"""
    return _memory_manager.get_character_user_memory(character_id, user_id, limit)

async def generate_character_response(character_name: str, character_persona: str, user_memories: List[Dict], user_prompt: str, user_display_name: str) -> str:
    """生成角色回應"""
    try:
        import google.generativeai as genai
        
        # 設定 Google AI
        api_key = os.getenv("GOOGLE_API_KEY")
        if not api_key:
            return "「抱歉，我現在無法思考...」"
            
        genai.configure(api_key=api_key)  # type: ignore
        model = genai.GenerativeModel('gemini-pro')  # type: ignore
        
        # 建構記憶內容
        memory_context = ""
        if user_memories:
            memory_context = "\n".join([mem.get('content', '') for mem in user_memories[-5:]])  # 最近5條記憶
            
        # 建構提示
        prompt = f"""你是{character_name}。

角色設定：
{character_persona}

與{user_display_name}的對話記憶：
{memory_context}

現在{user_display_name}對你說：{user_prompt}

請以{character_name}的身份回應，保持角色的個性和語氣。回應要自然、有趣，並且符合角色設定。"""

        response = model.generate_content(prompt)
        return response.text if response.text else "「...」"
        
    except Exception as e:
        print(f"生成回應時發生錯誤: {e}")
        return "「抱歉，我現在有點累...」" 