"""
Aspen 模拟任务数据集

定义训练和验证数据集
"""

from typing import List, Dict, Any
from aspen_lit_agent import AspenTask


class AspenDataset:
    """Aspen 模拟任务数据集"""
    
    def __init__(self, tasks: List[AspenTask]):
        self.tasks = tasks
    
    def __len__(self) -> int:
        return len(self.tasks)
    
    def __getitem__(self, index: int) -> AspenTask:
        return self.tasks[index]


def create_training_dataset() -> AspenDataset:
    """
    创建训练数据集
    
    包含不同难度和类型的 Aspen 模拟任务
    """
    tasks = [
        # 简单任务 - 单个设备
        AspenTask(
            task_id="train_001",
            user_requirement="创建一个简单的混合器模拟,混合两股物流,一股是水,流量100 kmol/hr,温度25°C,压力1 bar;另一股是乙醇,流量50 kmol/hr,温度30°C,压力1 bar。",
            difficulty="easy"
        ),
        
        AspenTask(
            task_id="train_002",
            user_requirement="设计一个加热器,将进料流股从25°C加热到100°C,进料为纯水,流量200 kmol/hr,压力2 bar。",
            difficulty="easy"
        ),
        
        AspenTask(
            task_id="train_003",
            user_requirement="创建一个闪蒸罐模拟,进料为水-乙醇混合物(摩尔比1:1),总流量150 kmol/hr,温度80°C,压力1.5 bar,闪蒸压力降至1 bar。",
            difficulty="easy"
        ),
        
        # 中等难度 - 多个设备串联
        AspenTask(
            task_id="train_004",
            user_requirement="设计一个简单的精馏塔,分离水-乙醇混合物。进料组成:水60%,乙醇40%(摩尔分数),流量100 kmol/hr,温度25°C,压力1 bar。塔顶产品乙醇纯度要求95%以上。",
            difficulty="medium"
        ),
        
        AspenTask(
            task_id="train_005",
            user_requirement="创建一个反应-分离流程:首先在反应器中进行A+B->C的反应(转化率80%),然后通过闪蒸分离产物。进料A和B各50 kmol/hr,温度100°C,压力5 bar。",
            difficulty="medium"
        ),
        
        AspenTask(
            task_id="train_006",
            user_requirement="设计一个换热网络:冷流股从30°C加热到80°C,流量100 kmol/hr;热流股从120°C冷却到60°C,流量80 kmol/hr。使用换热器和加热器/冷却器组合。",
            difficulty="medium"
        ),
        
        # 困难任务 - 复杂流程
        AspenTask(
            task_id="train_007",
            user_requirement="设计一个完整的乙醇生产流程:包括发酵反应器、预精馏塔、精馏塔和脱水单元。原料为葡萄糖溶液,最终产品为99.5%的无水乙醇。",
            difficulty="hard"
        ),
        
        AspenTask(
            task_id="train_008",
            user_requirement="创建一个循环流程:反应器产物经过分离后,未反应物料循环回反应器。要求设置收敛循环,并优化循环比以达到最佳经济性。",
            difficulty="hard"
        ),
        
        # 参数优化任务
        AspenTask(
            task_id="train_009",
            user_requirement="优化精馏塔操作参数:给定进料组成和流量,通过调整回流比和塔板数,使塔顶产品纯度达到98%,同时最小化能耗。",
            difficulty="medium"
        ),
        
        AspenTask(
            task_id="train_010",
            user_requirement="设计一个三组分分离系统:使用两个精馏塔串联,分离A-B-C混合物(各占1/3)。要求每个产品纯度都达到95%以上。",
            difficulty="hard"
        ),
    ]
    
    return AspenDataset(tasks)


def create_validation_dataset() -> AspenDataset:
    """
    创建验证数据集
    
    用于评估模型性能
    """
    tasks = [
        AspenTask(
            task_id="val_001",
            user_requirement="创建一个泵模拟,将水从1 bar增压到10 bar,流量50 kmol/hr,温度25°C。计算所需功率。",
            difficulty="easy"
        ),
        
        AspenTask(
            task_id="val_002",
            user_requirement="设计一个分离器,将气液混合物分离。进料为水-空气混合物,气相摩尔分数0.3,总流量100 kmol/hr,温度50°C,压力2 bar。",
            difficulty="easy"
        ),
        
        AspenTask(
            task_id="val_003",
            user_requirement="创建一个反应-换热-分离集成流程:反应器中A+B->C(放热反应),反应热用于预热进料,产物通过精馏分离。",
            difficulty="hard"
        ),
        
        AspenTask(
            task_id="val_004",
            user_requirement="设计一个压缩机系统,将气体从1 bar压缩到20 bar,包括多级压缩和级间冷却。进料为空气,流量1000 kmol/hr,温度25°C。",
            difficulty="medium"
        ),
        
        AspenTask(
            task_id="val_005",
            user_requirement="优化一个现有的精馏塔:给定塔的结构参数,通过调整操作条件(回流比、进料位置、塔顶压力)来提高分离效率。",
            difficulty="medium"
        ),
    ]
    
    return AspenDataset(tasks)


def create_test_dataset() -> AspenDataset:
    """
    创建测试数据集
    
    用于最终评估
    """
    tasks = [
        AspenTask(
            task_id="test_001",
            user_requirement="设计一个完整的甲醇合成流程:包括原料气压缩、合成反应器、产物冷凝分离和循环系统。",
            difficulty="hard"
        ),
        
        AspenTask(
            task_id="test_002",
            user_requirement="创建一个复杂的多组分精馏系统:分离五组分混合物,使用三个精馏塔,每个产品纯度要求90%以上。",
            difficulty="hard"
        ),
        
        AspenTask(
            task_id="test_003",
            user_requirement="设计一个能量集成的化工流程:包括反应、分离、换热网络,要求最小化外部公用工程消耗。",
            difficulty="hard"
        ),
    ]
    
    return AspenDataset(tasks)
