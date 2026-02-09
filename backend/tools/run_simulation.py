from typing import Dict, Any, List
import os
import sys
import logging
import requests
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
ASPEN_SIMULATOR_URL = os.getenv("ASPEN_SIMULATOR_URL")


# 工具2：运行模拟
async def run_simulation(config: Dict[str, Any]) -> Dict[str, Any]:
    """运行化工流程模拟"""
    try:
        logger.info(f"向模拟器发送请求: {ASPEN_SIMULATOR_URL}")

        # 发送配置到模拟器
        response = requests.post(
            f"{ASPEN_SIMULATOR_URL}/run-aspen-simulation",
            json=config,
            timeout=3000,
            verify=False
        )
        return response.json()
    except requests.exceptions.RequestException as e:
        error_msg = f"连接模拟器失败: {str(e)}"
        logger.error(error_msg)