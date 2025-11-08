import subprocess
import threading
import time
import os
from flask import Flask, jsonify
from dotenv import load_dotenv

app = Flask(__name__)

# Bot 腳本路徑
BOT_SCRIPTS = {
    "AIbot": "python AIbot/main.py",
    "MusicBot": "python Discord-Music-Bot-main/bot.py"
}

bot_processes = {}
last_heartbeat = time.time()

# 加載本地 .env（開發用）
load_dotenv()

def run_bot(name, command):
    print(f"[{name}] 正在啟動...")
    try:
        process = subprocess.Popen(
            command,
            shell=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True
        )
        bot_processes[name] = process
        print(f"[{name}] 已啟動，PID: {process.pid}")

        for line in process.stdout:
            print(f"[{name} LOG] {line.strip()}")
        
        process.wait()
        print(f"[{name}] 已結束，返回碼: {process.returncode}")

    except Exception as e:
        print(f"[{name}] 啟動失敗: {e}")
    finally:
        bot_processes.pop(name, None)

def start_bots_in_threads():
    for name, command in BOT_SCRIPTS.items():
        thread = threading.Thread(target=run_bot, args=(name, command))
        thread.daemon = True
        thread.start()
        time.sleep(1)

def monitor_bots_and_heartbeat():
    while True:
        current_time = time.time()
        if current_time - last_heartbeat > 300:
            print("[Monitor] Web Service 心跳超時警告")

        for name, process in list(bot_processes.items()):
            if process.poll() is not None:
                print(f"[Monitor] {name} 已停止，嘗試重新啟動...")
                thread = threading.Thread(target=run_bot, args=(name, BOT_SCRIPTS[name]))
                thread.daemon = True
                thread.start()
        
        time.sleep(60)

@app.route('/heartbeat')
def heartbeat():
    global last_heartbeat
    last_heartbeat = time.time()
    
    status = {
        "status": "running",
        "timestamp": time.time(),
        "bots": {}
    }
    
    for name, process in bot_processes.items():
        status["bots"][name] = {
            "pid": process.pid,
            "is_running": process.poll() is None
        }
    
    return jsonify(status)

if __name__ == "__main__":
    start_bots_in_threads()

    monitor_thread = threading.Thread(target=monitor_bots_and_heartbeat)
    monitor_thread.daemon = True
    monitor_thread.start()

    port = int(os.environ.get("PORT", 5000))

    try:
        from gunicorn.app.base import BaseApplication

        class FlaskGunicornApp(BaseApplication):
            def __init__(self, app, options=None):
                self.options = options or {}
                self.application = app
                super().__init__()

            def load_config(self):
                for key, value in self.options.items():
                    if key in self.cfg.settings and value is not None:
                        self.cfg.set(key.lower(), value)

            def load(self):
                return self.application

        gunicorn_options = {
            'bind': f'0.0.0.0:{port}',
            'workers': 1,
            'timeout': 120,
            'loglevel': 'info',
            'capture_output': True,
            'enable_stdio_inheritance': True,
        }
        
        FlaskGunicornApp(app, gunicorn_options).run()

    except ImportError:
        app.run(host='0.0.0.0', port=port, debug=False)
