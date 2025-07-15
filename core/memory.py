# type: ignore[import]
import os
import sys
import google.generativeai as genai
import asyncio
from dotenv import load_dotenv
import firebase_admin
from firebase_admin import credentials, firestore
from google.cloud.firestore import SERVER_TIMESTAMP
import json
import re
import traceback
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo
from typing import List

# 對話歷史和活躍使用者追蹤
conversation_histories = {}
active_users = {}  # 追蹤每個頻道的活躍使用者

# 設定日誌的時區 (例如：台北時間 UTC+8)
LOG_TIMEZONE = ZoneInfo("Asia/Taipei")

# 記憶體管理
MAX_CONVERSATIONS = 50
MAX_HISTORY_LENGTH = 15  # 增加到15則以便更好處理群聊
ACTIVE_USER_TIMEOUT = 300  # 5分鐘後認為使用者不活躍
MEMORY_CONSOLIDATION_THRESHOLD = 30
MEMORY_CONSOLIDATION_INTERVAL = 86400  # 每24小時強制整理一次

# 追蹤每個使用者的上次整理時間
last_consolidation_time = {}

# 添加併發控制
consolidation_locks = {}  # 用於防止同時整理同一用戶的記憶

def cleanup_old_conversations():
    """清理舊對話，包括相關的記憶整理時間記錄"""
    if len(conversation_histories) > MAX_CONVERSATIONS:
        oldest_channels = list(conversation_histories.keys())[:len(conversation_histories) - MAX_CONVERSATIONS]
        for channel_id in oldest_channels:
            del conversation_histories[channel_id]
            if channel_id in active_users:
                del active_users[channel_id]
    
    # 清理舊的整理時間記錄
    if len(last_consolidation_time) > MAX_CONVERSATIONS:
        # 保留最近的記錄
        sorted_items = sorted(last_consolidation_time.items(), key=lambda x: x[1], reverse=True)
        last_consolidation_time.clear()
        last_consolidation_time.update(dict(sorted_items[:MAX_CONVERSATIONS]))

def update_active_users(channel_id: int, user_id: str, user_name: str):
    """更新頻道中的活躍使用者列表"""
    if channel_id not in active_users:
        active_users[channel_id] = {}
    
    active_users[channel_id][user_id] = {
        'name': user_name,
        'last_active': datetime.now()
    }
    
    # 清理不活躍的使用者
    cutoff_time = datetime.now() - timedelta(seconds=ACTIVE_USER_TIMEOUT)
    active_users[channel_id] = {
        uid: info for uid, info in active_users[channel_id].items()
        if info['last_active'] > cutoff_time
    }

def get_active_users_list(channel_id: int) -> list:
    """獲取頻道中的活躍使用者列表"""
    if channel_id not in active_users:
        return []
    
    cutoff_time = datetime.now() - timedelta(seconds=ACTIVE_USER_TIMEOUT)
    return [
        info['name'] for uid, info in active_users[channel_id].items()
        if info['last_active'] > cutoff_time
    ]

# --- 初始化設定 ---
load_dotenv()
GEMINI_API_KEY = os.getenv('GEMINI_API_KEY')
FIREBASE_CREDENTIALS_JSON = os.getenv('FIREBASE_CREDENTIALS_JSON')

if not GEMINI_API_KEY:
    print("錯誤：請在 .env 檔案中設定 GEMINI_API_KEY")
    sys.exit(1)

# --- 初始化 Firebase ---
try:
    firebase_creds_json = os.getenv('FIREBASE_CREDENTIALS_JSON')
    if firebase_creds_json:
        firebase_creds_dict = json.loads(firebase_creds_json)
        cred = credentials.Certificate(firebase_creds_dict)
        firebase_admin.initialize_app(cred)
        db = firestore.client()
        print("Firebase 初始化成功 (來自 Secret)。")
    else:
        print("錯誤：找不到 FIREBASE_CREDENTIALS_JSON 這個 Secret。")
        db = None
