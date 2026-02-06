"""AutoGen化工流程模拟后端

使用AutoGen框架构建智能体，通过工具调用处理化工流程模拟请求。
"""

from typing import Dict, Any, List
import os
import io
import sys
import ast
import logging
import aiofiles
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from autogen_agentchat.agents import AssistantAgent
from autogen_core.models import ModelFamily
from autogen_ext.models.openai import OpenAIChatCompletionClient
from prompt.llm_prompt import system_prompt
from tools.get_schema import get_schema
from tools.run_simulation import run_simulation
from tools.get_result import get_result
from fastapi import WebSocket, WebSocketDisconnect
import json
from fastapi.responses import FileResponse
from pathlib import Path
from autogen_agentchat.messages import (
    TextMessage,
    ToolCallExecutionEvent,
    ToolCallRequestEvent,
    ModelClientStreamingChunkEvent,
    ThoughtEvent
)

from autogen_core import CancellationToken

load_dotenv()
# 确保标准输出使用UTF-8编码
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

# 配置
MODEL = os.getenv("MODEL", "deepseek-chat")
MODEL_API_KEY = os.getenv("MODEL_API_KEY")
MODEL_API_URL = os.getenv("MODEL_API_URL")  # 模型API地址
ASPEN_SIMULATOR_URL = os.getenv("ASPEN_SIMULATOR_URL")

# 创建必要的目录
BASE_DIR = os.path.dirname(__file__)
os.makedirs(BASE_DIR, exist_ok=True)

# 智能体状态持久化路径
state_path = "agent_state.json"
history_path = "agent_history.json"

# 初始化FastAPI应用
app = FastAPI(title="化工流程模拟智能体", version="1.0.0")

# 添加CORS中间件
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class ChatRequest(BaseModel):
    """聊天请求模型"""
    message: str

# 配置日志使用UTF-8
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),  # 使用重定向的标准输出
        logging.FileHandler('app.log', encoding='utf-8')  # 文件也使用UTF-8
    ]
)
logger = logging.getLogger(__name__)

async def creat_model_client() -> OpenAIChatCompletionClient:
    """获取智能体实例"""
    try:
        # 创建模型客户端
        model_client = OpenAIChatCompletionClient(
            api_key=MODEL_API_KEY,
            base_url=MODEL_API_URL,
            model=MODEL,
            temperature=0.2,
            max_tokens=8192,
            model_info={
                "vision": False,  # 是否支持视觉
                "function_calling": True,  # 是否支持函数调用
                "json_output": True,  # 是否支持JSON输出
                "family": ModelFamily.UNKNOWN,  # 模型家族，国内模型写UNKOWN即可，可以是 OPENAI、CLAUDE、R1等
                "structured_output": True,  # 是否支持结构化输出
                # 可选字段
                "multiple_system_messages": False,  # 是否支持多个系统消息
            }
        )
        return model_client
    except Exception as e:
        logger.error(f"创建模型客户端失败: {e}")
        raise HTTPException(status_code=500, detail=f"模型初始化失败: {str(e)}")

async def chemical_expert_agent(model_client: OpenAIChatCompletionClient) -> AssistantAgent:
    # 创建化工专家智能体
    agent = AssistantAgent(
        name="chemical_expert",
        model_client=model_client,
        system_message=system_prompt,
        tools = [get_schema, run_simulation, get_result],
        reflect_on_tool_use=True,
        model_client_stream=True,
        max_tool_iterations=100,
    )

    # 加载状态（如果存在）
    if os.path.exists(state_path):
        try:
            async with aiofiles.open(state_path, "r", encoding="utf-8") as f:
                state = json.loads(await f.read())
            await agent.load_state(state)
            logger.info("智能体状态已加载")
        except Exception as e:
            logger.warning(f"加载智能体状态失败: {e}")

    return agent

