import threading
from flask import Flask, jsonify
import bilet_bot
import os

app = Flask(__name__)

@app.route("/")
def health():
    """Render health check endpoint."""
    return jsonify({
        "status": "running",
        "bot": "Bilet Takip Botu",
        "last_check": bilet_bot.last_check_time,
    })

def start_bot():
    """Bot'u arka plan thread'inde çalıştırır."""
    bilet_bot.bot_loop()

# Gunicorn ile çalışırken thread'in başlaması için __main__ dışına alıyoruz
bot_thread = threading.Thread(target=start_bot, daemon=True)
bot_thread.start()

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
