"""
AutoGen化工流程模拟后端 - 不使用 Agent Lightning (Windows 兼容)

完全不依赖 agentlightning，手动记录轨迹和计算奖励
"""

import asyncio
import json
import logging
import os
import sys
import time
from pathlib import Path
from typing import Any, Dict, Optional, List

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse

# 原有导入
from autogen_agentchat.messages import (
    TextMessage,
    ToolCallExecutionEvent,
    ToolCallRequestEvent,
    ModelClientStreamingChunkEvent,
    ThoughtEvent,
)
from autogen_agentchat.agents import AssistantAgent
from autogen_core import CancellationToken
from autogen_ext.models.openai import OpenAIChatCompletionClient

from prompt.llm_prompt import system_prompt
from tools.get_schema import get_schema
from tools.run_simulation import run_simulation
from tools.get_result import get_result

load_dotenv()

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler('app_no_agl.log', encoding='utf-8')
    ]
)
logger = logging.getLogger(__name__)

# 配置
MODEL = os.getenv("MODEL", "deepseek-chat")
MODEL_API_KEY = os.getenv("MODEL_API_KEY")
MODEL_API_URL = os.getenv("MODEL_API_URL")

# 创建必要的目录
BASE_DIR = Path(__file__).parent
DATA_DIR = BASE_DIR / "rl_data"
DATA_DIR.mkdir(exist_ok=True)

