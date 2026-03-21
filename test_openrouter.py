# test_openrouter.py
import os
import requests
from dotenv import load_dotenv

load_dotenv()

api_key = os.getenv("QWEN_API_KEY")
if not api_key:
    print("❌ QWEN_API_KEY not found in .env")
    exit(1)

ENDPOINT = "https://openrouter.ai/api/v1/chat/completions"

headers = {
    "Authorization": f"Bearer {api_key}",
    "Content-Type": "application/json",
    "HTTP-Referer": "https://github.com/bot-gold",
}

payload = {
    # ✅ ชื่อโมเดลที่ถูกต้องบน OpenRouter:
    "model": "qwen/qwen-plus",  # ← แก้ตรงนี้!
    "messages": [
        {"role": "user", "content": "Hello, are you Qwen?"}
    ],
    "max_tokens": 50
}

try:
    print(f"🧪 Testing OpenRouter + {payload['model']}...")
    response = requests.post(ENDPOINT, headers=headers, json=payload, timeout=10)
    
    print(f"📊 Status: {response.status_code}")
    
    if response.status_code == 200:
        result = response.json()
        content = result["choices"][0]["message"]["content"]
        print(f"✅ Success! Response: {content}")
    else:
        print(f"❌ Error: {response.text}")
        
except Exception as e:
    print(f"❌ Error: {e}")