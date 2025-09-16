import os
import requests
from dotenv import load_dotenv

load_dotenv()

INSTANCE_ID = os.getenv("INSTANCE_ID")
TOKEN = os.getenv("TOKEN")

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
