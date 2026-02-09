"""
Aspen 流程模拟智能体 - Agent Lightning 集成

将现有的 Aspen 智能体封装为 LitAgent,支持强化学习训练
"""

import json
import logging
import os
import sys
from typing import Any, Dict, Optional
from pathlib import Path

# Agent Lightning 导入
from agentlightning import (
    LitAgent,
    emit_reward,
    emit_message,
    emit_annotation,
    OperationContext
)
from agentlightning.types import NamedResources, Rollout, RolloutRawResult

# AutoGen 导入
from autogen_agentchat.agents import AssistantAgent
from autogen_ext.models.openai import OpenAIChatCompletionClient
from autogen_core.models import ModelFamily
from autogen_agentchat.messages import TextMessage
from autogen_core import CancellationToken

# 本地工具导入
sys.path.append(str(Path(__file__).parent.parent.parent / "backend"))
from tools.get_schema import get_schema
from tools.run_simulation import run_simulation
from tools.get_result import get_result
from prompt.llm_prompt import system_prompt

logger = logging.getLogger(__name__)


class AspenTask:
    """Aspen 模拟任务定义"""
    
    def __init__(
        self,
        task_id: str,
        user_requirement: str,
        expected_output: Optional[Dict[str, Any]] = None,
        difficulty: str = "medium"
    ):
        self.task_id = task_id
        self.user_requirement = user_requirement
        self.expected_output = expected_output
        self.difficulty = difficulty
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "task_id": self.task_id,
            "user_requirement": self.user_requirement,
            "expected_output": self.expected_output,
            "difficulty": self.difficulty
        }


