#!/usr/bin/env python3
"""
顧北辰 Discord Bot
獨立的虛擬人物 Bot，使用 GU_BEICHEN_TOKEN
"""

import sys
import os

# 確保可以導入 core 模組
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.character_bot import run_character_bot_with_restart

# --- 角色專屬設定 ---
CHARACTER_ID = "gu_beichen"
TOKEN_ENV_VAR = "GU_BEICHEN_TOKEN"
PROACTIVE_KEYWORDS = ["顧北辰", "gu_beichen", "顧", "北辰", "beichen"]

def main():
    """啟動顧北辰 Bot"""
    print("🎭 顧北辰 Discord Bot")
    print("=" * 50)
    
    # 運行 Bot（包含自動重啟功能）
    run_character_bot_with_restart(CHARACTER_ID, TOKEN_ENV_VAR, PROACTIVE_KEYWORDS)

if __name__ == "__main__":
    main() 