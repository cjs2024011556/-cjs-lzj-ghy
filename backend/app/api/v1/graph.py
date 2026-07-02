"""
故障图谱 API（创新杀手锏）
- GET /graph/visualize - 整图（限制节点数）
- GET /graph/related - 关键词找相关子图
- GET /graph/stats - 图谱统计
- POST /graph/build - 重建图谱
"""
from typing import List, Optional
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from app.services.graph_service import get_graph_service
from app.core.logger import logger

router = APIRouter()


class RelatedRequest(BaseModel):
    keywords: List[str]
    max_hops: int = 2


@router.get("/visualize")
async def visualize(max_nodes: int = Query(200, ge=10, le=500)):
    """获取图谱可视化数据（vis.js 格式）"""
    try:
        gs = get_graph_service()
        return gs.get_full_graph(max_nodes=max_nodes)
    except Exception as e:
        logger.error(f"图谱可视化失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/related")
async def related(req: RelatedRequest):
    """根据关键词找相关子图"""
    try:
        gs = get_graph_service()
        if not req.keywords:
            raise HTTPException(status_code=400, detail="keywords 不能为空")
        return gs.find_related(req.keywords, max_hops=req.max_hops)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"图谱关联查询失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/stats")
async def stats():
    """图谱统计"""
    try:
        gs = get_graph_service()
        return gs.stats()
    except Exception as e:
        logger.error(f"图谱统计失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/build")
async def build_graph():
    """重建图谱（从案例+手册+SOP 重新构建）"""
    try:
        # 延迟导入避免循环
        from scripts.build_graph import build as run_build
        run_build()
        gs = get_graph_service()
        return {
            "success": True,
            "stats": gs.stats(),
        }
    except Exception as e:
        logger.error(f"图谱构建失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))