except Exception as e:
    print(f"Firebase 初始化失敗: {e}")
    db = None

# --- 初始化 Gemini AI ---
genai.configure(api_key=GEMINI_API_KEY)  # type: ignore
gemini_model = genai.GenerativeModel('models/gemini-2.0-flash')  # type: ignore

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

def get_user_memories(user_id: str):
    """從 Firebase 讀取使用者的長期記憶"""
    if not db:
        return []
    try:
        doc_ref = db.collection("users").document(user_id)
        doc = doc_ref.get()
        if doc.exists:
            doc_data = doc.to_dict()
            return doc_data.get("memories", []) if doc_data else []
        return []
    except Exception as e:
        print(f"讀取使用者 {user_id} 的記憶失敗：{e}")
        traceback.print_exc()
        return []

def get_multiple_user_memories(user_ids: list) -> dict:
    """批量獲取多個使用者的記憶"""
    if not db:
        return {}
    
    memories = {}
    for user_id in user_ids:
        try:
            doc_ref = db.collection("users").document(user_id)
            doc = doc_ref.get()
            if doc.exists:
                doc_data = doc.to_dict()
                user_memories = doc_data.get("memories", []) if doc_data else []
                if user_memories:
                    memories[user_id] = user_memories
        except Exception as e:
            print(f"讀取使用者 {user_id} 記憶失敗：{e}")
            traceback.print_exc()
    
    return memories

async def process_memory_background(new_messages: list, user_name: str, user_id: str):
    """在背景處理記憶，不影響使用者體驗"""
    print(f"開始處理使用者 {user_id} 的背景記憶任務⋯⋯")
    try:
        print(f"提取使用者 {user_id} 的記憶摘要⋯⋯")
        summary = await extract_memory_summary(new_messages, user_name)
        if summary:
            print(f"為使用者 {user_id} 儲存記憶摘要⋯⋯")
            await save_memory_to_firebase(user_id, summary, user_name)
    except Exception as e:
        print(f"背景記憶處理失敗：{e}")
        print(traceback.format_exc())

async def consolidate_user_memories(user_id: str) -> bool:
    """改進的記憶整理，增加併發控制"""
    if not db:
        return False

    # 防止同時整理同一用戶的記憶
    if user_id in consolidation_locks:
        print(f"使用者 {user_id} 的記憶正在整理中，跳過")
        return False
    
    consolidation_locks[user_id] = True

    try:
        # 獲取使用者的現有記憶
        doc_ref = db.collection("users").document(user_id)
        doc = doc_ref.get()
        if not doc.exists:
            return False
        
        doc_data = doc.to_dict()
        existing_memories = doc_data.get("memories", []) if doc_data else []
        if len(existing_memories) < 10:  # 記憶太少不需要整理
            return False
        
        # 準備整理提示詞
        memories_text = "\n".join([f"- {memory}" for memory in existing_memories])
        
        consolidation_prompt = f"""
You are a memory organization assistant. Please organize the following user's memories into a concise summary, removing duplicates and overly detailed content.

Existing memories:
{memories_text}

Organize the summary using the following format:
1. Merge similar memories (e.g., repeated mentions of interests or relationships)
2. Remove redundant information
3. Keep important personal traits and events
4. Use concise sentences
5. Avoid numbering or symbols, one key point per line

Output the organized memory directly, without any introductory text.
"""
        
        # 使用 Gemini 進行整理
        model = genai.GenerativeModel("models/gemini-2.0-flash")  # type: ignore
        response = await asyncio.to_thread(model.generate_content, consolidation_prompt)
        consolidated_text = response.text.strip() if response.text else ""
        
        if not consolidated_text:
            return False
        
        # 清理整理後的記憶
        consolidated_lines = []
        for line in consolidated_text.split('\n'):
            # 移除可能的數字編號和符號
            cleaned_line = re.sub(r'^\d+\.\s*', '', line.strip())
            cleaned_line = re.sub(r'^[-•*]\s*', '', cleaned_line)
            if cleaned_line and len(cleaned_line) > 3:  # 過濾太短的內容
                consolidated_lines.append(cleaned_line)
        
        if not consolidated_lines:
            return False
        
        # 更新 Firebase（增加錯誤處理）
        try:
            doc_ref.set({
                "memories": consolidated_lines,
                "last_updated": SERVER_TIMESTAMP,
                "last_consolidated": SERVER_TIMESTAMP
            }, merge=True)
            
            print(f"已為使用者 {user_id} 整理記憶：{len(existing_memories)} -> {len(consolidated_lines)}")
        
            # 更新整理時間
            last_consolidation_time[user_id] = datetime.now(timezone.utc)
            return True
        
        except Exception as e:
            print(f"更新 Firebase 失敗：{e}")
            traceback.print_exc()
            return False

    except Exception as e:
        print(f"記憶整理失敗：{e}")
        traceback.print_exc()
        return False
    finally:
        # 清理鎖
        consolidation_locks.pop(user_id, None)

