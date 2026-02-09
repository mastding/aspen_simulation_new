"""
Aspen 智能体训练算法

基于 Agent Lightning 的 FastAlgorithm 实现简单的基线算法
"""

import asyncio
import logging
from typing import Any, Dict, List, Optional

from agentlightning import (
    Algorithm,
    FastAlgorithm,
    LightningStore,
    TraceAdapter,
    NamedResources,
    EnqueueRolloutRequest,
)
from agentlightning.types import Dataset

logger = logging.getLogger(__name__)


class AspenBaselineAlgorithm(FastAlgorithm):
    """
    Aspen 智能体基线算法
    
    简单的基线算法,用于:
    1. 从数据集生成任务并入队
    2. 等待任务完成
    3. 收集奖励和轨迹
    4. 分析性能并记录日志
    
    这是一个同步算法,适合快速调试和验证流程
    """
    
    def __init__(
        self,
        max_rollouts_per_task: int = 1,
        log_interval: int = 5,
    ):
        """
        初始化算法
        
        Args:
            max_rollouts_per_task: 每个任务最多执行的次数
            log_interval: 日志记录间隔
        """
        super().__init__()
        self.max_rollouts_per_task = max_rollouts_per_task
        self.log_interval = log_interval
        
        # 统计信息
        self.total_rollouts = 0
        self.successful_rollouts = 0
        self.failed_rollouts = 0
        self.total_reward = 0.0
        self.rewards_history: List[float] = []
    
    def run(
        self,
        train_dataset: Optional[Dataset[Any]] = None,
        val_dataset: Optional[Dataset[Any]] = None,
    ) -> None:
        """
        运行训练算法
        
        Args:
            train_dataset: 训练数据集
            val_dataset: 验证数据集
        """
        logger.info("=" * 80)
        logger.info("开始 Aspen 智能体基线训练")
        logger.info("=" * 80)
        
        if train_dataset is None:
            logger.warning("未提供训练数据集,训练结束")
            return
        
        store = self.get_store()
        
        # 阶段 1: 训练
        logger.info(f"\n{'='*80}")
        logger.info("阶段 1: 训练阶段")
        logger.info(f"{'='*80}")
        self._run_phase(store, train_dataset, mode="train")
        
        # 阶段 2: 验证(如果提供了验证集)
        if val_dataset is not None:
            logger.info(f"\n{'='*80}")
            logger.info("阶段 2: 验证阶段")
            logger.info(f"{'='*80}")
            self._run_phase(store, val_dataset, mode="val")
        
        # 输出最终统计
        self._print_final_statistics()
    
    def _run_phase(
        self,
        store: LightningStore,
        dataset: Dataset[Any],
        mode: str = "train"
    ) -> None:
        """
        运行单个阶段(训练或验证)
        
        Args:
            store: LightningStore 实例
            dataset: 数据集
            mode: 模式 ("train" 或 "val")
        """
        logger.info(f"数据集大小: {len(dataset)}")
        
        # 入队所有任务
        rollout_requests = []
        for idx, task in enumerate(dataset):
            for attempt in range(self.max_rollouts_per_task):
                rollout_requests.append(
                    EnqueueRolloutRequest(
                        input=task,
                        mode=mode,
                        metadata={
                            "task_index": idx,
                            "attempt": attempt,
                            "task_id": getattr(task, "task_id", f"{mode}_{idx}"),
                        }
                    )
                )
        
        logger.info(f"入队 {len(rollout_requests)} 个 rollout 任务")
        
        # 批量入队
        rollouts = asyncio.run(store.enqueue_many_rollouts(rollout_requests))
        rollout_ids = [r.rollout_id for r in rollouts]
        
        logger.info(f"成功入队 {len(rollout_ids)} 个任务,等待执行完成...")
        
        # 等待所有任务完成
        completed_rollouts = asyncio.run(
            store.wait_for_rollouts(rollout_ids=rollout_ids, timeout=3600.0)
        )
        
        logger.info(f"完成 {len(completed_rollouts)} 个任务")
        
        # 分析结果
        self._analyze_results(store, completed_rollouts, mode)
    
    def _analyze_results(
        self,
        store: LightningStore,
        rollouts: List[Any],
        mode: str
    ) -> None:
        """
        分析 rollout 结果
        
        Args:
            store: LightningStore 实例
            rollouts: 完成的 rollout 列表
            mode: 模式标识
        """
        logger.info(f"\n{'='*60}")
        logger.info(f"{mode.upper()} 阶段结果分析")
        logger.info(f"{'='*60}")
        
        for rollout in rollouts:
            self.total_rollouts += 1
            
            # 获取 spans 来提取奖励
            spans = asyncio.run(
                store.query_spans(
                    rollout_id=rollout.rollout_id,
                    attempt_id="latest"
                )
            )
            
            # 提取奖励
            reward = self._extract_reward_from_spans(spans)
            
            if reward is not None:
                self.total_reward += reward
                self.rewards_history.append(reward)
            
            # 统计成功/失败
            if rollout.status == "succeeded":
                self.successful_rollouts += 1
                status_symbol = "✓"
            else:
                self.failed_rollouts += 1
                status_symbol = "✗"
            
            # 定期输出日志
            if self.total_rollouts % self.log_interval == 0:
                avg_reward = (
                    self.total_reward / len(self.rewards_history)
                    if self.rewards_history else 0.0
                )
                logger.info(
                    f"{status_symbol} Rollout {self.total_rollouts}: "
                    f"ID={rollout.rollout_id[:8]}..., "
                    f"Status={rollout.status}, "
                    f"Reward={reward:.3f if reward else 'N/A'}, "
                    f"AvgReward={avg_reward:.3f}"
                )
    
    def _extract_reward_from_spans(self, spans: List[Any]) -> Optional[float]:
        """
        从 spans 中提取奖励值
        
        Args:
            spans: Span 列表
        
        Returns:
            奖励值,如果未找到则返回 None
        """
        for span in spans:
            if span.attributes and "reward" in span.attributes:
                return float(span.attributes["reward"])
        return None
    
    def _print_final_statistics(self) -> None:
        """输出最终统计信息"""
        logger.info(f"\n{'='*80}")
        logger.info("训练完成 - 最终统计")
        logger.info(f"{'='*80}")
        logger.info(f"总 Rollouts: {self.total_rollouts}")
        logger.info(f"成功: {self.successful_rollouts} ({self.successful_rollouts/self.total_rollouts*100:.1f}%)")
        logger.info(f"失败: {self.failed_rollouts} ({self.failed_rollouts/self.total_rollouts*100:.1f}%)")
        
        if self.rewards_history:
            avg_reward = sum(self.rewards_history) / len(self.rewards_history)
            max_reward = max(self.rewards_history)
            min_reward = min(self.rewards_history)
            
            logger.info(f"\n奖励统计:")
            logger.info(f"  平均奖励: {avg_reward:.3f}")
            logger.info(f"  最大奖励: {max_reward:.3f}")
            logger.info(f"  最小奖励: {min_reward:.3f}")
            logger.info(f"  总奖励: {self.total_reward:.3f}")
            
            # 奖励分布
            high_reward = sum(1 for r in self.rewards_history if r > 0.7)
            medium_reward = sum(1 for r in self.rewards_history if 0.3 <= r <= 0.7)
            low_reward = sum(1 for r in self.rewards_history if r < 0.3)
            
            logger.info(f"\n奖励分布:")
            logger.info(f"  高奖励 (>0.7): {high_reward} ({high_reward/len(self.rewards_history)*100:.1f}%)")
            logger.info(f"  中等奖励 (0.3-0.7): {medium_reward} ({medium_reward/len(self.rewards_history)*100:.1f}%)")
            logger.info(f"  低奖励 (<0.3): {low_reward} ({low_reward/len(self.rewards_history)*100:.1f}%)")
        
        logger.info(f"{'='*80}\n")