# 初始化 FastAPI
app = FastAPI(title="化工流程模拟智能体 (No Agent Lightning)", version="2.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ============================================================================
# 全局变量
# ============================================================================

logger.warning("=" * 80)
logger.warning("Windows 兼容版本: 不使用 Agent Lightning")
logger.warning("手动记录轨迹和计算奖励")
logger.warning("数据保存在内存和 JSON 文件中")
logger.warning("=" * 80)

# AutoGen 智能体
aspen_agent: Optional[AssistantAgent] = None

# 任务计数器
task_counter = 0

# 轨迹数据存储
trajectories_data: List[Dict[str, Any]] = []

# JSON 文件路径
TRAJECTORIES_FILE = DATA_DIR / "trajectories.json"


def save_trajectories():
    """保存轨迹到 JSON 文件"""
    try:
        with open(TRAJECTORIES_FILE, 'w', encoding='utf-8') as f:
            json.dump(trajectories_data, f, ensure_ascii=False, indent=2)
        logger.info(f"轨迹已保存到 {TRAJECTORIES_FILE}")
    except Exception as e:
        logger.error(f"保存轨迹失败: {e}")


def load_trajectories():
    """从 JSON 文件加载轨迹"""
    global trajectories_data
    try:
        if TRAJECTORIES_FILE.exists():
            with open(TRAJECTORIES_FILE, 'r', encoding='utf-8') as f:
                trajectories_data = json.load(f)
            logger.info(f"已加载 {len(trajectories_data)} 条轨迹")
    except Exception as e:
        logger.error(f"加载轨迹失败: {e}")
        trajectories_data = []


def create_agent() -> AssistantAgent:
    """创建 AutoGen 智能体"""
    model_client = OpenAIChatCompletionClient(
        model=MODEL,
        api_key=MODEL_API_KEY,
        base_url=MODEL_API_URL,
        model_capabilities={
            "vision": False,
            "function_calling": True,
            "json_output": False,
        }
    )
    
    agent = AssistantAgent(
        name="AspenAgent",
        model_client=model_client,
        tools=[get_schema, run_simulation, get_result],
        system_message=system_prompt,
        reflect_on_tool_use=True,
        model_client_stream=True,  # 启用流式输出
        max_tool_iterations=100,  # 允许多轮工具调用，直到任务完成
    )
    
    return agent


def get_aspen_agent() -> AssistantAgent:
    """获取或创建智能体实例"""
    global aspen_agent
    if aspen_agent is None:
        logger.info("初始化 AspenAgent...")
        aspen_agent = create_agent()
        logger.info("AspenAgent 初始化完成")
    return aspen_agent


def calculate_reward(user_message: str, response: str, tool_calls: List[Dict]) -> Dict[str, float]:
    """
    计算任务奖励
    
    Returns:
        包含总奖励和各维度奖励的字典
    """
    # 1. 任务完成度 (40%)
    completion_score = 0.0
    keywords = ["创建", "运行", "模拟", "结果", "成功", "完成"]
    for keyword in keywords:
        if keyword in response:
            completion_score += 0.15
    
    # 检查是否提到文件路径
    if "file" in response.lower() or "路径" in response or ".bkp" in response:
        completion_score += 0.1
    
    # 检查响应长度
    if 50 < len(response) < 500:
        completion_score += 0.1
    
    completion_score = min(completion_score, 1.0)
    
    # 2. 工具使用效率 (30%)
    tool_efficiency = 0.0
    num_tools = len(tool_calls)
    
    if num_tools == 0:
        tool_efficiency = 0.3  # 不需要工具也能回答
    elif num_tools <= 3:
        tool_efficiency = 1.0  # 理想的工具调用次数
    elif num_tools <= 5:
        tool_efficiency = 0.7
    else:
        tool_efficiency = 0.4  # 工具调用过多
    
    # 检查工具调用成功率
    successful_tools = sum(1 for tc in tool_calls if not tc.get("is_error", False))
    if num_tools > 0:
        success_rate = successful_tools / num_tools
        tool_efficiency *= success_rate
    
    # 3. 响应质量 (30%)
    response_quality = 0.0
    
    # 长度合理性
    if 50 <= len(response) <= 500:
        response_quality += 0.4
    elif len(response) < 50:
        response_quality += 0.1
    elif len(response) > 500:
        response_quality += 0.2
    
    # 是否包含错误信息
    error_keywords = ["错误", "失败", "error", "failed", "exception"]
    has_error = any(kw in response.lower() for kw in error_keywords)
    if not has_error:
        response_quality += 0.3
    
    # 是否结构化
    if any(marker in response for marker in ["1.", "2.", "-", "•"]):
        response_quality += 0.3
    
    response_quality = min(response_quality, 1.0)
    
    # 计算总奖励
    total_reward = (
        completion_score * 0.4 +
        tool_efficiency * 0.3 +
        response_quality * 0.3
    )
    
    return {
        "total": total_reward,
        "task_completion": completion_score,
        "tool_efficiency": tool_efficiency,
        "response_quality": response_quality
    }


# ============================================================================
# WebSocket 连接管理
# ============================================================================

class ConnectionManager:
    def __init__(self):
        self.active_connections: list[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)
        logger.info(f"WebSocket 连接建立,当前连接数: {len(self.active_connections)}")

    def disconnect(self, websocket: WebSocket):
        self.active_connections.remove(websocket)
        logger.info(f"WebSocket 连接断开,当前连接数: {len(self.active_connections)}")

    async def send_payload(self, websocket: WebSocket, payload: dict):
        """发送统一格式的 JSON 负载"""
        await websocket.send_text(json.dumps(payload, ensure_ascii=False))


manager = ConnectionManager()


# ============================================================================
# WebSocket 端点
# ============================================================================

@app.websocket("/ws/chat")
async def websocket_chat(websocket: WebSocket):
    """
    WebSocket 聊天端点
    
    功能:
    1. 接收前端用户消息
    2. 执行智能体任务
    3. 自动计算奖励
    4. 记录轨迹数据
    5. 实时推送响应到前端
    """
    await manager.connect(websocket)
    
    # 获取智能体
    agent = get_aspen_agent()
    
    try:
        while True:
            # 1. 接收前端消息
            data = await websocket.receive_text()
            user_input_data = json.loads(data)
            user_message = user_input_data["message"]
            
            logger.info(f"收到用户消息: {user_message[:100]}...")
            
            # 2. 创建任务记录
            global task_counter
            task_counter += 1
            task_id = f"task_{task_counter}"
            
            start_time = time.time()
            trajectory = {
                "task_id": task_id,
                "user_message": user_message,
                "start_time": start_time,
                "spans": [],
                "tool_calls": []
            }
            
            # 发送任务开始信号
            await manager.send_payload(websocket, {
                "type": "task_started",
                "task_id": task_id
            })
            
            # 3. 执行智能体任务(流式输出)
            accumulated_content = ""
            
            try:
                trajectory["spans"].append({
                    "type": "message",
                    "content": f"开始处理任务: {task_id}",
                    "timestamp": time.time()
                })
                
                # 流式执行
                logger.info("开始流式执行智能体任务...")
                chunk_count = 0
                async for chunk in agent.on_messages_stream(
                    [TextMessage(content=user_message, source="user")],
                    CancellationToken()
                ):
                    chunk_count += 1
                    payload = {"role": "assistant", "type": "update"}
                    
                    # 思维链
                    if isinstance(chunk, ThoughtEvent):
                        logger.debug(f"[Chunk {chunk_count}] 思考: {chunk.content[:100]}...")
                        payload.update({"thought": chunk.content})
                        trajectory["spans"].append({
                            "type": "thought",
                            "content": chunk.content,
                            "timestamp": time.time()
                        })
                    
                    # 流式文本
                    elif isinstance(chunk, ModelClientStreamingChunkEvent):
                        accumulated_content += chunk.content
                        logger.debug(f"[Chunk {chunk_count}] 文本片段: {chunk.content[:50]}...")
                    
                    # 工具调用请求
                    elif isinstance(chunk, ToolCallRequestEvent):
                        tool_calls = [
                            {
                                "id": tc.id if hasattr(tc, 'id') else f"call_{idx}",
                                "function_name": tc.name,
                                "args": tc.arguments
                            } for idx, tc in enumerate(chunk.content)
                        ]
                        logger.info(f"[Chunk {chunk_count}] 工具调用请求: {[tc['function_name'] for tc in tool_calls]}")
                        payload.update({
                            "status": "tool_calling",
                            "tool_calls": tool_calls
                        })
                        trajectory["spans"].append({
                            "type": "tool_call_request",
                            "tools": tool_calls,
                            "timestamp": time.time()
                        })
                    
                    # 工具执行结果
                    elif isinstance(chunk, ToolCallExecutionEvent):
                        tool_results = []
                        for res in chunk.content:
                            result_data = {
                                "call_id": res.call_id,
                                "result": res.content,
                                "is_error": False
                            }
                            
                            # 记录工具调用
                            trajectory["tool_calls"].append(result_data)
                            
                            # 提取文件路径
                            try:
                                import ast
                                result_json = ast.literal_eval(res.content)
                                if result_json.get('success'):
                                    file_paths = []
                                    for key in ['aspen_file_path', 'config_file_path', 'result_file_path']:
                                        if key in result_json:
                                            file_paths.append({
                                                "path": result_json[key],
                                                "type": key.split('_')[0]
                                            })
                                    if file_paths:
                                        result_data["file_paths"] = file_paths
                                    logger.info(f"[Chunk {chunk_count}] 工具执行成功: {result_json.get('message', 'N/A')}")
                                else:
                                    logger.warning(f"[Chunk {chunk_count}] 工具执行失败: {result_json.get('message', 'N/A')}")
                            except Exception as e:
                                logger.debug(f"解析工具结果失败: {e}")
                            
                            tool_results.append(result_data)
                        
                        payload.update({
                            "status": "tool_executed",
                            "tool_results": tool_results
                        })
                        trajectory["spans"].append({
                            "type": "tool_execution",
                            "results": tool_results,
                            "timestamp": time.time()
                        })
                    
                    await manager.send_payload(websocket, payload)
                
                logger.info(f"流式执行完成，共处理 {chunk_count} 个事件块")
                
                # 4. 发送完整响应
                if accumulated_content:
                    await manager.send_payload(websocket, {
                        "role": "assistant",
                        "type": "update",
                        "content": accumulated_content
                    })
                    trajectory["spans"].append({
                        "type": "response",
                        "content": accumulated_content,
                        "timestamp": time.time()
                    })
                
                # 5. 计算奖励
                logger.info("计算任务奖励...")
                logger.info(f"任务统计: 工具调用 {len(trajectory['tool_calls'])} 次, "
                          f"响应长度 {len(accumulated_content)} 字符")
                
                rewards = calculate_reward(
                    user_message,
                    accumulated_content,
                    trajectory["tool_calls"]
                )
                
                end_time = time.time()
                trajectory["end_time"] = end_time
                trajectory["duration"] = end_time - start_time
                trajectory["response"] = accumulated_content
                trajectory["reward"] = rewards["total"]
                trajectory["reward_dimensions"] = {
                    "task_completion": rewards["task_completion"],
                    "tool_efficiency": rewards["tool_efficiency"],
                    "response_quality": rewards["response_quality"]
                }
                trajectory["status"] = "succeeded"
                
                # 保存轨迹
                trajectories_data.append(trajectory)
                save_trajectories()
                
                logger.info(f"任务完成 - 奖励: {rewards['total']:.3f}")
                
                # 发送完成信号
                await manager.send_payload(websocket, {
                    "type": "done",
                    "task_id": task_id,
                    "reward": rewards["total"],
                    "reward_dimensions": trajectory["reward_dimensions"],
                    "status": "succeeded"
                })
                
            except Exception as e:
                logger.error(f"任务执行失败: {e}", exc_info=True)
                
                end_time = time.time()
                trajectory["end_time"] = end_time
                trajectory["duration"] = end_time - start_time
                trajectory["error"] = str(e)
                trajectory["reward"] = -1.0
                trajectory["status"] = "failed"
                
                trajectories_data.append(trajectory)
                save_trajectories()
                
                await manager.send_payload(websocket, {
                    "type": "error",
                    "task_id": task_id,
                    "error": str(e),
                    "status": "failed"
                })
    
    except WebSocketDisconnect:
        manager.disconnect(websocket)
        logger.info("WebSocket 连接断开")
    except Exception as e:
        logger.error(f"WebSocket 错误: {e}", exc_info=True)
        manager.disconnect(websocket)


# ============================================================================
# 数据查询 API
# ============================================================================

@app.get("/api/trajectories")
async def get_trajectories(limit: int = 50, offset: int = 0):
    """查询轨迹历史"""
    try:
        total = len(trajectories_data)
        start = min(offset, total)
        end = min(offset + limit, total)
        
        # 返回最新的数据（倒序）
        return {
            "total": total,
            "trajectories": list(reversed(trajectories_data))[start:end]
        }
    except Exception as e:
        logger.error(f"查询轨迹失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/trajectories/{task_id}")
async def get_trajectory(task_id: str):
    """查询特定任务的轨迹"""
    try:
        for traj in trajectories_data:
            if traj["task_id"] == task_id:
                return traj
        
        raise HTTPException(status_code=404, detail="任务不存在")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"查询轨迹失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/statistics")
