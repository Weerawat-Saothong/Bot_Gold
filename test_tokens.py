import requests
import json

LINE_TOKEN_1 = "qx/7500j4ULBOeqyBZRFRP1WrwKg1wSiFUYhdGr2jv6i5Lx3iheDo9xRvCvGzRzIkMZKqLpHjABRyN3J1c/YOK41xyIcSFjSa0+U7cw4pRQSN4xBxRKnepa+S0otvFY0WAUigtIfhrSxNCF6aIM8MQdB04t89/1O/w1cDnyilFU="
LINE_TOKEN_2 = "r8YEBaB+oJ1Sq15wwh/DI62VdTLn56w1633Ssq0e38citJipJt2xzuYMKvS871zGkMZKqLpHjABRyN3J1c/YOK41xyIcSFjSa0+U7cw4pRTj7nnvhc29lzCtbmByIkFxN2yMfR4rc0TPiJQXxaH3YgdB04t89/1O/w1cDnyilFU="

url = "https://api.line.me/v2/bot/message/broadcast"

def test_token(token, name):
    print(f"Testing token {name}...")
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }
    data = {
        "messages":[{"type":"text","text": f"TEST {name}"}]
    }
    r = requests.post(url, headers=headers, json=data)
    print(f"Result {name}: {r.status_code} - {r.text}")

test_token(LINE_TOKEN_1, "Token1 (qx/)")
test_token(LINE_TOKEN_2, "Token2 (r8/)")
