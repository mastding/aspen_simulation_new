from typing import Dict, Any, List, Optional
import os
import io
import sys
import json
import logging
import requests
import aiofiles
from datetime import datetime
from dotenv import load_dotenv


load_dotenv()

# 配置日志使用UTF-8
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),  # 使用重定向的标准输出
        logging.FileHandler('app.log', encoding='utf-8')  # 文件也使用UTF-8
    ]
)
logger = logging.getLogger(__name__)

# schema目录
BASE_DIR = os.path.dirname(__file__)
print(BASE_DIR)
WHOLE_SCHEMA_PATH = os.path.join(BASE_DIR, "../../aspen/schema/whole_schema.json")
BASE_SCHEMA_PATH = os.path.join(BASE_DIR, "../../aspen/schema/base_schema.json")
ASPEN_SIMULATOR_URL = os.getenv("ASPEN_SIMULATOR_URL", "http://localhost:8002")

# 支持的设备类型列表（示例，根据实际文件调整）
SUPPORTED_BLOCK_TYPES = ["reactor", "mixer", "splitter", "heat_exchanger", "separator", "pump", "compressor"]

# 工具1：获取Schema（增强版）
async def get_schema(block_types: Optional[List[str]] = None) -> str:
    """获取化工流程配置的JSON Schema"""
    try:
        logger.info(f"获取Schema - 请求的设备类型: {block_types}")
        
        # 1. 加载基础schema
        if os.path.exists(BASE_SCHEMA_PATH):
            async with aiofiles.open(BASE_SCHEMA_PATH, "r", encoding="utf-8") as f:
                base_schema_content = await f.read()
                base_schema = json.loads(base_schema_content)
                logger.info(f"基础schema加载成功，大小: {len(base_schema_content)} 字符")
        else:
            logger.error(f"基础schema文件不存在: {BASE_SCHEMA_PATH}")
            return json.dumps({"error": "基础schema文件不存在"}, ensure_ascii=False)
        
        # 2. 如果没有指定设备类型，返回完整schema
        if not block_types:
            logger.info("未指定设备类型，返回完整schema")
            return base_schema

        # 4. 加载指定的设备schema
        schema_dir = os.path.join(BASE_DIR, "../../aspen/schema")

        for block_type in block_types:
            block_filename = f"blocks_{block_type}_data.json"
            block_path = os.path.join(schema_dir, block_filename)
            if os.path.exists(block_path):
                async with aiofiles.open(block_path, "r", encoding="utf-8") as f:
                    block_content = await f.read()
                    block_data = json.loads(block_content)
                    base_schema["properties"][f"blocks_{block_type}_data"] = block_data[f"blocks_{block_type}_data"]
                    logger.info(f"已加载设备schema: {block_type}")
        return json.dumps(base_schema, ensure_ascii=False)
    except Exception as e:
                    logger.error(f"加载设备schema失败: {e}")


