"""AutoGen化工流程模拟后端

使用AutoGen框架构建智能体，通过工具调用处理化工流程模拟请求。
"""

from typing import Dict, Any, List
import os
import io
import sys
import json
import logging
import aiofiles
from datetime import datetime
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from autogen_agentchat.agents import AssistantAgent
from autogen_agentchat.messages import TextMessage
from autogen_core import CancellationToken
from autogen_core.models import ModelFamily
from autogen_ext.models.openai import OpenAIChatCompletionClient
from prompt.llm_prompt import system_prompt
from tools.get_schema import get_schema
from tools.run_simulation import run_simulation
from tools.get_result import get_result

load_dotenv()
# 确保标准输出使用UTF-8编码
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

# 配置
MODEL = os.getenv("MODEL", "deepseek-chat")
MODEL_API_KEY = os.getenv("MODEL_API_KEY")
MODEL_API_URL = os.getenv("MODEL_API_URL")  # 模型API地址
ASPEN_SIMULATOR_URL = os.getenv("ASPEN_SIMULATOR_URL", "http://localhost:8002")

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
        max_tool_iterations=10,
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

@app.post("/chat", response_model=TextMessage)
async def chat(request: ChatRequest) -> TextMessage:
    """处理用户消息"""
    try:
        # 创建模型客户端
        model_client = await creat_model_client()
        # 获取智能体
        agent = await chemical_expert_agent(model_client)

        # 创建用户消息
        user_message = TextMessage(
            content=request.message,
            source="user"
        )

        logger.info(f"处理用户消息: {request.message[:100]}...")

        # 获取响应
        response = await agent.on_messages(
            messages=[user_message],
            cancellation_token=CancellationToken()
        )

        # 保存智能体状态
        state = await agent.save_state()
        async with aiofiles.open(state_path, "w", encoding="utf-8") as f:
            await f.write(json.dumps(state, ensure_ascii=False).encode("utf-8").decode("utf-8"))

        # 保存历史记录
        history = await get_history()
        history.append({
            "role": "user",
            "content": request.message,
            "timestamp": datetime.now().isoformat()
        })

        response_content = response.chat_message.content
        history.append({
            "role": "assistant",
            "content": response_content,
            "timestamp": datetime.now().isoformat()
        })

        # 保持最近100条历史记录
        if len(history) > 100:
            history = history[-100:]

        async with aiofiles.open(history_path, "w", encoding="utf-8") as f:
            await f.write(json.dumps(history, ensure_ascii=False, indent=2).encode("utf-8").decode("utf-8"))

        assert isinstance(response.chat_message, TextMessage)
        return response.chat_message

    except Exception as e:
        logger.exception(f"处理聊天请求时出错: {e}")
        raise HTTPException(status_code=500, detail=f"处理请求时出错: {str(e)}")

if __name__ == "__main__":
    import uvicorn

    # 启动服务
    host = os.getenv("HOST", "0.0.0.0")
    port = int(os.getenv("PORT", "8000"))

    logger.info(f"启动化工流程模拟智能体服务 - {host}:{port}")
    logger.info(f"使用模型: {MODEL}")
    logger.info(f"模拟器地址: {ASPEN_SIMULATOR_URL}")

    uvicorn.run(app, host=host, port=port)