# 此脚本为句子互动调用接收消息回调接口
# 注意这里参数不可以设定死

from fastapi import FastAPI, Body, Query, HTTPException

app = FastAPI()

@app.post("/api/receive_data")
async def receive_data(
    msg_signature: str = Query(None, description="The message signature"),
    timestamp: int = Query(None, description="The timestamp"),
    nonce: int = Query(None, description="The nonce"),
    data: dict = Body(None, description="The JSON data in the request body")
):
    if msg_signature is None or timestamp is None or nonce is None:
        raise HTTPException(status_code=400, detail="Query parameters are missing")

    if data is None:
        raise HTTPException(status_code=400, detail="No JSON data provided in the request body")

    # 处理接收到的数据
    print(f"Received data: {data}")
    print(f"Query parameters: msg_signature={msg_signature}, timestamp={timestamp}, nonce={nonce}")

    return {"status": "success", "data": data, "query_params": {"msg_signature": msg_signature, "timestamp": timestamp, "nonce": nonce}}

# 运行 uvicorn
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8600)