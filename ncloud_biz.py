import sys, json
import os
import hashlib
import hmac
import base64
import requests
import time

def	make_signature():
    timestamp = int(time.time() * 1000)
    timestamp = str(timestamp)

    access_key = "ncp_iam_BPASKR1H4e1yoTi6Rzoc"				# access key id (from portal or Sub Account)
    secret_key = "ncp_iam_BPKSKRHXfDqFpRy7mEqVkUdFkSEmR2xy9y"				# secret key (from portal or Sub Account)
    secret_key = bytes(secret_key, 'UTF-8')

    method = "GET"
    uri = "/photos/puppy.jpg?query1=&query2"

    message = method + " " + uri + "\n" + timestamp + "\n" + access_key
    message = bytes(message, 'UTF-8')
    signingKey = base64.b64encode(hmac.new(secret_key, message, digestmod=hashlib.sha256).digest())

    return signingKey, timestamp

def send_alimtalk() :

    sign_key = list(make_signature())
    signingKey = str(sign_key[0])
    extract = signingKey[2:len(signingKey)-1]
    timestamp = sign_key[1]

    print(extract)
    print(timestamp)
    
    # API 엔드포인트 URL
    url = "https://sens.apigw.ntruss.com/alimtalk/v2/services/ncp:kkobizmsg:kr:3361782:keeper/messages"

    # 요청 헤더 설정
    headers = {
        "Content-Type": "application/json;charset=UTF-8"
        ,"x-ncp-apigw-timestamp": timestamp
        ,"x-ncp-iam-access-key": "ncp_iam_BPASKR1H4e1yoTi6Rzoc"
        ,"x-ncp-apigw-signature-v2": extract
    }

    # 요청 본문 데이터 설정
    requestBody = {
        "templateCode": "CallbackMessage",
        "plusFriendId": "열한시키퍼",
        "messages": [
            {
            "to": "01022317362",
            "content": "string",
            "headerContent": "string"
            }
        ]
    }
    
    # POST 요청 보내기
    response = requests.post(url, headers=headers, json=requestBody)
    response_text = json.loads(response.text)

    return response_text


print(send_alimtalk())