async def get_statistics():
    """获取统计信息"""
    try:
        total = len(trajectories_data)
        succeeded = sum(1 for t in trajectories_data if t.get("status") == "succeeded")
        failed = sum(1 for t in trajectories_data if t.get("status") == "failed")
        
        rewards = [t["reward"] for t in trajectories_data if "reward" in t and t["reward"] > 0]
        avg_reward = sum(rewards) / len(rewards) if rewards else 0
        max_reward = max(rewards) if rewards else 0
        min_reward = min(rewards) if rewards else 0
        
        return {
            "total_tasks": total,
            "succeeded": succeeded,
            "failed": failed,
            "average_reward": round(avg_reward, 3),
            "max_reward": round(max_reward, 3),
            "min_reward": round(min_reward, 3),
            "storage": "json-file",
            "file_path": str(TRAJECTORIES_FILE)
        }
    except Exception as e:
        logger.error(f"获取统计信息失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# 文件下载
# ============================================================================

@app.get("/download")
async def download_file(file_path: str):
    """下载文件接口"""
    try:
        file_path_obj = Path(file_path)
        
        if not file_path_obj.exists():
            raise HTTPException(status_code=404, detail="文件不存在")
        
        allowed_extensions = {'.bkp', '.apw', '.json', '.xlsx', '.xls', '.txt', '.log', '.out'}
        if file_path_obj.suffix.lower() not in allowed_extensions:
            raise HTTPException(status_code=403, detail="不允许下载此类型文件")
        
        return FileResponse(
            path=file_path_obj,
            filename=file_path_obj.name,
            media_type='application/octet-stream'
        )
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"下载文件失败: {e}")
        raise HTTPException(status_code=500, detail=f"下载文件失败: {str(e)}")


