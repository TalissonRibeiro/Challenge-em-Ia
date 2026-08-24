"""
app.py

Aplicação Flask que expõe o agente inteligente via API REST e uma interface
web simples de chat.
"""

import os
from flask import Flask, request, jsonify, render_template
from dotenv import load_dotenv

load_dotenv()

from agent import get_agent  # noqa: E402  (import após load_dotenv de propósito)

app = Flask(__name__)


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/health")
def health():
    return jsonify({"status": "ok"})


@app.route("/perguntar", methods=["POST"])
def perguntar():
    data = request.get_json(silent=True) or {}
    question = (data.get("pergunta") or "").strip()

    if not question:
        return jsonify({"erro": "Envie um campo 'pergunta' no corpo da requisição."}), 400

    try:
        agent = get_agent()
        resposta = agent.ask(question)
        return jsonify({"pergunta": question, "resposta": resposta})
    except Exception as exc:  # noqa: BLE001
        return jsonify({"erro": f"Falha ao processar a pergunta: {exc}"}), 500


if __name__ == "__main__":
    port = int(os.getenv("PORT", "8080"))
    app.run(host="0.0.0.0", port=port, debug=False)
