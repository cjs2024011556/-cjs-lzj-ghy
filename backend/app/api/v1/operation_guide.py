"""
标准化作业指引 API（F3）
基于设备类型与检修等级，输出步骤化 SOP + 合规校验
"""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from typing import List, Optional

from app.services.operation_guide_service import OperationGuideService
from app.core.logger import logger

router = APIRouter()
_service = OperationGuideService()


class GuideRequest(BaseModel):
    equipment_type: str = Field(..., description="设备类型: 液压系统/电机/阀门/泵")
    equipment_model: Optional[str] = Field(default=None)
    maintenance_level: str = Field(..., description="daily/level_1/level_2/level_3/overhaul")
    fault_description: Optional[str] = None


class Step(BaseModel):
    step_no: int
    title: str
    action: str
    risk_level: str
    tools: List[str] = []
    compliance: List[str] = []
    estimated_minutes: int = 0


class GuideResponse(BaseModel):
    sop_id: str
    name: str
    equipment_type: str
    equipment_model: Optional[str] = None
    maintenance_level: str
    estimated_minutes: int
    tools: List[str]
    safety_warnings: List[str]
    steps: List[Step]
    personalized_notes: Optional[str] = None
    source: str
    model: str
    latency_ms: float


@router.post("/generate", response_model=GuideResponse)
async def generate_operation_guide(req: GuideRequest):
    """生成作业指引"""
    try:
        guide = await _service.generate_guide(
            equipment_type=req.equipment_type,
            equipment_model=req.equipment_model,
            maintenance_level=req.maintenance_level,
            fault_description=req.fault_description,
        )
        return GuideResponse(**guide)
    except Exception as e:
        logger.error(f"生成作业指引失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/sops")
async def list_sops():
    """列出内置 SOP 库"""
    return {"sops": _service.list_sops()}


@router.get("/levels")
async def list_maintenance_levels():
    """支持的检修等级"""
    return {
        "levels": [
            {"code": "daily", "name": "日常巡检"},
            {"code": "level_1", "name": "一级保养"},
            {"code": "level_2", "name": "二级保养"},
            {"code": "level_3", "name": "三级检修"},
            {"code": "overhaul", "name": "大修"},
        ]
    }
