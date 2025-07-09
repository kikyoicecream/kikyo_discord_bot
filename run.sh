#!/bin/bash
# A wrapper script to run the bot and restart it if needed.

echo "正在啟動 Bot..."

trap "echo '偵測到手動停止指令，正在關閉 Bot...'; exit 0" INT

while true; do
    # 使用 python3 執行你的 bot
    # 確保你的環境中有 python3
    python3 bot.py
    exit_code=$?

    if [ $exit_code -eq 26 ]; then
        echo "偵測到重啟指令，5 秒後重新啟動 Bot..."
        sleep 5
    else
        echo "Bot 已正常停止，退出碼為 $exit_code。"
        break
    fi
done