async def should_consolidate_memories(user_id: str) -> bool:
    """改進的記憶整理需求判斷"""
    if not db:
        return False
    
    try:
        # 檢查記憶數量
        doc_ref = db.collection("users").document(user_id)
        doc = doc_ref.get()
        if not doc.exists:
            return False
        
        doc_data = doc.to_dict()
        memories = doc_data.get("memories", []) if doc_data else []
        
        # 如果記憶數量超過閾值，需要整理
        if len(memories) >= MEMORY_CONSOLIDATION_THRESHOLD:
            return True
        
        # 統一使用 UTC 時間進行比較
        current_time = datetime.now(timezone.utc)

        # 檢查本地記錄的時間間隔
        last_time = last_consolidation_time.get(user_id)
        if last_time:
            # 轉換為 UTC 時間
            if last_time.tzinfo is not None:
                last_time_utc = last_time.utctimetuple()
                last_time_utc = datetime(*last_time_utc[:6])
            else:
                last_time_utc = last_time
            
            time_diff = current_time - last_time_utc
            if time_diff.total_seconds() >= MEMORY_CONSOLIDATION_INTERVAL:
                return True
            
        # 檢查 Firebase 中的上次整理時間
        data = doc.to_dict()
        if data and "last_consolidated" in data and data["last_consolidated"]:
            try:
                last_consolidated = data["last_consolidated"]
                if hasattr(last_consolidated, 'timestamp'):
                    # Firestore Timestamp 轉換為 UTC datetime
                    last_consolidated_utc = datetime.fromtimestamp(
                            last_consolidated.timestamp(), 
                            timezone.utc
                        )
                    time_diff = current_time - last_consolidated_utc
                    if time_diff.total_seconds() >= MEMORY_CONSOLIDATION_INTERVAL:
                        return True
            except Exception as e:
                print(f"解析 Firebase 時間戳失敗：{e}")
                traceback.print_exc()
                # 如果時間解析失敗，根據記憶數量判斷
                return len(memories) >= 10
        else:
            # 從未整理過，如果有足夠記憶就整理
            return len(memories) >= 10
        
        return False
        
    except Exception as e:
        print(f"檢查整理需求失敗：{e}")
        traceback.print_exc()
        return False

async def handle_consolidate_command(message, user_id: str):
    """處理手動整理記憶的命令"""
    try:
        success = await consolidate_user_memories(user_id)
        if success:
            await message.reply("✅ 記憶整理完成！", mention_author=False)
        else:
            await message.reply("❌ 記憶整理失敗或無需整理", mention_author=False)
    except Exception as e:
        await message.reply("❌ 記憶整理過程中發生錯誤", mention_author=False)
        print(f"手動整理記憶失敗：{e}")
        traceback.print_exc()

