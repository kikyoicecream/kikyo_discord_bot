#!/usr/bin/env python3
"""
群組對話追蹤模組
負責追蹤活躍使用者和群組對話上下文
"""

import json
import os
import asyncio
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Set
from google.cloud import firestore
from google.oauth2 import service_account

class GroupConversationTracker:
    """群組對話追蹤器"""
    
    def __init__(self):
        self.db = self._init_firestore()
        self.active_users: Dict[str, Dict[int, Dict[str, dict]]] = {}  # {character_id: {channel_id: {user_id: user_data}}}
        self.channel_contexts: Dict[str, Dict[int, List[dict]]] = {}   # {character_id: {channel_id: [message_contexts]}}
        
    def _init_firestore(self):
        """初始化 Firestore 連接"""
        try:
            firebase_credentials = os.getenv("FIREBASE_CREDENTIALS_JSON")
            if not firebase_credentials:
                print("❌ 未找到 FIREBASE_CREDENTIALS_JSON 環境變數")
                return None
                
            credentials_dict = json.loads(firebase_credentials)
            credentials = service_account.Credentials.from_service_account_info(credentials_dict)
            
            db = firestore.Client(credentials=credentials, project=credentials_dict['project_id'])
            print("✅ 群組對話追蹤器 Firestore 連接成功")
            return db
        except Exception as e:
            print(f"❌ 群組對話追蹤器 Firestore 連接失敗: {e}")
            return None
    
    def track_user_activity(self, character_id: str, channel_id: int, user_id: int, user_name: str, message_content: str):
        """追蹤使用者活動"""
        if character_id not in self.active_users:
            self.active_users[character_id] = {}
        if character_id not in self.channel_contexts:
            self.channel_contexts[character_id] = {}
            
        if channel_id not in self.active_users[character_id]:
            self.active_users[character_id][channel_id] = {}
        if channel_id not in self.channel_contexts[character_id]:
            self.channel_contexts[character_id][channel_id] = []
        
        # 更新活躍使用者
        current_time = datetime.now()
        user_id_str = str(user_id)
        self.active_users[character_id][channel_id][user_id_str] = {
            'name': user_name,
            'last_activity': current_time,
            'message_count': self.active_users[character_id][channel_id].get(user_id_str, {}).get('message_count', 0) + 1,
            'last_message': message_content[:100]  # 只保留前100字符
        }
        
        # 添加對話上下文
        context_entry = {
            'user_id': user_id,
            'user_name': user_name,
            'message': message_content,
            'timestamp': current_time,
            'is_bot': False
        }
        
        self.channel_contexts[character_id][channel_id].append(context_entry)
        
        # 只保留最近50則對話記錄
        if len(self.channel_contexts[character_id][channel_id]) > 50:
            self.channel_contexts[character_id][channel_id] = self.channel_contexts[character_id][channel_id][-50:]
    
    def track_bot_response(self, character_id: str, channel_id: int, bot_name: str, response_content: str):
        """追蹤BOT回應"""
        if character_id not in self.channel_contexts:
            self.channel_contexts[character_id] = {}
            
        if channel_id not in self.channel_contexts[character_id]:
            self.channel_contexts[character_id][channel_id] = []
        
        # 添加BOT回應到對話上下文
        current_time = datetime.now()
        context_entry = {
            'user_id': 0,  # BOT的ID設為0
            'user_name': bot_name,
            'message': response_content,
            'timestamp': current_time,
            'is_bot': True
        }
        
        self.channel_contexts[character_id][channel_id].append(context_entry)
        
        # 只保留最近50則對話記錄
        if len(self.channel_contexts[character_id][channel_id]) > 50:
            self.channel_contexts[character_id][channel_id] = self.channel_contexts[character_id][channel_id][-50:]
    
    def get_active_users_in_channel(self, character_id: str, channel_id: int, minutes: int = 30) -> List[dict]:
        """獲取指定時間內在該頻道活躍的使用者"""
        if character_id not in self.active_users or channel_id not in self.active_users[character_id]:
            return []
        
        current_time = datetime.now()
        cutoff_time = current_time - timedelta(minutes=minutes)
        
        active_users = []
        for user_id_str, user_data in self.active_users[character_id][channel_id].items():
            if user_data['last_activity'] > cutoff_time:
                active_users.append({
                    'user_id': int(user_id_str),
                    'name': user_data['name'],
                    'message_count': user_data['message_count'],
                    'last_activity': user_data['last_activity'],
                    'last_message': user_data['last_message']
                })
        
        # 按最後活動時間排序
        active_users.sort(key=lambda x: x['last_activity'], reverse=True)
        return active_users
    
    def get_recent_conversation_context(self, character_id: str, channel_id: int, limit: int = 10) -> List[dict]:
        """獲取最近的對話上下文"""
        if character_id not in self.channel_contexts or channel_id not in self.channel_contexts[character_id]:
            return []
        
        return self.channel_contexts[character_id][channel_id][-limit:]
    
    def get_conversation_summary(self, character_id: str, channel_id: int) -> str:
        """生成對話摘要"""
        active_users = self.get_active_users_in_channel(character_id, channel_id)
        recent_context = self.get_recent_conversation_context(character_id, channel_id, 5)
        
        if not active_users:
            return "目前沒有活躍的使用者"
        
        summary_parts = []
        
        # 活躍使用者摘要
        user_names = [user['name'] for user in active_users[:5]]  # 最多5個使用者
        if len(user_names) == 1:
            summary_parts.append(f"目前 {user_names[0]} 正在與我對話")
        else:
            summary_parts.append(f"目前活躍的使用者包括：{', '.join(user_names)}")
        
        # 最近的對話摘要
        if recent_context:
            recent_topics = []
            for context in recent_context[-6:]:  # 最近6則（包含BOT回應）
                if context['message'] and len(context['message']) > 10:
                    # 區分BOT和使用者訊息
                    if context.get('is_bot', False):
                        recent_topics.append(f"{context['user_name']}（BOT）：{context['message'][:30]}...")
                    else:
                        recent_topics.append(f"{context['user_name']}：{context['message'][:30]}...")
            
            if recent_topics:
                summary_parts.append(f"最近的對話：{' | '.join(recent_topics)}")
        
        return " | ".join(summary_parts)
    
    async def save_group_context_to_firestore(self, character_id: str, channel_id: int):
        """將群組對話上下文保存到 Firestore"""
        if not self.db:
            return False
        
        try:
            active_users = self.get_active_users_in_channel(character_id, channel_id)
            recent_context = self.get_recent_conversation_context(character_id, channel_id, 20)
            
            # 保存到 Firestore
            doc_ref = self.db.collection(character_id).document('group_context').collection('channels').document(str(channel_id))
            
            doc_ref.set({
                'last_updated': datetime.now(),
                'active_users': active_users,
                'recent_context': recent_context,
                'summary': self.get_conversation_summary(character_id, channel_id)
            })
            
            return True
        except Exception as e:
            print(f"保存群組上下文時發生錯誤: {e}")
            return False
    
    def cleanup_old_activity(self, character_id: str, minutes: int = 60):
        """清理過期的活動記錄"""
        current_time = datetime.now()
        cutoff_time = current_time - timedelta(minutes=minutes)
        
        if character_id in self.active_users:
            for channel_id in list(self.active_users[character_id].keys()):
                # 清理過期的使用者活動
                expired_users = []
                for user_id_str, user_data in self.active_users[character_id][channel_id].items():
                    if user_data['last_activity'] < cutoff_time:
                        expired_users.append(user_id_str)
                
                for user_id_str in expired_users:
                    del self.active_users[character_id][channel_id][user_id_str]
                
                # 如果頻道沒有活躍使用者，清理頻道記錄
                if not self.active_users[character_id][channel_id]:
                    del self.active_users[character_id][channel_id]
        
        if character_id in self.channel_contexts:
            for channel_id in list(self.channel_contexts[character_id].keys()):
                # 清理過期的對話上下文
                self.channel_contexts[character_id][channel_id] = [
                    context for context in self.channel_contexts[character_id][channel_id]
                    if context['timestamp'] > cutoff_time
                ]
                
                # 如果頻道沒有對話記錄，清理頻道記錄
                if not self.channel_contexts[character_id][channel_id]:
                    del self.channel_contexts[character_id][channel_id]