class AspenPromptOptimizationAlgorithm(Algorithm):
    """
    Aspen 智能体提示优化算法
    
    基于奖励反馈优化系统提示模板
    这是一个异步算法,适合长时间运行的训练
    """
    
    def __init__(
        self,
        optimization_iterations: int = 5,
        rollouts_per_iteration: int = 10,
        top_k_prompts: int = 3,
    ):
        """
        初始化提示优化算法
        
        Args:
            optimization_iterations: 优化迭代次数
            rollouts_per_iteration: 每次迭代的 rollout 数量
            top_k_prompts: 保留的最佳提示数量
        """
        super().__init__()
        self.optimization_iterations = optimization_iterations
        self.rollouts_per_iteration = rollouts_per_iteration
        self.top_k_prompts = top_k_prompts
        
        # 提示模板候选
        self.prompt_candidates: List[Dict[str, Any]] = []
        self.prompt_performance: Dict[str, List[float]] = {}
    
    def is_async(self) -> bool:
        """标记为异步算法"""
        return True
    
    async def run(
        self,
        train_dataset: Optional[Dataset[Any]] = None,
        val_dataset: Optional[Dataset[Any]] = None,
    ) -> None:
        """
        运行提示优化算法
        
        Args:
            train_dataset: 训练数据集
            val_dataset: 验证数据集
        """
        logger.info("=" * 80)
        logger.info("开始 Aspen 智能体提示优化训练")
        logger.info("=" * 80)
        
        if train_dataset is None:
            logger.warning("未提供训练数据集,训练结束")
            return
        
        store = self.get_store()
        
        # 初始化提示候选
        self._initialize_prompt_candidates()
        
        # 迭代优化
        for iteration in range(self.optimization_iterations):
            logger.info(f"\n{'='*80}")
            logger.info(f"优化迭代 {iteration + 1}/{self.optimization_iterations}")
            logger.info(f"{'='*80}")
            
            # 为每个提示候选运行 rollouts
            for prompt_idx, prompt_data in enumerate(self.prompt_candidates):
                logger.info(f"\n测试提示候选 {prompt_idx + 1}/{len(self.prompt_candidates)}")
                
                # 创建资源
                resources = NamedResources(
                    resources_id=f"prompt_iter{iteration}_cand{prompt_idx}",
                    resources={
                        "system_prompt": prompt_data["prompt"]
                    }
                )
                
                # 添加资源到 store
                await store.add_resources(resources)
                
                # 运行 rollouts
                rewards = await self._run_rollouts_with_prompt(
                    store,
                    train_dataset,
                    resources.resources_id,
                    num_rollouts=self.rollouts_per_iteration
                )
                
                # 记录性能
                prompt_id = prompt_data["id"]
                if prompt_id not in self.prompt_performance:
                    self.prompt_performance[prompt_id] = []
                self.prompt_performance[prompt_id].extend(rewards)
                
                avg_reward = sum(rewards) / len(rewards) if rewards else 0.0
                logger.info(f"  平均奖励: {avg_reward:.3f}")
            
            # 选择最佳提示并生成新候选
            self._update_prompt_candidates()
        
        # 输出最终结果
        self._print_optimization_results()
    
    def _initialize_prompt_candidates(self) -> None:
        """初始化提示候选"""
        from prompt.llm_prompt import system_prompt
        
        # 基础提示
        self.prompt_candidates = [
            {
                "id": "base",
                "prompt": system_prompt,
                "description": "原始系统提示"
            }
        ]
        
        # 可以添加更多变体
        # 例如:强调效率、强调准确性、强调详细解释等
        
        logger.info(f"初始化 {len(self.prompt_candidates)} 个提示候选")
    
    async def _run_rollouts_with_prompt(
        self,
        store: LightningStore,
        dataset: Dataset[Any],
        resources_id: str,
        num_rollouts: int
    ) -> List[float]:
        """
        使用特定提示运行 rollouts
        
        Args:
            store: LightningStore 实例
            dataset: 数据集
            resources_id: 资源 ID
            num_rollouts: rollout 数量
        
        Returns:
            奖励列表
        """
        # 随机选择任务
        import random
        tasks = random.sample(list(dataset), min(num_rollouts, len(dataset)))
        
        # 入队任务
        rollout_requests = [
            EnqueueRolloutRequest(
                input=task,
                mode="train",
                resources_id=resources_id,
                metadata={"task_id": getattr(task, "task_id", f"task_{i}")}
            )
            for i, task in enumerate(tasks)
        ]
        
        rollouts = await store.enqueue_many_rollouts(rollout_requests)
        rollout_ids = [r.rollout_id for r in rollouts]
        
        # 等待完成
        completed_rollouts = await store.wait_for_rollouts(
            rollout_ids=rollout_ids,
            timeout=1800.0
        )
        
        # 提取奖励
        rewards = []
        for rollout in completed_rollouts:
            spans = await store.query_spans(
                rollout_id=rollout.rollout_id,
                attempt_id="latest"
            )
            
            for span in spans:
                if span.attributes and "reward" in span.attributes:
                    rewards.append(float(span.attributes["reward"]))
                    break
        
        return rewards
    
    def _update_prompt_candidates(self) -> None:
        """根据性能更新提示候选"""
        # 计算每个提示的平均性能
        prompt_scores = {}
        for prompt_id, rewards in self.prompt_performance.items():
            if rewards:
                prompt_scores[prompt_id] = sum(rewards) / len(rewards)
        
        # 选择 top-k
        top_prompts = sorted(
            prompt_scores.items(),
            key=lambda x: x[1],
            reverse=True
        )[:self.top_k_prompts]
        
        logger.info(f"\nTop {self.top_k_prompts} 提示:")
        for prompt_id, score in top_prompts:
            logger.info(f"  {prompt_id}: {score:.3f}")
        
        # 保留最佳提示
        self.prompt_candidates = [
            p for p in self.prompt_candidates
            if p["id"] in [pid for pid, _ in top_prompts]
        ]
    
    def _print_optimization_results(self) -> None:
        """输出优化结果"""
        logger.info(f"\n{'='*80}")
        logger.info("提示优化完成")
        logger.info(f"{'='*80}")
        
        for prompt_id, rewards in self.prompt_performance.items():
            if rewards:
                avg_reward = sum(rewards) / len(rewards)
                logger.info(f"{prompt_id}: 平均奖励 = {avg_reward:.3f} (n={len(rewards)})")
        
        logger.info(f"{'='*80}\n")
