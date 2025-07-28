import os
import asyncio
import json
from typing import Dict, Optional, List
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
import discord
from firebase_utils import firebase_manager
import memory

class CharacterRegistry:
    """簡化的角色註冊器 - 專注於角色設定管理"""
    
    def __init__(self):
        self.characters: Dict[str, dict] = {}
        self.firebase = firebase_manager
        self.db = self.firebase.db

    
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
            print(f"🔧 {character_data.get('name', '未知')}角色資料：{len(character_data)} 欄，總長度 {len(formatted_data)} 字符")
            return formatted_data
        except Exception as e:
            print(f"❌ 格式化角色資料失敗：{e}")
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
    
    async def should_respond(self, message, character_id, client, proactive_keywords=None):
        """檢查是否需要回應此訊息"""
        # 檢查是否需要回應
        mentioned = client.user.mentioned_in(message)
        contains_keyword = False
        
        # 如果是私訊，總是回應（不需要關鍵字）
        if message.guild is None:
            return True
        
        if proactive_keywords:
            contains_keyword = any(keyword.lower() in message.content.lower() for keyword in proactive_keywords)
        
        return mentioned or contains_keyword
    
    def _build_group_context(self, character_id: str, channel_id: int, user_name: str) -> str:
        """建構群組對話上下文 - 簡化版本"""
        try:
            from group_conversation_tracker import get_conversation_summary, get_active_users_in_channel, get_recent_conversation_context
            
            # 獲取群組摘要
            group_summary = get_conversation_summary(character_id, channel_id)
            
            # 獲取活躍使用者
            active_users = get_active_users_in_channel(character_id, channel_id, 30)
            other_users = [user for user in active_users if user['name'] != user_name]
            
            # 建構上下文
            context_parts = []
            if group_summary:
                context_parts.append(f"群組對話情況：{group_summary}")
            
            if other_users:
                other_user_names = [user['name'] for user in other_users[:3]]
                context_parts.append(f"其他活躍使用者：{', '.join(other_user_names)}")
            
            # 獲取最近對話記錄
            recent_context = get_recent_conversation_context(character_id, channel_id, 8)
            if recent_context:
                conversation_lines = []
                for context in recent_context:
                    if context['message'] and len(context['message']) > 5:
                        conversation_lines.append(f"{context['user_name']}：{context['message']}")
                
                if conversation_lines:
                    context_parts.append(f"最近對話記錄：\n" + "\n".join(conversation_lines))
            
            return "\n".join(context_parts) if context_parts else ""
            
        except Exception as e:
            print(f"建構群組上下文時發生錯誤：{e}")
            return ""
    
    async def handle_message(self, message, character_id, client, proactive_keywords=None, gemini_config=None):
        """處理角色訊息（簡化版本）"""
        
        user_prompt = message.content
        
        # 檢查是否被提及，如果是則移除提及標記
        if client.user.mentioned_in(message):
            user_prompt = user_prompt.replace(f'<@{client.user.id}>', '').strip()
        
        # 直接使用當前角色 ID
        persona_id = character_id
        
        if not user_prompt:
            try:
                await message.reply("「想說什麼？我在聽。」", mention_author=False)
            except discord.errors.HTTPException:
                await message.channel.send(f"{message.author.mention} 「想說什麼？我在聽。」")
            except Exception:
                await message.channel.send("「想說什麼？我在聽。」")
            return True
        
        try:
            # 獲取角色資料
            character_data = self.characters.get(persona_id, {})
            if not character_data:
                try:
                    await message.reply("「抱歉，我的設定資料似乎有問題……」", mention_author=False)
                except discord.errors.HTTPException:
                    await message.channel.send(f"{message.author.mention} 「抱歉，我的設定資料似乎有問題……」")
                except Exception:
                    await message.channel.send("「抱歉，我的設定資料似乎有問題……」")
                return True
                
            # 提取基本資訊
            user_name = message.author.display_name
            user_id = str(message.author.id)
            channel_id = message.channel.id
            bot_name = character_data.get('name', persona_id)
            
            # 追蹤使用者活動
            try:
                from group_conversation_tracker import track_user_activity
                track_user_activity(character_id, channel_id, message.author.id, user_name, user_prompt)
            except Exception as e:
                print(f"追蹤使用者活動時發生錯誤: {e}")
            
            # 格式化角色描述
            character_persona = self._format_character_data(character_data)
            
            # 獲取使用者記憶
            user_memories = memory.get_character_user_memory(persona_id, user_id)
            
            # 建構群組上下文（簡化）
            group_context = self._build_group_context(character_id, channel_id, user_name)
            
            # 生成回應
            response = await memory.generate_character_response(
                bot_name, 
                character_persona, 
                user_memories, 
                user_prompt, 
                user_name,
                group_context,
                gemini_config
            )
            
            # 保存記憶
            memory_content = f"{user_name} 說：{user_prompt}"
            save_success = await memory.save_character_user_memory(persona_id, user_id, memory_content, user_name)
            if not save_success:
                print(f"⚠️ 記憶保存失敗：{persona_id} - {user_id}")
            
            # 發送回應
            try:
                await message.reply(response, mention_author=False)
            except discord.errors.HTTPException as e:
                print(f"回覆失敗，改為普通發送：{e}")
                # 檢查是否是內容長度錯誤 (error code: 50035)
                if "50035" in str(e) or "4000 or fewer in length" in str(e) or "2000 or fewer in length" in str(e):
                    await message.channel.send("「抱歉，我想講的話太多了……」")
                else:
                    await message.channel.send(f"{message.author.mention} {response}")
            except Exception as e:
                print(f"回覆時發生未知錯誤：{e}")
                await message.channel.send(f"{message.author.mention} {response}")
            
            # 追蹤BOT回應
            try:
                from group_conversation_tracker import track_bot_response
                track_bot_response(character_id, channel_id, bot_name, response)
            except Exception as e:
                print(f"追蹤BOT回應時發生錯誤：{e}")
            
        except Exception as e:
            print(f"處理訊息時發生錯誤：{e}")
            try:
                await message.reply("「抱歉，我現在有點累……」", mention_author=False)
            except discord.errors.HTTPException:
                await message.channel.send(f"{message.author.mention} 「抱歉，我現在有點累……」")
            except Exception:
                await message.channel.send("「抱歉，我現在有點累……」")
        
        return True 