#!/usr/bin/env python3
"""
記憶管理模組
負責角色的記憶存取和管理
"""
from dotenv import load_dotenv
load_dotenv()
import asyncio
from datetime import datetime
from typing import Dict, List, Optional
import google.generativeai as genai
from google.generativeai.types import HarmCategory, HarmBlockThreshold
from firebase_utils import firebase_manager
from functools import wraps


# 常數定義
DEFAULT_MODEL = 'gemini-2.0-flash'  # 預設模型
DEFAULT_RESPONSE_MODEL = 'gemini-2.5-pro'  # 預設回應模型

# 全域配置 Gemini API
import os
api_key = os.getenv("GOOGLE_API_KEY")
if api_key:
    genai.configure(api_key=api_key)  # type: ignore
    print("✅ Gemini 全域配置完成")
else:
    print("⚠️ 未找到 GOOGLE_API_KEY")

def with_character_context(func):
    """裝飾器：自動為函式提供 character_name 和 user_name 變數"""
    @wraps(func)
    async def wrapper(self, *args, **kwargs):
        # 從參數中提取 character_id 和 user_name
        character_id = kwargs.get('character_id') or (args[0] if args else None)
        user_name = kwargs.get('user_name', "使用者")
        
        # 從 character_id 獲取 character_name
        if character_id:
            system_config = self.firebase.get_character_system_config(character_id)
            character_name = system_config.get('name', character_id)
        else:
            character_name = "角色"
        
        # 將變數添加到 self 中，讓所有方法都能使用
        self._current_character_name = character_name
        self._current_user_name = user_name
        
        return await func(self, *args, **kwargs)
    
    @wraps(func)
    def sync_wrapper(self, *args, **kwargs):
        # 同步版本的裝飾器
        character_id = kwargs.get('character_id') or (args[0] if args else None)
        user_name = kwargs.get('user_name', "使用者")
        
        if character_id:
            system_config = self.firebase.get_character_system_config(character_id)
            character_name = system_config.get('name', character_id)
        else:
            character_name = "角色"
        
        self._current_character_name = character_name
        self._current_user_name = user_name
        
        return func(self, *args, **kwargs)
    
    # 根據函式是否為 async 返回對應的裝飾器
    if asyncio.iscoroutinefunction(func):
        return wrapper
    else:
        return sync_wrapper

