import discord
from discord import app_commands
import os
import sys
import subprocess
import time
import asyncio
from dotenv import load_dotenv
from core.character_registry_custom import CharacterRegistry
from core import memory
from typing import List, Optional, Dict

class CharacterBot:
    """通用角色 Bot 類別"""
    
    def __init__(self, character_id: str, token_env_var: str, proactive_keywords: Optional[List[str]] = None, gemini_config: Optional[dict] = None):
        self.character_id = character_id
        self.token_env_var = token_env_var
        self.proactive_keywords = proactive_keywords if proactive_keywords is not None else []
        self.gemini_config = gemini_config or {}
        
        # Discord Bot 設定
        intents = discord.Intents.default()
        intents.message_content = True
        
        # 連線穩定性設定
        self.client = discord.Client(
            intents=intents,
            heartbeat_timeout=60.0,  # 心跳超時時間
            max_messages=1000,       # 訊息快取數量
        )
        self.tree = app_commands.CommandTree(self.client)
        
        # 載入環境變數
        load_dotenv()
        self.token = os.getenv(token_env_var)
        
        # 權限設定 - 支援個別角色權限
        self.allowed_guild_ids = self._get_character_permission("ALLOWED_GUILDS")
        self.allowed_channel_ids = self._get_character_permission("ALLOWED_CHANNELS")
        self.bot_owner_ids = self._get_character_permission("BOT_OWNER_IDS")
        
        # 初始化角色註冊器
        self.character_registry = CharacterRegistry()
        
        # 設定事件處理器
        self._setup_events()
        self._setup_commands()
    
    def _get_character_permission(self, permission_type: str) -> List[int]:
        """取得角色專屬權限設定，如果沒有則使用全域設定"""
        # 先嘗試取得角色專屬設定 (例如: SHEN_ZE_ALLOWED_GUILDS)
        character_specific_key = f"{self.character_id.upper()}_" + permission_type
        character_specific_value = os.getenv(character_specific_key, "")
        
        if character_specific_value.strip():
            # 如果有角色專屬設定，使用它
            return [int(x) for x in character_specific_value.split(",") if x.strip().isdigit()]
        else:
            # 否則使用全域設定
            global_value = os.getenv(permission_type, "")
            return [int(x) for x in global_value.split(",") if x.strip().isdigit()]
        
    def _setup_events(self):
        """設定事件處理器"""
        
        @self.client.event
        async def on_ready():
            print(f'🤖 {self.character_id} Bot 已成功登入為 {self.client.user}')
            
            # 註冊角色
            success = self.character_registry.register_character(self.character_id)
            if success:
                print(f"✅ 成功註冊角色：{self.character_id}")
            else:
                print(f"❌ 註冊角色失敗：{self.character_id}")
            
            # 同步指令
            try:
                if self.allowed_guild_ids and len(self.allowed_guild_ids) > 0:
                    for guild_id in self.allowed_guild_ids:
                        await self.tree.sync(guild=discord.Object(id=guild_id))
                    print(f"已為 {len(self.allowed_guild_ids)} 個指定的伺服器同步指令。")
                else:
                    synced = await self.tree.sync()
                    print(f"已全域同步 {len(synced)} 個指令。")
            except Exception as e:
                print(f"同步指令失敗：{e}")
        
        @self.client.event
        async def on_disconnect():
            print(f'⚠️ {self.character_id} Bot 連線中斷')
        
        @self.client.event
        async def on_resumed():
            print(f'✅ {self.character_id} Bot 連線已恢復')
        
        @self.client.event
        async def on_message(message):
            """處理訊息"""
            # 忽略 Bot 自己的訊息
            if message.author == self.client.user:
                return
            
            # 檢查頻道權限
            if self.allowed_channel_ids and message.channel.id not in self.allowed_channel_ids:
                return
            
            # 檢查伺服器權限
            if self.allowed_guild_ids and message.guild and message.guild.id not in self.allowed_guild_ids:
                return
            
            # 處理訊息（只使用自己的角色）
            await self.character_registry.handle_message(
                message, 
                self.character_id, 
                self.client, 
                self.proactive_keywords,
                self.gemini_config
            )
    
    def _setup_commands(self):
        """設定斜線指令"""
        
        @self.tree.command(name="restart", description=f"重新啟動 {self.character_id} Bot (僅限擁有者使用)")
        async def restart(interaction: discord.Interaction):
            """重新啟動機器人"""
            if not self.bot_owner_ids or interaction.user.id not in self.bot_owner_ids:
                await interaction.response.send_message("❌ 你沒有權限使用此指令。", ephemeral=True)
                return

            await interaction.response.send_message(f"🔄 {self.character_id} Bot 正在重新啟動⋯⋯", ephemeral=True)
            print(f"--- 由擁有者觸發 {self.character_id} Bot 重新啟動 ---")
            await self.client.close()
            sys.exit(26)
        
        @self.tree.command(name="info", description=f"顯示 {self.character_id} 的資訊")
        async def info(interaction: discord.Interaction):
            """顯示角色資訊"""
            character_name = self.character_registry.get_character_setting(self.character_id, 'name', self.character_id)
            character_persona = self.character_registry.get_character_setting(self.character_id, 'persona', '未設定')
            
            embed = discord.Embed(
                title=f"🤖 {character_name}",
                description=character_persona[:1000] if character_persona else "角色設定未載入",
                color=discord.Color.blue()
            )
            embed.add_field(name="角色 ID", value=self.character_id, inline=True)
            embed.add_field(name="狀態", value="✅ 線上", inline=True)
            
            await interaction.response.send_message(embed=embed, ephemeral=True)
        
        @self.tree.command(name="memory_stats", description=f"顯示 {self.character_id} 的記憶統計")
        async def memory_stats(interaction: discord.Interaction):
            """顯示記憶統計"""
            if not self.bot_owner_ids or interaction.user.id not in self.bot_owner_ids:
                await interaction.response.send_message("❌ 你沒有權限使用此指令。", ephemeral=True)
                return
            
            user_memories = memory.get_character_user_memory(self.character_id, str(interaction.user.id))
            memory_count = len(user_memories) if user_memories else 0
            total_chars = sum(len(mem) for mem in user_memories) if user_memories else 0
            
            embed = discord.Embed(
                title=f"📊 {self.character_id} 記憶統計",
                color=discord.Color.green()
            )
            embed.add_field(name="記憶數量", value=f"{memory_count} 則", inline=True)
            embed.add_field(name="總字符數", value=f"{total_chars} 字符", inline=True)
            
            await interaction.response.send_message(embed=embed, ephemeral=True)
        
        @self.tree.command(name="active_users", description=f"顯示 {self.character_id} 的活躍使用者")
        async def active_users(interaction: discord.Interaction):
            """顯示活躍使用者"""
            if not self.bot_owner_ids or interaction.user.id not in self.bot_owner_ids:
                await interaction.response.send_message("❌ 你沒有權限使用此指令。", ephemeral=True)
                return
            
            try:
                from core.group_conversation_tracker import get_active_users_in_channel, get_conversation_summary
                
                channel_id = interaction.channel_id
                if channel_id is None:
                    await interaction.response.send_message("❌ 無法獲取頻道資訊。", ephemeral=True)
                    return
                    
                active_users = get_active_users_in_channel(self.character_id, channel_id, 30)
                conversation_summary = get_conversation_summary(self.character_id, channel_id)
                
                embed = discord.Embed(
                    title=f"👥 {self.character_id} 活躍使用者",
                    description=conversation_summary,
                    color=discord.Color.blue()
                )
                
                if active_users:
                    for i, user in enumerate(active_users[:5], 1):  # 最多顯示5個使用者
                        embed.add_field(
                            name=f"{i}. {user['name']}",
                            value=f"訊息數：{user['message_count']}\n最後活動：{user['last_activity'].strftime('%H:%M:%S')}",
                            inline=True
                        )
                else:
                    embed.add_field(name="狀態", value="目前沒有活躍使用者", inline=False)
                
                await interaction.response.send_message(embed=embed, ephemeral=True)
                
            except Exception as e:
                print(f"獲取活躍使用者時發生錯誤: {e}")
                await interaction.response.send_message("❌ 獲取活躍使用者資訊時發生錯誤。", ephemeral=True)
        
        @self.tree.command(name="gemini_config", description=f"顯示 {self.character_id} 的 Gemini AI 參數設定")
        async def gemini_config(interaction: discord.Interaction):
            """顯示 Gemini AI 參數設定"""
            if not self.bot_owner_ids or interaction.user.id not in self.bot_owner_ids:
                await interaction.response.send_message("❌ 你沒有權限使用此指令。", ephemeral=True)
                return
            
            embed = discord.Embed(
                title=f"🤖 {self.character_id} Gemini AI 參數",
                color=discord.Color.purple()
            )
            
            # 顯示當前參數
            temperature = self.gemini_config.get('temperature', '未設定')
            top_k = self.gemini_config.get('top_k', '未設定')
            top_p = self.gemini_config.get('top_p', '未設定')
            
            embed.add_field(name="🌡️ Temperature", value=f"{temperature}", inline=True)
            embed.add_field(name="🎯 Top-K", value=f"{top_k}", inline=True)
            embed.add_field(name="📊 Top-P", value=f"{top_p}", inline=True)
            
            # 參數說明
            embed.add_field(
                name="📝 參數說明", 
                value="""**Temperature**: 控制創造性 (0.0-1.0)
**Top-K**: 詞彙多樣性 (1-40)
**Top-P**: 核採樣 (0.0-1.0)""", 
                inline=False
            )
            
            await interaction.response.send_message(embed=embed, ephemeral=True)
    
    def run(self):
        """運行 Bot"""
        if not self.token:
            print(f"❌ 錯誤：請在 .env 檔案中設定 {self.token_env_var}")
            return False
        
        try:
            self.client.run(self.token)
            return True
        except Exception as e:
            print(f"❌ {self.character_id} Bot 運行時發生錯誤：{e}")
            return False

def run_character_bot_with_restart(character_id: str, token_env_var: str, proactive_keywords: Optional[List[str]] = None, gemini_config: Optional[dict] = None):
    """運行角色 Bot 並支援自動重啟"""
    print(f"🚀 正在啟動 {character_id} Bot...")
    
    try:
        while True:
            print(f"--- 啟動 {character_id} Bot 主程序 ---")
            
            # 創建並運行 Bot
            bot = CharacterBot(character_id, token_env_var, proactive_keywords, gemini_config)
            success = bot.run()
            
            # 如果運行失敗，退出
            if not success:
                print(f"--- {character_id} Bot 啟動失敗 ---")
                break
                
    except KeyboardInterrupt:
        print(f"\n--- 偵測到手動停止指令，正在關閉 {character_id} Bot... ---")
        sys.exit(0)
    except SystemExit as e:
        if e.code == 26:
            print(f"--- 偵測到 {character_id} Bot 重啟指令，2 秒後重新啟動... ---")
            time.sleep(2)
            # 重新啟動整個程序
            os.execv(sys.executable, [sys.executable] + sys.argv)
        else:
            print(f"--- {character_id} Bot 已停止，退出碼為 {e.code} ---")
            sys.exit(e.code) 