class AspenLitAgent(LitAgent[AspenTask]):
    """
    Aspen 流程模拟智能体 - 支持强化学习训练
    
    该智能体封装了 AutoGen 的化工专家智能体,并集成了 Agent Lightning
    的追踪和奖励机制,用于强化学习训练。
    """
    
    def __init__(
        self,
        model: str = "deepseek-chat",
        api_key: Optional[str] = None,
        api_url: Optional[str] = None,
        temperature: float = 0.2,
        max_tokens: int = 8192,
        max_tool_iterations: int = 100
    ):
        """
        初始化 Aspen 智能体
        
        Args:
            model: 使用的模型名称
            api_key: API 密钥
            api_url: API 地址
            temperature: 温度参数
            max_tokens: 最大 token 数
            max_tool_iterations: 最大工具调用迭代次数
        """
        super().__init__()
        
        self.model = model
        self.api_key = api_key or os.getenv("MODEL_API_KEY")
        self.api_url = api_url or os.getenv("MODEL_API_URL")
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.max_tool_iterations = max_tool_iterations
        
        # 创建模型客户端
        self.model_client = None
        self.agent = None
        
        logger.info(f"初始化 AspenLitAgent - 模型: {model}")
    
    def _create_model_client(self) -> OpenAIChatCompletionClient:
        """创建模型客户端"""
        return OpenAIChatCompletionClient(
            api_key=self.api_key,
            base_url=self.api_url,
            model=self.model,
            temperature=self.temperature,
            max_tokens=self.max_tokens,
            model_info={
                "vision": False,
                "function_calling": True,
                "json_output": True,
                "family": ModelFamily.UNKNOWN,
                "structured_output": True,
                "multiple_system_messages": False,
            }
        )
    
    def _create_agent(self) -> AssistantAgent:
        """创建 AutoGen 智能体"""
        if self.model_client is None:
            self.model_client = self._create_model_client()
        
        return AssistantAgent(
            name="aspen_expert",
            model_client=self.model_client,
            system_message=system_prompt,
            tools=[get_schema, run_simulation, get_result],
            reflect_on_tool_use=True,
            model_client_stream=False,  # 训练时不使用流式输出
            max_tool_iterations=self.max_tool_iterations,
        )
    
    async def rollout_async(
        self,
        task: AspenTask,
        resources: NamedResources,
        rollout: Rollout
    ) -> RolloutRawResult:
        """
        异步执行单个 Aspen 模拟任务
        
        Args:
            task: Aspen 模拟任务
            resources: 命名资源(可包含提示模板等)
            rollout: Rollout 元数据
        
        Returns:
            最终奖励值(float)
        """
        logger.info(f"开始执行任务: {task.task_id}")
        
        # 发射任务开始消息
        emit_message(f"开始执行 Aspen 模拟任务: {task.task_id}")
        emit_annotation({
            "task_id": task.task_id,
            "difficulty": task.difficulty,
            "requirement": task.user_requirement
        })
        
        try:
            # 创建智能体(如果还未创建)
            if self.agent is None:
                with OperationContext("create_agent", {"model": self.model}):
                    self.agent = self._create_agent()
                    emit_message("智能体创建成功")
            
            # 使用资源中的提示模板(如果有)
            if "system_prompt" in resources:
                self.agent.system_message = resources["system_prompt"]
                emit_message("使用自定义系统提示")
            
            # 执行任务
            with OperationContext("execute_task", task.to_dict()):
                user_message = TextMessage(
                    content=task.user_requirement,
                    source="user"
                )
                
                response = await self.agent.on_messages(
                    messages=[user_message],
                    cancellation_token=CancellationToken()
                )
                
                response_content = response.chat_message.content
                emit_message(f"智能体响应: {response_content[:200]}...")
            
            # 计算奖励
            reward = self._calculate_reward(task, response, response_content)
            
            # 发射奖励
            emit_reward(
                reward=reward,
                dimensions={
                    "task_completion": reward,
                    "tool_usage_efficiency": self._calculate_tool_efficiency(),
                    "response_quality": self._calculate_response_quality(response_content)
                }
            )
            
            logger.info(f"任务完成 - 奖励: {reward}")
            return reward
            
        except Exception as e:
            logger.error(f"任务执行失败: {e}", exc_info=True)
            emit_message(f"任务执行失败: {str(e)}")
            
            # 失败时给予负奖励
            emit_reward(reward=-1.0)
            return -1.0
    
    def _calculate_reward(
        self,
        task: AspenTask,
        response: Any,
        response_content: str
    ) -> float:
        """
        计算任务奖励
        
        奖励组成:
        1. 任务完成度 (0-0.4)
        2. 工具使用效率 (0-0.3)
        3. 响应质量 (0-0.3)
        
        Args:
            task: 任务对象
            response: 智能体响应
            response_content: 响应内容
        
        Returns:
            总奖励值 (0-1.0)
        """
        reward = 0.0
        
        # 1. 任务完成度
        completion_reward = self._calculate_completion_reward(task, response_content)
        reward += completion_reward * 0.4
        
        # 2. 工具使用效率
        efficiency_reward = self._calculate_tool_efficiency()
        reward += efficiency_reward * 0.3
        
        # 3. 响应质量
        quality_reward = self._calculate_response_quality(response_content)
        reward += quality_reward * 0.3
        
        return reward
    
    def _calculate_completion_reward(
        self,
        task: AspenTask,
        response_content: str
    ) -> float:
        """
        计算任务完成度奖励
        
        检查:
        - 是否成功生成配置文件
        - 是否成功运行模拟
        - 是否成功获取结果
        """
        reward = 0.0
        
        # 检查关键词
        success_keywords = [
            "成功",
            "完成",
            "模拟结果",
            "配置文件",
            "result",
            "success"
        ]
        
        failure_keywords = [
            "失败",
            "错误",
            "异常",
            "error",
            "failed",
            "exception"
        ]
        
        # 基础完成度
        if any(keyword in response_content.lower() for keyword in success_keywords):
            reward += 0.5
        
        # 检查是否包含失败信息
        if any(keyword in response_content.lower() for keyword in failure_keywords):
            reward -= 0.3
        
        # 检查是否包含文件路径(说明生成了文件)
        if "file_path" in response_content.lower() or ".bkp" in response_content:
            reward += 0.3
        
        # 检查是否包含结果数据
        if "result" in response_content.lower() and "data" in response_content.lower():
            reward += 0.2
        
        return max(0.0, min(1.0, reward))
    
    def _calculate_tool_efficiency(self) -> float:
        """
        计算工具使用效率
        
        考虑:
        - 工具调用次数
        - 工具调用顺序的合理性
        """
        # 这里简化处理,实际可以通过追踪工具调用历史来计算
        # 可以从 self.agent 的内部状态获取工具调用信息
        
        # 理想的工具调用顺序: get_schema -> run_simulation -> get_result
        # 调用次数越少越好(但至少要调用必要的工具)
        
        return 0.8  # 默认值,可以根据实际情况优化
    
    def _calculate_response_quality(self, response_content: str) -> float:
        """
        计算响应质量
        
        考虑:
        - 响应长度是否合理
        - 是否包含关键信息
        - 是否结构化
        """
        reward = 0.0
        
        # 长度合理性
        length = len(response_content)
        if 100 < length < 5000:
            reward += 0.3
        elif length >= 5000:
            reward += 0.2
        else:
            reward += 0.1
        
        # 结构化程度
        if "{" in response_content and "}" in response_content:
            reward += 0.2
        
        # 包含关键信息
        key_info = ["配置", "模拟", "结果", "参数", "config", "simulation", "result"]
        matched = sum(1 for info in key_info if info in response_content.lower())
        reward += min(0.5, matched * 0.1)
        
        return min(1.0, reward)


# 便捷函数
def create_aspen_agent(**kwargs) -> AspenLitAgent:
    """创建 Aspen 智能体的便捷函数"""
    return AspenLitAgent(**kwargs)
