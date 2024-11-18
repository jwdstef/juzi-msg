from fastapi import FastAPI, Body, Query, HTTPException
from pydantic import BaseModel
import requests
import json
from typing import Dict, Optional
import uuid
import time
import aiomysql
from get_product_link import get_product_link_response

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
            user="juzi",  # MySQL用户名
            password="C2G4XRFCHLaPnxrD",  # MySQL密码
            db="juzi",  # 数据库名称
            port=3307,
            autocommit=True  # 自动提交事务
        )
        log_to_file("MySQL连接成功", "INFO")
        return connection
    except Exception as e:
        log_to_file(f"MySQL连接失败: {e}", "ERROR")
        raise HTTPException(status_code=500, detail="数据库连接错误")


# 记录日志到文件
def log_to_file(message: str, level: str = "INFO", filename_prefix="log"):
    """
    按标准格式记录日志。

    参数:
    message (str): 要记录的消息。
    level (str): 日志的严重级别（'INFO'，'ERROR'，'DEBUG'等）。
    filename_prefix (str): 日志文件的前缀。
    """
    date_str = time.strftime("%Y%m%d")
    filename = f"{filename_prefix}_{date_str}.txt"

    log_time = time.strftime('%Y-%m-%d %H:%M:%S')

    log_entry = f"[{log_time}] [{level}] - {message}\n"  # 标准化日志格式

    with open(filename, "a", encoding="utf-8") as log_file:
        log_file.write(log_entry)


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
def send_message(im_bot_id: str, im_contact_id: Optional[str], im_room_id: Optional[str], room_topic: Optional[str],
                 message_type: int,
                 payload: dict, token: str, external_request_id: str, is_announcement: Optional[bool] = None,
                 is_at_all: Optional[bool] = None):
    url = f"https://hub.juzibot.com/api/v2/message/send?token={token}"

    data = {
        "imBotId": im_bot_id,
        "messageType": message_type,
        "payload": payload,
        "externalRequestId": external_request_id,
        # 新增的字段
        "isAnnouncement": is_announcement,
        "isAtAll": is_at_all,
        "imRoomId": im_room_id,
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

    # 群聊场景：仅当机器人被艾特时才响应
    if data.imRoomId:  # 检查是否是群聊
        if f"@有方方工" in original_query:  # 检测是否艾特了机器人
            query_for_bot = original_query.replace(f"@有方方工", "").strip()

            # 调用机器人，并记录响应
            bot_response = call_bot(query_for_bot)
            # 打印出 bot_response 的内容进行调试
            print(f"Original bot response: {bot_response}")

            if ('抱歉' in bot_response or
                    '很抱歉' in bot_response or
                    '您提问的内容我暂时无法解答，可以联系我司FAE同事进行解答，谢谢！' in bot_response or
                    '您好，您提问的内容我暂时无法解答，可以联系我司FAE同事进行解答，谢谢！' in bot_response or
                    ("💾 资料链接:" in bot_response and "http" not in bot_response)):
                # 使用 get_product_link_response 获取新的回复
                bot_response = get_product_link_response(query_for_bot)
                log_to_file("Bot could not answer, used doubao to get response")

            # 构建艾特发送者的回复，艾特之后换行再回答
            response_text = f"@{data.contactName}\n{bot_response}"
            data.payload.text = response_text
            data.payload.mention = [data.imContactId]  # 将发送者的wxid添加到mention数组中

            # 发送消息
            external_request_id = str(uuid.uuid4())
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

            # 插入数据库
            await insert_message_to_db(
                contact_name=data.contactName or "",
                query_text=original_query,
                bot_response=bot_response,
                room_topic=data.roomTopic or "",
                msg_type=0  # 消息类型设为0，表示触发了机器人
            )
        else:
            # 没有艾特机器人时，直接记录消息
            await insert_message_to_db(
                contact_name=data.contactName or "",
                query_text=original_query,
                bot_response="",
                room_topic=data.roomTopic or "",
                msg_type=1  # 消息类型设为1，表示未触发机器人
            )
            return {"status": "recorded", "reason": "no mention of bot"}

    # 私聊场景：消息必须以 "方工" 开头
    else:  # 检查是否是私聊
        if original_query.startswith("方工"):
            query_for_bot = original_query.replace("方工", "").strip()

            # 调用机器人，并记录响应
            bot_response = call_bot(query_for_bot)
            print(f"Original bot response: {bot_response}")
            # 检查机器人是否无法解答
            if ('抱歉' in bot_response or
                    '很抱歉' in bot_response or
                    '您提问的内容我暂时无法解答，可以联系我司FAE同事进行解答，谢谢！' in bot_response or
                    '您好，您提问的内容我暂时无法解答，可以联系我司FAE同事进行解答，谢谢' in bot_response or
                    ("💾 资料链接:" in bot_response and "http" not in bot_response)):
                log_to_file("Bot response indicated need for doubao, calling get_doubao_response...", "INFO")
                # 使用 get_product_link_response 获取新的回复
                bot_response = get_product_link_response(query_for_bot)
                log_to_file("Bot could not answer, used doubao to get response")

            # 构建私聊的回复
            data.payload.text = bot_response

            # 发送消息
            external_request_id = str(uuid.uuid4())
            send_response = send_message(
                data.imBotId,
                data.imContactId,
                None,  # 私聊不需要 imRoomId
                None,
                data.messageType,
                data.payload.dict(),
                data.token,
                external_request_id
            )

            # 插入数据库
            await insert_message_to_db(
                contact_name=data.contactName or "",
                query_text=original_query,
                bot_response=bot_response,
                room_topic="",
                msg_type=0  # 消息类型设为0，表示触发了机器人
            )
        else:
            # 未以"方工"开头，直接记录消息
            await insert_message_to_db(
                contact_name=data.contactName or "",
                query_text=original_query,
                bot_response="",
                room_topic="",
                msg_type=1  # 消息类型设为1，表示未触发机器人
            )
            return {"status": "recorded", "reason": "no trigger word"}

    # 记录接收消息回调的总时间
    receive_elapsed_time = time.time() - receive_start_time
    log_to_file(f"Receive callback time: {receive_elapsed_time} seconds")

    return {"status": "success", "send_response": send_response,
            "query_params": {"msg_signature": msg_signature, "timestamp": timestamp, "nonce": nonce}}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8600)