async def extract_memory_summary(new_messages: list, current_user_name: str) -> str:
    """從新的對話消息中提取關於當前使用者的記憶摘要"""
    if not new_messages:
        return ""
    
    # 過濾出當前使用者的消息
    user_messages = [
        msg for msg in new_messages 
        if msg.get('name') == current_user_name and msg.get('role') == 'user'
    ]
    
    if not user_messages:
        return ""
    
    # 格式化對話內容，包含上下文
    messages_text = "\n".join([
        f"{msg.get('name', '某人')}: {msg['parts'][0]}"
        for msg in new_messages
    ])
    
    prompt = f"""
You are a memory extraction assistant. From the conversation below, identify important information about {current_user_name}, including: personal preferences, hobbies or interests, significant life events or experiences, emotional state or personality traits, relationships or interactions with other users, and any other facts worth remembering long-term.

Conversation:
{messages_text}

Please extract only information related to {current_user_name}, listing each point as a concise sentence, one per line, without numbering or formatting symbols.
If there is no important information worth remembering, reply with "None."

Example format:
Enjoys watching anime
Lives in Taipei
Currently learning programming
Has a good relationship with other users
"""
    
    try:
        model = genai.GenerativeModel("models/gemini-2.0-flash")  # type: ignore
        response = await asyncio.to_thread(model.generate_content, prompt)
        result = response.text.strip() if response.text else ""
        
        if result and result != "無":
            lines = result.split('\n')
            cleaned_lines = []
            for line in lines:
                # 移除行首的數字編號（如 "1. ", "2. " 等）
                cleaned_line = re.sub(r'^\d+\.\s*', '', line.strip())
                # 移除行首的破折號或其他符號
                cleaned_line = re.sub(r'^[-•*]\s*', '', cleaned_line)
                if cleaned_line:
                    cleaned_lines.append(cleaned_line)
            result = '\n'.join(cleaned_lines)
        
        return result if result != "無" else ""
    except Exception as e:
        print(f"記憶摘要提取失敗：{e}")
        traceback.print_exc()
        return ""

async def save_memory_to_firebase(user_id: str, summary: str, user_name: str):
    """改進的記憶保存，增加更好的錯誤處理"""
    if not db or not summary:
        return
        
    try:
        doc_ref = db.collection("users").document(user_id)
        user_doc = doc_ref.get()
        doc_data = user_doc.to_dict() if user_doc.exists else None
        existing = doc_data.get("memories", []) if doc_data else []
        
        new_points = [line.strip() for line in summary.split("\n") if line.strip()]
        
        # 先加進去
        all_memories = existing + new_points

        # 如果超過30則，壓縮最舊的30則
        while len(all_memories) > 30:
            to_compress = all_memories[:30]
            compressed = await compress_memories(to_compress, user_name)
            # 用特殊標記區分壓縮記憶
            compressed = f"{compressed}"
            all_memories = [compressed] + all_memories[30:]

        # 最後只保留30則
        if len(all_memories) > 30:
            all_memories = all_memories[-30:]

        doc_ref.set({
            "memories": all_memories,
            "last_updated": SERVER_TIMESTAMP
        }, merge=True)
        timestamp = datetime.now(LOG_TIMEZONE).strftime('%Y/%m/%d %H:%M')
        print(f"{timestamp} 已為使用者 {user_id} 保存 {len(new_points)} 則新記憶，總共 {len(all_memories)} 則記憶")

    except Exception as e:
        print(f"保存記憶過程失敗：{e}")
        traceback.print_exc()

async def compress_memories(memories: list, user_name: str) -> str:
    """
    Using Gemini, compress multiple memory entries into a single narrative paragraph no longer than 100 tokens.
    """
    prompt = f"""
Please condense the following {len(memories)} memories about {user_name} into a summary, no longer than 100 tokens. Retain the most important traits, events, relationships, and interests. Present the summary as a narrative paragraph—do not use bullet points or numbering.

記憶內容：
{chr(10).join('- ' + m for m in memories)}
"""
    model = genai.GenerativeModel("models/gemini-2.0-flash")  # type: ignore
    response = await asyncio.to_thread(model.generate_content, prompt)
    return response.text.strip() if response.text else ""

