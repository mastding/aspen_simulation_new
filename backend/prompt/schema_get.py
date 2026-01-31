schema_get_prompt = f"""
调用工具时基于用户描述的化工任务，思考本次任务需要用到如下哪些设备，将需要用到的设备类型作为请求参数传递给工具：
当前支持的设备类型:
  "supported_block_types": [
    "Mixer",
    "RadFrac",
    "Valve",
    "Compr",
    "Heater",
    "Pump",
    "RStoic",
    "RPlug",
    "Flash2",
    "Decanter",
    "Sep",
    "Sep2",
    "DSTWU"
  ]
"""

