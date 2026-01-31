"""AutoGen化工流程模拟后端

使用AutoGen框架构建智能体，通过工具调用处理化工流程模拟请求。
"""

from typing import Dict, Any, List
import os
import io
import sys
import json
import logging
import requests
import aiofiles
from datetime import datetime
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from autogen_agentchat.agents import AssistantAgent
from autogen_agentchat.messages import TextMessage
from autogen_core import CancellationToken
from autogen_core.models import ModelFamily
from autogen_ext.models.openai import OpenAIChatCompletionClient
from prompt.llm_prompt import system_prompt

load_dotenv()
# 确保标准输出使用UTF-8编码
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

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


# schema_check_prompt = f"""
#     1.单元模拟无须配置循环物流，流程模拟必须配置循环物流，循环物料配置说明：block_connections中的循环物流必须包含入口和出口，且出口和入口的物流名称必须一致。比如精馏塔的液相循环到混合器，则精馏塔配置循环物料"EB-REC": "LD(OUT)"，混合器必须有"EB-REC": F(IN)的物料作为入口进行循环，混合器和精馏塔的循环物流名称"EB-REC"必须一致。
#     2.block_connections中使用的连接关系中的端口是否根据如下的枚举和适用描述进行选择
#     {{
#         "F(IN)": "进料 - 适用于几乎所有单元操作（混合器、反应器、塔、换热器等）",
#         "VD(OUT)": "气相产物 - 主要用于带冷凝器的精馏塔，作为最终产品的气相流股",
#         "LD(OUT)": "液相回流产品 - 主要用于带冷凝器的精馏塔，从塔顶冷凝器采出的液相产品，循环物流中常用",
#         "B(OUT)": "塔底产品 - 适用于精馏塔、吸收塔、汽提塔、液液萃取塔等具有塔釜的设备，比如blocks中的Sep2",
#         "P(OUT)": "产品输出 - 通用名称，可用于多种设备（闪蒸罐、反应器、泵等单出口设备）",
#         "V(OUT)": "气相输出 - 适用于闪蒸罐、蒸发器、汽液分离器、带再沸器的塔等",
#         "L(OUT)": "液相输出 - 适用于闪蒸罐、混合器、分离器、换热器、塔等，在精馏塔中特指回流液体",
#         "O(OUT)": "塔顶流出 - 主要用于不带冷凝器的精馏塔或简单塔，指从塔顶出来的总流出物，比如blocks中的Sep2"
#     }}
#     3. block_connections中只包含"P(OUT)"的stream流股，代表该流股为产品输出，在stream_data的配置中，请勿对该流股的配置输入参数。
#     4. blocks_RadFrac_data["CONFIG_DATA"]["CONDENSER"]的值需遵循如下要求：
#     {{
#         "TOTAL": "全凝器，不允许block_connections中类型为RadFrac的block配置的馏出物流股指定相=汽相或全汽相VD(OUT),必须指定液相馏出物流股LD(OUT)",
#         "PARTIAL-V": "部分汽相，不允许block_connections中类型为RadFrac的block配置的馏出物流股指定液相LD(OUT)",
#         "PARTIAL-V-L": "部分汽相-液相,不允许block_connections中类型为RadFrac的block配置的馏出物流股指定相=汽相或全汽相VD(OUT),必须指定液相馏出物流股LD(OUT)",
#         "NONE": "无，不允许流股配置指定液相馏出物流股LD(OUT)"XQ
#     }}
#     5. blocks_RStoic_data中的组分不能既是反应物又是反应的产物，反应物和产物的组分必须在components中包含，
#     6. 确保反应器配置的反应物与产物的总原子数守恒，比如C8H10->C8H8+H2则守恒，如果是C8H10->C8H8+2H2，则不守恒。
#     6. block_connections中的分离器、闪蒸罐、塔等设备如果配置了循环物流。比如VD(OUT)或者LD(OUT)，需检查该物料是否重新进入到其他的设备作为F(IN)进行循环
#     """
# thought_process_prompt = f"""
# 请按照以下步骤思考，并在思考过程中展示你的推理过程：
# 步骤1：分析用户描述的化工流程
# - 识别主要设备单元
# - 理解物料流向
# - 确定关键操作参数
#
# 步骤2：设计流程结构
# - 选择合适的设备类型，如果是Radrac精馏塔任务，需要先生成DSWTU设备配置模拟运行后获取回流比、塔板数初值。
# - 设计合理的连接关系，连接关系必须符合JSON Schema的block_connections的枚举定义，不要编造P1(OUT)等新的端口配置
# - 确定物料平衡
#
# 步骤3：验证配置逻辑，必须符合JSON Schema的格式和检查要求
# - 检查端口连接的正确性，端口关系必须符合JSON Schema的block_connections枚举定义，不要编造P1(OUT)等新的端口配置
# - 验证冷凝器类型与流股的匹配
# - 确保反应器配置合理，需检查并确保配置的反应物与产物的总原子数守恒。
#
# 步骤4：生成最终配置。
# - 严格按照JSON Schema格式
# - 确保所有必填字段完整
# - 验证配置逻辑一致性
# """
#
# system_prompt = f"""角色：你是一个专业的化工流程模拟专家。请根据用户提供的化工流程信息，完成化工流程配置生成和模拟运行任务。
# 1.调用工具获取JSON Schema，并根据获取的JSON Schema生成JSON格式的化工流程配置，生成配置过程遵循如下要求：
# schema检查要求:{schema_check_prompt}。思考流程:{thought_process_prompt}。
# 2.调用aspen simulation工具运行模拟配置，如果模拟结果中的success值为true则代表模拟成功，则将模拟运行结果完整返回，如果模拟失败则重新生成配置并再次调用工具模拟运行，直到模拟成功。
# """