# ============================================================================
# 健康检查
# ============================================================================

@app.get("/health")
async def health_check():
    """健康检查"""
    return {
        "status": "healthy",
        "storage": "json-file",
        "file_path": str(TRAJECTORIES_FILE),
        "agent": "AutoGen AssistantAgent",
        "model": MODEL,
        "total_tasks": len(trajectories_data)
    }


# ============================================================================
# 启动时加载数据
# ============================================================================

@app.on_event("startup")
async def startup_event():
    """启动时加载历史数据"""
    load_trajectories()


if __name__ == "__main__":
    import uvicorn
    
    host = os.getenv("HOST", "0.0.0.0")
    port = int(os.getenv("PORT", "8000"))
    
    logger.info("=" * 80)
    logger.info("启动化工流程模拟智能体服务 (不使用 Agent Lightning)")
    logger.info("=" * 80)
    logger.info(f"服务地址: {host}:{port}")
    logger.info(f"使用模型: {MODEL}")
    logger.info(f"数据存储: JSON 文件 ({TRAJECTORIES_FILE})")
    logger.info(f"WebSocket: ws://{host}:{port}/ws/chat")
    logger.info("=" * 80)
    logger.info("功能: 自动记录轨迹、计算奖励、持久化存储")
    logger.info("=" * 80)
    
    uvicorn.run(app, host=host, port=port)
