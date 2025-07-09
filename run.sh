import subprocess
import time
import sys

print("正在啟動 Bot...")

while True:
    # 使用 sys.executable 可以確保我們用的是同一個 Python 環境來執行 bot.py
    process = subprocess.run([sys.executable, 'bot.py'])
    exit_code = process.returncode

    if exit_code == 26:
        print("偵測到重啟指令，5 秒後重新啟動 Bot...")
        time.sleep(5)
    else:
        print(f"Bot 已停止，退出碼為 {exit_code}。將不會自動重啟。")
        break