# 配置
MODEL = os.getenv("MODEL", "deepseek-chat")
MODEL_API_KEY = os.getenv("MODEL_API_KEY")
MODEL_API_URL = os.getenv("MODEL_API_URL")  # 模型API地址
ASPEN_SIMULATOR_URL = os.getenv("ASPEN_SIMULATOR_URL", "http://localhost:8002")

BASE_DIR = os.path.dirname(__file__)
SCHEMA_PATH = os.path.join(BASE_DIR, "../aspen/schema/process_schema.json")

# 创建必要的目录
os.makedirs(BASE_DIR, exist_ok=True)

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

# 智能体状态持久化路径
state_path = "agent_state.json"
history_path = "agent_history.json"


class ChatRequest(BaseModel):
    """聊天请求模型"""
    message: str

# 工具1：获取Schema
async def get_schema() -> str:
    """获取化工流程配置的JSON Schema"""
    try:
        if os.path.exists(SCHEMA_PATH):
            async with aiofiles.open(SCHEMA_PATH, "r", encoding="utf-8") as f:
                schema_content = await f.read()
            return schema_content
    except Exception as e:
        logger.error(f"获取Schema时出错: {e}")
        return f"错误: 无法读取Schema - {str(e)}"

# 工具2：运行模拟
async def run_simulation(config: Dict[str, Any]) -> Dict[str, Any]:
    """运行化工流程模拟"""
    try:
        logger.info(f"向模拟器发送请求: {ASPEN_SIMULATOR_URL}")

        # 发送配置到模拟器
        response = requests.post(
            f"{ASPEN_SIMULATOR_URL}/run-aspen-simulation",
            json=config,
            timeout=3000
        )
        return response.json()
        # if response.status_code == 200:
        #     result = response.json()
        #     return {
        #         "success": True,
        #         "result": result,
        #         "message": "模拟完成",
        #         "timestamp": datetime.now().isoformat()
        #     }
        # else:
        #     error_msg = f"模拟器返回错误: {response.status_code} - {response.text}"
        #     logger.error(error_msg)
        #     return {
        #         "success": False,
        #         "error": error_msg,
        #         "timestamp": datetime.now().isoformat()
        #     }
    except requests.exceptions.RequestException as e:
        error_msg = f"连接模拟器失败: {str(e)}"
        logger.error(error_msg)

async def chemical_simulation_expert_agent() -> AssistantAgent:
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
    except Exception as e:
        logger.error(f"创建模型客户端失败: {e}")
        raise HTTPException(status_code=500, detail=f"模型初始化失败: {str(e)}")

    # 创建智能体
    agent = AssistantAgent(
        name="chemical_simulation_expert",
        model_client=model_client,
        system_message=system_prompt,
        tools = [get_schema, run_simulation],
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
        # 获取智能体
        agent = await chemical_simulation_expert_agent()

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