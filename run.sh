import subprocess
import time
import sys

print("正在啟動 Bot...")

try:
    while True:
        # 使用 sys.executable 可以確保我們用的是同一個 Python 環境來執行 bot.py
        process = subprocess.run([sys.executable, 'bot.py'])
        exit_code = process.returncode

        if exit_code == 26:
            print("偵測到重啟指令，5 秒後重新啟動 Bot...")
            time.sleep(5)
        else:
            print(f"Bot 已正常停止，退出碼為 {exit_code}。")
            break
except KeyboardInterrupt:
    print("\n偵測到手動停止指令 (KeyboardInterrupt)，正在關閉 Bot...")
    # 子程序應該已經被同一個信號終止了。
    # 我們可以優雅地退出。
    sys.exit(0)