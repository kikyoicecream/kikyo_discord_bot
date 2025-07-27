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
import logging
from typing import Dict, Any, Optional
from dotenv import load_dotenv
from firebase_utils import firebase_manager
from character_bot import run_character_bot_with_restart

# 設定 Discord 日誌級別，減少詳細訊息
logging.getLogger('discord.client').setLevel(logging.WARNING)
logging.getLogger('discord.gateway').setLevel(logging.WARNING)

# 載入環境變數
load_dotenv()

# 不再需要 sys.path 設定，因為所有檔案都在根目錄

class MultiBotLauncher:
    """多 Bot 啟動器"""
    
    def __init__(self):
        # 使用統一的 Firebase 管理器
        self.firebase = firebase_manager
        self.bots = self.load_characters_from_firestore()
        self.running = False
    
    @property
    def db(self):
        """獲取 Firestore 資料庫實例"""
        return self.firebase.db
    
    def _get_all_character_ids(self):
        """動態獲取所有角色集合 ID"""
        if not self.db:
            self.firebase.log_error("獲取角色列表", "Firestore 未連接")
            return []
        
        # 排除的集合名稱（範本、測試等）
        excluded_collections = ["template", "prompt"]
        
        try:
            # 獲取所有頂層集合
            collections = self.db.collections()
            character_ids = []
            
            for collection in collections:
                collection_id = collection.id
                
                # 檢查是否在排除清單中
                if collection_id in excluded_collections:
                    continue
                
                # 檢查是否為角色集合（有 system 文件）
                system_ref = self.db.collection(collection_id).document('system')
                system_doc = system_ref.get()
                
                if system_doc.exists:
                    character_ids.append(collection_id)
            return character_ids
            
        except Exception as e:
            self.firebase.log_error("獲取角色集合", e)
            return []
    
    def load_characters_from_firestore(self):
        """從 Firestore 載入角色設定"""
        if not self.db:
            self.firebase.log_error("載入角色設定", "Firestore 未連接")
            return []
        
        try:
            # 動態獲取所有角色集合
            character_ids = self._get_all_character_ids()
            bots = []
            
            for character_id in character_ids:
                try:
                    # 從 Firestore 讀取系統配置
                    system_ref = self.db.collection(character_id).document('system')
                    system_doc = system_ref.get()
                    
                    if system_doc.exists:
                        system_config = system_doc.to_dict()
                        
                        if system_config.get('enabled', True):  # 只載入啟用的角色
                            character_name = system_config.get('name', character_id)
                            bots.append({
                                'name': character_name,
                                'character_id': character_id,
                                'token_env': system_config.get('token_env', ''),
                                'process': None,
                                'enabled': True
                            })
                            print(f"✅ 已從 Firestore 載入角色：{character_name}")
                except Exception as e:
                    self.firebase.log_error(f"載入角色 {character_id}", e)
                    continue
            
            return bots
            
        except Exception as e:
            self.firebase.log_error("從 Firestore 載入角色設定", e)
            return []
    
    def load_character_config(self, character_id: str) -> Optional[Dict[str, Any]]:
        """從 Firestore 載入角色配置"""
        try:
            # 使用統一的系統配置讀取方法
            system_config = self.firebase.get_character_system_config(character_id)
            
            if not system_config:
                self.firebase.log_error("載入角色配置", f"找不到角色 {character_id} 的系統配置")
                return None
            
            # 簡化的配置格式（移除複雜的向下相容邏輯）
            config = {
                'name': system_config.get('name', character_id),
                'token_env': system_config.get('token_env', ''),
                'proactive_keywords': system_config.get('proactive_keywords', []),
                'enabled': system_config.get('enabled', True),
                'gemini_config': system_config.get('gemini_config', {})  # 直接使用 Firestore 中的設定
            }
            
            return config
                
        except Exception as e:
            self.firebase.log_error("從 Firestore 載入角色配置", e)
            return None
    
    def check_tokens(self):
        """檢查必要的 Token 是否存在"""
        for bot in self.bots:
            if bot['enabled']:
                token = os.getenv(bot['token_env'])
                if not token:
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
                    
                    # 載入角色配置
                    config = self.load_character_config(bot_info['character_id'])
                    
                    if config:
                        gemini_config = config.get('gemini_config', {})
                        
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
            self.stop_all_bots()
    
    def stop_all_bots(self):
        """停止所有 Bot"""
        print("\n🛑 正在停止所有 Bot……")
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
    launcher = MultiBotLauncher()
    launcher.start_all_bots()

if __name__ == "__main__":
    main() 