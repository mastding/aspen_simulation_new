# Aspen 智能体强化学习训练

基于 Agent Lightning 框架的 Aspen 流程模拟智能体强化学习训练实现。

## 项目结构

```
reinforcement_learning/
├── src/
│   ├── aspen_lit_agent.py      # LitAgent 封装
│   ├── aspen_dataset.py         # 训练数据集
│   ├── aspen_algorithm.py       # 训练算法
│   └── train.py                 # 训练脚本
├── configs/                     # 配置文件
├── data/                        # 数据目录
├── models/                      # 模型保存目录
└── README.md                    # 本文件
```

## 快速开始

### 1. 环境准备

确保已安装 Agent Lightning 和相关依赖:

```bash
# 安装 Agent Lightning
pip install agentlightning

# 安装 Aspen 项目依赖
cd aspen/backend
pip install -r requirements.txt
```

### 2. 配置环境变量

创建 `.env` 文件:

```bash
MODEL=deepseek-chat
MODEL_API_KEY=your_api_key_here
MODEL_API_URL=https://api.deepseek.com/v1
ASPEN_SIMULATOR_URL=http://localhost:8002
```

### 3. 运行训练

#### 开发模式(快速调试)

```bash
python src/train.py --mode dev --n-runners 2
```

#### 完整训练模式

```bash
python src/train.py --mode train --algorithm baseline --n-runners 4
```

## 核心组件说明

### AspenLitAgent

封装了 AutoGen 化工专家智能体,集成 Agent Lightning 的追踪和奖励机制。

**主要功能:**
- 异步执行 Aspen 模拟任务
- 自动计算多维度奖励
- 发射追踪事件和注释

### 奖励计算

奖励由三部分组成:
1. **任务完成度** (40%): 是否成功生成配置、运行模拟、获取结果
2. **工具使用效率** (30%): 工具调用次数和顺序的合理性
3. **响应质量** (30%): 响应长度、结构化程度、关键信息完整性

### 训练算法

#### 1. 基线算法 (AspenBaselineAlgorithm)

简单的同步算法,用于快速验证流程:
- 批量入队所有任务
- 等待执行完成
- 收集和分析奖励

#### 2. 提示优化算法 (AspenPromptOptimizationAlgorithm)

异步算法,通过迭代优化系统提示:
- 维护多个提示候选
- 评估每个提示的性能
- 选择最佳提示并生成新变体

## 命令行参数

```bash
python src/train.py --help
```

主要参数:
- `--model`: 模型名称
- `--algorithm`: 训练算法 (baseline/prompt_opt)
- `--n-runners`: 并行 runner 数量
- `--mode`: 运行模式 (dev/train)
- `--use-validation`: 是否使用验证集
- `--use-test`: 是否使用测试集
```


## 数据集说明

### 训练集 (10个任务)
- 简单任务 (3个): 单个设备模拟
- 中等任务 (4个): 多设备串联流程
- 困难任务 (3个): 复杂流程和优化

### 验证集 (5个任务)
用于评估模型泛化能力

### 测试集 (3个任务)
最终评估,包含最复杂的工业流程

## 训练流程

1. **初始化阶段**
   - 创建 AspenLitAgent
   - 加载数据集
   - 初始化 Tracer 和 Store

2. **训练阶段**
   - 算法从数据集生成任务
   - Runner 执行任务并发射 spans
   - Store 收集和同步数据
   - 算法分析奖励并更新策略

3. **验证阶段** (可选)
   - 在验证集上评估性能
   - 不更新模型参数

4. **测试阶段** (可选)
   - 最终性能评估

## 监控和日志

训练过程会生成详细日志:
- 控制台输出: 实时进度
- `training.log`: 完整训练日志
- Agent Lightning Store: 所有 spans 和奖励

## 扩展和定制

### 添加新任务

编辑 `src/aspen_dataset.py`:

```python
AspenTask(
    task_id="custom_001",
    user_requirement="你的任务描述",
    difficulty="medium"
)
```

### 自定义奖励函数

修改 `AspenLitAgent._calculate_reward()` 方法

### 实现新算法

继承 `Algorithm` 或 `FastAlgorithm` 类

## 故障排查

### 常见问题

1. **连接 Aspen 模拟器失败**
   - 检查 `ASPEN_SIMULATOR_URL` 配置
   - 确保模拟器服务正在运行

2. **API 调用失败**
   - 验证 `MODEL_API_KEY` 和 `MODEL_API_URL`
   - 检查网络连接

3. **内存不足**
   - 减少 `--n-runners` 数量
   - 使用更小的数据集

## 性能优化建议

1. **并行度调整**: 根据机器性能调整 `n_runners`
2. **批处理**: 使用 `enqueue_many_rollouts` 批量入队
3. **异步执行**: 使用异步算法提高效率
4. **资源管理**: 及时清理完成的 rollouts

## 参考资料

- [Agent Lightning 文档](https://microsoft.github.io/agent-lightning/)
- [AutoGen 文档](https://microsoft.github.io/autogen/)
- [Aspen Plus 文档](https://www.aspentech.com/)

## 许可证

MIT License