def format_character_profile(persona: dict) -> str:
    """格式化角色資料"""
    profile_lines = []
    for key, value in persona.items():
        key_formatted = key.replace("_", " ").capitalize()
        if isinstance(value, list):
            value = ", ".join(value)
        elif value is None or value == "":
            continue
        profile_lines.append(f"- {key_formatted}: {value}")
    return "\n".join(profile_lines)

def format_group_memories(memories_dict: dict, active_users_dict: dict) -> str:
    """格式化群組中活躍使用者的記憶"""
    if not memories_dict:
        return "目前沒有關於其他使用者的記憶記錄"
    
    formatted_memories = []
    for user_id, memories in memories_dict.items():
        # 找到使用者名稱
        user_name = "未知使用者"
        for uid, info in active_users_dict.items():
            if uid == user_id:
                user_name = info['name']
                break
        
        if memories:
            formatted_memories.append(f"關於 {user_name}:")
            for memory in memories[-5:]:  # 只顯示最近5則記憶
                formatted_memories.append(f"  - {memory}")
    
    return "\n".join(formatted_memories) if formatted_memories else "目前沒有關於其他使用者的記憶記錄"

# --- 角色特定記憶系統 ---
def get_character_user_memories(character_id: str, user_id: str) -> List[dict]:
    """從 Firestore 獲取特定角色的用戶記憶 (新結構: character_id/users/discord_user_id/memory)"""
    if not db:
        return []
    
    try:
        # 新結構：character_id/users/discord_user_id/memory
        memory_doc_ref = db.collection(character_id).document('users').collection(user_id).document('memory')
        memory_doc = memory_doc_ref.get()
        
        if memory_doc.exists:
            memory_data = memory_doc.to_dict()
            if memory_data:
                # 將條列式欄位轉換為 list
                memory_list = []
                for key, value in memory_data.items():
                    if key.startswith('memory_') or key.isdigit():  # 支援 memory_1, memory_2 或 1, 2, 3 格式
                        memory_list.append({
                            'content': value,
                            'timestamp': datetime.now(ZoneInfo('Asia/Taipei')),  # 預設時間戳
                            'user_id': user_id,
                            'field_name': key
                        })
                
                # 按欄位名稱排序
                memory_list.sort(key=lambda x: x['field_name'])
                return memory_list
        
        return []
    except Exception as e:
        print(f"獲取角色 {character_id} 用戶 {user_id} 記憶失敗: {e}")
        return []

def save_character_user_memory(character_id: str, user_id: str, memory_content: str):
    """保存用戶記憶到特定角色的 Firestore (新結構: character_id/users/discord_user_id/memory)"""
    if not db:
        return
    
    try:
        # 新結構：character_id/users/discord_user_id/memory
        memory_doc_ref = db.collection(character_id).document('users').collection(user_id).document('memory')
        memory_doc = memory_doc_ref.get()
        
        current_memories = {}
        if memory_doc.exists:
            current_memories = memory_doc.to_dict() or {}
        
        # 找到下一個可用的記憶欄位編號
        memory_keys = [key for key in current_memories.keys() if key.startswith('memory_')]
        if memory_keys:
            # 提取數字並找到最大值
            numbers = []
            for key in memory_keys:
                try:
                    num = int(key.split('_')[1])
                    numbers.append(num)
                except:
                    pass
            next_num = max(numbers) + 1 if numbers else 1
        else:
            next_num = 1
        
        # 添加新記憶
        new_field_name = f"memory_{next_num}"
        current_memories[new_field_name] = memory_content
        current_memories['last_updated'] = SERVER_TIMESTAMP
        
        # 保存更新的記憶
        memory_doc_ref.set(current_memories, merge=True)
        
        # 檢查是否需要整理記憶
        check_and_consolidate_character_memories(character_id, user_id)
        
    except Exception as e:
        print(f"保存角色 {character_id} 用戶 {user_id} 記憶失敗: {e}")

