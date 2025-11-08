import subprocess
import threading
import time
import os
from flask import Flask, jsonify
from dotenv import load_dotenv

load_dotenv()
app = Flask(__name__)

BOT_SCRIPTS = {
    "UnifiedDiscordBot": "python unified_bot/main.py"
}

bot_processes = {}
last_heartbeat = time.time()


def run_bot(name, command):
    print(f"[{name}] 啟動中...")
    try:
        process = subprocess.Popen(
            command,
            shell=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True
        )
        bot_processes[name] = process
        print(f"[{name}] 已啟動 PID={process.pid}")

        for line in process.stdout:
            print(f"[{name}] {line.strip()}")

        process.wait()
        print(f"[{name}] 結束 (Code {process.returncode})")

    except Exception as e:
        print(f"[{name}] 啟動失敗: {e}")
    finally:
        bot_processes.pop(name, None)


def start_bots():
    print("[Service] 啟動機器人線程中...")
    for name, cmd in BOT_SCRIPTS.items():
        t = threading.Thread(target=run_bot, args=(name, cmd), daemon=True)
        t.start()
        time.sleep(1)


def monitor_bots():
    print("[Monitor] 啟動監控線程...")
    while True:
        now = time.time()
        if now - last_heartbeat > 300:
            print(f"[Monitor] ⚠️ Web 心跳超時：{time.ctime(last_heartbeat)}")

        for name, p in list(bot_processes.items()):
            if p.poll() is not None:
                print(f"[Monitor] {name} 已停止，重新啟動中...")
                t = threading.Thread(target=run_bot, args=(name, BOT_SCRIPTS[name]), daemon=True)
                t.start()

        time.sleep(60)


@app.route("/heartbeat")
def heartbeat():
    global last_heartbeat
    last_heartbeat = time.time()
    status = {
        "status": "running",
        "timestamp": last_heartbeat,
        "bots": {
            name: {
                "pid": p.pid,
                "is_running": p.poll() is None
            } for name, p in bot_processes.items()
        }
    }
    return jsonify(status)


if __name__ == "__main__":
    start_bots()
    threading.Thread(target=monitor_bots, daemon=True).start()
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)
