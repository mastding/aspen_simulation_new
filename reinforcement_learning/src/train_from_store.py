"""
从 Store 读取在线收集的数据进行离线训练

使用方法:
    python train_from_store.py --db-path ../../backend/rl_data/aspen_trajectories.db
"""

import argparse
import asyncio
import logging
import sys
from pathlib import Path
from typing import List, Dict, Any

from agentlightning.store import SQLiteLightningStore
from aspen_lit_agent import AspenTask
from aspen_algorithm import AspenBaselineAlgorithm

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class StoreDataset:
    """从 Store 读取数据的数据集"""
    
    def __init__(self, rollouts: List[Any]):
        self.rollouts = rollouts
        self.tasks = []
        
        # 将 rollouts 转换为 AspenTask
        for rollout in rollouts:
            if isinstance(rollout.input, dict):
                task = AspenTask(
                    task_id=rollout.input.get('task_id', rollout.rollout_id),
                    user_requirement=rollout.input.get('user_requirement', ''),
                    difficulty=rollout.input.get('difficulty', 'unknown')
                )
                self.tasks.append(task)
    
    def __len__(self) -> int:
        return len(self.tasks)
    
    def __getitem__(self, index: int) -> AspenTask:
        return self.tasks[index]


async def load_data_from_store(db_path: str, mode: str = "online") -> StoreDataset:
    """从 Store 加载数据"""
    logger.info(f"从数据库加载数据: {db_path}")
    
    store = SQLiteLightningStore(db_path=db_path, thread_safe=True)
    
    # 查询指定模式的 rollouts
    rollouts = await store.query_rollouts(
        mode_in=[mode] if mode else None,
        limit=-1,
        sort_by="start_time",
        sort_order="asc"
    )
    
    logger.info(f"加载了 {len(rollouts)} 个 rollouts")
    
    # 统计信息
    succeeded = sum(1 for r in rollouts if r.status == "succeeded")
    failed = sum(1 for r in rollouts if r.status == "failed")
    
    logger.info(f"  成功: {succeeded}")
    logger.info(f"  失败: {failed}")
    
    return StoreDataset(rollouts)


async def analyze_rewards(db_path: str):
    """分析存储的奖励数据"""
    logger.info("分析奖励数据...")
    
    store = SQLiteLightningStore(db_path=db_path, thread_safe=True)
    
    rollouts = await store.query_rollouts(limit=-1)
    
    rewards = []
    reward_dimensions = {
        "task_completion": [],
        "tool_usage_efficiency": [],
        "response_quality": []
    }
    
    for rollout in rollouts:
        spans = await store.query_spans(
            rollout_id=rollout.rollout_id,
            attempt_id="latest"
        )
        
        for span in spans:
            if span.attributes and "reward" in span.attributes:
                reward = span.attributes["reward"]
                rewards.append(reward)
                
                dims = span.attributes.get("dimensions", {})
                for key in reward_dimensions:
                    if key in dims:
                        reward_dimensions[key].append(dims[key])
    
    if rewards:
        logger.info(f"\n奖励统计:")
        logger.info(f"  总数: {len(rewards)}")
        logger.info(f"  平均: {sum(rewards) / len(rewards):.3f}")
        logger.info(f"  最大: {max(rewards):.3f}")
        logger.info(f"  最小: {min(rewards):.3f}")
        
        logger.info(f"\n奖励维度:")
        for dim, values in reward_dimensions.items():
            if values:
                logger.info(f"  {dim}:")
                logger.info(f"    平均: {sum(values) / len(values):.3f}")
                logger.info(f"    最大: {max(values):.3f}")
                logger.info(f"    最小: {min(values):.3f}")
    else:
        logger.warning("未找到奖励数据")


def parse_args():
    """解析命令行参数"""
    parser = argparse.ArgumentParser(
        description="从 Store 读取数据进行离线训练"
    )
    
    parser.add_argument(
        "--db-path",
        type=str,
        required=True,
        help="SQLite 数据库路径"
    )
    parser.add_argument(
        "--mode",
        type=str,
        default="online",
        help="数据模式 (online/train/val/test)"
    )
    parser.add_argument(
        "--analyze-only",
        action="store_true",
        help="仅分析数据,不进行训练"
    )
    parser.add_argument(
        "--algorithm",
        type=str,
        choices=["baseline"],
        default="baseline",
        help="训练算法"
    )
    
    return parser.parse_args()


async def main_async():
    """异步主函数"""
    args = parse_args()
    
    # 检查数据库文件
    db_path = Path(args.db_path)
    if not db_path.exists():
        logger.error(f"数据库文件不存在: {db_path}")
        return
    
    logger.info("=" * 80)
    logger.info("从 Store 读取数据进行离线训练")
    logger.info("=" * 80)
    logger.info(f"数据库: {db_path}")
    logger.info(f"模式: {args.mode}")
    logger.info("=" * 80)
    
    # 分析奖励
    await analyze_rewards(str(db_path))
    
    if args.analyze_only:
        logger.info("\n仅分析模式,跳过训练")
        return
    
    # 加载数据
    dataset = await load_data_from_store(str(db_path), args.mode)
    
    if len(dataset) == 0:
        logger.warning("数据集为空,无法训练")
        return
    
    logger.info(f"\n数据集大小: {len(dataset)}")
    
    # 显示示例任务
    logger.info("\n示例任务:")
    for i, task in enumerate(dataset[:3]):
        logger.info(f"  {i+1}. {task.task_id}: {task.user_requirement[:50]}...")
    
    logger.info("\n" + "=" * 80)
    logger.info("注意: 当前脚本仅用于数据分析")
    logger.info("完整的离线训练需要:")
    logger.info("  1. 创建新的 Store 实例")
    logger.info("  2. 将数据重新入队")
    logger.info("  3. 运行训练算法")
    logger.info("=" * 80)
    
    # TODO: 实现完整的离线训练流程
    # 1. 创建新的 Store
    # 2. 将历史数据作为训练集
    # 3. 运行算法进行策略优化


def main():
    """主函数"""
    asyncio.run(main_async())


if __name__ == "__main__":
    main()
