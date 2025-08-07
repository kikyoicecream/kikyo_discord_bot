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

class MemoryManager:
    """記憶管理器"""
    
    def __init__(self):
        # 使用統一的 Firebase 管理器
        self.firebase = firebase_manager
    
    @property
    def db(self):
        """獲取 Firestore 資料庫實例"""
        return self.firebase.db
    
    async def save_character_user_memory(self, character_id: str, user_id: str, content: str, user_name: str = "使用者"):
        """保存角色與使用者的對話記憶（簡化版本 - 所有使用者記憶存在單一文件）"""
        if not self.db:
            print("❌ Firestore 資料庫連接失敗，無法保存記憶")
            return False
            
        try:
            print(f"📝 正在處理記憶：{character_id} - {user_id}")
            
            # 使用 Gemini API 整理和摘要記憶
            summarized_memory = await self._summarize_memory_with_gemini(content, user_name, character_id)
            
            # 使用新的簡化路徑結構：/{character_id}/users/（單一文件包含所有使用者）
            doc_ref = self.db.collection(character_id).document('users')
            
            # 獲取現有記憶文件
            doc = doc_ref.get()  # type: ignore
            if doc.exists:
                data = doc.to_dict()
                all_users_memories = data if data else {}
            else:
                all_users_memories = {}
                print(f"🆕 為角色 {character_id} 創建新的使用者記憶文檔")
            
            # 獲取該使用者的記憶陣列
            user_memories = all_users_memories.get(user_id, [])
            
            # 將摘要內容添加到記憶陣列中
            user_memories.append(summarized_memory)
            
            # 當記憶超過門檻時，統整成一則摘要
            memory_limit = firebase_manager.get_memory_limit()
            if len(user_memories) > memory_limit:
                print(f"📋 使用者 {user_id} 記憶超過 {memory_limit} 則，正在統整記憶……")
                consolidated_memory = await self._consolidate_memories_with_gemini(user_memories, user_name, character_id)
                user_memories = [consolidated_memory]  # 只保留統整後的記憶
                print(f"✅ 記憶已統整完成")
            
            # 更新該使用者的記憶
            all_users_memories[user_id] = user_memories
            
            # 保存到 Firestore - 單一文件格式
            doc_ref.set(all_users_memories)
            
            print(f"✅ 記憶保存成功：使用者 {user_id} 現有 {len(user_memories)} 則記憶")
            return True
            
        except Exception as e:
            self.firebase.log_error("保存記憶", e)
            return False

    def get_character_user_memory(self, character_id: str, user_id: str, limit: int = 25) -> List[str]:
        """獲取角色與使用者的對話記憶（簡化版本 - 從單一文件中獲取）"""
        if not self.db:
            return []
            
        try:
            # 使用新的簡化路徑結構：/{character_id}/users/
            doc_ref = self.db.collection(character_id).document('users')
            doc = doc_ref.get()  # type: ignore
            
            if doc.exists:
                data = doc.to_dict()
                if data and user_id in data:
                    user_memories = data[user_id]  # 取得該使用者的記憶陣列
                    
                    # 返回最近的記憶（根據限制）
                    if len(user_memories) <= limit:
                        return user_memories
                    else:
                        return user_memories[-limit:]  # 返回最後 limit 則記憶
                else:
                    return []  # 該使用者沒有記憶
            else:
                return []  # 該角色沒有任何使用者記憶
                
        except Exception as e:
            self.firebase.log_error("獲取記憶", e)
            return []
    
    def _get_prompt_from_firestore(self, prompt_type: str, character_id: str = None) -> tuple[str, str]:
        """從 Firestore 獲取指定類型的 prompt 和 model 設定，支援個別角色自定義prompt"""
        if character_id:
            return self.firebase.get_character_prompt_config(character_id, prompt_type)
        else:
            return self.firebase.get_prompt_with_model(prompt_type)

    def _get_character_gemini_config_from_firestore(self, character_id: str) -> dict:
        """從 Firestore 獲取角色專用的完整 Gemini 設定"""
        return self.firebase.get_character_gemini_config(character_id)

    def _get_character_model_from_firestore(self, character_id: str) -> str:
        """從 Firestore 獲取角色專用的模型設定"""
        gemini_config = self._get_character_gemini_config_from_firestore(character_id)
        return gemini_config.get('model', DEFAULT_RESPONSE_MODEL)

    async def _summarize_memory_with_gemini(self, content: str, user_name: str = "使用者", character_id: str = "角色") -> str:
        """使用 Gemini API 整理和摘要記憶"""
        try:
            # 從 Firestore 獲取 prompt 和 model 設定，支援個別角色自定義prompt
            base_prompt, model_name = self._get_prompt_from_firestore('user_memories', character_id)
            if not base_prompt.strip():
                print(f"❌ Firestore 中沒有 user_memories prompt，無法處理記憶")
                return f"使用者進行了對話互動：{content[:30]}……"
            
            # 使用 Firestore 中指定的模型
            model = genai.GenerativeModel(model_name)  # type: ignore
            
            # 從 character_id 獲取 character_name
            system_config = self.firebase.get_character_system_config(character_id)
            character_name = system_config.get('name', character_id)  # 如果沒有設定 name，回退使用 character_id
            
            # 格式化 Firestore 中的 prompt，然後添加對話內容
            try:
                formatted_prompt = base_prompt.format(
                    character_name=character_name,  # 改用 character_name
                    user_name=user_name
                )
            except KeyError as e:
                print(f"❌ user_memories prompt 中使用了不存在的變數：{e}")
                print(f"📋 可用變數：character_name={character_name}, user_name={user_name}")
                print(f"🔍 請檢查 Firestore /prompt/user_memories/content 中是否使用了 {{character_id}} 而不是 {{character_name}}")
                return f"使用者進行了對話互動：{content[:30]}……"
            
            prompt = f"""
{formatted_prompt}

Conversation:
{content}
"""
            
            response = model.generate_content(prompt)
            summarized = response.text if response.text else content
            
            # 檢查是否返回了空內容
            if self.firebase.is_empty_response(summarized):
                print(f"⚠️ Gemini 返回空內容，使用備用記憶")
                return f"使用者進行了對話互動：{content[:30]}……"
            
            print(f"📋 記憶摘要完成：{summarized[:30]}")
            return summarized
            
        except Exception as e:
            return self.firebase.log_error("記憶摘要", e, f"使用者進行了對話互動：{content[:30]}……")

    async def _consolidate_memories_with_gemini(self, memories: List[str], user_name: str = "使用者", character_id: str = None) -> str:
        """使用 Gemini API 將多別角色自定義prompt）"""
        try:
            
            # 過濾掉 None 或無意義的記憶
            filtered_memories = [memory for memory in memories if not self.firebase.is_empty_response(memory)]
            
            if not filtered_memories:
                print("⚠️ 所有記憶都是 None，使用備用統整")
                return f"與 {user_name} 有過多次對話互動"
            
            # 從 Firestore 獲取 prompt 和 model 設定，支援個別角色自定義prompt
            base_prompt, model_name = self._get_prompt_from_firestore('memories_summary', character_id)
            if not base_prompt.strip():
                print(f"❌ Firestore 中沒有 memories_summary prompt，無法統整記憶")
                return f"與 {user_name} 有過多次對話互動"
            
            # 格式化 Firestore 中的 prompt，然後添加現有記憶
            try:
                formatted_prompt = base_prompt.format(
                    user_name=user_name
                )
            except KeyError as e:
                print(f"❌ memories_summary prompt 中使用了不存在的變數：{e}")
                print(f"📋 可用變數：user_name={user_name}")
                print(f"🔍 請檢查 Firestore /prompt/memories_summary/content 中的變數名稱")
                return f"與 {user_name} 有過多次對話互動"
            
            prompt = f"""
{formatted_prompt}

Existing memories:
{filtered_memories}
"""
            
            model = genai.GenerativeModel(model_name)  # type: ignore
            response = await asyncio.to_thread(model.generate_content, prompt)
            consolidated = response.text.strip() if response.text else ""
            
            if self.firebase.is_empty_response(consolidated):
                # 如果沒有回應，使用簡單合併
                consolidated = f"與 {user_name} 有過多次對話互動，包括：{', '.join(filtered_memories[:3])}"
            
            print(f"📋 記憶統整完成：{len(consolidated)} 字符")
            return consolidated
            
        except Exception as e:
            return self.firebase.log_error("記憶統整", e, f"與 {user_name} 有過多次對話互動")



