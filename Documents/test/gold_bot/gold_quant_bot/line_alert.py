import requests

LINE_TOKEN = "PUT_YOUR_TOKEN_HERE"

def send_line(message):

    url = "https://api.line.me/v2/bot/message/broadcast"

    headers = {
        "Authorization": f"Bearer qx/7500j4ULBOeqyBZRFRP1WrwKg1wSiFUYhdGr2jv6i5Lx3iheDo9xRvCvGzRzIkMZKqLpHjABRyN3J1c/YOK41xyIcSFjSa0+U7cw4pRQSN4xBxRKnepa+S0otvFY0WAUigtIfhrSxNCF6aIM8MQdB04t89/1O/w1cDnyilFU=",
        "Content-Type": "application/json"
    }

    data = {
        "messages":[
            {
                "type":"text",
                "text": message
            }
        ]
    }

    requests.post(url, headers=headers, json=data)
