import os
import json
from volcenginesdkarkruntime import Ark
import dotenv

# 加载环境变量
dotenv.load_dotenv(".env")

# 从环境变量中获取模型 ID 和 API 凭证
model_id = os.getenv("ENDPOINT_ID")
api_key = os.getenv("API_KEY")
ak = os.getenv("AK")
sk = os.getenv("SK")

# 初始化 Ark 客户端
client = Ark(api_key=api_key, ak=ak, sk=sk)

# 读取 JSON 文件并将数据加载为字典
file_path = "neoway_data_structured.json"
with open(file_path, 'r', encoding='utf-8') as f:
    data_dict = json.load(f)

def get_doubao_response(user_input: str) -> str:
    """
    根据用户输入，使用 Ark API 生成回复。
    
    参数:
    user_input (str): 用户的输入文本。
    
    返回:
    str: AI 生成的回复。
    """
    # 创建系统提示，包含所有数据和详细指导
    data_text = "\n".join(
        f"型号: {model}\n" + "\n".join(
            f"描述: {entry['描述']}\n链接: {', '.join(entry['链接']) if isinstance(entry['链接'], list) else entry['链接']}"
            for entry in entries
        )
        for model, entries in data_dict.items()
    )

    # 改进后的系统提示，包含多条链接的格式
    system_prompt = (
        "你是豆包，一个由字节跳动开发的智能对话助手。\n"
        "以下是一些型号、描述和链接的数据：\n"
        f"{data_text}\n"
        "当用户输入请求时，你需要：\n"
        "1. 提取用户输入中的型号并与数据中匹配，允许模糊匹配，确保型号部分匹配时也能识别。\n"
        "2. 提取用户输入中的其他关键词（例如 'GPS功能' 或 '封装'），并在数据的描述中查找相关内容。\n"
        "3. 在找到的描述中，优先返回包含关键字的描述和链接，避免冗余信息。\n"
        "4. 如果找到多个链接，按以下格式返回：\n"
        "💾 资料链接:\n"
        "[链接1名称]: <链接1>\n"
        "[链接2名称]: <链接2>\n"
        "5. 如果无法找到完整匹配的记录，建议最相似的结果，确保用户获取到尽可能相关的信息。\n"
        "以下是一些示例：\n"
        "用户：N58-CA-091AS1带GPS功能吗\n"
        "助手：\n"
        "根据现有资料，N58-CA 支持 GPS 功能。您可以参考以下链接获取更多信息：\n"
        "💾 资料链接:\n"
        "[N58-CA 资料链接]: https://drive.weixin.qq.com/s?k=AGwAyQfnAGgF90nseL\n"
        "[N58-CA 驱动]: https://drive.weixin.qq.com/s?k=AGwAyQfnAGg317r7Fu\n"
        "[N58-CA 工具]: https://drive.weixin.qq.com/s?k=AGwAyQfnAGgC8hHQNS\n"
        "[N58-CA 视频指南]: https://drive.weixin.qq.com/s?k=AGwAyQfnAGgRsjE0pN\n"
        "[N58-CA EVK 用户指南]: https://drive.weixin.qq.com/s?k=AGwAyQfnAGgY9yDgEm\n"
        "如果没有找到直接信息，也可以提供相关资料链接供用户参考。\n"
    )

    # 通过模型发送对话请求
    response = client.chat.completions.create(
        model=model_id,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_input},
        ]
    )

    # 获取 AI 的回复
    ai_reply = response.choices[0].message.content

    return ai_reply


if __name__ == "__main__":
    test_input = "发一下N725B的硬件设计指南和Datasheet"
    print(get_doubao_response(test_input))
