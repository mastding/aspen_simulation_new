# Aspen 智能体 - 强化学习集成版

## 功能特性

✅ **WebSocket 实时通信**: 前端通过 WebSocket 与智能体交互
✅ **轨迹自动记录**: 所有对话和操作自动存储到 SQLite
✅ **奖励自动计算**: 每次任务完成后自动计算多维度奖励
✅ **离线训练支持**: 存储的数据可用于后续离线强化学习训练
✅ **数据查询 API**: 提供 REST API 查询历史轨迹

## 快速开始

### 1. 安装依赖

```bash
# 安装 Agent Lightning
pip install agentlightning

# 安装其他依赖
pip install -r requirements.txt
```

### 2. 配置环境变量

确保 `.env` 文件包含:

```bash
MODEL=deepseek-chat
MODEL_API_KEY=your_api_key_here
MODEL_API_URL=https://api.deepseek.com/v1
ASPEN_SIMULATOR_URL=http://localhost:8002
```

### 3. 启动服务

```bash
python main_with_rl.py
```

服务将在 `http://localhost:8000` 启动

### 4. 前端连接

前端通过 WebSocket 连接:

```javascript
const ws = new WebSocket('ws://localhost:8000/ws/chat');

// 发送消息
ws.send(JSON.stringify({
    message: "创建一个简单的混合器模拟..."
}));

// 接收响应
ws.onmessage = (event) => {
    const data = JSON.parse(event.data);
    console.log(data);
};
```

## 数据存储

### 存储位置

所有轨迹数据存储在:
```
aspen/backend/rl_data/aspen_trajectories.db
```

### 数据结构

每次对话包含:

1. **Rollout**: 任务执行记录
   - rollout_id: 唯一标识
   - status: 状态 (succeeded/failed)
   - input: 用户输入
   - metadata: 元数据

2. **Attempt**: 执行尝试
   - attempt_id: 尝试标识
   - start_time/end_time: 时间戳
   - worker_id: 执行器ID

3. **Spans**: 详细追踪事件
   - 消息 (message)
   - 注释 (annotation)
   - 操作上下文 (operation)
   - **奖励 (reward)** ⭐

### 奖励计算

每次任务自动计算三维度奖励:

```python
总奖励 = 任务完成度 × 0.4 + 工具效率 × 0.3 + 响应质量 × 0.3
```

- **任务完成度**: 检查成功/失败关键词、文件生成、结果数据
- **工具效率**: 评估工具调用顺序和次数
- **响应质量**: 分析长度、结构化程度、关键信息

## 查看数据

### 方法 1: 使用查看工具

```bash
# 查看所有轨迹
python view_trajectories.py

# 导出到 JSON
python view_trajectories.py --export --output my_data.json
```

### 方法 2: 使用 API

```bash
# 查询所有 rollouts
curl http://localhost:8000/api/rollouts

# 查询特定 rollout 的 spans
curl http://localhost:8000/api/rollouts/{rollout_id}/spans

# 获取统计信息
curl http://localhost:8000/api/statistics
```

### 方法 3: 直接查询数据库

```bash
sqlite3 rl_data/aspen_trajectories.db

# 查看表
.tables

# 查询 rollouts
SELECT * FROM rollouts ORDER BY start_time DESC LIMIT 10;

# 查询 spans
SELECT * FROM spans WHERE rollout_id = 'xxx';
```

## API 端点

### WebSocket

- `ws://localhost:8000/ws/chat` - 聊天 WebSocket

### REST API

- `GET /api/rollouts` - 查询 rollouts
  - 参数: `limit`, `offset`
  
- `GET /api/rollouts/{rollout_id}/spans` - 查询 spans

- `GET /api/statistics` - 获取统计信息

- `GET /health` - 健康检查

- `GET /download?file_path=xxx` - 下载文件

## 离线训练

存储的数据可用于离线强化学习训练:

```bash
cd ../reinforcement_learning

# 使用存储的数据训练
python src/train_from_store.py \
    --db-path ../backend/rl_data/aspen_trajectories.db \
    --algorithm baseline
```

## 数据示例

### Rollout 示例

```json
{
  "rollout_id": "rollout_abc123",
  "status": "succeeded",
  "mode": "online",
  "start_time": 1707456789.123,
  "end_time": 1707456820.456,
  "input": {
    "task_id": "online_1",
    "user_requirement": "创建一个简单的混合器模拟...",
    "difficulty": "unknown"
  },
  "metadata": {
    "source": "websocket",
    "user_message": "创建一个简单的混合器模拟...",
    "timestamp": 1707456789.0
  }
}
```

### Span 示例 (奖励)

```json
{
  "span_id": "span_006",
  "name": "reward",
  "start_time": 1707456815.500,
  "end_time": 1707456815.501,
  "attributes": {
    "reward": 0.75,
    "dimensions": {
      "task_completion": 0.8,
      "tool_usage_efficiency": 0.7,
      "response_quality": 0.75
    }
  }
}
```

## 与原版本的区别

| 功能 | 原版本 (main.py) | RL版本 (main_with_rl.py) |
|------|-----------------|-------------------------|
| WebSocket | ✅ | ✅ |
| 流式输出 | ✅ | ✅ |
| 工具调用 | ✅ | ✅ |
| 轨迹记录 | ❌ | ✅ SQLite |
| 奖励计算 | ❌ | ✅ 自动 |
| 数据查询 | ❌ | ✅ REST API |
| 离线训练 | ❌ | ✅ 支持 |

## 故障排查

### 问题 1: 数据库文件不存在

**解决**: 首次运行会自动创建,确保 `rl_data` 目录有写权限

### 问题 2: WebSocket 连接失败

**检查**:
1. 服务是否正常启动
2. 端口是否被占用
3. 防火墙设置

### 问题 3: 奖励值异常

**原因**: 奖励计算基于响应内容,如果响应格式异常可能导致奖励偏低

**解决**: 检查 `AspenLitAgent._calculate_reward()` 逻辑

## 性能优化

1. **数据库优化**: 定期清理旧数据
   ```bash
   sqlite3 rl_data/aspen_trajectories.db "DELETE FROM spans WHERE start_time < xxx"
   ```

2. **并发控制**: 调整 `thread_safe=True` 参数

3. **批量查询**: 使用 `limit` 和 `offset` 分页查询

## 下一步

1. ✅ 实现在线数据收集
2. ✅ 自动奖励计算
3. ✅ SQLite 持久化
4. 🔄 实现从 Store 读取数据的离线训练脚本
5. 🔄 添加人工反馈接口 (RLHF)
6. 🔄 实现在线学习和模型更新

## 许可证

MIT License
