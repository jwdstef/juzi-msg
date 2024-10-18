from fastapi import FastAPI, Body, Query, HTTPException
from pydantic import BaseModel
import requests
import json
from typing import Dict, Optional
import uuid
import time
import aiomysql

app = FastAPI()

class Payload(BaseModel):
    text: str
    quoteMessageId: Optional[str] = None  # 引用的消息ID
    mention: Optional[list[str]] = None  # @人的wxid列表

class MessageData(BaseModel):
    imBotId: str
    imContactId: Optional[str] = None  # 客户的系统wxid
    contactName: Optional[str] = None  # 客户的名字，用于艾特
    imRoomId: Optional[str] = None  # 群聊的系统wxid
    roomTopic: Optional[str] = None  # 群聊名称
    messageType: int
    payload: Payload
    token: str
    messageId: str  # 增加 messageId 字段

# 存储已处理的消息ID，用于去重
processed_message_ids: Dict[str, str] = {}

# 创建 MySQL 数据库连接
async def create_connection():
    try:
        connection = await aiomysql.connect(
            host="116.62.108.89",  # MySQL数据库地址
            user="juzi",       # MySQL用户名
            password="C2G4XRFCHLaPnxrD",  # MySQL密码
            db="juzi",  # 数据库名称
            port=3307,
            autocommit=True  # 自动提交事务
        )
        return connection
    except Exception as e:
        log_to_file(f"Error connecting to MySQL: {e}")
        raise HTTPException(status_code=500, detail="Database connection error")

# 记录日志到文件
def log_to_file(message: str, filename_prefix="log"):
    date_str = time.strftime("%Y%m%d")
    filename = f"{filename_prefix}_{date_str}.txt"
    with open(filename, "a", encoding="utf-8") as log_file:
        log_file.write(f"{time.strftime('%Y-%m-%d %H:%M:%S')} - {message}\n")

# 插入消息数据到数据库
async def insert_message_to_db(contact_name: str, query_text: str, bot_response: str, room_topic: str, msg_type: int):
    connection = await create_connection()
    async with connection.cursor() as cursor:
        # 创建插入语句
        insert_query = """
        INSERT INTO messages (contact_name, query_text, bot_response, room_topic, type, created_at)
        VALUES (%s, %s, %s, %s, %s, NOW())
        """
        # 插入的数据
        record = (contact_name, query_text, bot_response, room_topic, msg_type)

        try:
            await cursor.execute(insert_query, record)
            await connection.commit()
        except Exception as e:
            log_to_file(f"Failed to insert into MySQL: {e}")
            raise HTTPException(status_code=500, detail="Database insertion error")
        finally:
            connection.close()

# 调用聊天机器人
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
        log_to_file(f"Failed to call bot: {response.text}")  # 输出错误信息以便调试
        raise HTTPException(status_code=response.status_code, detail=f"Failed to call bot: {response.text}")

    response_data = response.json()

    log_to_file(f"Bot response data: {response_data}")  # 打印机器人响应数据以便调试

    final_responses = [message['content'] for message in response_data.get('messages', []) if
                       message['type'] == 'answer' and message['content_type'] == 'text']

    if not final_responses:
        log_to_file("No answer found in bot response")  # 输出错误信息以便调试
        raise HTTPException(status_code=500, detail="Bot did not return a valid response")

    return final_responses[0]

# 发送消息到外部接口
def send_message(im_bot_id: str, im_contact_id: Optional[str], im_room_id: Optional[str], room_topic: Optional[str], message_type: int,
                 payload: dict, token: str, external_request_id: str):
    url = f"https://hub.juzibot.com/api/v2/message/send?token={token}"

    data = {
        "imBotId": im_bot_id,
        "messageType": message_type,
        "payload": payload,
        "externalRequestId": external_request_id,
    }

    if im_room_id:
        data["imRoomId"] = im_room_id
        data["roomTopic"] = room_topic
        data["imContactId"] = None
    else:
        data["imContactId"] = im_contact_id

    headers = {
        'Content-Type': 'application/json'
    }

    response = requests.post(url, headers=headers, data=json.dumps(data))

    if response.status_code != 200:
        log_to_file(f"Failed to send message: {response.text}")  # 输出错误信息以便调试
        raise HTTPException(status_code=response.status_code, detail=f"Failed to send message: {response.text}")

    return response.json()

