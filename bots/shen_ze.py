#!/usr/bin/env python3
"""
沈澤 Discord Bot
獨立的虛擬人物 Bot，使用 SHEN_ZE_TOKEN
"""

import sys
import os

# 確保可以導入 core 模組
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.character_bot import run_character_bot_with_restart

# --- 角色專屬設定 ---
CHARACTER_ID = "shen_ze"
TOKEN_ENV_VAR = "SHEN_ZE_TOKEN"
PROACTIVE_KEYWORDS = ["沈澤", "shen_ze", "沈", "澤", "叔叔"]

def main():
    """啟動沈澤 Bot"""
    print("🎭 沈澤 Discord Bot")
    print("=" * 50)
    
    # 運行 Bot（包含自動重啟功能）
    run_character_bot_with_restart(CHARACTER_ID, TOKEN_ENV_VAR, PROACTIVE_KEYWORDS)

if __name__ == "__main__":
    main()