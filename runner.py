from flask import Flask, jsonify
import threading
import time
import sys

app = Flask(__name__)

@app.route('/')
def home():
    return "Hello, Flask App is running!"

@app.route('/data')
def get_data():
    return jsonify({"message": "This is some data from the Flask app.", "timestamp": time.time()})

@app.route('/greet/<name>')
def greet(name):
    return f"Hello, {name}!"

def background_task():
    for i in range(5):
        time.sleep(2)
        print(f"Background task working... {i+1}/5")
    print("Background task finished.")

@app.route('/start_task', methods=['GET'])
def start_task():
    thread = threading.Thread(target=background_task, daemon=True)
    thread.start()
    return jsonify({"status": "Background task started!"})

if __name__ == "__main__":
    try:
        app.run(host='0.0.0.0', port=5000, debug=True)
    except Exception as e:
        print(f"Error starting Flask app: {e}")
        sys.exit(1)