class MemoryManager:
    """記憶管理器"""
    
    def __init__(self):
        # 使用統一的 Firebase 管理器
        self.firebase = firebase_manager
        # 初始化當前上下文變數
        self._current_character_name = "角色"
        self._current_user_name = "使用者"
    
    @property
    def db(self):
        """獲取 Firestore 資料庫實例"""
        return self.firebase.db
    
    @property
    def character_name(self):
        """獲取當前角色名稱"""
        return self._current_character_name
    
    @property
    def user_name(self):
        """獲取當前使用者名稱"""
        return self._current_user_name
    
    def format_with_context(self, text: str) -> str:
        """使用當前上下文格式化文字"""
        try:
            return text.format(
                character_name=self._current_character_name,
                user_name=self._current_user_name
            )
        except KeyError as e:
            print(f"❌ 格式化文字時使用了不存在的變數：{e}")
            print(f"📋 可用變數：character_name={self._current_character_name}, user_name={self._current_user_name}")
            return text
    
    def _get_prompt_and_model(self, prompt_type: str, character_id: str = None) -> tuple[str, str]:
        """統一的 prompt 和 model 獲取方法"""
        if prompt_type in ['user_memories', 'memories_summary']:
            return self.firebase.get_prompt_with_model(prompt_type)
        elif character_id:
            return self.firebase.get_character_prompt_config(character_id, prompt_type)
        else:
            return self.firebase.get_prompt_with_model(prompt_type)
    
    def _create_gemini_model(self, model_name: str, config: dict = None) -> genai.GenerativeModel:
        """建立 Gemini 模型的統一方法"""
        generation_config = {}
        if config:
            generation_config = {param: config[param] 
                               for param in ['temperature', 'top_k', 'top_p', 'max_output_tokens'] 
                               if param in config}
        
        # 安全設定
        safety_settings = [
            {"category": HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT, "threshold": HarmBlockThreshold.BLOCK_NONE},
            {"category": HarmCategory.HARM_CATEGORY_HARASSMENT, "threshold": HarmBlockThreshold.BLOCK_NONE},
            {"category": HarmCategory.HARM_CATEGORY_HATE_SPEECH, "threshold": HarmBlockThreshold.BLOCK_NONE},
            {"category": HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT, "threshold": HarmBlockThreshold.BLOCK_NONE}
        ]
        
        return genai.GenerativeModel(model_name, generation_config=generation_config, safety_settings=safety_settings)  # type: ignore
    
    async def _process_with_gemini(self, prompt_type: str, content: str, memories: List[str] = None) -> str:
        """統一的 Gemini 處理方法"""
        try:
            base_prompt, model_name = self._get_prompt_and_model(prompt_type)
            if not base_prompt.strip():
                print(f"❌ Firestore 中沒有 {prompt_type} prompt，無法處理")
                return self._get_fallback_response(prompt_type, content)
            
            model = self._create_gemini_model(model_name)
            formatted_prompt = self.format_with_context(base_prompt)
            
            if memories:
                prompt = f"{formatted_prompt}\n\nExisting memories:\n{memories}"
            else:
                prompt = f"{formatted_prompt}\n\nConversation:\n{content}"
            
            response = await asyncio.to_thread(model.generate_content, prompt)
            result = response.text.strip() if response.text else ""
            
            if self.firebase.is_empty_response(result):
                print(f"⚠️ Gemini 返回空內容，使用備用回應")
                return self._get_fallback_response(prompt_type, content)
            
            return result
            
        except Exception as e:
            return self.firebase.log_error(f"{prompt_type} 處理", e, self._get_fallback_response(prompt_type, content))
    
    def _get_fallback_response(self, prompt_type: str, content: str) -> str:
        """獲取備用回應"""
        if prompt_type == 'user_memories':
            return f"使用者進行了對話互動：{content[:30]}……"
        elif prompt_type == 'memories_summary':
            return f"與 {self.user_name} 有過多次對話互動"
        else:
            return f"處理 {prompt_type} 時發生錯誤"
    
    @with_character_context
    async def save_character_user_memory(self, character_id: str, user_id: str, content: str, user_name: str = "使用者"):
        """保存角色與使用者的對話記憶"""
        if not self.db:
            print("❌ Firestore 資料庫連接失敗，無法保存記憶")
            return False
            
        try:
            print(f"📝 正在處理記憶：{character_id} - {user_id}")
            
            # 使用統一的 Gemini 處理方法
            summarized_memory = await self._process_with_gemini('user_memories', content)
            
            # 獲取或建立記憶文檔
            doc_ref = self.db.collection(character_id).document('users')
            doc = doc_ref.get()  # type: ignore
            all_users_memories = doc.to_dict() if doc.exists else {}
            
            if not doc.exists:
                print(f"🆕 為角色 {self.character_name} 建立新的使用者記憶文檔")
            
            # 更新使用者記憶
            user_memories = all_users_memories.get(user_id, [])
            user_memories.append(summarized_memory)
            
            # 檢查記憶限制並統整
            memory_limit = firebase_manager.get_memory_limit()
            if len(user_memories) > memory_limit:
                print(f"📋 使用者 {user_id} 記憶超過 {memory_limit} 則，正在統整記憶……")
                consolidated_memory = await self._process_with_gemini('memories_summary', "", user_memories)
                user_memories = [consolidated_memory]
                print(f"✅ 記憶已統整完成")
            
            # 保存到 Firestore
            all_users_memories[user_id] = user_memories
            doc_ref.set(all_users_memories)
            
            print(f"✅ 記憶保存成功：使用者 {user_id} 現有 {len(user_memories)} 則記憶")
            return True
            
        except Exception as e:
            self.firebase.log_error("保存記憶", e)
            return False

    @with_character_context
    def get_character_user_memory(self, character_id: str, user_id: str, limit: int = 25) -> List[str]:
        """獲取角色與使用者的對話記憶"""
        if not self.db:
            return []
            
        try:
            doc_ref = self.db.collection(character_id).document('users')
            doc = doc_ref.get()  # type: ignore
            
            if doc.exists:
                data = doc.to_dict()
                if data and user_id in data:
                    user_memories = data[user_id]
                    return user_memories[-limit:] if len(user_memories) > limit else user_memories
            
            return []
                
        except Exception as e:
            self.firebase.log_error("獲取記憶", e)
            return []

