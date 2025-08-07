#!/usr/bin/env python3
"""
Firebase 統一工具類
統一管理 Firestore 連接、錯誤處理和配置讀取
"""

import json
import os
import time
from typing import Dict, Any, Optional, Tuple
from google.cloud import firestore
from google.oauth2 import service_account
from dotenv import load_dotenv

# 載入環境變數
load_dotenv()


class FirebaseManager:
    """Firebase 統一管理器 - 單例模式"""
    
    _instance = None
    _db = None
    _cache = {}
    _cache_timestamp = 0
    _cache_duration = 300  # 5分鐘快取
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialize()
        return cls._instance
    
    def _initialize(self):
        """初始化 Firestore 連接"""
        if self._db is None:
            self._db = self._init_firestore()
    
    def _init_firestore(self):
        """初始化 Firestore 連接"""
        try:
            firebase_credentials = os.getenv("FIREBASE_CREDENTIALS_JSON")
            if not firebase_credentials:
                self.log_error("Firestore 初始化", "未找到 FIREBASE_CREDENTIALS_JSON 環境變數")
                return None
                
            credentials_dict = json.loads(firebase_credentials)
            credentials = service_account.Credentials.from_service_account_info(credentials_dict)
            
            db = firestore.Client(credentials=credentials, project=credentials_dict['project_id'])
            print("✅ Firestore 連接成功")
            return db
        except Exception as e:
            self.log_error("Firestore 初始化", e)
            return None
    
    @property
    def db(self):
        """獲取 Firestore 資料庫實例"""
        if self._db is None:
            self._db = self._init_firestore()
        return self._db
    
    def log_error(self, operation: str, error, fallback_message: str = "操作失敗"):
        """統一的錯誤處理和日誌記錄"""
        if isinstance(error, Exception):
            print(f"❌ {operation}時發生錯誤：{error}")
        else:
            print(f"❌ {operation}：{error}")
        return fallback_message
    
    def is_empty_response(self, response: str) -> bool:
        """檢查回應是否為空或無意義"""
        return not response or response.strip().lower() in ["none", "none.", "無", "無重要資訊"]
    
    def get_from_cache(self, cache_key: str) -> Optional[Any]:
        """從快取獲取數據"""
        current_time = time.time()
        if (current_time - self._cache_timestamp < self._cache_duration and 
            cache_key in self._cache):
            return self._cache[cache_key]
        return None
    
    def set_to_cache(self, cache_key: str, value: Any):
        """將數據存入快取"""
        self._cache[cache_key] = value
        self._cache_timestamp = time.time()
    
    def get_firestore_field(self, collection: str, document: str, field: str, 
                           default: Any = None, cache_key: str = None, 
                           description: str = None, show_load_message: bool = True) -> Any:
        """通用的 Firestore 欄位讀取方法"""
        if not self.db:
            if description and show_load_message:
                print(f"❌ Firestore 未連接，無法獲取 {description}")
            return default
        
        # 使用快取
        if cache_key:
            cached_value = self.get_from_cache(cache_key)
            if cached_value is not None:
                return cached_value
        
        try:
            doc_ref = self.db.collection(collection).document(document)
            doc = doc_ref.get()
            
            if doc.exists:
                data = doc.to_dict()
                value = data.get(field, default) if data else default
                
                # 更新快取
                if cache_key:
                    self.set_to_cache(cache_key, value)
                
                if description and show_load_message:
                    print(f"✅ 已載入 {description}")
                return value
            else:
                if description and show_load_message:
                    print(f"⚠️ 找不到 {description}，使用預設值: {default}")
                return default
                
        except Exception as e:
            if description and show_load_message:
                self.log_error(f"獲取 {description}", e)
            return default
    
    def get_character_gemini_config(self, character_id: str) -> Dict[str, Any]:
        """獲取角色的完整 Gemini 設定"""
        if not self.db:
            return {}
        
        try:
            cache_key = f"{character_id}_gemini_config"
            cached_config = self.get_from_cache(cache_key)
            if cached_config is not None:
                return cached_config
            
            # 從 Firestore 讀取
            doc = self.db.collection(character_id).document('system').get()
            if doc.exists:
                system_data = doc.to_dict()
                gemini_config = system_data.get('gemini_config', {})
                character_name = system_data.get('name', character_id)  # 獲取角色名稱
            else:
                gemini_config = {}
                character_name = character_id
            
            # 更新快取
            self.set_to_cache(cache_key, gemini_config)
            
            # 只在首次載入時顯示訊息
            if gemini_config and not self.get_from_cache(f"{character_id}_gemini_loaded"):
                print(f"✅ 已載入角色 {character_name} 的 Gemini 設定")
                self.set_to_cache(f"{character_id}_gemini_loaded", True)
            
            return gemini_config
            
        except Exception as e:
            self.log_error(f"獲取角色 {character_id} Gemini 設定", e)
            return {}
    
    def get_character_system_config(self, character_id: str) -> Dict[str, Any]:
        """獲取角色的完整系統設定"""
        if not self.db:
            return {}
        
        try:
            cache_key = f"{character_id}_system_config"
            cached_config = self.get_from_cache(cache_key)
            if cached_config is not None:
                return cached_config
            
            # 從 Firestore 讀取
            doc = self.db.collection(character_id).document('system').get()
            system_config = doc.to_dict() if doc.exists else {}
            
            # 更新快取
            self.set_to_cache(cache_key, system_config)
            
            # 只在首次載入時顯示訊息
            if system_config and not self.get_from_cache(f"{character_id}_system_loaded"):
                character_name = system_config.get('name', character_id)  # 獲取角色名稱
                print(f"✅ 已載入角色 {character_name} 的系統設定")
                self.set_to_cache(f"{character_id}_system_loaded", True)
            
            return system_config
            
        except Exception as e:
            self.log_error(f"獲取角色 {character_id} 系統設定", e)
            return {}
    
    def get_prompt_with_model(self, prompt_type: str) -> Tuple[str, str]:
        """從 Firestore 獲取指定類型的 prompt 和 model 設定"""
        content = self.get_firestore_field(
            collection='prompt',
            document=prompt_type,
            field='content',
            default='',
            cache_key=f"{prompt_type}_content"
        )
        
        model = self.get_firestore_field(
            collection='prompt',
            document=prompt_type,
            field='model',
            default='gemini-2.0-flash',
            cache_key=f"{prompt_type}_model"
        )
        
        return content, model
    
    def get_memory_limit(self) -> int:
        """從 Firestore 獲取記憶統整門檻"""
        return self.get_firestore_field(
            collection='prompt',
            document='memories_summary',
            field='memory_limit',
            default=15,  # 預設值
            cache_key="memory_limit"
        )
    
    def get_character_prompt_config(self, character_id: str, prompt_type: str) -> Tuple[str, str]:
        """獲取角色的prompt設定，支援個別角色自定義prompt"""
        if not self.db:
            return "", "gemini-2.0-flash"
        
        try:
            # 先檢查角色是否有自定義prompt設定
            system_doc = self.db.collection(character_id).document('system').get()
            if system_doc.exists:
                system_config = system_doc.to_dict()
                allowed_custom_prompt = system_config.get('allowed_custom_prompt', False)
                
                if allowed_custom_prompt:
                    # 使用角色的自定義prompt
                    custom_prompt = system_config.get('custom_prompt', '')
                    if custom_prompt:
                        print(f"✅ 使用角色 {character_id} 的自定義prompt")
                        return custom_prompt, "gemini-2.0-flash"  # 自定義prompt使用預設模型
            
            # 如果沒有自定義prompt或未啟用，則使用統一的prompt集合
            print(f"✅ 使用統一prompt集合的 {prompt_type} 設定")
            return self.get_prompt_with_model(prompt_type)
            
        except Exception as e:
            self.log_error(f"獲取角色 {character_id} prompt設定", e)
            return "", "gemini-2.0-flash"
 

# 全域 Firebase 管理器實例
firebase_manager = FirebaseManager() 