from flask import Flask, request
import requests
import os
from responder import handle_message
from dotenv import load_dotenv

load_dotenv()

TOKEN = os.getenv("TOKEN")
INSTANCE_ID = os.getenv("INSTANCE_ID")

app = Flask(__name__)

@app.route("/", methods=["POST"])
def webhook():
    try:
        incoming_data = request.json
        message = incoming_data.get("data", {}).get("body", "")
        sender = incoming_data.get("data", {}).get("from", "")

        if message and sender:
            reply = handle_message(message)
            send_message(sender, reply)

        return "OK", 200

    except Exception as e:
        return f"Error: {str(e)}", 500

def send_message(to, message):
    url = f"https://api.ultramsg.com/instance{INSTANCE_ID}/messages/chat?token={TOKEN}"

    payload = {
        'to': to,
        'body': message
    }

    headers = {
        'Content-Type': 'application/x-www-form-urlencoded'
    }

    # 🟡 Cetak URL dan payload
    print("🛰️ FULL URL:", url)
    print("📦 PAYLOAD:", payload)

    response = requests.post(url, data=payload, headers=headers)

    print("📬 RESPON ULTRAMSG:", response.status_code, response.text)
    return response.json()

if __name__ == "__main__":
    app.run()
