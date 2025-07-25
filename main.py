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
from google.cloud import firestore
from google.oauth2 import service_account
from character_bot import run_character_bot_with_restart

# 載入環境變數
load_dotenv()

# 不再需要 sys.path 設定，因為所有檔案都在根目錄

class MultiBotLauncher:
    """多 Bot 啟動器"""
    
    def __init__(self):
        self.db = self._init_firestore()
        self.bots = self.load_characters_from_firestore()
        self.running = False
    
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
            print("✅ Firestore 連接成功")
            return db
        except Exception as e:
            print(f"❌ Firestore 連接失敗：{e}")
            return None
    
    def load_characters_from_firestore(self):
        """從 Firestore 載入角色設定"""
        if not self.db:
            print("❌ Firestore 未連接，無法載入角色設定")
            return []
        
        try:
            character_ids = ["shen_ze", "gu_beichen", "fan_chengxi"]  # 可以改為動態獲取
            bots = []
            
            for character_id in character_ids:
                try:
                    # 從 Firestore 讀取系統配置
                    system_ref = self.db.collection(character_id).document('system')
                    system_doc = system_ref.get()
                    
                    if system_doc.exists:
                        system_config = system_doc.to_dict()
                        
                        if system_config.get('enabled', True):  # 只載入啟用的角色
                            bots.append({
                                'name': system_config.get('name', character_id),
                                'character_id': character_id,
                                'token_env': system_config.get('token_env', ''),
                                'process': None,
                                'enabled': True
                            })
                            print(f"✅ 載入角色：{system_config.get('name', character_id)}")
                        else:
                            print(f"⚠️ 角色 {character_id} 已停用，跳過載入")
                    else:
                        print(f"⚠️ 找不到角色 {character_id} 的系統配置")
                        
                except Exception as e:
                    print(f"❌ 載入角色 {character_id} 失敗：{e}")
                    continue
            
            print(f"✅ 從 Firestore 載入了 {len(bots)} 個角色")
            return bots
            
        except Exception as e:
            print(f"❌ 從 Firestore 載入角色設定失敗: {e}")
            return []
    
    def load_character_config(self, character_id: str) -> Optional[Dict[str, Any]]:
        """從 Firestore 載入角色配置"""
        if not self.db:
            print(f"❌ Firestore 未連接，無法載入 {character_id} 配置")
            return None
            
        try:
            # 從 Firestore 讀取系統配置
            system_ref = self.db.collection(character_id).document('system')
            system_doc = system_ref.get()
            
            if system_doc.exists:
                system_config = system_doc.to_dict()
                
                # 轉換為舊格式以保持相容性
                config = {
                    'name': system_config.get('name', character_id),
                    'token_env': system_config.get('token_env', ''),
                    'proactive_keywords': system_config.get('proactive_keywords', []),
                    'enabled': system_config.get('enabled', True),
                    'gemini_config': {
                        'temperature': system_config.get('temperature', 1.0),
                        'top_k': system_config.get('top_k', 40),
                        'top_p': system_config.get('top_p', 0.9)
                    }
                }
                
                return config
            else:
                print(f"❌ 找不到角色 {character_id} 的系統配置")
                return None
                
        except Exception as e:
            print(f"❌ 從 Firestore 載入角色配置失敗: {e}")
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