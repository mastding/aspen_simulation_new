from typing import Dict, Any, List
import os
import json
import pandas as pd
from datetime import datetime


async def get_result(file_path: str) -> str:
    """
    读取本地Excel结果文件，自动读取所有工作表，用于大模型调用后进行结果分析

    参数:
    - file_path: Excel文件路径
    - max_rows_per_sheet: 每个工作表最大读取行数，None表示读取所有行

    返回:
    - JSON字符串格式的Excel数据，包含所有工作表的内容
    """
    try:
        # 验证文件路径
        if not os.path.exists(file_path):
            return json.dumps({
                "error": f"文件不存在: {file_path}",
                "timestamp": datetime.now().isoformat()
            }, ensure_ascii=False)

        # 使用ExcelFile对象获取所有工作表信息
        excel_file = pd.ExcelFile(file_path)
        sheet_names = excel_file.sheet_names

        # 构建返回结果
        result = {
            "status": "success",
            "file_info": {
                "file_name": os.path.basename(file_path),
                "file_path": file_path,
                "sheet_count": len(sheet_names),
                "sheet_names": sheet_names,
                "read_time": datetime.now().isoformat()
            },
            "data": {}
        }

        # 读取所有工作表
        for sheet_name in sheet_names:
            try:
                # 读取当前工作表
                df = pd.read_excel(file_path,
                                   sheet_name=sheet_name)

                # 处理当前工作表数据
                sheet_data = {
                    "row_count": len(df),
                    "column_count": len(df.columns),
                    "column_names": df.columns.tolist(),
                    "data": df.where(pd.notnull(df), None).to_dict(orient='records')
                }

                # 添加到结果中
                result["data"][sheet_name] = sheet_data

            except Exception as e:
                # 如果某个工作表读取失败，记录错误信息
                result["data"][sheet_name] = {
                    "error": f"读取工作表失败: {str(e)}",
                    "row_count": 0,
                    "column_count": 0
                }

        return json.dumps(result, ensure_ascii=False, default=str)

    except Exception as e:
        return json.dumps({
            "error": f"读取Excel文件失败: {str(e)}",
            "file_path": file_path,
            "timestamp": datetime.now().isoformat()
        }, ensure_ascii=False, default=str)