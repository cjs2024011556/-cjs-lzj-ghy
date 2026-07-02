"""
共享常量 API（设备类型等）
"""
from fastapi import APIRouter

from app.constants.equipment import EQUIPMENT_TYPES

router = APIRouter()


@router.get("/equipment")
async def list_equipment():
    """设备类型列表（前后端单一真相源）"""
    return {"equipment": EQUIPMENT_TYPES, "total": len(EQUIPMENT_TYPES)}