def check_and_consolidate_character_memories(character_id: str, user_id: str):
    """檢查並整理特定角色的用戶記憶 (新結構)"""
    if not db:
        return
        
    try:
        # 新結構：character_id/users/discord_user_id/memory
        memory_doc_ref = db.collection(character_id).document('users').collection(user_id).document('memory')
        memory_doc = memory_doc_ref.get()
        
        if not memory_doc.exists:
            return
            
        memory_data = memory_doc.to_dict() or {}
        
        # 獲取所有記憶欄位
        memory_fields = {}
        for key, value in memory_data.items():
            if key.startswith('memory_') and isinstance(value, str):
                try:
                    num = int(key.split('_')[1])
                    memory_fields[num] = value
                except:
                    pass
        
        # 如果記憶超過 30 條，進行整理
        if len(memory_fields) > 30:
            # 按編號排序
            sorted_memories = sorted(memory_fields.items())
            
            # 保留最新的 10 條記憶
            recent_memories = sorted_memories[-10:]
            old_memories = sorted_memories[:-10]
            
            # 整理舊記憶
            old_content = [content for _, content in old_memories]
            
            # 使用 AI 整理記憶
            consolidated_content = consolidate_memories_with_ai(old_content, f"角色 {character_id} 的用戶 {user_id}")
            
            # 重新組織記憶結構
            new_memories = {'last_updated': SERVER_TIMESTAMP}
            
            # 添加整理後的摘要
            if consolidated_content:
                new_memories['memory_1'] = f"記憶摘要：{consolidated_content}"  # type: ignore
                
            # 添加最近的記憶
            for i, (_, content) in enumerate(recent_memories, start=2):
                new_memories[f'memory_{i}'] = content
            
            # 更新 Firestore
            memory_doc_ref.set(new_memories)
            
            print(f"已為角色 {character_id} 用戶 {user_id} 整理記憶：{len(old_memories)} -> 1 條摘要 + {len(recent_memories)} 條最新記憶")
                
    except Exception as e:
        print(f"整理角色 {character_id} 用戶 {user_id} 記憶失敗: {e}")

def consolidate_memories_with_ai(memories: List[str], context: str) -> str:
    """使用 AI 整理記憶"""
    if not memories:
        return ""
    
    try:
        prompt = f"""
請將以下 {len(memories)} 條關於{context}的記憶整理成一個簡潔的摘要，保留最重要的資訊：

記憶內容：
{chr(10).join('- ' + mem for mem in memories if mem.strip())}

請用繁體中文回應，將重要的個人特質、事件、關係和興趣整理成一段不超過 100 字的摘要。
"""
        
        response = gemini_model.generate_content(prompt)
        return response.text.strip() if response.text else ""
    except Exception as e:
        print(f"AI 整理記憶失敗: {e}")
        return f"過去的記憶摘要：{' '.join(memories[:5])}"  # 簡單的備用方案

async def generate_character_response(character_name: str, character_persona: str, user_memories: List[dict], user_prompt: str, user_display_name: str) -> str:
    """為特定角色生成回應"""
    try:
        # 建立記憶上下文
        memory_context = ""
        if user_memories:
            memory_context = f"\n\n關於 {user_display_name} 的記憶：\n"
            for mem in user_memories[-5:]:  # 只使用最近 5 條記憶
                memory_context += f"- {mem.get('content', '')}\n"
        
        # 建立完整的提示
        full_prompt = f"""你是 {character_name}。

{character_persona}

{memory_context}

現在請回應：{user_prompt}"""
        
        response = await asyncio.to_thread(gemini_model.generate_content, full_prompt)
        return response.text.strip() if response.text else "「我現在有點累...」"
    except Exception as e:
        print(f"生成角色回應失敗: {e}")
        return "「抱歉，我現在有點累...」"