from fastapi import FastAPI, Body, Query, HTTPException
from pydantic import BaseModel
import requests
import json
from typing import Dict, Optional
import uuid

app = FastAPI()

class Payload(BaseModel):
    text: str

class MessageData(BaseModel):
    imBotId: str
    imContactId: Optional[str] = None  # 客户的系统wxid
    imRoomId: Optional[str] = None  # 群聊的系统wxid
    messageType: int
    payload: Payload
    token: str
    messageId: str  # 增加 messageId 字段

# 存储已处理的消息ID，用于去重
processed_message_ids: Dict[str, str] = {}

@app.post("/api/receive_data")
async def receive_data(
    msg_signature: str = Query(None, description="The message signature"),
    timestamp: int = Query(None, description="The timestamp"),
    nonce: int = Query(None, description="The nonce"),
    data: MessageData = Body(None, description="The JSON data in the request body")
):
    if msg_signature is None or timestamp is None or nonce is None:
        raise HTTPException(status_code=400, detail="Query parameters are missing")

    if data is None:
        raise HTTPException(status_code=400, detail="No JSON data provided in the request body")

    # 打印接收到的数据
    print(f"Received data: {data}")
    print(f"Query parameters: msg_signature={msg_signature}, timestamp={timestamp}, nonce={nonce}")

    # 检查消息中是否包含“方工”
    if "方工" not in data.payload.text:
        print("Message does not contain the trigger word '方工'. Ignoring the message.")
        return {"status": "ignored", "reason": "no trigger word"}

    # 过滤托管账号自己发送的消息
    if data.imBotId == data.imContactId:
        print("Filtered out self-sent message to avoid loop.")
        return {"status": "filtered", "reason": "self-sent message"}

    # 去重过滤处理
    if data.messageId in processed_message_ids:
        print(f"Filtered out duplicate message with ID: {data.messageId}")
        return {"status": "filtered", "reason": "duplicate message"}
    else:
        processed_message_ids[data.messageId] = data.imBotId

    # 调用机器人处理消息，去掉“方工”后再传递
    query_text = data.payload.text.replace("方工 ", "")
    bot_response = call_bot(query_text)

    # 更新消息内容为机器人的响应
    data.payload.text = bot_response

    # 生成唯一的 externalRequestId
    external_request_id = str(uuid.uuid4())

    # 从接收到的数据中提取需要的信息，并调用发送消息的函数
    send_response = send_message(
        data.imBotId,
        data.imContactId,
        data.imRoomId,
        data.messageType,
        data.payload.dict(),
        data.token,
        external_request_id
    )

    return {"status": "success", "send_response": send_response, "query_params": {"msg_signature": msg_signature, "timestamp": timestamp, "nonce": nonce}}

def call_bot(query: str) -> str:
    personal_access_token = 'pat_o6mZ3gPN7ZpdYn8luRIPmFruJpj0pySJmn2RN4Ub7ZhpHYuvLMkUh9WVqsft1zjB'
    bot_id = '7397238203918647323'
    conversation_id = 'jkdshflkjdfsh'
    user = 'CustomizedString123'

    url = 'https://api.coze.cn/open_api/v2/chat'

    headers = {
        'Authorization': f'Bearer {personal_access_token}',
        'Content-Type': 'application/json',
        'Accept': '*/*',
        'Host': 'api.coze.cn',
        'Connection': 'keep-alive'
    }

    data = {
        "conversation_id": conversation_id,
        "bot_id": bot_id,
        "user": user,
        "query": query,
        "stream": False
    }

    response = requests.post(url, headers=headers, json=data)

    if response.status_code != 200:
        print(f"Failed to call bot: {response.text}")  # 输出错误信息以便调试
        raise HTTPException(status_code=response.status_code, detail=f"Failed to call bot: {response.text}")

    response_data = response.json()

    print(f"Bot response data: {response_data}")  # 打印机器人响应数据以便调试

    # 提取最终的文本响应，只选择content_type为"text"且type为"answer"的内容
    final_responses = [message['content'] for message in response_data.get('messages', []) if message['type'] == 'answer' and message['content_type'] == 'text']

    if not final_responses:
        print("No answer found in bot response")  # 输出错误信息以便调试
        raise HTTPException(status_code=500, detail="Bot did not return a valid response")

    return final_responses[0]

def send_message(im_bot_id: str, im_contact_id: Optional[str], im_room_id: Optional[str], message_type: int, payload: dict, token: str, external_request_id: str):
    url = f"https://hub.juzibot.com/api/v2/message/send?token={token}"

    data = {
        "imBotId": im_bot_id,
        "messageType": message_type,
        "payload": payload,
        "externalRequestId": external_request_id  # 添加 externalRequestId 字段
    }

    if im_room_id:
        data["imRoomId"] = im_room_id
        data["imContactId"] = None
    else:
        data["imContactId"] = im_contact_id

    headers = {
        'Content-Type': 'application/json'
    }

    response = requests.post(url, headers=headers, data=json.dumps(data))

    if response.status_code != 200:
        print(f"Failed to send message: {response.text}")  # 输出错误信息以便调试
        raise HTTPException(status_code=response.status_code, detail=f"Failed to send message: {response.text}")

    return response.json()

# 运行 uvicorn
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8600)
