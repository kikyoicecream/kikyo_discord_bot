#!/usr/bin/env python3
"""
基於情感關鍵字的智能表情符號回應系統
"""

import os
import json
import random
import firebase_admin
from firebase_admin import firestore
from dotenv import load_dotenv
from typing import Dict, Optional, List

# 載入環境變數
load_dotenv()

class SmartEmojiResponseManager:
    """智能表情符號回應管理器"""
    
    def __init__(self):
        self.db = self._initialize_firebase()
        self.cache = {}  # 快取表情符號配置
    
    def _initialize_firebase(self):
        """初始化 Firebase"""
        try:
            if firebase_admin._apps:
                db = firestore.client()
                print("✅ Firebase 已初始化")
                return db
                
            firebase_creds_json = os.getenv('FIREBASE_CREDENTIALS_JSON')
            if firebase_creds_json:
                firebase_creds_dict = json.loads(firebase_creds_json)
                cred = firebase_admin.credentials.Certificate(firebase_creds_dict)
                firebase_admin.initialize_app(cred)
                db = firestore.client()
                print("✅ Firebase 初始化成功")
                return db
            else:
                print("❌ 找不到 FIREBASE_CREDENTIALS_JSON")
                return None
        except Exception as e:
            print(f"❌ Firebase 初始化失敗: {e}")
            return None
    
    def get_emoji_response(self, character_id: str, message_content: str, guild=None) -> Optional[str]:
        """檢查訊息並返回對應的情感表情符號"""
        if not self.db:
            return None
        
        # 檢查快取
        if character_id not in self.cache:
            self._load_emoji_config(character_id)
        
        if character_id not in self.cache:
            return None
        
        emoji_config = self.cache[character_id]
        
        # 檢查是否啟用
        if not emoji_config.get('enabled', True):
            return None
        
        # 分析訊息情感
        detected_emotion = self._analyze_emotion(message_content, emoji_config)
        
        # 優先使用情感對應的 emoji
        if detected_emotion:
            trigger_emojis = emoji_config.get('trigger_emojis', {})
            emotion_emojis = trigger_emojis.get(detected_emotion, [])
            
            if emotion_emojis:
                return random.choice(emotion_emojis)
        
        # 如果沒有檢測到特定情感，從通用表情符號池中隨機選擇
        general_emojis = emoji_config.get('general_emojis', [])
        if general_emojis and random.random() < 0.3:  # 30% 機率使用通用表情符號
            return random.choice(general_emojis)
        
        # 如果都沒有，嘗試使用伺服器自訂 emoji
        if guild and hasattr(guild, 'emojis'):
            server_emojis = list(guild.emojis)
            if server_emojis and random.random() < 0.2:  # 20% 機率使用伺服器 emoji
                return str(random.choice(server_emojis))
        
        return None
    
    def _analyze_emotion(self, message_content: str, emoji_config: Dict) -> Optional[str]:
        """分析訊息情感"""
        content = message_content.lower()
        trigger_keywords = emoji_config.get('trigger_keywords', {})
        
        # 檢查每種情感
        for emotion, keywords in trigger_keywords.items():
            for keyword in keywords:
                if keyword.lower() in content:
                    return emotion
        
        return None
    
    def _load_emoji_config(self, character_id: str):
        """從 Firestore 載入表情符號配置"""
        if not self.db:
            print(f"❌ Firebase 未初始化，無法載入 {character_id} 配置")
            return
            
        try:
            doc_ref = self.db.collection(character_id).document('emoji_system')
            doc = doc_ref.get()
            
            if doc.exists:
                data = doc.to_dict()
                self.cache[character_id] = data
                print(f"✅ 載入 {character_id} 的智能表情符號配置")
            else:
                print(f"❌ {character_id} 的 emoji_system 配置不存在，請在 Firestore 中手動建立")
                
        except Exception as e:
            print(f"❌ 載入 {character_id} 表情符號配置失敗: {e}")
    
    def add_emotion_keyword(self, character_id: str, emotion: str, keyword: str):
        """新增情感關鍵字"""
        if not self.db:
            return False
        
        try:
            if character_id not in self.cache:
                self._load_emoji_config(character_id)
            
            if character_id not in self.cache:
                return False
            
            config = self.cache[character_id]
            if 'trigger_keywords' not in config:
                config['trigger_keywords'] = {}
            
            if emotion not in config['trigger_keywords']:
                config['trigger_keywords'][emotion] = []
            
            if keyword not in config['trigger_keywords'][emotion]:
                config['trigger_keywords'][emotion].append(keyword)
                self._save_emoji_config(character_id, config)
                print(f"✅ 為 {character_id} 新增情感關鍵字：{emotion} -> {keyword}")
                return True
            
            return False
            
        except Exception as e:
            print(f"❌ 新增情感關鍵字失敗: {e}")
            return False
    
    def add_emotion_emoji(self, character_id: str, emotion: str, emoji: str):
        """新增情感表情符號"""
        if not self.db:
            return False
        
        try:
            if character_id not in self.cache:
                self._load_emoji_config(character_id)
            
            if character_id not in self.cache:
                return False
            
            config = self.cache[character_id]
            if 'trigger_emojis' not in config:
                config['trigger_emojis'] = {}
            
            if emotion not in config['trigger_emojis']:
                config['trigger_emojis'][emotion] = []
            
            if emoji not in config['trigger_emojis'][emotion]:
                config['trigger_emojis'][emotion].append(emoji)
                self._save_emoji_config(character_id, config)
                print(f"✅ 為 {character_id} 新增情感表情符號：{emotion} -> {emoji}")
                return True
            
            return False
            
        except Exception as e:
            print(f"❌ 新增情感表情符號失敗: {e}")
            return False
    
    def _save_emoji_config(self, character_id: str, config: Dict):
        """儲存表情符號配置到 Firestore"""
        if not self.db:
            print(f"❌ Firebase 未初始化，無法儲存 {character_id} 配置")
            return
            
        try:
            doc_ref = self.db.collection(character_id).document('emoji_system')
            doc_ref.set(config)
            print(f"✅ 儲存 {character_id} 的智能表情符號配置")
        except Exception as e:
            print(f"❌ 儲存 {character_id} 表情符號配置失敗: {e}")
    
    def get_character_emotions(self, character_id: str) -> Dict[str, List[str]]:
        """取得角色的所有情感關鍵字"""
        if character_id not in self.cache:
            self._load_emoji_config(character_id)
        
        if character_id in self.cache:
            return self.cache[character_id].get('trigger_keywords', {})
        
        return {}
    
    def get_character_emoji_map(self, character_id: str) -> Dict[str, List[str]]:
        """取得角色的所有情感表情符號映射"""
        if character_id not in self.cache:
            self._load_emoji_config(character_id)
        
        if character_id in self.cache:
            return self.cache[character_id].get('trigger_emojis', {})
        
        return {}
    
    def set_emoji_enabled(self, character_id: str, enabled: bool):
        """設定表情符號回應是否啟用"""
        if not self.db:
            return False
        
        try:
            if character_id not in self.cache:
                self._load_emoji_config(character_id)
            
            if character_id not in self.cache:
                return False
            
            config = self.cache[character_id]
            config['enabled'] = enabled
            
            self._save_emoji_config(character_id, config)
            
            status = "啟用" if enabled else "停用"
            print(f"✅ {character_id} 智能表情符號回應已{status}")
            return True
            
        except Exception as e:
            print(f"❌ 設定表情符號回應狀態失敗: {e}")
            return False
    
    def refresh_cache(self, character_id: Optional[str] = None):
        """重新整理快取"""
        if character_id:
            if character_id in self.cache:
                del self.cache[character_id]
            self._load_emoji_config(character_id)
        else:
            self.cache.clear()
            for char_id in ['shen_ze', 'gu_beichen', 'fan_chengxi']:
                self._load_emoji_config(char_id)

    def get_server_emoji_stats(self, guild) -> Dict:
        """獲取伺服器 emoji 統計資訊"""
        if not guild or not hasattr(guild, 'emojis'):
            return {"total": 0, "animated": 0, "static": 0, "sample": []}
        
        emojis = list(guild.emojis)
        animated_count = sum(1 for emoji in emojis if emoji.animated)
        static_count = len(emojis) - animated_count
        
        # 取前5個作為樣本
        sample = [str(emoji) for emoji in emojis[:5]]
        
        return {
            "total": len(emojis),
            "animated": animated_count,
            "static": static_count,
            "sample": sample
        }

# 全域實例
smart_emoji_manager = SmartEmojiResponseManager() 