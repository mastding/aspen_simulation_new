# Aspen 智能体强化学习实现指南

## 概述

本文档详细说明如何使用 Agent Lightning 框架训练 Aspen 流程模拟智能体。

## 架构设计

### 1. 核心组件关系

```
┌─────────────────────────────────────────────────────────┐
│                    Trainer (训练编排)                    │
├─────────────────────────────────────────────────────────┤
│                                                         │
│  ┌──────────────┐      ┌──────────────┐               │
│  │  Algorithm   │◄────►│    Store     │               │
│  │  (训练算法)   │      │  (数据同步)   │               │
│  └──────────────┘      └──────────────┘               │
│         │                      ▲                       │
│         │                      │                       │
│         ▼                      │                       │
│  ┌──────────────┐      ┌──────────────┐               │
│  │   Dataset    │      │    Spans     │               │
│  │  (任务数据)   │      │  (追踪数据)   │               │
│  └──────────────┘      └──────────────┘               │
│                               ▲                        │
│                               │                        │
│         ┌─────────────────────┘                        │
│         │                                              │
│  ┌──────────────┐      ┌──────────────┐               │
│  │   Runner     │◄────►│   Tracer     │               │
│  │  (执行器)     │      │  (追踪器)     │               │
│  └──────────────┘      └──────────────┘               │
│         │                                              │
│         ▼                                              │
│  ┌──────────────┐                                      │
│  │  LitAgent    │                                      │
│  │ (Aspen智能体) │                                      │
│  └──────────────┘                                      │
│         │                                              │
│         ▼                                              │
│  ┌──────────────┐                                      │
│  │ AutoGen Agent│                                      │
│  │ (化工专家)    │                                      │
│  └──────────────┘                                      │
└─────────────────────────────────────────────────────────┘
```

### 2. 数据流

```
1. Algorithm 从 Dataset 读取任务
   ↓
2. Algorithm 将任务入队到 Store
   ↓
3. Runner 从 Store 获取任务
   ↓
4. Runner 调用 LitAgent.rollout_async()
   ↓
5. LitAgent 执行任务并发射 spans
   ↓
6. Tracer 捕获 spans 并发送到 Store
   ↓
7. Store 持久化 spans 和奖励
   ↓
8. Algorithm 从 Store 读取结果
   ↓
9. Algorithm 分析并更新策略
```

## 实现细节

### AspenLitAgent 实现

```python
class AspenLitAgent(LitAgent[AspenTask]):
    """
    关键方法:
    1. rollout_async(): 异步执行任务
    2. _calculate_reward(): 计算多维度奖励
    3. _create_agent(): 创建 AutoGen 智能体
    """
```

**奖励计算逻辑:**

```python
总奖励 = 任务完成度 × 0.4 + 工具效率 × 0.3 + 响应质量 × 0.3

任务完成度:
- 包含成功关键词: +0.5
- 包含失败关键词: -0.3
- 包含文件路径: +0.3
- 包含结果数据: +0.2

工具效率:
- 理想调用顺序: get_schema → run_simulation → get_result
- 调用次数越少越好

响应质量:
- 长度合理 (100-5000字符): +0.3
- 结构化 (包含JSON): +0.2
- 包含关键信息: +0.5
```

### 训练算法实现

#### 基线算法 (同步)

```python
class AspenBaselineAlgorithm(FastAlgorithm):
    def run(self, train_dataset, val_dataset):
        # 1. 批量入队所有任务
        rollouts = store.enqueue_many_rollouts(requests)
        
        # 2. 等待完成
        completed = store.wait_for_rollouts(rollout_ids)
        
        # 3. 分析结果
        self._analyze_results(completed)
```

#### 提示优化算法 (异步)

```python
class AspenPromptOptimizationAlgorithm(Algorithm):
    async def run(self, train_dataset, val_dataset):
        for iteration in range(self.iterations):
            # 1. 测试每个提示候选
            for prompt in self.candidates:
                rewards = await self._run_with_prompt(prompt)
                self.performance[prompt.id] = rewards
            
            # 2. 选择最佳提示
            self._update_candidates()
```

## 使用示例

### 示例 1: 快速开发调试

```bash
# 使用 dev 模式快速验证流程
python src/train.py \
    --mode dev \
    --algorithm baseline \
    --n-runners 1 \
    --max-rollouts-per-task 1
```

