"""
AutoGen化工流程模拟后端 - 集成强化学习

使用 Agent Lightning 记录所有交互轨迹,支持离线训练
"""

import asyncio
import ast
import json
import logging
import os
import sys
from pathlib import Path
from typing import Any, Dict, Optional

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse

# Agent Lightning 导入
from agentlightning import (
    emit_reward,
    emit_message,
    emit_annotation,
)
from agentlightning.emitter.annotation import OperationContext
from agentlightning.store import InMemoryLightningStore
from agentlightning.tracer import AgentOpsTracer
from agentlightning.types import NamedResources

# 添加强化学习模块路径
rl_path = Path(__file__).parent.parent / "reinforcement_learning" / "src"
sys.path.insert(0, str(rl_path))

from reinforcement_learning.src.aspen_lit_agent import AspenTask, AspenLitAgent

# 原有导入
from autogen_agentchat.messages import (
    TextMessage,
    ToolCallExecutionEvent,
    ToolCallRequestEvent,
    ModelClientStreamingChunkEvent,
    ThoughtEvent,
)
from autogen_core import CancellationToken
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
        logging.FileHandler('app_with_rl.log', encoding='utf-8')
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
app = FastAPI(title="化工流程模拟智能体 (with RL)", version="2.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ============================================================================
# 全局变量: Agent Lightning 组件
# ============================================================================

# Store - 存储所有轨迹数据
# 注意: SQLiteLightningStore 尚未在 agentlightning 中实现，使用 InMemoryLightningStore
logger.info("使用内存存储 (InMemoryLightningStore)")
logger.warning("注意: 数据不会持久化到磁盘，重启后会丢失")
store = InMemoryLightningStore(thread_safe=True)

# Tracer - 追踪执行过程
tracer = AgentOpsTracer(
    agentops_managed=True,
    instrument_managed=True,
    daemon=True
)

# AspenLitAgent - 强化学习智能体
aspen_agent: Optional[AspenLitAgent] = None

# 任务计数器
task_counter = 0


def get_aspen_agent() -> AspenLitAgent:
    """获取或创建 AspenLitAgent 实例"""
    global aspen_agent
    if aspen_agent is None:
        logger.info("初始化 AspenLitAgent...")
        aspen_agent = AspenLitAgent(
            model=MODEL,
            api_key=MODEL_API_KEY,
            api_url=MODEL_API_URL,
            temperature=0.2,
            max_tool_iterations=100
        )
        logger.info("AspenLitAgent 初始化完成")
    return aspen_agent


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
# WebSocket 端点 - 集成强化学习
# ============================================================================

@app.websocket("/ws/chat")
async def websocket_chat_with_rl(websocket: WebSocket):
    """
    WebSocket 聊天端点 - 集成强化学习轨迹记录

    功能:
    1. 接收前端用户消息
    2. 创建 Rollout 并记录到 Store
    3. 执行 AspenLitAgent 任务
    4. 自动计算奖励
    5. 存储所有 spans 到 SQLite
    6. 实时推送响应到前端
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

            # 2. 创建任务
            global task_counter
            task_counter += 1
            task = AspenTask(
                task_id=f"online_{task_counter}",
                user_requirement=user_message,
                difficulty="unknown"  # 在线任务难度未知
            )

            # 3. 创建 Rollout 并记录到 Store
            logger.info(f"创建 Rollout: {task.task_id}")
            rollout = await store.start_rollout(
                input=task.to_dict(),
                mode="online",  # 标记为在线模式
                resources_id=None,
                metadata={
                    "source": "websocket",
                    "user_message": user_message,
                    "timestamp": asyncio.get_event_loop().time()
                }
            )

            # 发送 rollout 信息到前端
            await manager.send_payload(websocket, {
                "type": "rollout_started",
                "rollout_id": rollout.rollout_id,
                "attempt_id": rollout.attempt.attempt_id,
                "task_id": task.task_id
            })

            # 4. 使用 Tracer 上下文执行任务
            with tracer.trace(
                    name=f"online_task_{task.task_id}",
                    rollout_id=rollout.rollout_id,
                    attempt_id=rollout.attempt.attempt_id
            ):
                # 发射任务开始事件
                emit_message(f"开始处理在线任务: {task.task_id}")
                emit_annotation({
                    "task_id": task.task_id,
                    "user_message": user_message,
                    "mode": "online"
                })

                # 5. 执行智能体任务(流式输出)
                accumulated_content = ""

                try:
                    # 获取 AutoGen agent
                    if agent.agent is None:
                        with OperationContext("create_agent", {"model": MODEL}):
                            agent.agent = agent._create_agent()
                            emit_message("智能体创建成功")

                    # 流式执行
                    async for chunk in agent.agent.on_messages_stream(
                            [TextMessage(content=user_message, source="user")],
                            CancellationToken()
                    ):
                        payload = {"role": "assistant", "type": "update"}

                        # 思维链
                        if isinstance(chunk, ThoughtEvent):
                            payload.update({"thought": chunk.content})
                            emit_message(f"思考: {chunk.content}")

                        # 流式文本
                        elif isinstance(chunk, ModelClientStreamingChunkEvent):
                            accumulated_content += chunk.content

                        # 工具调用请求
                        elif isinstance(chunk, ToolCallRequestEvent):
                            tool_calls = [
                                {
                                    "id": tc.id if hasattr(tc, 'id') else f"call_{idx}",
                                    "function_name": tc.name,
                                    "args": tc.arguments
                                } for idx, tc in enumerate(chunk.content)
                            ]
                            payload.update({
                                "status": "tool_calling",
                                "tool_calls": tool_calls
                            })
                            emit_annotation({
                                "event": "tool_call_request",
                                "tools": tool_calls
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

                                # 提取文件路径
                                try:
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
                                except Exception:
                                    pass

                                tool_results.append(result_data)

                            payload.update({
                                "status": "tool_executed",
                                "tool_results": tool_results
                            })
                            emit_annotation({
                                "event": "tool_execution",
                                "results": tool_results
                            })

                        await manager.send_payload(websocket, payload)

                    # 6. 发送完整响应
                    if accumulated_content:
                        await manager.send_payload(websocket, {
                            "role": "assistant",
                            "type": "update",
                            "content": accumulated_content
                        })
                        emit_message(f"智能体响应: {accumulated_content[:200]}...")

                    # 7. 计算奖励
                    logger.info("计算任务奖励...")
                    reward = agent._calculate_reward(
                        task,
                        None,  # response object
                        accumulated_content
                    )

                    # 发射奖励
                    emit_reward(
                        reward=reward,
                        dimensions={
                            "task_completion": agent._calculate_completion_reward(task, accumulated_content),
                            "tool_efficiency": agent._calculate_tool_efficiency(),
                            "response_quality": agent._calculate_response_quality(accumulated_content)
                        }
                    )

                    logger.info(f"任务完成 - 奖励: {reward:.3f}")

                    # 8. 更新 Rollout 状态
                    await store.update_rollout_status(
                        rollout_id=rollout.rollout_id,
                        status="succeeded"
                    )

                    # 发送完成信号
                    await manager.send_payload(websocket, {
                        "type": "done",
                        "rollout_id": rollout.rollout_id,
                        "reward": reward,
                        "status": "succeeded"
                    })

                except Exception as e:
                    logger.error(f"任务执行失败: {e}", exc_info=True)
                    emit_message(f"任务执行失败: {str(e)}")
                    emit_reward(reward=-1.0)

                    await store.update_rollout_status(
                        rollout_id=rollout.rollout_id,
                        status="failed"
                    )

                    await manager.send_payload(websocket, {
                        "type": "error",
                        "rollout_id": rollout.rollout_id,
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

@app.get("/api/rollouts")
async def get_rollouts(limit: int = 50, offset: int = 0):
    """查询 Rollout 历史"""
    try:
        rollouts = await store.query_rollouts(
            limit=limit,
            offset=offset,
            sort_by="start_time",
            sort_order="desc"
        )

        return {
            "total": len(rollouts),
            "rollouts": [
                {
                    "rollout_id": r.rollout_id,
                    "status": r.status,
                    "mode": r.mode,
                    "start_time": r.start_time,
                    "end_time": r.end_time,
                    "input": r.input,
                    "metadata": r.metadata
                }
                for r in rollouts
            ]
        }
    except Exception as e:
        logger.error(f"查询 rollouts 失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/rollouts/{rollout_id}/spans")
async def get_rollout_spans(rollout_id: str):
    """查询特定 Rollout 的所有 Spans"""
    try:
        spans = await store.query_spans(
            rollout_id=rollout_id,
            attempt_id="latest"
        )

        return {
            "rollout_id": rollout_id,
            "total_spans": len(spans),
            "spans": [
                {
                    "span_id": s.span_id,
                    "name": s.name,
                    "start_time": s.start_time,
                    "end_time": s.end_time,
                    "attributes": s.attributes
                }
                for s in spans
            ]
        }
    except Exception as e:
        logger.error(f"查询 spans 失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/statistics")
async def get_statistics():
    """获取统计信息"""
    try:
        stats = await store.statistics()
        return stats
    except Exception as e:
        logger.error(f"获取统计信息失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# 文件下载 (保留原有功能)
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
        "store": "SQLiteLightningStore",
        "db_path": str(DATA_DIR / "aspen_trajectories.db"),
        "agent": "AspenLitAgent",
        "model": MODEL
    }


if __name__ == "__main__":
    import uvicorn

    host = os.getenv("HOST", "0.0.0.0")
    port = int(os.getenv("PORT", "8000"))

    logger.info("=" * 80)
    logger.info("启动化工流程模拟智能体服务 (集成强化学习)")
    logger.info("=" * 80)
    logger.info(f"服务地址: {host}:{port}")
    logger.info(f"使用模型: {MODEL}")
    logger.info(f"数据存储: {DATA_DIR / 'aspen_trajectories.db'}")
    logger.info(f"WebSocket: ws://{host}:{port}/ws/chat")
    logger.info("=" * 80)

    uvicorn.run(app, host=host, port=port)
