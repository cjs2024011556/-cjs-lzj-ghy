"""
知识服务单元测试
"""
import pytest
import json
from pathlib import Path

from app.services.knowledge_service import KnowledgeService


class TestKnowledgeService:
    """不依赖外部数据库的纯逻辑测试"""

    @pytest.mark.asyncio
    async def test_submit_case(self):
        service = KnowledgeService()
        case = await service.submit_case(
            title="测试",
            equipment_type="液压系统",
            equipment_model="TEST-001",
            fault_description="测试故障",
            solution="测试方案",
            tags=["test"],
            submitter="tester",
        )
        assert case["case_id"].startswith("CASE-")
        assert case["status"] == "pending"
        assert case["title"] == "测试"

    @pytest.mark.asyncio
    async def test_review_case_approve(self):
        service = KnowledgeService()
        case = await service.submit_case(
            title="测试2",
            equipment_type="电机",
            fault_description="x",
            solution="y",
            tags=[],
        )
        # 注意：审核会尝试调 Milvus，可能失败但不影响状态变更
        reviewed = await service.review_case(
            case_id=case["case_id"],
            approved=True,
            reviewer="admin",
        )
        assert reviewed is not None
        assert reviewed["status"] in ("approved", "approved")  # 审核状态

    @pytest.mark.asyncio
    async def test_review_case_reject(self):
        service = KnowledgeService()
        case = await service.submit_case(
            title="测试3",
            equipment_type="阀门",
            fault_description="x",
            solution="y",
            tags=[],
        )
        reviewed = await service.review_case(
            case_id=case["case_id"],
            approved=False,
            review_comment="信息不完整",
        )
        assert reviewed["status"] == "rejected"
        assert reviewed["review_comment"] == "信息不完整"

    @pytest.mark.asyncio
    async def test_submit_feedback(self):
        service = KnowledgeService()
        fb = await service.submit_feedback(
            query="问题",
            original_answer="原答案",
            correction="纠正",
            rating=4,
        )
        assert fb["feedback_id"].startswith("FB-")
        assert fb["rating"] == 4

    @pytest.mark.asyncio
    async def test_list_cases(self):
        service = KnowledgeService()
        await service.submit_case("a", "x", fault_description="", solution="")
        await service.submit_case("b", "y", fault_description="", solution="")
        cases = await service.list_cases()
        assert len(cases) >= 2

    @pytest.mark.asyncio
    async def test_list_cases_filtered(self):
        service = KnowledgeService()
        c1 = await service.submit_case("a", "x", fault_description="", solution="")
        c2 = await service.submit_case("b", "y", fault_description="", solution="")
        await service.review_case(c2["case_id"], approved=True)
        pending = await service.list_cases("pending")
        assert c1["case_id"] in [c["case_id"] for c in pending]