**预期输出:**
```
================================================================================
Aspen 智能体强化学习训练
================================================================================
模型: deepseek-chat
算法: baseline
模式: dev
并行 Runners: 1
================================================================================

创建 Aspen 智能体...
加载数据集...
训练集大小: 10

================================================================================
开始训练...
================================================================================

阶段 1: 训练阶段
数据集大小: 10
入队 10 个 rollout 任务
成功入队 10 个任务,等待执行完成...
✓ Rollout 5: ID=abc12345..., Status=succeeded, Reward=0.750, AvgReward=0.680
完成 10 个任务

训练完成 - 最终统计
总 Rollouts: 10
成功: 8 (80.0%)
失败: 2 (20.0%)

奖励统计:
  平均奖励: 0.680
  最大奖励: 0.850
  最小奖励: 0.320
```

### 示例 2: 完整训练

```bash
# 使用多个 runner 并行训练
python src/train.py \
    --mode train \
    --algorithm baseline \
    --n-runners 4 \
    --use-validation \
    --max-rollouts-per-task 3
```

### 示例 3: 提示优化

```bash
# 使用提示优化算法
python src/train.py \
    --mode train \
    --algorithm prompt_opt \
    --n-runners 2 \
    --optimization-iterations 10 \
    --use-validation
```

## 性能调优

### 1. 并行度优化

```python
# CPU 密集型任务
n_runners = cpu_count() - 1

# IO 密集型任务 (API 调用)
n_runners = cpu_count() * 2

# 内存受限
n_runners = min(4, available_memory_gb // 2)
```

### 2. 批处理优化

```python
# 批量入队减少网络开销
batch_size = 50
for i in range(0, len(tasks), batch_size):
    batch = tasks[i:i+batch_size]
    await store.enqueue_many_rollouts(batch)
```

### 3. 超时设置

```python
# 根据任务复杂度设置超时
RolloutConfig(
    timeout_seconds=1800,  # 30分钟
    max_attempts=3,        # 最多重试3次
    retry_condition=["failed", "timeout"]
)
```

## 监控和调试

### 1. 日志级别

```python
# 开发阶段: DEBUG
logging.basicConfig(level=logging.DEBUG)

# 生产环境: INFO
logging.basicConfig(level=logging.INFO)
```

### 2. Store 统计

```python
# 查看 Store 统计信息
stats = await store.statistics()
print(f"Total rollouts: {stats['total_rollouts']}")
print(f"Total spans: {stats['total_spans']}")
```

### 3. 追踪分析

```python
# 查询特定 rollout 的 spans
spans = await store.query_spans(
    rollout_id=rollout_id,
    attempt_id="latest"
)

# 分析工具调用
for span in spans:
    if "tool_call" in span.name:
        print(f"Tool: {span.attributes.get('tool_name')}")
```

## 常见问题

### Q1: 如何添加自定义奖励维度?

```python
# 在 AspenLitAgent._calculate_reward() 中添加
emit_reward(
    reward=total_reward,
    dimensions={
        "task_completion": completion_reward,
        "tool_efficiency": efficiency_reward,
        "response_quality": quality_reward,
        "custom_metric": custom_reward  # 新增
    }
)
```

### Q2: 如何保存和加载训练状态?

```python
# 保存
state = await agent.save_state()
with open("agent_state.json", "w") as f:
    json.dump(state, f)

# 加载
with open("agent_state.json", "r") as f:
    state = json.load(f)
await agent.load_state(state)
```

### Q3: 如何使用不同的 Store 后端?

```python
# MongoDB
from agentlightning.store import MongoLightningStore
store = MongoLightningStore(
    connection_string="mongodb://localhost:27017",
    database_name="aspen_training"
)

# SQLite
from agentlightning.store import SQLiteLightningStore
store = SQLiteLightningStore(
    db_path="aspen_training.db"
)
```

## 下一步

1. **扩展数据集**: 添加更多真实的工业流程任务
2. **优化奖励函数**: 根据实际需求调整奖励权重
3. **实现高级算法**: 如 PPO、DPO 等
4. **集成评估指标**: 添加更多性能指标
5. **部署生产环境**: 使用分布式 Store 和 Runner

## 参考资源

- [Agent Lightning 官方文档](https://microsoft.github.io/agent-lightning/)
- [AutoGen 教程](https://microsoft.github.io/autogen/)
- [强化学习基础](https://spinningup.openai.com/)
