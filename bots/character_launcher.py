#!/usr/bin/env python3
"""
通用角色 Bot 啟動器
使用 JSON 配置檔案管理角色設定
"""

import sys
import os
import json
from typing import Dict, Any, Optional

# 確保可以導入 core 模組
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.character_bot import run_character_bot_with_restart

def load_character_config(character_id: str) -> Optional[Dict[str, Any]]:
    """載入角色配置"""
    try:
        # 修正路徑：配置檔案現在在 bots 目錄下
        config_path = os.path.join(os.path.dirname(__file__), 'characters.json')
        with open(config_path, 'r', encoding='utf-8') as f:
            configs = json.load(f)
            return configs.get(character_id)
    except Exception as e:
        print(f"❌ 載入角色配置失敗: {e}")
        return None

def main():
    """主程序"""
    # 從命令列參數獲取角色 ID
    if len(sys.argv) < 2:
        print("❌ 錯誤：請提供角色 ID")
        print("用法: python character_launcher.py <character_id>")
        print("可用角色:")
        
        # 顯示所有可用角色
        try:
            config_path = os.path.join(os.path.dirname(__file__), 'characters.json')
            with open(config_path, 'r', encoding='utf-8') as f:
                configs = json.load(f)
                for char_id, config in configs.items():
                    status = "✅ 啟用" if config.get('enabled', False) else "❌ 停用"
                    print(f"  - {char_id}: {config.get('name', char_id)} ({status})")
        except Exception as e:
            print(f"❌ 無法讀取配置檔案: {e}")
        
        sys.exit(1)
    
    character_id = sys.argv[1]
    
    # 載入角色配置
    config = load_character_config(character_id)
    if not config:
        print(f"❌ 錯誤：找不到角色 {character_id} 的配置")
        sys.exit(1)
    
    # 檢查角色是否啟用
    if not config.get('enabled', False):
        print(f"❌ 錯誤：角色 {character_id} 已停用")
        sys.exit(1)
    
    # 顯示角色資訊
    print(f"🎭 {config.get('name', character_id)} Discord Bot")
    print("=" * 50)
    print(f"📝 描述: {config.get('description', '無描述')}")
    
    gemini_config = config.get('gemini_config', {})
    print(f"🌡️ Temperature: {gemini_config.get('temperature', 'N/A')}")
    print(f"🎯 Top-K: {gemini_config.get('top_k', 'N/A')}")
    print(f"📊 Top-P: {gemini_config.get('top_p', 'N/A')}")
    print("=" * 50)
    
    # 啟動 Bot
    run_character_bot_with_restart(
        character_id=character_id,
        token_env_var=config['token_env'],
        proactive_keywords=config['proactive_keywords'],
        gemini_config=gemini_config
    )

if __name__ == "__main__":
    main() 