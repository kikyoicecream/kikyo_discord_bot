import subprocess
import time
import sys

# This script is designed to be run with Python.
# It acts as a wrapper for bot.py to handle restarts, which is useful
# in hosting environments where the startup command cannot be changed.

print("正在啟動 Bot...")

try:
    while True:
        # Use sys.executable to ensure we use the same Python environment
        # that is running this script to execute bot.py.
        process = subprocess.run([sys.executable, 'bot.py'])
        exit_code = process.returncode

        if exit_code == 26:
            print("偵測到重啟指令，5 秒後重新啟動 Bot...")
            time.sleep(5)
        else:
            print(f"Bot 已正常停止，退出碼為 {exit_code}。")
            break
except KeyboardInterrupt:
    print("\n偵測到手動停止指令 (Ctrl+C)，正在關閉 Bot...")
    sys.exit(0)