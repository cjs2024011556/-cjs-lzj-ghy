"""
设备类型共享常量（前后端单一真相源）
- 前端：frontend/src/constants/equipment.ts 通过 fetch 后端 /constants/equipment 获取
- 后端：本文件 + /api/v1/constants/equipment 返回 JSON
"""
from typing import List, Dict

EQUIPMENT_TYPES: List[Dict[str, str]] = [
    {"value": "焊接机器人", "label": "焊接机器人"},
    {"value": "AGV", "label": "AGV 移动机器人"},
    {"value": "冲压机", "label": "冲压机"},
    {"value": "机器视觉", "label": "机器视觉系统"},
]
