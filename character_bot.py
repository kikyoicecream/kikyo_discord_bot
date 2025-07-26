import discord
from discord import app_commands
from discord.ext import commands
import os
import sys
import time
import asyncio
import json
from dotenv import load_dotenv
load_dotenv()
from google.cloud import firestore
from google.oauth2 import service_account
from character_registry_custom import CharacterRegistry
import memory
from emoji_responses import smart_emoji_manager
from typing import List, Optional, Dict

class CharacterBot:
    """通用角色 Bot 類別（已修正）"""
    
    def __init__(self, character_id: str, token_env_var: str, proactive_keywords: Optional[List[str]] = None, gemini_config: Optional[dict] = None):
        self.character_id = character_id
        self.token_env_var = token_env_var
        self.proactive_keywords = proactive_keywords if proactive_keywords is not None else []
        self.gemini_config = gemini_config or {}

        # 初始化角色註冊器（需要在取得角色名稱之前）
        self.character_registry = CharacterRegistry()
        
        # 先註冊角色，再取得角色名稱
        self.character_registry.register_character(self.character_id)
        self.character_name = self._get_character_name()

        # 初始化 Firestore 連接
        self.db = self._init_firestore()

        # --- 修正 #1: 統一使用 commands.Bot ---
        # 直接將 self.client 初始化為 commands.Bot，它包含了所有需要的功能，包括 .tree
        intents = discord.Intents.default()
        intents.message_content = True
        self.client = commands.Bot(
            command_prefix=f'!{character_id.lower()}', # 為每個 bot 設定獨特的前綴以供除錯
            intents=intents,
            heartbeat_timeout=60.0,
            max_messages=1000
        )
        
        # 載入環境變數
        self.token = os.getenv(token_env_var)
        
        # 權限設定 - 從 Firestore 讀取（使用字串處理 Discord ID）
        self.allowed_guild_ids = self._get_character_permission_from_firestore("allowed_guilds")
        self.allowed_channel_ids = self._get_character_permission_from_firestore("allowed_channels")
        
        # 顯示簡化的權限設定
        guild_count = len(self.allowed_guild_ids)
        channel_count = len(self.allowed_channel_ids)
        print(f"🔐 {self.character_id}: {guild_count}個伺服器, {channel_count}個頻道")
        
        # 設定事件處理器和指令
        self._setup_events_and_commands()
    
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
            return db
        except Exception as e:
            print(f"❌ Firestore 連接失敗：{e}")
            return None
        
    def _get_character_name(self):
        """取得角色名稱"""
        return self.character_registry.get_character_setting(self.character_id, 'name', self.character_id)
    
    async def _check_emoji_response(self, message) -> Optional[str]:
        """檢查是否需要回應表情符號"""
        return smart_emoji_manager.get_emoji_response(self.character_id, message.content, message.guild)

    def _setup_events_and_commands(self):
        """設定事件處理器與斜線指令"""
        
        # 為每個角色創建獨特的指令名稱，避免衝突
        character_prefix = self.character_id.lower()
        
        # --- 事件處理器 ---

        @self.client.event
        async def on_ready():
            print(f'🤖 {self.character_id} Bot 已成功登入為 {self.client.user}')

            try:
                synced = await self.client.tree.sync()
                print(f"✅ {self.character_name} Bot 同步了 {len(synced)} 個指令")
            except Exception as e:
                print(f"❌ {self.character_name} Bot 指令同步失敗：{e}")

        @self.client.event
        async def on_disconnect():
            print(f'⚠️ {self.character_name} Bot 連線中斷')
        
        @self.client.event
        async def on_resumed():
            print(f'✅ {self.character_name} Bot 連線已恢復')

        @self.client.event
        async def on_message(message):
            # 忽略 Bot 自己的訊息
            if message.author == self.client.user:
                return
            
            # 權限檢查... (使用字串比較)
            if self.allowed_channel_ids and str(message.channel.id) not in self.allowed_channel_ids:
                return
            if self.allowed_guild_ids and message.guild and str(message.guild.id) not in self.allowed_guild_ids:
                return
            
            # 檢查表情符號回應
            emoji_response = await self._check_emoji_response(message)
            if emoji_response:
                try:
                    await message.add_reaction(emoji_response)
                    print(f"😊 {self.character_id} 對關鍵字回應表情符號: {emoji_response}")
                except Exception as e:
                    print(f"❌ 添加表情符號失敗: {e}")
                # 不 return，讓程式繼續處理文字回應
            
            # 檢查是否需要回應
            should_respond = await self.character_registry.should_respond(
                message, self.character_id, self.client, self.proactive_keywords
            )
            
            if not should_respond:
                return
            
            # Typing 狀態處理... (您的原始邏輯)
            typing_task = None
            async def maintain_typing():
                try:
                    while True:
                        async with message.channel.typing():
                            await asyncio.sleep(8)
                except asyncio.CancelledError:
                    pass
            
            typing_task = asyncio.create_task(maintain_typing())
            await asyncio.sleep(0.1)
            
            try:
                await self.character_registry.handle_message(
                    message, self.character_id, self.client, self.proactive_keywords, self.gemini_config
                )
            finally:
                if typing_task and not typing_task.done():
                    typing_task.cancel()
                    try:
                        await typing_task
                    except asyncio.CancelledError:
                        pass
        
        # --- 斜線指令 ---
        
        @self.client.tree.command(name=f"{character_prefix}_restart", description=f"重新啟動 {self.character_name} Bot")
        async def restart(interaction: discord.Interaction):
            await interaction.response.send_message(f"🔄 {self.character_name} Bot 正在重新啟動⋯⋯", ephemeral=True)
            print(f"--- 由 {interaction.user.name} 觸發 {self.character_name} Bot 重新啟動 ---")
            await self.client.close()
            sys.exit(26)
        
        @self.client.tree.command(name=f"{character_prefix}_keywords", description=f"顯示 {self.character_name} 的主動關鍵字")
        async def info(interaction: discord.Interaction):
            
            # 取得主動關鍵字
            keywords_text = "無設定"
            if self.proactive_keywords:
                keywords_text = "、".join(self.proactive_keywords)
            
            embed = discord.Embed(
                title=f"👤 {self.character_name}",
                description=f"**主動關鍵字：**{keywords_text}",
                color=discord.Color.blue()
            )
            
            await interaction.response.send_message(embed=embed, ephemeral=True)
        
        @self.client.tree.command(name=f"{character_prefix}_memories", description=f"顯示 {self.character_name} 的記憶內容")
        async def memory_content(interaction: discord.Interaction):
            user_memories = memory.get_character_user_memory(self.character_id, str(interaction.user.id))
            
            if not user_memories:
                await interaction.response.send_message(f"❌ {self.character_name} 還沒有與你的記憶。", ephemeral=True)
                return
            
            # 建立記憶內容的 embed
            embed = discord.Embed(
                title=f"💭 {self.character_name} 與你的記憶",
                description=f"共 {len(user_memories)} 則記憶",
                color=discord.Color.blue()
            )
            
            # 顯示所有記憶
            for i, memory_text in enumerate(user_memories, 1):
                # 限制每則記憶的長度，避免 embed 過長
                display_text = memory_text[:500] + "..." if len(memory_text) > 500 else memory_text
                embed.add_field(
                    name=f"記憶 #{i}",
                    value=display_text,
                    inline=False
                )
            
            await interaction.response.send_message(embed=embed, ephemeral=True)
        
        @self.client.tree.command(name=f"{character_prefix}_intro", description=f"顯示 {self.character_name} 的角色簡介")
        async def character_intro(interaction: discord.Interaction):
            # 從 Firestore 讀取角色簡介
            try:
                system_ref = self.db.collection(self.character_id).document('system')
                system_doc = system_ref.get()
                
                if system_doc.exists:
                    system_config = system_doc.to_dict()
                    intro_text = system_config.get('intro', '暫無角色簡介')
                else:
                    intro_text = '❌ 找不到系統配置'
                
                embed = discord.Embed(
                    title=f"👤 {self.character_name} 角色簡介",
                    description=intro_text,
                    color=discord.Color.blue()
                )
                
                await interaction.response.send_message(embed=embed, ephemeral=True)
                
            except Exception as e:
                await interaction.response.send_message(
                    f"❌ 讀取角色簡介時發生錯誤：{str(e)}", 
                    ephemeral=True
                )
        
    def _get_character_permission_from_firestore(self, permission_field: str) -> List[str]:
        """從 Firestore 取得角色權限設定（使用字串處理 Discord ID）"""
        if not self.db:
            print(f"❌ Firestore 未連接，無法讀取 {self.character_id} 的權限設定")
            return []
        
        try:
            # 從 Firestore 讀取系統配置
            system_ref = self.db.collection(self.character_id).document('system')
            system_doc = system_ref.get()
            
            if system_doc.exists:
                system_config = system_doc.to_dict()
                firestore_permissions = system_config.get(permission_field, [])
                
                # 將所有 Discord ID 轉換為字串，避免數字精度問題
                processed_permissions = []
                for x in firestore_permissions:
                    if isinstance(x, str):
                        # 如果是字串，直接使用
                        if x.isdigit():
                            processed_permissions.append(x)
                    elif isinstance(x, (int, float)):
                        # 如果是數字，轉換為字串
                        processed_permissions.append(str(int(x)))
                
                return processed_permissions
            else:
                print(f"❌ 找不到 {self.character_id} 的系統配置")
                return []
                
        except Exception as e:
            print(f"❌ 從 Firestore 讀取 {self.character_id} 權限失敗：{e}")
            return []
        
    def run(self):
        """運行 Bot"""
        if not self.token:
            print(f"❌ 錯誤：請在 .env 檔案中設定 {self.token_env_var}")
            return
        
        try:
            # 現在 self.client 是一個 Bot 物件，可以直接運行
            self.client.run(self.token)
        except Exception as e:
            print(f"❌ {self.character_name} Bot 運行時發生錯誤：{e}")

# --- 啟動器部分保持不變 ---
def run_character_bot_with_restart(character_id: str, token_env_var: str, proactive_keywords: Optional[List[str]] = None, gemini_config: Optional[dict] = None):
    """運行角色 Bot 並支援自動重啟"""
    try:
        while True:
            
            bot = CharacterBot(character_id, token_env_var, proactive_keywords, gemini_config)
            bot.run() # .run() 現在沒有回傳值了
            
            # 這裡的邏輯需要調整，因為 .run() 是阻塞的
            # SystemExit 會在這裡被捕捉到
            print(f"--- {character_id} Bot 似乎已停止，準備重啟或退出 ---")

    except KeyboardInterrupt:
        print(f"\n--- 偵測到手動停止指令，正在關閉 {character_id} Bot... ---")
        sys.exit(0)
    except SystemExit as e:
        if e.code == 26:
            print(f"--- 偵測到 {character_id} Bot 重啟指令，2 秒後重新啟動... ---")
            time.sleep(2)
            os.execv(sys.executable, [sys.executable] + sys.argv)
        else:
            print(f"--- {character_id} Bot 已停止，退出碼為 {e.code} ---")
            sys.exit(e.code)