from typing import List, Tuple, Dict
from tqdm import tqdm
from langchain_community.document_loaders import PyPDFLoader
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain.output_parsers import StructuredOutputParser, ResponseSchema
import requests
import json

class TripleExtractor:
    def __init__(self, model_name: str = "qwen2"):
        self.model_name = model_name
        self.ollama_url = "http://localhost:11434/api/generate"
        self.text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=2000,
            chunk_overlap=200,
            length_function=len,
        )
        self.output_parser = self._create_parser()
        
    def _create_parser(self):
        """创建结构化输出解析器"""
        response_schemas = [
            ResponseSchema(name="basic_params", description="基本参数，包括尺寸、重量、温度等", type="list"),
            ResponseSchema(name="electrical_params", description="电气特性，包括电压、电流、功耗等", type="list"),
            ResponseSchema(name="performance_params", description="性能参数，包括处理器、内存、频段等", type="list"),
            ResponseSchema(name="interface_params", description="接口参数，包括天线、UART、USB等", type="list"),
        ]
        return StructuredOutputParser.from_response_schemas(response_schemas)

    def extract_text_from_pdf(self, pdf_path: str) -> str:
        """从PDF文件中提取文本，使用Langchain的PDF加载器"""
        loader = PyPDFLoader(pdf_path)
        pages = loader.load()
        
        # 使用tqdm显示处理进度
        texts = []
        for page in tqdm(pages, desc="处理PDF页面", unit="页"):
            texts.append(page.page_content)
            
        # 将文本分割成更小的块
        text_chunks = self.text_splitter.split_text("\n".join(texts))
        
        # 合并所有文本块
        return "\n".join(text_chunks)
    
    def create_prompt(self, text: str) -> str:
        """创建提示词"""
        return f"""你是一个专业的技术文档信息提取助手。请仔细阅读以下产品规格书，并严格按照JSON格式提取N58模组的技术参数信息。

        必须返回如下JSON格式（不要返回其他任何内容）：
        {{
            "basic_params": [
                {{"name": "尺寸", "value": "30.00×28.00×2.50", "unit": "mm"}},
                {{"name": "重量", "value": "4.63", "unit": "g"}},
                {{"name": "工作温度", "value": "-30~+75", "unit": "°C"}}
            ],
            "electrical_params": [
                {{"name": "工作电压", "value": "3.4-4.2", "unit": "V"}},
                {{"name": "待机电流", "value": "16", "unit": "mA"}}
            ],
            "performance_params": [
                {{"name": "处理器", "value": "ARM Cortex-A5", "unit": null}},
                {{"name": "RAM", "value": "128", "unit": "Mb"}}
            ],
            "interface_params": [
                {{"name": "UART接口", "value": "3", "unit": "个"}},
                {{"name": "USB接口", "value": "1", "unit": "个"}}
            ]
        }}

        注意事项：
        1. 必须严格按照上述JSON格式返回
        2. 不要添加任何解释性文字
        3. 确保JSON格式的完整性和正确性
        4. 所有数值必须准确提取自文档

        需要提取的参数类别：
        - basic_params: 尺寸、重量、温度等基本参数
        - electrical_params: 电压、电流、功耗等电气参数
        - performance_params: 处理器、��存、频段等性能参数
        - interface_params: UART、USB、天线等接口参数

        文本内容:
        {text}

        请直接返回JSON格式数据："""
    
    def call_ollama(self, prompt: str) -> str:
        """调用Ollama API"""
        payload = {
            "model": self.model_name,
            "prompt": prompt,
            "stream": False
        }
        
        response = requests.post(self.ollama_url, json=payload)
        if response.status_code == 200:
            return response.json()['response']
        else:
            raise Exception(f"Ollama API调用失败: {response.status_code}")
    
    def parse_response(self, response: str) -> List[Dict]:
        """解析响应"""
        try:
            # 清理响应文本，尝试找到JSON部分
            response = response.strip()
            start = response.find('{')
            end = response.rfind('}') + 1
            
            if start == -1 or end == 0:
                print("响应中未找到JSON格式数据")
                return []
            
            json_str = response[start:end]
            print("\n=== 提取的JSON字符串 ===")
            print(json_str)
            
            # 尝试解析JSON
            data = json.loads(json_str)
            
            # 验证数据结构
            required_keys = ['basic_params', 'electrical_params', 'performance_params', 'interface_params']
            if not all(key in data for key in required_keys):
                print("JSON数据缺少必要的键")
                return []
            
            # 转换为三元组格式
            triples = []
            for category, params in data.items():
                if not isinstance(params, list):
                    continue
                for param in params:
                    if not all(k in param for k in ('name', 'value')):
                        continue
                    triple = {
                        "subject": "N58模组",
                        "predicate": param["name"],
                        "object": f"{param['value']}{param.get('unit', '')}"
                    }
                    triples.append(triple)
            
            return triples
            
        except json.JSONDecodeError as e:
            print(f"JSON解析错误: {str(e)}")
            print("原始响应:")
            print(response)
            return []
        except Exception as e:
            print(f"解析过程中出现错误: {str(e)}")
            return []
    
    def extract_triples(self, pdf_path: str) -> List[Dict]:
        """主要处理函数"""
        # 1. 提取文本
        text = self.extract_text_from_pdf(pdf_path)

        
        # 2. 创建提示词
        prompt = self.create_prompt(text)
        
        # 3. 调用模型
        response = self.call_ollama(prompt)
        
        # 4. 解析结果
        triples = self.parse_response(response)
        
        return triples

def main():
    # 使用示例
    extractor = TripleExtractor(model_name="qwen2")
    pdf_path = "Neoway_N58_产品规格书_V2.6.pdf"
    
    try:
        # 首先提取文本
        text = extractor.extract_text_from_pdf(pdf_path)
        print("\n=== 提取的文本内容 ===")
        print(text[:1000])  # 只显示前1000个字符
        print("...\n")
        
        # 然后提取三元组
        triples = extractor.extract_triples(pdf_path)
        print("=== 提取的参数信息 ===")
        if triples:
            for triple in triples:
                print(f"参数: {triple['predicate']}")
                print(f"取值: {triple['object']}")
                print("---")
        else:
            print("未能成功提取参数信息")
            
        # 打印原始响应用于调试
        print("\n=== 调试信息 ===")
        response = extractor.call_ollama(extractor.create_prompt(text))
        print("模型响应:")
        print(response)
    
    except Exception as e:
        print(f"处理过程中出现错误: {str(e)}")

if __name__ == "__main__":
    main()