# 全域群組對話追蹤器實例
_group_tracker = GroupConversationTracker()

def track_user_activity(character_id: str, channel_id: int, user_id: int, user_name: str, message_content: str):
    """追蹤使用者活動"""
    _group_tracker.track_user_activity(character_id, channel_id, user_id, user_name, message_content)

def track_bot_response(character_id: str, channel_id: int, bot_name: str, response_content: str):
    """追蹤BOT回應"""
    _group_tracker.track_bot_response(character_id, channel_id, bot_name, response_content)

def get_active_users_in_channel(character_id: str, channel_id: int, minutes: int = 30) -> List[dict]:
    """獲取指定時間內在該頻道活躍的使用者"""
    return _group_tracker.get_active_users_in_channel(character_id, channel_id, minutes)

def get_conversation_summary(character_id: str, channel_id: int) -> str:
    """生成對話摘要"""
    return _group_tracker.get_conversation_summary(character_id, channel_id)

def get_recent_conversation_context(character_id: str, channel_id: int, limit: int = 10) -> List[dict]:
    """獲取最近的對話上下文"""
    return _group_tracker.get_recent_conversation_context(character_id, channel_id, limit)

async def save_group_context_to_firestore(character_id: str, channel_id: int):
    """將群組對話上下文保存到 Firestore"""
    return await _group_tracker.save_group_context_to_firestore(character_id, channel_id)

def cleanup_old_activity(character_id: str, minutes: int = 60):
    """清理過期的活動記錄"""
    _group_tracker.cleanup_old_activity(character_id, minutes) 