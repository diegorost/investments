import os
from flask import Flask, render_template, request, jsonify

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
app = Flask(__name__, template_folder=os.path.join(BASE_DIR, "templates"))

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/calcular", methods=["POST"])
def calcular():
    data = request.json
    capital = float(data.get("capital", 1000))
    pct = float(data.get("pct", 6)) / 100
    ops_semana = int(data.get("ops_semana", 3))
    semanas = int(data.get("semanas", 4))

    total_ops = ops_semana * semanas
    capitals = [capital]
    for _ in range(total_ops):
        capitals.append(capitals[-1] * (1 + pct))

    filas = []
    for i in range(1, total_ops + 1):
        semana = (i - 1) // ops_semana + 1
        cap_antes = capitals[i - 1]
        cap_despues = capitals[i]
        ganancia_op = cap_despues - cap_antes
        filas.append({
            "op": i,
            "semana": semana,
            "capital": round(cap_despues, 2),
            "ganancia_op": round(ganancia_op, 2),
        })

    final = capitals[-1]
    ganancia_total = final - capital
    retorno_pct = ((final / capital) - 1) * 100

    return jsonify({
        "capitals": [round(c, 2) for c in capitals],
        "filas": filas,
        "final": round(final, 2),
        "ganancia_total": round(ganancia_total, 2),
        "retorno_pct": round(retorno_pct, 2),
    })

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
