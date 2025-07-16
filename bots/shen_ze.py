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
PROACTIVE_KEYWORDS = ["叔叔"]

# --- Gemini AI 參數設定 ---
GEMINI_TEMPERATURE = 1.0      # 創造性：0.0-1.0 (越高越有創意)
GEMINI_TOP_K = 40            # 詞彙多樣性：1-40 (越高越多樣)
GEMINI_TOP_P = 0.95          # 核採樣：0.0-1.0 (越高越集中)

def main():
    """啟動沈澤 Bot"""
    print("🎭 沈澤 Discord Bot")
    print("=" * 50)
    print(f"🌡️ Temperature: {GEMINI_TEMPERATURE}")
    print(f"🎯 Top-K: {GEMINI_TOP_K}")
    print(f"📊 Top-P: {GEMINI_TOP_P}")
    print("=" * 50)
    
    # 運行 Bot（包含自動重啟功能）
    run_character_bot_with_restart(
        CHARACTER_ID, 
        TOKEN_ENV_VAR, 
        PROACTIVE_KEYWORDS,
        gemini_config={
            'temperature': GEMINI_TEMPERATURE,
            'top_k': GEMINI_TOP_K,
            'top_p': GEMINI_TOP_P
        }
    )

if __name__ == "__main__":
    main() 