import discord
from discord import app_commands
import os
import sys
import subprocess
import time
from dotenv import load_dotenv
from core.character_registry_custom import CharacterRegistry

def run_bot():
    """運行 Discord Bot 的主要函數"""
    # --- Discord Bot 設定 ---
    intents = discord.Intents.default()
    intents.message_content = True
    client = discord.Client(intents=intents)
    tree = app_commands.CommandTree(client)

    # --- 初始化設定 ---
    load_dotenv()
    ALLOWED_GUILD_IDS = [int(x) for x in os.getenv("ALLOWED_GUILDS", "").split(",") if x.strip().isdigit()]
    ALLOWED_CHANNEL_IDS = [int(x) for x in os.getenv("ALLOWED_CHANNELS", "").split(",") if x.strip().isdigit()]
    DISCORD_TOKEN = os.getenv('DISCORD_TOKEN')
    BOT_OWNER_IDS = [int(id) for id in os.getenv("BOT_OWNER_IDS", "").split(',') if id.strip().isdigit()]

    if not DISCORD_TOKEN:
        print("錯誤：請在 .env 檔案中設定 DISCORD_TOKEN")
        return False

    # --- 初始化角色註冊器 ---
    character_registry = CharacterRegistry()

    # 註冊所有角色
    def register_all_characters():
        """註冊所有可用的角色"""
        characters_to_register = [
            "shen_ze",
            # 未來可以加入更多角色，例如：
            # "kikyo",
            # "other_character"
        ]
        
        for character_id in characters_to_register:
            success = character_registry.register_character(character_id)
            if success:
                print(f"✅ 成功註冊角色: {character_id}")
            else:
                print(f"❌ 註冊角色失敗: {character_id}")
        
        registered_characters = list(character_registry.characters.keys())
        print(f"已註冊的角色: {registered_characters}")

    # 在啟動時註冊角色
    register_all_characters()

    # --- Bot 事件處理 ---
    @client.event
    async def on_ready():
        print(f'Bot 已成功登入為 {client.user}')
        try:
            if ALLOWED_GUILD_IDS and len(ALLOWED_GUILD_IDS) > 0:
                for guild_id in ALLOWED_GUILD_IDS:
                    await tree.sync(guild=discord.Object(id=guild_id))
                print(f"已為 {len(ALLOWED_GUILD_IDS)} 個指定的伺服器同步指令。")
            else:
                synced = await tree.sync()
                print(f"已全域同步 {len(synced)} 個指令。")
        except Exception as e:
            print(f"同步指令失敗: {e}")

    @client.event
    async def on_message(message):
        """處理所有訊息"""
        # 忽略 Bot 自己的訊息
        if message.author == client.user:
            return
        
        # 檢查頻道權限
        if ALLOWED_CHANNEL_IDS and message.channel.id not in ALLOWED_CHANNEL_IDS:
            return
        
        # 檢查伺服器權限
        if ALLOWED_GUILD_IDS and message.guild and message.guild.id not in ALLOWED_GUILD_IDS:
            return
        
        # 使用沈澤作為預設角色處理訊息
        proactive_keywords = ["沈澤", "shen_ze", "沈", "澤"]
        await character_registry.handle_message(message, "shen_ze", client, proactive_keywords)

    @tree.command(name="rsz", description="重新啟動BOT (僅限擁有者使用)")
    async def rsz(interaction: discord.Interaction):
        """重新啟動機器人"""
        if not BOT_OWNER_IDS or interaction.user.id not in BOT_OWNER_IDS:
            await interaction.response.send_message("❌ 你沒有權限使用此指令。", ephemeral=True)
            return

        await interaction.response.send_message("Bot 正在重新啟動⋯⋯", ephemeral=True)
        print("--- 由擁有者觸發 Bot 重新啟動 ---")
        await client.close()
        sys.exit(26)

    @tree.command(name="角色", description="切換或查看可用的角色")
    async def characters(interaction: discord.Interaction, character_name: str = ""):
        """角色管理指令"""
        if character_name:
            # 嘗試切換角色
            if character_name in character_registry.characters:
                await interaction.response.send_message(f"已切換到角色：{character_name}", ephemeral=True)
            else:
                await interaction.response.send_message(f"找不到角色：{character_name}", ephemeral=True)
        else:
            # 顯示所有可用角色
            characters_list = list(character_registry.characters.keys())
            if characters_list:
                await interaction.response.send_message(f"可用角色：{', '.join(characters_list)}", ephemeral=True)
            else:
                await interaction.response.send_message("目前沒有可用的角色", ephemeral=True)

    # --- 啟動 Bot ---
    try:
        client.run(DISCORD_TOKEN)
    except Exception as e:
        print(f"Bot 運行時發生錯誤: {e}")
        return False
    
    return True

def main():
    """
    Bot 啟動與監控主程序。
    這個函數會啟動 Bot，並在收到特定退出碼 (26) 時自動重啟它。
    """
    # 確保我們在腳本所在的目錄下執行
    os.chdir(os.path.dirname(os.path.abspath(__file__)))
    
    print("🚀 正在啟動 Kikyo Discord Bot...")
    
    try:
        while True:
            print("--- 啟動 Bot 主程序 ---")
            
            # 創建子進程運行 bot
            process = subprocess.run([sys.executable, __file__, "--run-bot"])
            
            if process.returncode == 26:
                print("--- 偵測到重啟指令 (退出碼 26)，2 秒後重新啟動 Bot... ---")
                time.sleep(2)
            else:
                print(f"--- Bot 已停止，退出碼為 {process.returncode}。管理者腳本將關閉。 ---")
                break
    except KeyboardInterrupt:
        print("\n--- 偵測到手動停止指令 (Ctrl+C)，正在關閉 Bot... ---")
        sys.exit(0)

if __name__ == "__main__":
    # 檢查是否是子進程運行 bot
    if len(sys.argv) > 1 and sys.argv[1] == "--run-bot":
        run_bot()
    else:
        # 主進程運行監控器
        main()