#!/bin/bash
# Aspen 智能体训练启动脚本

set -e

echo "========================================="
echo "Aspen 智能体强化学习训练"
echo "========================================="

# 检查环境
if [ ! -f ".env" ]; then
    echo "错误: 未找到 .env 文件"
    echo "请复制 .env.example 并配置:"
    echo "  cp .env.example .env"
    exit 1
fi

# 加载环境变量
source .env

# 检查依赖
echo "检查依赖..."
python -c "import agentlightning" 2>/dev/null || {
    echo "错误: 未安装 agentlightning"
    echo "请运行: pip install -r requirements.txt"
    exit 1
}

# 创建必要的目录
mkdir -p data models logs

# 解析参数
MODE=${1:-dev}
ALGORITHM=${2:-baseline}
N_RUNNERS=${3:-2}

echo ""
echo "配置:"
echo "  模式: $MODE"
echo "  算法: $ALGORITHM"
echo "  并行数: $N_RUNNERS"
echo ""

# 运行训练
echo "开始训练..."
python src/train.py \
    --mode $MODE \
    --algorithm $ALGORITHM \
    --n-runners $N_RUNNERS \
    --use-validation

echo ""
echo "========================================="
echo "训练完成!"
echo "========================================="
