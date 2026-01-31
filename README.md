一、项目概述
这是一个基于ASPEN智能的化工流程模拟系统，集成了自然语言处理（NLP）技术，实现了从自然语言描述到化工流程模拟的端到端智能化解决方案。

二、核心功能
1. 单元模拟
支持多种化工单元设备（混合器、换热器、反应器、精馏塔等）
自动生成设备配置参数并调用aspen模拟运行

2. 流程模拟
支持化工复杂流程的模拟运行

三、项目结构
aspen_simulation/
├── frontend/
│   ├── index.html                  # 主前端界面
│
├── backend/
│   ├── main-new.py                 # 后端主程序
│   ├── aspen/                      # AI模型存储目录
│   │   ├── aspen2json.py           # ASPEN模拟文件配置提取
│   │   └── aspenagent.py           # ASPEN模拟器服务
│   │   └── process_schema.json     # ASPEN配置JSON Schema
│   ├── simulation_results/         # 模拟结果存储
│   ├── generated_configs/          # 生成的配置存储
│   ├── feedback_records/           # 用户反馈记录
│   └── requirements.txt            # Python依赖列表

四、安装与部署
1.代码拉取
git clone <repository-url>

2.创建虚拟环境
python -m venv venv

3.安装依赖
cd ./backend
pip install -r requirements.txt

4.配置环境变量
.env 文件：
DEEPSEEK_API_KEY=your_api_key_here
ASPEN_SIMULATOR_URL=http://localhost:6000

5.运行后端服务
python main.py
主程序服务将在 https://localhost:8443 启动
python aspenagent.py
ASPEN模拟器服务将在 http://localhost:6000 启动