import subprocess
import threading
import time
import os
from flask import Flask, jsonify
from dotenv import load_dotenv # 用於本地開發時加載 .env

os.environ['PYTHONIOENCODING'] = 'utf-8'

# --- Flask 應用初始化 ---
app = Flask(__name__)

# --- 配置區塊 ---
# 定義要啟動的Bot腳本路徑
# 假設你的專案結構如下：
# your_bot_project/
# ├── runner.py
# ├── AIbot/
# │   └── main.py
# └── Discord-Music-Bot-main/
#     └── bot.py
BOT_SCRIPTS = {
    "AIbot": "python AIbot/main.py",
    "MusicBot": "python Discord-Music-Bot-main/bot.py"
}

# 用於追蹤Bot進程的字典
bot_processes = {}
# 用於心跳檢測的最後活動時間
last_heartbeat = time.time()

# --- 環境變數加載 (主要用於本地開發) ---
# 在 Render 等雲端平台，環境變數會直接注入到運行時環境中，
# 因此 load_dotenv() 不會找到 .env 文件，但 os.getenv() 仍會正常工作。
load_dotenv()

# --- Bot 啟動和監控函數 ---
def run_bot(name, command):
    """
    啟動一個Bot進程並監控它。
    如果進程意外停止，此函數將結束，監控執行緒會負責重新啟動。
    """
    print(f"[{name}] 正在啟動...")
    try:
        # Popen 允許非阻塞地啟動外部進程
        process = subprocess.Popen(
            command,
            shell=True,
            stdout=subprocess.PIPE, # 捕獲標準輸出
            stderr=subprocess.STDOUT, # 重定向標準錯誤到標準輸出
            text=True # 以文本模式處理輸出
        )
        bot_processes[name] = process
        print(f"[{name}] 已啟動，PID: {process.pid}")

        # 持續讀取Bot的輸出並打印，以方便調試
        # 這會阻塞這個執行緒，直到Bot進程結束
        for line in process.stdout:
            print(f"[{name} LOG] {line.strip()}")
        
        process.wait() # 等待Bot進程結束
        print(f"[{name}] 進程已結束，返回碼: {process.returncode}")
        
    except Exception as e:
        print(f"[{name}] 啟動失敗: {e}")
    finally:
        # 不論成功或失敗，如果進程記錄存在，則移除它
        if name in bot_processes:
            del bot_processes[name]

def start_bots_in_threads():
    """為每個Bot腳本啟動一個單獨的執行緒。"""
    for name, command in BOT_SCRIPTS.items():
        thread = threading.Thread(target=run_bot, args=(name, command))
        thread.daemon = True # 設置為守護執行緒，這樣主程序結束時它們會自動終止
        thread.start()
        time.sleep(1) # 給一點時間讓bot啟動，避免同時啟動導致資源問題

def monitor_bots_and_heartbeat():
    """
    監控Bot進程和Web Service的心跳。
    這個函數在一個獨立的守護執行緒中運行。
    """
    while True:
        current_time = time.time()
        
        # 檢查Web Service心跳是否超時 (5分鐘沒有被訪問)
        # 這主要是一個警示，不會自動重啟Web服務本身，因為Web服務是主進程
        if current_time - last_heartbeat > 300:
            print("[Monitor] Web Service 心跳超時警告：可能沒有外部服務在檢測或服務已停止響應。")

        # 檢查Bot進程是否仍在運行
        # 這裡使用 list(bot_processes.items()) 是為了避免在迭代字典時修改它
        for name, process in list(bot_processes.items()):
            if process.poll() is not None:  # 如果進程已結束 (returncode不是None)
                print(f"[Monitor] 警告: {name} Bot 進程已停止。正在嘗試重新啟動...")
                # 重新啟動這個Bot
                thread = threading.Thread(target=run_bot, args=(name, BOT_SCRIPTS[name]))
                thread.daemon = True
                thread.start()
        
        time.sleep(60) # 每60秒檢查一次

# --- Flask Web Service 端點 ---
@app.route('/heartbeat')
def heartbeat():
    """提供一個心跳端點，用於確認Web Service是否在運行。"""
    global last_heartbeat
    last_heartbeat = time.time() # 更新心跳時間
    
    status = {
        "status": "running",
        "timestamp": time.time(),
        "bots": {}
    }
    
    # 獲取所有正在運行Bot的狀態
    for name, process in bot_processes.items():
        status["bots"][name] = {
            "pid": process.pid,
            "is_running": process.poll() is None # None表示進程仍在運行
        }
    
    return jsonify(status)

# --- 主程序入口 ---
if __name__ == "__main__":
    # 步驟 1: 啟動所有 Discord Bot
    print("[Main] 啟動所有 Discord Bot 執行緒...")
    start_bots_in_threads()

    # 步驟 2: 啟動一個獨立執行緒來監控Bot進程和Web Service的心跳
    print("[Main] 啟動 Bot 監控執行緒...")
    monitor_thread = threading.Thread(target=monitor_bots_and_heartbeat)
    monitor_thread.daemon = True
    monitor_thread.start()

    print("[Main] 所有 Bot 和監控執行緒已啟動。")
    print("[Main] 準備啟動 Flask Web Service...")

    # 步驟 3: 啟動 Flask Web Service
    # Render 會提供一個 PORT 環境變數，我們的服務應該監聽這個端口
    port = int(os.environ.get("PORT", 5000)) # 默認為 5000，但在 Render 通常是 10000+

    try:
        # 嘗試從 gunicorn 庫導入 BaseApplication
        from gunicorn.app.base import BaseApplication

        class FlaskGunicornApp(BaseApplication):
            def __init__(self, app, options=None):
                self.options = options or {}
                self.application = app
                super().__init__()

            def load_config(self):
                # 遍歷選項並將它們設置到 Gunicorn 配置中
                for key, value in self.options.items():
                    if key in self.cfg.settings and value is not None:
                        self.cfg.set(key.lower(), value)

            def load(self):
                # 返回 Flask 應用實例
                return self.application

        # Gunicorn 配置選項
        gunicorn_options = {
            'bind': f'0.0.0.0:{port}',  # 監聽所有網絡接口和指定的端口
            'workers': 1,               # 通常一個 worker 對於單個 Flask 應用就足夠了
            'timeout': 120,             # 增加請求超時時間 (秒)
            'loglevel': 'info',         # 日誌級別
            'capture_output': True,     # 捕獲並打印 worker 的 stdout/stderr
            'enable_stdio_inheritance': True, # 允許 worker 繼承主進程的 stdout/stderr
        }
        
        print(f"[Main] 正在使用 Gunicorn 啟動 Flask 應用在 0.0.0.0:{port}...")
        FlaskGunicornApp(app, gunicorn_options).run()

    except ImportError:
        # 如果 Gunicorn 未安裝，則回退到 Flask 自帶的開發伺服器
        # 不推薦在生產環境使用
        print("[Main] Gunicorn 未安裝，回退到 Flask 自帶開發伺服器。此不適用於生產環境！")
        app.run(host='0.0.0.0', port=port, debug=False) # 關閉 debug 模式