# 全域記憶管理器實例
_memory_manager = MemoryManager()

async def save_character_user_memory(character_id: str, user_id: str, content: str, user_name: str = "使用者"):
    """保存角色與使用者的對話記憶"""
    return await _memory_manager.save_character_user_memory(character_id, user_id, content, user_name)

def get_character_user_memory(character_id: str, user_id: str, limit: int = 25) -> List[str]:
    """獲取角色與使用者的對話記憶"""
    return _memory_manager.get_character_user_memory(character_id, user_id, limit)

def get_current_context() -> tuple[str, str]:
    """獲取當前上下文（角色名稱和使用者名稱）"""
    return _memory_manager.character_name, _memory_manager.user_name

def format_text_with_context(text: str) -> str:
    """使用當前上下文格式化文字"""
    return _memory_manager.format_with_context(text)

def _build_system_prompt(character_name: str, character_persona: str, user_display_name: str, 
                        group_context: str, user_memories: List[str], user_prompt: str, character_id: str = None) -> str:
    """構建系統提示詞"""
    # 獲取系統提示詞模板
    if character_id:
        base_system_prompt, _ = firebase_manager.get_character_prompt_config(character_id, 'system')
    else:
        base_system_prompt, _ = firebase_manager.get_prompt_with_model('system')
    
    if not base_system_prompt.strip():
        raise ValueError("Firestore 中沒有 system prompt")
    
    try:
        formatted_system_prompt = base_system_prompt.format(character_name=character_name)
    except KeyError as e:
        print(f"❌ system prompt 中使用了不存在的變數：{e}")
        print(f"📋 可用變數：character_name={character_name}")
        print(f"💡 system prompt 只支援 character_name 變數")
        raise ValueError(f"System prompt 變數錯誤：{e}")
    
    memory_context = "\n".join(user_memories) if user_memories else "暫無記憶"
    
    return f"""{formatted_system_prompt}

## 角色設定
{character_persona}

## 群組對話情況
{group_context if group_context else f"- 當前與我對話的使用者: {user_display_name}"}

## 關於 {user_display_name} 的記憶
{memory_context}

## 目前輸入
{user_display_name}：{user_prompt}
"""

async def generate_character_response(character_name: str, character_persona: str, user_memories: List[str], user_prompt: str, user_display_name: str, group_context: str = "", gemini_config: Optional[dict] = None, character_id: str = None) -> str:
    """生成角色回應"""
    try:
        # 合併配置設定
        firestore_config = firebase_manager.get_character_gemini_config(character_name)
        merged_config = firestore_config.copy()
        if gemini_config:
            merged_config.update(gemini_config)
        
        # 檢查角色是否啟用
        if not merged_config.get('enabled', True):
            print(f"⚠️ 角色 {character_name} 被停用")
            return "「我現在不太方便說話……」"
        
        # 顯示設定資訊
        model_name = merged_config.get('model', DEFAULT_RESPONSE_MODEL)
        if firestore_config:
            print(f"🎭 使用角色 {character_name} 的設定: model={model_name}, temp={merged_config.get('temperature', '預設')}")
        
        # 建立模型和提示詞
        model = _memory_manager._create_gemini_model(model_name, merged_config)
        actual_character_id = character_id if character_id else character_name
        system_prompt = _build_system_prompt(character_name, character_persona, user_display_name, 
                                           group_context, user_memories, user_prompt, actual_character_id)
        
        # 生成回應
        response = await asyncio.to_thread(model.generate_content, system_prompt)
        return response.text if response.text else "「抱歉，我現在腦中沒什麼想法……」"
        
    except ValueError as e:
        print(f"❌ {e}")
        return "「抱歉，我現在有點累……」"
    except Exception as e:
        print(f"❌ 生成回應時發生錯誤：{e}")
        return "「抱歉，我現在有點累……」" 