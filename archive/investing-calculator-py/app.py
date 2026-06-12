import os
import sys
import threading
import webbrowser
import time
from flask import Flask, send_from_directory, request, jsonify

if getattr(sys, 'frozen', False):
    BASE_DIR = sys._MEIPASS
else:
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))
app = Flask(__name__)

@app.route("/")
def index():
    return send_from_directory(BASE_DIR, "index.html")

@app.route("/calculate", methods=["POST"])
def calculate():
    data = request.json
    capital = float(data.get("capital", 1000))
    pct = float(data.get("pct", 6)) / 100
    ops_per_week = int(data.get("ops_per_week", 3))
    weeks = int(data.get("weeks", 4))

    total_ops = ops_per_week * weeks
    capitals = [capital]
    for _ in range(total_ops):
        capitals.append(capitals[-1] * (1 + pct))

    rows = []
    for i in range(1, total_ops + 1):
        week = (i - 1) // ops_per_week + 1
        cap_before = capitals[i - 1]
        cap_after = capitals[i]
        profit_op = cap_after - cap_before
        rows.append({
            "op": i,
            "week": week,
            "capital": round(cap_after, 2),
            "profit_op": round(profit_op, 2),
        })

    final = capitals[-1]
    total_profit = final - capital
    return_pct = ((final / capital) - 1) * 100

    return jsonify({
        "capitals": [round(c, 2) for c in capitals],
        "rows": rows,
        "final": round(final, 2),
        "total_profit": round(total_profit, 2),
        "return_pct": round(return_pct, 2),
    })

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    if getattr(sys, 'frozen', False):
        threading.Thread(target=lambda: (time.sleep(1.2), webbrowser.open(f"http://localhost:{port}")), daemon=True).start()
    app.run(host="0.0.0.0", port=port)
