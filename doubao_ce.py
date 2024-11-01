、import os
import json
from volcenginesdkarkruntime import Ark
import dotenv

# 加载环境变量
dotenv.load_dotenv(".env")

# 初始化 Ark 客户端
# 从环境变量中获取模型 ID 和 API 凭证
model_id = os.getenv("ENDPOINT_ID")
api_key = os.getenv("API_KEY")
ak = os.getenv("AK")
sk = os.getenv("SK")

# 初始化 Ark 客户端
client = Ark(api_key=api_key, ak=ak, sk=sk)
# 从环境变量中获取模型 ID
model_id = os.getenv("ENDPOINT_ID")

# 欢迎语
Welcome_Text = "您好，我是豆包，您的大模型对话助手，请问有什么可以帮到您？(输入 'exit' 退出对话)"
print(Welcome_Text)

# 进入多轮对话的循环
while True:
    # 从终端获取用户输入
    user_input = input("User：\r\n")

    # 检查用户是否想退出
    if user_input.lower() in ["exit", "quit"]:
        print("AI：感谢您的使用，再见！")
        break

    # 创建流式对话请求
    stream = client.chat.completions.create(
        model=model_id,
        messages=[
            {"role": "system", "content": "你是豆包，是由字节跳动开发的 AI 人工智能助手"},
            {"role": "user", "content": user_input},  # 使用终端输入的内容
        ],
        stream=True
    )

    print("AI:")
    # 初始化一个空字符串来存储所有文本
    full_text = ""

    # 逐块读取流式输出并将结果打印
    for chunk in stream:
        if not chunk.choices:
            continue
        # 获取文本内容
        text = chunk.choices[0].delta.content

        # 输出文本到控制台
        print(text, end="")

        # 将文本累积到 full_text
        full_text += text

    print("\r\n")
