# doubao.py

import os
from volcenginesdkarkruntime import Ark
import dotenv
import pandas as pd
import re

# 加载环境变量
dotenv.load_dotenv(".env")

# 从环境变量中获取模型 ID 和 API 凭证
model_id = os.getenv("ENDPOINT_ID")
api_key = os.getenv("API_KEY")
ak = os.getenv("AK")
sk = os.getenv("SK")

# 初始化 Ark 客户端
client = Ark(api_key=api_key, ak=ak, sk=sk)

# 读取 Excel 文件并填充型号列
file_path = "Neoway_齐套性资料_AI喂养链接.xlsx"
df = pd.read_excel(file_path)
df['型号'] = df['型号'].fillna(method='ffill')

# 将数据转换为列表形式
data_list = df.to_dict('records')

def get_doubao_response(user_input: str) -> str:
    """
    根据用户输入，使用 Ark API 生成回复。

    参数:
    user_input (str): 用户的输入文本。

    返回:
    str: AI 生成的回复。
    """
    # 将型号、描述和链接拼接成字符串，提供给模型作为上下文
    data_text = "\n".join(
        f"型号: {item['型号']}\n描述: {item['描述']}\n链接: {item['链接']}\n"
        for item in data_list if pd.notna(item['链接'])
    )

    # 创建系统提示，包含所有数据和详细指导
    system_prompt = (
        "你是豆包，一个由字节跳动开发的智能对话助手。\n"
        "以下是一些型号、描述和链接的数据：\n"
        f"{data_text}\n"
        "当用户输入请求时，你需要：\n"
        "1. 从用户的输入中提取相关的型号，即使型号包含更多细节或版本号（例如，'N58-CA-091AS1'）。\n"
        "2. 在数据中找到与该型号最接近的记录，允许部分匹配或模糊匹配（例如，'N58-CA-091AS1' 可以匹配到 'N58-CA'）。\n"
        "3. 提取用户输入中的其他关键词（例如，'GPS功能'）。\n"
        "4. 在匹配到的记录中，依据描述字段，找到与这些关键词相关的资料。\n"
        "5. 如果找到一个链接，使用以下格式：\n"
        "💾 资料链接: <链接>\n"
        "6. 如果找到多个链接，使用以下格式：\n"
        "💾 资料链接:\n"
        "<链接1>\n"
        "<链接2>\n"
        "7. 将所有匹配的描述和链接发送给用户。\n"
        "8. 如果未找到任何匹配的资料，礼貌地告知用户。\n"
        "以下是一些示例：\n"
        "用户：N58-CA-091AS1带GPS功能吗\n"
        "助手：\n"
        "根据现有资料，N58-CA 支持 GPS 功能。您可以参考以下链接获取更多信息：\n"
        "💾 资料链接: https://example.com/N58-CA-GPS\n"
        "如果有多个链接：\n"
        "💾 资料链接:\n"
        "https://example.com/N58-CA-GPS\n"
        "https://example.com/N58-CA-Manual\n"
        "如果没有直接的信息，也可以提供相关的资料链接供用户参考。\n"
    )

    # 创建对话请求，让模型处理所有逻辑
    response = client.chat.completions.create(
        model=model_id,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_input},
        ]
    )

        # 在每一步增加日志输出
    # print(f"Received user input: {user_input}")
    # print(f"Data text for context: {data_text}...")  # 只打印前500个字符以免输出过长
    print("Sending request to AI model...")

    # 获取 AI 的回复
    ai_reply = response.choices[0].message.content

    return ai_reply
if __name__ == "__main__":
    test_input = "N720V5T-VS8规格书"
    # test_input = "发一下N58驱动"
    print(get_doubao_response(test_input))
