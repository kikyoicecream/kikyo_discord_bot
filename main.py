#!/usr/bin/env python3
"""
多角色 Bot 啟動器
可以同時運行多個獨立的角色 Bot
"""

import subprocess
import sys
import os
import time
import threading
import json
from typing import Dict, Any, Optional
from dotenv import load_dotenv
from core.character_bot import run_character_bot_with_restart

# 載入環境變數
load_dotenv()

# 確保可以導入 core 模組
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

class MultiBotLauncher:
    """多 Bot 啟動器"""
    
    def __init__(self):
        self.bots = self.load_characters_from_json()
        self.running = False
    
    def load_characters_from_json(self):
        """從 characters.json 載入角色設定"""
        try:
            with open('characters.json', 'r', encoding='utf-8') as f:
                characters_data = json.load(f)
            
            bots = []
            for character_id, character_info in characters_data.items():
                if character_info.get('enabled', True):  # 只載入啟用的角色
                    bots.append({
                        'name': character_info.get('name', character_id),
                        'character_id': character_id,
                        'token_env': character_info['token_env'],
                        'process': None,
                        'enabled': True
                    })
            
            print(f"✅ 從 characters.json 載入了 {len(bots)} 個角色")
            return bots
            
        except FileNotFoundError:
            print("❌ 找不到 characters.json 檔案")
            return []
        except json.JSONDecodeError as e:
            print(f"❌ characters.json 格式錯誤: {e}")
            return []
        except Exception as e:
            print(f"❌ 載入角色設定失敗: {e}")
            return []
    
    def load_character_config(self, character_id: str) -> Optional[Dict[str, Any]]:
        """載入角色配置"""
        try:
            config_path = 'characters.json'
            with open(config_path, 'r', encoding='utf-8') as f:
                configs = json.load(f)
                return configs.get(character_id)
        except Exception as e:
            print(f"❌ 載入角色配置失敗: {e}")
            return None
    
    def check_tokens(self):
        """檢查必要的 Token 是否存在"""
        print("🔍 檢查 Discord Token……")
        
        for bot in self.bots:
            if bot['enabled']:
                token = os.getenv(bot['token_env'])
                if token:
                    print(f"✅ {bot['name']} Token 已設定")
                else:
                    print(f"❌ {bot['name']} Token 未設定 ({bot['token_env']})")
                    bot['enabled'] = False
        
        enabled_bots = [bot for bot in self.bots if bot['enabled']]
        if not enabled_bots:
            print("❌ 沒有可啟動的 Bot，請檢查 Token 設定")
            return False
        
        return True
    
    def start_bot(self, bot_info):
        """啟動單個 Bot"""
        def run_bot():
            while self.running:
                try:
                    print(f"🚀 啟動 {bot_info['name']} Bot……")
                    
                    # 載入角色配置
                    config = self.load_character_config(bot_info['character_id'])
                    
                    if config:
                        gemini_config = config.get('gemini_config', {})
                        print(f"🌡️ Temperature: {gemini_config.get('temperature', 'N/A')}")
                        print(f"🎯 Top-K: {gemini_config.get('top_k', 'N/A')}")
                        print(f"📊 Top-P: {gemini_config.get('top_p', 'N/A')}")
                        print("=" * 50)
                        
                        # 直接調用 Bot 啟動函數
                        run_character_bot_with_restart(
                            character_id=bot_info['character_id'],
                            token_env_var=config['token_env'],
                            proactive_keywords=config['proactive_keywords'],
                            gemini_config=gemini_config
                        )
                    else:
                        print(f"❌ {bot_info['name']} 配置載入失敗")
                        break
                        
                except Exception as e:
                    print(f"❌ {bot_info['name']} Bot 啟動失敗: {e}")
                    time.sleep(5)
        
        thread = threading.Thread(target=run_bot, daemon=True)
        thread.start()
        return thread
    
    def start_all_bots(self):
        """啟動所有啟用的 Bot"""
        if not self.check_tokens():
            return
        
        self.running = True
        enabled_bots = [bot for bot in self.bots if bot['enabled']]
        
        print(f"\n🎭 啟動 {len(enabled_bots)} 個角色 Bot……")
        print("=" * 50)
        
        threads = []
        for bot in enabled_bots:
            thread = self.start_bot(bot)
            threads.append(thread)
            time.sleep(1)  # 錯開啟動時間
        
        try:
            # 等待所有 Bot 運行
            for thread in threads:
                thread.join()
        except KeyboardInterrupt:
            print("\n⏹️ 正在停止所有 Bot……")
            self.stop_all_bots()
    
    def stop_all_bots(self):
        """停止所有 Bot"""
        print("🛑 正在停止所有 Bot……")
        self.running = False
    
    def show_status(self):
        """顯示所有 Bot 狀態"""
        print("\n📊 Bot 狀態:")
        print("-" * 40)
        
        if not self.bots:
            print("❌ 沒有可用的角色")
            return
        
        for i, bot in enumerate(self.bots, 1):
            status = "🟢 運行中" if bot['process'] and bot['process'].poll() is None else "🔴 已停止"
            enabled = "✅ 啟用" if bot['enabled'] else "❌ 停用"
            print(f"{i}. {bot['name']}: {status} ({enabled})")

def main():
    """主程序"""
    print("🎭 多角色 Discord Bot 啟動器")
    print("=" * 50)
    
    launcher = MultiBotLauncher()
    launcher.start_all_bots()

if __name__ == "__main__":
    main() 