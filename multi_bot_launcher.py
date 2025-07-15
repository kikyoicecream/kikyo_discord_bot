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
from dotenv import load_dotenv

# 載入環境變數
load_dotenv()

class MultiBotLauncher:
    """多 Bot 啟動器"""
    
    def __init__(self):
        self.bots = [
            {
                'name': '沈澤',
                'file': 'bots/shen_ze.py',
                'token_env': 'SHEN_ZE_TOKEN',
                'process': None,
                'enabled': True
            },
            {
                'name': '顧北辰',
                'file': 'bots/gu_beichen.py',
                'token_env': 'GU_BEICHEN_TOKEN',
                'process': None,
                'enabled': False  # 預設關閉，需要時再啟用
            },
            {
                'name': '桔梗',
                'file': 'bots/kikyo.py',
                'token_env': 'KIKYO_TOKEN',
                'process': None,
                'enabled': False  # 預設關閉，需要時再啟用
            }
        ]
        
        self.running = False
    
    def check_tokens(self):
        """檢查必要的 Token 是否存在"""
        print("🔍 檢查 Discord Token...")
        
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
                    print(f"🚀 啟動 {bot_info['name']} Bot...")
                    process = subprocess.Popen([sys.executable, bot_info['file']])
                    bot_info['process'] = process
                    process.wait()
                    
                    if process.returncode == 26:
                        print(f"🔄 {bot_info['name']} Bot 正在重啟...")
                        time.sleep(2)
                    else:
                        print(f"⏹️ {bot_info['name']} Bot 已停止")
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
        
        print(f"\n🎭 啟動 {len(enabled_bots)} 個角色 Bot...")
        print("=" * 60)
        
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
            print("\n⏹️ 正在停止所有 Bot...")
            self.stop_all_bots()
    
    def stop_all_bots(self):
        """停止所有 Bot"""
        self.running = False
        
        for bot in self.bots:
            if bot['process'] and bot['process'].poll() is None:
                try:
                    bot['process'].terminate()
                    bot['process'].wait(timeout=5)
                    print(f"⏹️ {bot['name']} Bot 已停止")
                except:
                    bot['process'].kill()
                    print(f"🔴 強制停止 {bot['name']} Bot")
    
    def show_status(self):
        """顯示所有 Bot 狀態"""
        print("\n📊 Bot 狀態:")
        print("-" * 40)
        
        for bot in self.bots:
            status = "🟢 運行中" if bot['process'] and bot['process'].poll() is None else "🔴 已停止"
            enabled = "✅ 啟用" if bot['enabled'] else "❌ 停用"
            print(f"{bot['name']}: {status} ({enabled})")
    
    def interactive_menu(self):
        """互動式選單"""
        while True:
            print("\n🎮 多 Bot 控制台")
            print("=" * 40)
            print("1. 啟動所有 Bot")
            print("2. 顯示 Bot 狀態")
            print("3. 啟用/停用 Bot")
            print("4. 停止所有 Bot")
            print("5. 退出")
            
            choice = input("\n請選擇操作 (1-5): ").strip()
            
            if choice == "1":
                self.start_all_bots()
            elif choice == "2":
                self.show_status()
            elif choice == "3":
                self.toggle_bot_menu()
            elif choice == "4":
                self.stop_all_bots()
            elif choice == "5":
                self.stop_all_bots()
                print("👋 再見！")
                break
            else:
                print("❌ 無效的選擇，請重試")
    
    def toggle_bot_menu(self):
        """切換 Bot 啟用狀態的選單"""
        print("\n🔧 Bot 啟用/停用設定:")
        print("-" * 30)
        
        for i, bot in enumerate(self.bots, 1):
            status = "✅ 啟用" if bot['enabled'] else "❌ 停用"
            print(f"{i}. {bot['name']}: {status}")
        
        try:
            choice = int(input("\n選擇要切換的 Bot (輸入數字): ")) - 1
            if 0 <= choice < len(self.bots):
                bot = self.bots[choice]
                bot['enabled'] = not bot['enabled']
                status = "啟用" if bot['enabled'] else "停用"
                print(f"✅ {bot['name']} 已{status}")
            else:
                print("❌ 無效的選擇")
        except ValueError:
            print("❌ 請輸入有效的數字")

def main():
    """主程序"""
    print("🎭 多角色 Discord Bot 啟動器")
    print("=" * 50)
    
    launcher = MultiBotLauncher()
    
    # 檢查命令列參數
    if len(sys.argv) > 1:
        if sys.argv[1] == "--auto":
            # 自動啟動模式
            launcher.start_all_bots()
        elif sys.argv[1] == "--status":
            # 顯示狀態
            launcher.show_status()
        else:
            print("❌ 未知的參數")
    else:
        # 互動式模式
        launcher.interactive_menu()

if __name__ == "__main__":
    main() 