# 在 main.py 的 download_file 路由中，更新允许的文件扩展名
@app.get("/download")
async def download_file(file_path: str):
    """下载文件接口"""
    try:
        file_path_obj = Path(file_path)

        if not file_path_obj.exists():
            raise HTTPException(status_code=404, detail="文件不存在")

        # 扩展允许的文件类型
        allowed_extensions = {'.bkp', '.apw', '.json', '.xlsx', '.xls', '.txt', '.log', '.out'}
        if file_path_obj.suffix.lower() not in allowed_extensions:
            raise HTTPException(status_code=403, detail="不允许下载此类型文件")

        filename = file_path_obj.name

        # 根据文件扩展名设置Content-Type
        content_types = {
            '.bkp': 'application/octet-stream',
            '.apw': 'application/octet-stream',
            '.json': 'application/json',
            '.xlsx': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            '.xls': 'application/vnd.ms-excel',
            '.txt': 'text/plain',
            '.log': 'text/plain',
            '.out': 'text/plain'
        }

        media_type = content_types.get(file_path_obj.suffix.lower(), 'application/octet-stream')

        return FileResponse(
            path=file_path_obj,
            filename=filename,
            media_type=media_type
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"下载文件失败: {e}")
        raise HTTPException(status_code=500, detail=f"下载文件失败: {str(e)}")

async def get_history() -> List[Dict[str, Any]]:
    """获取聊天历史"""
    if not os.path.exists(history_path):
        return []
    try:
        async with aiofiles.open(history_path, "r", encoding="utf-8") as f:
            content = await f.read()
            if content.strip():
                return json.loads(content)
            else:
                return []
    except Exception as e:
        logger.error(f"读取历史记录失败: {e}")
        return []

@app.get("/history")
async def history():
    """获取聊天历史"""
    try:
        return await get_history()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e

# @app.post("/chat", response_model=TextMessage)
# async def chat(request: ChatRequest) -> TextMessage:
#     """处理用户消息"""
#     try:
#         # 创建模型客户端
#         model_client = await creat_model_client()
#         # 获取智能体
#         agent = await chemical_expert_agent(model_client)
#
#         # 创建用户消息
#         user_message = TextMessage(
#             content=request.message,
#             source="user"
#         )
#
#         logger.info(f"处理用户消息: {request.message[:100]}...")
#
#         # 获取响应
#         response = await agent.on_messages(
#             messages=[user_message],
#             cancellation_token=CancellationToken()
#         )
#
#         # 保存智能体状态
#         state = await agent.save_state()
#         async with aiofiles.open(state_path, "w", encoding="utf-8") as f:
#             await f.write(json.dumps(state, ensure_ascii=False).encode("utf-8").decode("utf-8"))
#
#         # 保存历史记录
#         history = await get_history()
#         history.append({
#             "role": "user",
#             "content": request.message,
#             "timestamp": datetime.now().isoformat()
#         })
#
#         response_content = response.chat_message.content
#         history.append({
#             "role": "assistant",
#             "content": response_content,
#             "timestamp": datetime.now().isoformat()
#         })
#
#         # 保持最近100条历史记录
#         if len(history) > 100:
#             history = history[-100:]
#
#         async with aiofiles.open(history_path, "w", encoding="utf-8") as f:
#             await f.write(json.dumps(history, ensure_ascii=False, indent=2).encode("utf-8").decode("utf-8"))
#
#         assert isinstance(response.chat_message, TextMessage)
#         return response.chat_message
#
#     except Exception as e:
#         logger.exception(f"处理聊天请求时出错: {e}")
#         raise HTTPException(status_code=500, detail=f"处理请求时出错: {str(e)}")

