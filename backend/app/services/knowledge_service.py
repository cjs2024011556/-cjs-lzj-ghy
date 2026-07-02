"""
知识沉淀服务 - 案例/反馈入库与审核
"""
import json
import uuid
from pathlib import Path
from typing import List, Dict, Any, Optional
from datetime import datetime
from loguru import logger

from app.core.config import settings
from app.services.document_parser import DocumentParser
from app.services.vector_indexer import MilvusIndexer


# 内存存储（Phase 2 接入 PostgreSQL 后改为持久化）
_cases_db: Dict[str, Dict] = {}
_feedback_db: List[Dict] = []


class KnowledgeService:
    """知识沉淀服务

    业务: 一线人员提交案例 → 审核 → 入库 → 检索召回
    """

    def __init__(self):
        self.parser = DocumentParser()
        self.indexer = MilvusIndexer()

    # ---- 案例管理 ----

    async def submit_case(
        self,
        title: str,
        equipment_type: str,
        equipment_model: Optional[str],
        fault_description: str,
        solution: str,
        tags: List[str],
        submitter: str = "anonymous",
        file_path: Optional[str] = None,
    ) -> Dict[str, Any]:
        """提交案例（待审核状态）"""
        case_id = f"CASE-{uuid.uuid4().hex[:8].upper()}"

        case = {
            "case_id": case_id,
            "title": title,
            "equipment_type": equipment_type,
            "equipment_model": equipment_model or "",
            "fault_description": fault_description,
            "solution": solution,
            "tags": tags or [],
            "submitter": submitter,
            "status": "pending",
            "file_path": file_path or "",
            "submitted_at": datetime.now().isoformat(),
        }
        _cases_db[case_id] = case
        logger.info(f"✅ 案例提交: {case_id} - {title}")

        # 解析附件（如果有）
        if file_path and Path(file_path).exists():
            try:
                chunks = self.parser.parse(file_path)
                case["chunk_count"] = len(chunks)
            except Exception as e:
                logger.warning(f"附件解析失败: {e}")
                case["chunk_count"] = 0

        return case

    async def review_case(
        self,
        case_id: str,
        approved: bool,
        reviewer: str = "admin",
        review_comment: str = "",
    ) -> Optional[Dict[str, Any]]:
        """审核案例"""
        if case_id not in _cases_db:
            return None

        case = _cases_db[case_id]
        case["reviewer"] = reviewer
        case["review_comment"] = review_comment
        case["reviewed_at"] = datetime.now().isoformat()

        if approved:
            case["status"] = "approved"
            # 审核通过 → 索引到向量库
            try:
                indexed_count = await self._index_case(case)
                case["indexed_count"] = indexed_count
                logger.info(f"✅ 案例已索引: {case_id} ({indexed_count} chunks)")
            except Exception as e:
                logger.error(f"索引失败: {e}")
                case["index_error"] = str(e)
        else:
            case["status"] = "rejected"

        return case

    async def list_cases(self, status: Optional[str] = None) -> List[Dict[str, Any]]:
        """查询案例列表"""
        cases = list(_cases_db.values())
        if status:
            cases = [c for c in cases if c.get("status") == status]
        # 按时间倒序
        cases.sort(key=lambda c: c.get("submitted_at", ""), reverse=True)
        return cases

    async def get_case(self, case_id: str) -> Optional[Dict[str, Any]]:
        return _cases_db.get(case_id)

    async def _index_case(self, case: Dict[str, Any]) -> int:
        """将案例索引到向量库"""
        # 构造文档内容（合并多个字段）
        content = f"""案例标题: {case['title']}
设备类型: {case['equipment_type']}
设备型号: {case.get('equipment_model', '')}
标签: {', '.join(case.get('tags', []))}

故障描述:
{case['fault_description']}

解决方案:
{case['solution']}

提交人: {case['submitter']}
提交时间: {case['submitted_at']}"""

        from app.services.document_parser import DocumentChunk

        chunk = DocumentChunk(
            content=content,
            metadata={
                "source": f"case://{case['case_id']}",
                "chunk_index": 0,
                "length": len(content),
            },
        )
        return await self.indexer.index_chunks(
            chunks=[chunk],
            doc_type="case",
            equipment_type=case["equipment_type"],
            equipment_model=case.get("equipment_model", ""),
        )

    # ---- 反馈管理 ----

    async def submit_feedback(
        self,
        query: str,
        original_answer: str,
        correction: str = "",
        rating: int = 5,
        user: str = "anonymous",
    ) -> Dict[str, Any]:
        """用户反馈 / 修正"""
        feedback = {
            "feedback_id": f"FB-{uuid.uuid4().hex[:8].upper()}",
            "query": query,
            "original_answer": original_answer,
            "correction": correction,
            "rating": rating,
            "user": user,
            "created_at": datetime.now().isoformat(),
        }
        _feedback_db.append(feedback)
        logger.info(f"✅ 反馈记录: {feedback['feedback_id']}, rating={rating}")
        return feedback

    async def list_feedback(self) -> List[Dict[str, Any]]:
        return list(reversed(_feedback_db))

    # ---- 知识库导入 ----

    async def import_manuals(self, manuals_dir: str) -> Dict[str, int]:
        """批量导入手册目录"""
        manuals_path = Path(manuals_dir)
        if not manuals_path.exists():
            return {}

        results = {}
        for md_file in manuals_path.glob("*.md"):
            try:
                chunks = self.parser.parse(str(md_file))
                count = await self.indexer.index_chunks(
                    chunks=chunks,
                    doc_type="manual",
                )
                results[md_file.name] = count
                logger.info(f"✅ {md_file.name}: {count} chunks")
            except Exception as e:
                logger.error(f"❌ {md_file.name}: {e}")
                results[md_file.name] = -1
        return results

    async def import_cases(self, cases_json: str) -> int:
        """批量导入案例 JSON 文件"""
        path = Path(cases_json)
        if not path.exists():
            return 0

        data = json.loads(path.read_text(encoding="utf-8"))
        count = 0
        for c in data:
            case = await self.submit_case(
                title=c["title"],
                equipment_type=c["equipment_type"],
                equipment_model=c.get("equipment_model", ""),
                fault_description=c.get("fault_description", ""),
                solution=c.get("solution", ""),
                tags=c.get("tags", []),
                submitter=c.get("submitter", "imported"),
            )
            # 批量导入默认通过审核
            await self.review_case(case["case_id"], approved=True, reviewer="system")
            count += 1
        return count

    async def import_sops(self, sops_json: str) -> int:
        """批量导入 SOP JSON 文件"""
        path = Path(sops_json)
        if not path.exists():
            return 0

        data = json.loads(path.read_text(encoding="utf-8"))
        count = 0
        for sop in data:
            content = f"""SOP 名称: {sop['name']}
SOP ID: {sop['sop_id']}
设备类型: {sop['equipment_type']}
检修等级: {sop['maintenance_level']}
预计耗时: {sop.get('estimated_minutes', 0)} 分钟
所需工具: {', '.join(sop.get('tools', []))}

安全警告:
{chr(10).join(sop.get('safety_warnings', []))}

作业步骤:
"""
            for step in sop.get("steps", []):
                content += f"\n步骤 {step['step_no']}: {step['title']}\n"
                content += f"  操作: {step['action']}\n"
                content += f"  风险等级: {step['risk_level']}\n"
                content += f"  合规点: {', '.join(step.get('compliance', []))}\n"
                content += f"  预计耗时: {step.get('estimated_minutes', 0)} 分钟\n"

            from app.services.document_parser import DocumentChunk

            chunk = DocumentChunk(
                content=content,
                metadata={"source": f"sop://{sop['sop_id']}", "chunk_index": 0, "length": len(content)},
            )
            try:
                await self.indexer.index_chunks(
                    chunks=[chunk],
                    doc_type="sop",
                    equipment_type=sop["equipment_type"],
                )
                count += 1
            except Exception as e:
                logger.error(f"SOP 索引失败 {sop['sop_id']}: {e}")
        return count

    async def stats(self) -> Dict[str, int]:
        """知识库统计"""
        try:
            total_chunks = await self.indexer.count()
        except Exception:
            total_chunks = -1
        return {
            "total_chunks": total_chunks,
            "total_cases": len(_cases_db),
            "pending_cases": sum(1 for c in _cases_db.values() if c.get("status") == "pending"),
            "approved_cases": sum(1 for c in _cases_db.values() if c.get("status") == "approved"),
            "total_feedback": len(_feedback_db),
        }