@app.post("/api/receive_data")
async def receive_data(
        msg_signature: str = Query(None, description="The message signature"),
        timestamp: int = Query(None, description="The timestamp"),
        nonce: int = Query(None, description="The nonce"),
        data: MessageData = Body(None, description="The JSON data in the request body")
):
    receive_start_time = time.time()

    if msg_signature is None or timestamp is None or nonce is None:
        raise HTTPException(status_code=400, detail="Query parameters are missing")

    if data is None:
        raise HTTPException(status_code=400, detail="No JSON data provided in the request body")

    log_to_file(f"Received data: {data}")
    log_to_file(f"Query parameters: msg_signature={msg_signature}, timestamp={timestamp}, nonce={nonce}")

    # 过滤机器人自己发送的回复消息，避免重复记录
    if data.imBotId == data.imContactId:
        log_to_file("Filtered out self-sent message to avoid recording the bot's own reply.")
        return {"status": "filtered", "reason": "self-sent message"}

    # 获取客户的原始消息
    original_query = data.payload.text  # 完整记录客户的原始输入

    # 判断是否为群聊
    is_group_chat = data.imRoomId is not None

    should_respond = False
    msg_type = 1  # 默认消息类型为1，不触发机器人

    if is_group_chat:
        # 群聊场景，需要艾特机器人，且机器人名字为"有方*方工"
        bot_name_in_group = "有方*方工"

        # 检查payload是否包含mention信息
        mention_list = data.payload.mention or []

        log_to_file(f"Mention list: {mention_list}")

        # 判断机器人是否被艾特
        if data.imBotId in mention_list:
            log_to_file("Bot was mentioned in group chat.")

            # 设置为需要响应
            should_respond = True
            msg_type = 0  # 消息类型设为0，表示触发机器人

            # 去除艾特机器人的文本，提取用户的查询
            query_for_bot = original_query.replace(f"@{bot_name_in_group}", "").strip()

        else:
            log_to_file("Bot was not mentioned in group chat.")
    else:
        # 私聊场景，消息必须以"方工"开头
        if original_query.startswith("方工"):
            log_to_file("Private message starts with '方工'.")

            # 设置为需要响应
            should_respond = True
            msg_type = 0  # 消息类型设为0，表示触发机器人

            # 去除"方工"前缀，提取用户的查询
            query_for_bot = original_query.replace("方工", "", 1).strip()
        else:
            log_to_file("Private message does not start with '方工'.")

    if should_respond:
        # 调用机器人，并记录响应
        bot_start_time = time.time()
        bot_response = call_bot(query_for_bot)
        bot_elapsed_time = time.time() - bot_start_time
        log_to_file(f"Bot response time: {bot_elapsed_time} seconds")

        # 构建回复消息的payload
        if is_group_chat:
            # 群聊中，回复时需要艾特发送者
            mention_list = [data.imContactId] if data.imContactId else []
            response_text = f"@{data.contactName or ''} {bot_response}"
            data.payload.text = response_text
            data.payload.quoteMessageId = data.messageId
            data.payload.mention = mention_list
        else:
            # 私聊中，直接回复
            data.payload.text = bot_response
            data.payload.quoteMessageId = data.messageId

        # 发送消息
        external_request_id = str(uuid.uuid4())
        send_start_time = time.time()
        send_response = send_message(
            data.imBotId,
            data.imContactId,
            data.imRoomId,
            data.roomTopic,
            data.messageType,
            data.payload.dict(),
            data.token,
            external_request_id
        )
        send_elapsed_time = time.time() - send_start_time
        log_to_file(f"Send message time: {send_elapsed_time} seconds")

        # 插入数据库，记录原始问题和机器人回复
        await insert_message_to_db(
            contact_name=data.contactName or "",
            query_text=original_query,  # 插入客户的原始问题，不做任何修改
            bot_response=bot_response,
            room_topic=data.roomTopic or "",
            msg_type=msg_type  # 消息类型设为0，表示触发机器人
        )

        # 记录接收消息回调的总时间
        receive_elapsed_time = time.time() - receive_start_time
        log_to_file(f"Receive callback time: {receive_elapsed_time} seconds")

        return {"status": "success", "send_response": send_response,
                "query_params": {"msg_signature": msg_signature, "timestamp": timestamp, "nonce": nonce}}

    else:
        # 不需要响应时，直接插入数据库并不调用机器人
        await insert_message_to_db(
            contact_name=data.contactName or "",
            query_text=original_query,  # 插入客户的原始问题
            bot_response="",  # 没有机器人回复时留空
            room_topic=data.roomTopic or "",
            msg_type=msg_type  # 消息类型根据是否触发机器人而定
        )
        log_to_file(f"Message did not meet trigger conditions. Recorded with msg_type={msg_type}.")
        return {"status": "recorded", "reason": "did not meet trigger conditions"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8600)