# 扩展：WebSocket 管理器
class ConnectionManager:
    def __init__(self):
        self.active_connections: list[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        self.active_connections.remove(websocket)

    async def send_payload(self, websocket: WebSocket, payload: dict):
        """发送统一格式的 JSON 负载"""
        await websocket.send_text(json.dumps(payload, ensure_ascii=False))

manager = ConnectionManager()

@app.websocket("/ws/chat")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    # ... 初始化 agent ...
    # 创建模型客户端
    model_client = await creat_model_client()
    # 获取智能体
    agent = await chemical_expert_agent(model_client)
    try:
        while True:
            data = await websocket.receive_text()
            user_input = json.loads(data)["message"]
            accumulated_content = ""

            async for chunk in agent.on_messages_stream(
                    [TextMessage(content=user_input, source="user")],
                    CancellationToken()
            ):
                payload = {"role": "assistant", "type": "update"}

                # 情况 A: 思维链 (Thought)
                if isinstance(chunk, ThoughtEvent):
                    payload.update({"thought": chunk.content})

                # 情况B 用户完整回复: 流式文本块
                elif isinstance(chunk, ModelClientStreamingChunkEvent):
                    accumulated_content += chunk.content

                # 情况 C: 工具调用请求 (Request)
                elif isinstance(chunk, ToolCallRequestEvent):
                    # 注意：chunk.content 在这里是 List[FunctionCall]
                    payload.update({
                        "status": "tool_calling",
                        "tool_calls": [
                            {
                                "id": tc.id if hasattr(tc, 'id') else "call_" + str(index),
                                "function_name": tc.name,  # 注意：源码中可能是 tc.name 或 tc.function
                                "args": tc.arguments
                            } for index, tc in enumerate(chunk.content)
                        ]
                    })

                # # 情况 D: 工具执行结果 (Execution)
                # elif isinstance(chunk, ToolCallExecutionEvent):
                #     # 注意：chunk.content 在这里是 List[FunctionExecutionResult]
                #     payload.update({
                #         "status": "tool_executed",
                #         "tool_results": [
                #             {
                #                 "call_id": res.call_id,
                #                 "result": res.content,
                #                 "is_error": False
                #             } for res in chunk.content
                #         ]
                #     })
                # 情况 D: 工具执行结果 (Execution) - 修改这里
                elif isinstance(chunk, ToolCallExecutionEvent):
                    tool_results = []
                    for res in chunk.content:
                        logger.info(f"---------res={res}")
                        result_data = {
                            "call_id": res.call_id,
                            "result": res.content,
                            "is_error": False
                        }

                        # 如果是run_simulation工具的结果，解析JSON提取文件路径
                        try:
                            # 尝试解析结果为JSON
                            if 'run_simulation' in str(res):
                                result_json = ast.literal_eval(res.content)

                                # 提取所有存在的文件路径
                                file_paths = []

                                # 成功时包含3个文件
                                if result_json.get('success'):
                                    file_keys = ['aspen_file_path', 'config_file_path', 'result_file_path']
                                    for key in file_keys:
                                        if key in result_json:
                                            file_paths.append({
                                                "path": result_json[key],
                                                "type": key.split('_')[0]  # aspen, config, result
                                            })
                                    # 保存到临时变量中，等智能体回复后再发送
                                    files_to_download = file_paths
                                    logger.info(f"成功提取到 {len(file_paths)} 个文件路径")
                                # 失败时可能只包含1个文件
                                else:
                                    if 'aspen_file_path' in result_json:
                                        file_paths.append({
                                            "path": result_json['aspen_file_path'],
                                            "type": "aspen"
                                        })

                                if file_paths:
                                    result_data["file_paths"] = file_paths
                        except (json.JSONDecodeError, AttributeError) as e:
                            # 如果不是JSON格式或解析失败，则忽略
                            logger.info(f"解析run_simulation结果失败: {e}")
                            pass

                        tool_results.append(result_data)

                    payload.update({
                        "status": "tool_executed",
                        "tool_results": tool_results
                    })

                await manager.send_payload(websocket, payload)

            # 流结束后发送完整回复
            if accumulated_content:
                payload = {"role": "assistant", "type": "update", "content": accumulated_content}
                await manager.send_payload(websocket, payload)

                # 成功时，在智能体回复后发送文件下载信息
                if files_to_download:
                    download_payload = {
                        "role": "system",
                        "type": "file_download",
                        "file_paths": files_to_download
                    }
                    await manager.send_payload(websocket, download_payload)

            await manager.send_payload(websocket, {"type": "done"})

    except WebSocketDisconnect:
        manager.disconnect(websocket)

if __name__ == "__main__":
    import uvicorn

    # 启动服务
    host = os.getenv("HOST", "0.0.0.0")
    port = int(os.getenv("PORT", "8000"))

    logger.info(f"启动化工流程模拟智能体服务 - {host}:{port}")
    logger.info(f"使用模型: {MODEL}")
    logger.info(f"ASPEN模拟器地址: {ASPEN_SIMULATOR_URL}")

    uvicorn.run(app, host=host, port=port)