# 全域記憶管理器實例
_memory_manager = MemoryManager()

async def save_character_user_memory(character_id: str, user_id: str, content: str, user_name: str = "使用者"):
    """保存角色與使用者的對話記憶"""
    return await _memory_manager.save_character_user_memory(character_id, user_id, content, user_name)

def get_character_user_memory(character_id: str, user_id: str, limit: int = 25) -> List[str]:
    """獲取角色與使用者的對話記憶"""
    return _memory_manager.get_character_user_memory(character_id, user_id, limit)

def _create_gemini_model(merged_config: dict) -> genai.GenerativeModel:
    """創建配置好的 Gemini 模型"""
    # 設定 Gemini 參數
    generation_config = {param: merged_config[param] 
                        for param in ['temperature', 'top_k', 'top_p', 'max_output_tokens'] 
                        if param in merged_config}
    
    # 安全設定（直接在程式碼中設定）
    safety_settings = [
        {"category": HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT, "threshold": HarmBlockThreshold.BLOCK_NONE},
        {"category": HarmCategory.HARM_CATEGORY_HARASSMENT, "threshold": HarmBlockThreshold.BLOCK_NONE},
        {"category": HarmCategory.HARM_CATEGORY_HATE_SPEECH, "threshold": HarmBlockThreshold.BLOCK_NONE},
        {"category": HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT, "threshold": HarmBlockThreshold.BLOCK_NONE}
    ]
    
    model_name = merged_config.get('model', DEFAULT_RESPONSE_MODEL)
    return genai.GenerativeModel(model_name, generation_config=generation_config, safety_settings=safety_settings)  # type: ignore

def _build_system_prompt(character_name: str, character_persona: str, user_display_name: str, 
                        group_context: str, user_memories: List[str], user_prompt: str, character_id: str = None) -> str:
    """構建系統提示詞"""
    # 獲取系統提示詞模板，支援個別角色自定義prompt
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
        print(f"🔍 請檢查 Firestore /prompt/system/content 中是否使用了不存在的變數")
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
    """生成角色回應（專注於個人記憶，群組上下文由外部提供）"""
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
        
        # 創建模型和提示詞
        model = _create_gemini_model(merged_config)
        # 使用傳入的 character_id，如果沒有的話使用 character_name
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