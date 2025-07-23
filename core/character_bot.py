import discord
from discord import app_commands
from discord.ext import commands
import os
import sys
import time
import asyncio
from dotenv import load_dotenv
load_dotenv()
from core.character_registry_custom import CharacterRegistry
from core import memory
from core.emoji_responses import smart_emoji_manager
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
        
        # 取得角色名稱（只呼叫一次）
        self.character_name = self._get_character_name()

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
        
        # 權限設定 - 支援個別角色權限
        self.allowed_guild_ids = self._get_character_permission("ALLOWED_GUILDS")
        self.allowed_channel_ids = self._get_character_permission("ALLOWED_CHANNELS")
        self.bot_owner_ids = self._get_character_permission("BOT_OWNER_IDS")
        

        
        # 設定事件處理器和指令
        self._setup_events_and_commands()
        
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
            
            # 註冊角色
            success = self.character_registry.register_character(self.character_id)
            if success:
                print(f"✅ 成功註冊角色：{self.character_name}")
            else:
                print(f"❌ 註冊角色失敗：{self.character_name}")

            # --- 修正 #2: 在 on_ready 中自動同步指令 ---
            # 這是讓斜線指令出現的關鍵步驟
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
            
            # 權限檢查... (您的原始邏輯)
            if self.allowed_channel_ids and message.channel.id not in self.allowed_channel_ids:
                return
            if self.allowed_guild_ids and message.guild and message.guild.id not in self.allowed_guild_ids:
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
        
        @self.client.tree.command(name=f"{character_prefix}_memory", description=f"顯示 {self.character_name} 的記憶內容")
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
        
    def _get_character_permission(self, permission_type: str) -> List[int]:
        """取得角色專屬權限設定，如果沒有則使用全域設定"""
        character_specific_key = f"{self.character_id.upper()}_" + permission_type
        character_specific_value = os.getenv(character_specific_key, "")
        
        if character_specific_value.strip():
            return [int(x) for x in character_specific_value.split(",") if x.strip().isdigit()]
        else:
            global_value = os.getenv(permission_type, "")
            return [int(x) for x in global_value.split(",") if x.strip().isdigit()]
        
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
    print(f"🚀 正在啟動 {character_id} Bot...")
    
    try:
        while True:
            print(f"--- 啟動 {character_id} Bot 主程序 ---")
            
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