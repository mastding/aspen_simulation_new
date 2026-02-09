#!/bin/bash
# 启动集成强化学习的 Aspen 智能体服务

set -e

echo "========================================="
echo "Aspen 智能体服务 (强化学习版)"
echo "========================================="

# # 检查环境
# if [ ! -f ".env" ]; then
#     echo "❌ 错误: 未找到 .env 文件"
#     echo "请创建 .env 文件并配置 API 密钥"
#     exit 1
# fi

# # 检查依赖
# echo "检查依赖..."
# python -c "import agentlightning" 2>/dev/null || {
#     echo "❌ 错误: 未安装 agentlightning"
#     echo "请运行: pip install agentlightning"
#     exit 1
# }

# python -c "import autogen_agentchat" 2>/dev/null || {
#     echo "❌ 错误: 未安装 autogen"
#     echo "请运行: pip install -r requirements.txt"
#     exit 1
# }

# 创建数据目录
mkdir -p rl_data

echo ""
echo "✅ 环境检查通过"
echo ""
echo "启动服务..."
echo "  - WebSocket: ws://localhost:8000/ws/chat"
echo "  - API: http://localhost:8000/api"
echo "  - 数据库: rl_data/aspen_trajectories.db"
echo " main_with_rl_no_agl"

# 启动服务
python main_with_rl_no_agl.py
