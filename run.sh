#!/bin/bash
echo "正在啟動 Bot..."
until python3 bot.py; do
    exit_code=$?
    if [ $exit_code -eq 26 ]; then
        echo "偵測到重啟指令，5 秒後重新啟動 Bot..."
        sleep 5
    else
        echo "Bot 已停止，退出碼為 $exit_code。將不會自動重啟。"
        break
    fi
done