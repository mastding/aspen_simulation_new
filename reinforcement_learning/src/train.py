"""
Aspen 智能体训练脚本

使用 Agent Lightning 训练 Aspen 流程模拟智能体
"""

import argparse
import logging
import os
import sys
from pathlib import Path
from dotenv import load_dotenv

# 添加路径
sys.path.insert(0, str(Path(__file__).parent))

from aspen_lit_agent import AspenLitAgent
from aspen_dataset import (
    create_training_dataset,
    create_validation_dataset,
    create_test_dataset
)
from aspen_algorithm import AspenBaselineAlgorithm, AspenPromptOptimizationAlgorithm

from agentlightning import Trainer
from agentlightning.tracer import AgentOpsTracer
from agentlightning.store import InMemoryLightningStore

# 加载环境变量
load_dotenv()

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler('training.log', encoding='utf-8')
    ]
)
logger = logging.getLogger(__name__)


def parse_args():
    """解析命令行参数"""
    parser = argparse.ArgumentParser(
        description="训练 Aspen 流程模拟智能体"
    )
    
    # 模型配置
    parser.add_argument(
        "--model",
        type=str,
        default=os.getenv("MODEL", "deepseek-chat"),
        help="使用的模型名称"
    )
    parser.add_argument(
        "--api-key",
        type=str,
        default=os.getenv("MODEL_API_KEY"),
        help="模型 API 密钥"
    )
    parser.add_argument(
        "--api-url",
        type=str,
        default=os.getenv("MODEL_API_URL"),
        help="模型 API 地址"
    )
    parser.add_argument(
        "--temperature",
        type=float,
        default=0.2,
        help="模型温度参数"
    )
    
    # 训练配置
    parser.add_argument(
        "--algorithm",
        type=str,
        choices=["baseline", "prompt_opt"],
        default="baseline",
        help="训练算法: baseline(基线) 或 prompt_opt(提示优化)"
    )
    parser.add_argument(
        "--n-runners",
        type=int,
        default=2,
        help="并行 runner 数量"
    )
    parser.add_argument(
        "--max-rollouts",
        type=int,
        default=None,
        help="每个 runner 最大 rollout 数量"
    )
    parser.add_argument(
        "--mode",
        type=str,
        choices=["dev", "train"],
        default="dev",
        help="运行模式: dev(快速调试) 或 train(完整训练)"
    )
    
    # 数据集配置
    parser.add_argument(
        "--use-validation",
        action="store_true",
        help="是否使用验证集"
    )
    parser.add_argument(
        "--use-test",
        action="store_true",
        help="是否使用测试集"
    )
    
    # 算法特定参数
    parser.add_argument(
        "--max-rollouts-per-task",
        type=int,
        default=1,
        help="每个任务最多执行次数(baseline算法)"
    )
    parser.add_argument(
        "--optimization-iterations",
        type=int,
        default=5,
        help="优化迭代次数(prompt_opt算法)"
    )
    
    return parser.parse_args()


def create_algorithm(args):
    """根据参数创建算法"""
    if args.algorithm == "baseline":
        logger.info("使用基线算法")
        return AspenBaselineAlgorithm(
            max_rollouts_per_task=args.max_rollouts_per_task,
            log_interval=5
        )
    elif args.algorithm == "prompt_opt":
        logger.info("使用提示优化算法")
        return AspenPromptOptimizationAlgorithm(
            optimization_iterations=args.optimization_iterations,
            rollouts_per_iteration=10,
            top_k_prompts=3
        )
    else:
        raise ValueError(f"未知算法: {args.algorithm}")


def main():
    """主函数"""
    args = parse_args()
    
    logger.info("=" * 80)
    logger.info("Aspen 智能体强化学习训练")
    logger.info("=" * 80)
    logger.info(f"模型: {args.model}")
    logger.info(f"算法: {args.algorithm}")
    logger.info(f"模式: {args.mode}")
    logger.info(f"并行 Runners: {args.n_runners}")
    logger.info("=" * 80)
    
    # 创建智能体
    logger.info("\n创建 Aspen 智能体...")
    agent = AspenLitAgent(
        model=args.model,
        api_key=args.api_key,
        api_url=args.api_url,
        temperature=args.temperature,
        max_tool_iterations=100
    )
    
    # 创建数据集
    logger.info("加载数据集...")
    train_dataset = create_training_dataset()
    logger.info(f"训练集大小: {len(train_dataset)}")
    
    val_dataset = None
    if args.use_validation:
        val_dataset = create_validation_dataset()
        logger.info(f"验证集大小: {len(val_dataset)}")
    
    # 创建算法
    algorithm = create_algorithm(args)
    
    # 创建 Tracer
    tracer = AgentOpsTracer(
        agentops_managed=True,
        instrument_managed=True,
        daemon=True
    )
    
    # 创建 Store
    store = InMemoryLightningStore(thread_safe=True)
    
    # 创建 Trainer
    logger.info("\n创建 Trainer...")
    trainer = Trainer(
        algorithm=algorithm,
        store=store,
        tracer=tracer,
        n_runners=args.n_runners,
        max_rollouts=args.max_rollouts,
    )
    
    # 开始训练
    try:
        logger.info("\n" + "=" * 80)
        logger.info("开始训练...")
        logger.info("=" * 80 + "\n")
        
        if args.mode == "dev":
            # 开发模式 - 快速调试
            trainer.dev(agent, train_dataset, val_dataset=val_dataset)
        else:
            # 训练模式 - 完整训练
            trainer.fit(agent, train_dataset, val_dataset=val_dataset)
        
        logger.info("\n" + "=" * 80)
        logger.info("训练完成!")
        logger.info("=" * 80)
        
        # 如果需要,运行测试集
        if args.use_test:
            logger.info("\n运行测试集评估...")
            test_dataset = create_test_dataset()
            logger.info(f"测试集大小: {len(test_dataset)}")
            
            # 使用 dev 模式快速评估
            test_trainer = Trainer(
                algorithm=AspenBaselineAlgorithm(max_rollouts_per_task=1),
                store=store,
                tracer=tracer,
                n_runners=args.n_runners,
            )
            test_trainer.dev(agent, test_dataset)
        
    except KeyboardInterrupt:
        logger.warning("\n训练被用户中断")
    except Exception as e:
        logger.error(f"\n训练过程中出错: {e}", exc_info=True)
        raise
    finally:
        logger.info("\n清理资源...")


if __name__ == "__main__":
    main()
