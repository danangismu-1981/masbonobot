from flask import Flask, request
import requests
import os
from responder import handle_message
from dotenv import load_dotenv

load_dotenv()

TOKEN = os.getenv("TOKEN")
INSTANCE_ID = os.getenv("INSTANCE_ID")

app = Flask(__name__)

# 🛡️ cache sederhana untuk menolak pesan yang sama diproses dua kali
processed_message_ids = set()

@app.route("/", methods=["POST"])
def webhook():
    try:
        incoming_data = request.json or {}
        data = incoming_data.get("data", {}) or {}

        # ambil ID pesan dari payload ultramsg
        message_id = data.get("id") or incoming_data.get("id")

        print("📥 RAW INCOMING:", incoming_data)

        # kalau tidak ada ID, tetap kita proses tapi di-log
        if message_id:
            if message_id in processed_message_ids:
                print(f"⚠️ DUPLICATE MESSAGE DETECTED, SKIP: {message_id}")
                return "OK", 200  # langsung balas OK supaya ultramsg puas
            processed_message_ids.add(message_id)

        message = data.get("body", "")
        sender = data.get("from", "")

        if message and sender:
            reply = handle_message(message)
            send_message(sender, reply)
        else:
            print("ℹ️ Tidak ada message/from yang valid, dilewati.")

        return "OK", 200

    except Exception as e:
        print("❌ ERROR di webhook:", e)
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

    print("🛰️ FULL URL:", url)
    print("📦 PAYLOAD:", payload)

    response = requests.post(url, data=payload, headers=headers)

    print("📬 RESPON ULTRAMSG:", response.status_code, response.text)
    return response.json()


if __name__ == "__main__":
    app.run()
