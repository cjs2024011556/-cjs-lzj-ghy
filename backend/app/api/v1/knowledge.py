"""
知识沉淀与更新 API（F4）
- 案例提交/审核
- 知识库导入（管理员）
- 反馈收集
"""
from fastapi import APIRouter, UploadFile, File, Form, HTTPException
from pydantic import BaseModel, Field
from typing import Optional, List
from enum import Enum
from pathlib import Path
import shutil
import time

from app.services.knowledge_service import KnowledgeService
from app.core.config import settings, MANUALS_DIR, CASES_FILE, SOPS_FILE
from app.core.logger import logger

router = APIRouter()
_service = KnowledgeService()


class CaseStatus(str, Enum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"


class CaseSubmitRequest(BaseModel):
    title: str = Field(..., min_length=2, max_length=200)
    equipment_type: str
    equipment_model: Optional[str] = None
    fault_description: str
    solution: str
    tags: List[str] = []
    submitter: str = "anonymous"


class CaseReviewRequest(BaseModel):
    case_id: str
    approved: bool
    reviewer: str = "admin"
    review_comment: str = ""


class FeedbackRequest(BaseModel):
    query: str
    original_answer: str
    correction: str = ""
    rating: int = Field(default=5, ge=1, le=5)
    user: str = "anonymous"


# ---- 案例管理 ----

@router.post("/case/submit")
async def submit_case(req: CaseSubmitRequest):
    """一线人员提交案例"""
    try:
        case = await _service.submit_case(
            title=req.title,
            equipment_type=req.equipment_type,
            equipment_model=req.equipment_model,
            fault_description=req.fault_description,
            solution=req.solution,
            tags=req.tags,
            submitter=req.submitter,
        )
        return case
    except Exception as e:
        logger.error(f"提交案例失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/case/submit-with-file")
async def submit_case_with_file(
    title: str = Form(...),
    equipment_type: str = Form(...),
    equipment_model: Optional[str] = Form(default=None),
    fault_description: str = Form(...),
    solution: str = Form(...),
    tags: str = Form(default=""),
    submitter: str = Form(default="anonymous"),
    file: Optional[UploadFile] = File(default=None),
):
    """提交案例 + 上传附件"""
    try:
        file_path = None
        if file:
            upload_dir = Path(settings.UPLOAD_DIR) / "cases"
            upload_dir.mkdir(parents=True, exist_ok=True)
            file_path = upload_dir / f"{int(time.time())}_{file.filename}"
            with open(file_path, "wb") as f:
                shutil.copyfileobj(file.file, f)

        tag_list = [t.strip() for t in tags.split(",") if t.strip()]
        case = await _service.submit_case(
            title=title,
            equipment_type=equipment_type,
            equipment_model=equipment_model,
            fault_description=fault_description,
            solution=solution,
            tags=tag_list,
            submitter=submitter,
            file_path=str(file_path) if file_path else None,
        )
        return case
    except Exception as e:
        logger.error(f"提交案例失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/case/review")
async def review_case(req: CaseReviewRequest):
    """审核案例"""
    case = await _service.review_case(
        case_id=req.case_id,
        approved=req.approved,
        reviewer=req.reviewer,
        review_comment=req.review_comment,
    )
    if not case:
        raise HTTPException(status_code=404, detail="案例不存在")
    return case


@router.get("/case/list")
async def list_cases(status: Optional[CaseStatus] = None):
    """查询案例列表"""
    return {"cases": await _service.list_cases(status.value if status else None)}


@router.get("/case/{case_id}")
async def get_case(case_id: str):
    """查询单个案例"""
    case = await _service.get_case(case_id)
    if not case:
        raise HTTPException(status_code=404, detail="案例不存在")
    return case


# ---- 反馈管理 ----

@router.post("/feedback")
async def submit_feedback(req: FeedbackRequest):
    """用户反馈"""
    return await _service.submit_feedback(
        query=req.query,
        original_answer=req.original_answer,
        correction=req.correction,
        rating=req.rating,
        user=req.user,
    )


@router.get("/feedback")
async def list_feedback():
    return {"feedback": await _service.list_feedback()}


# ---- 知识库管理 ----

@router.post("/import/manuals")
async def import_manuals():
    """导入内置手册（管理员）"""
    results = await _service.import_manuals(str(MANUALS_DIR))
    return {"results": results, "total_files": len(results)}


@router.post("/import/cases")
async def import_cases():
    """导入内置案例（管理员）"""
    count = await _service.import_cases(str(CASES_FILE))
    return {"imported": count}


@router.post("/import/sops")
async def import_sops():
    """导入内置 SOP（管理员）"""
    count = await _service.import_sops(str(SOPS_FILE))
    return {"imported": count}


@router.post("/upload")
async def upload_manual(file: UploadFile = File(..., description="知识库文档（支持 .md / .txt / .pdf / .docx）")):
    """U4: 上传外部知识资料（保存 + 解析 + 索引）

    - .md / .txt：直接保存，RAG 关键词搜索立即可用
    - .pdf / .docx：解析后保存 .md 副本（关键词 fallback 可用）+ 尝试 Milvus 索引

    返回：保存的文件名 + 路径 + 估计段落数 + 索引状态
    """
    if not file.filename:
        raise HTTPException(status_code=400, detail="未提供文件名")

    # 检查文件类型
    filename = file.filename
    ext = Path(filename).suffix.lower()
    allowed_exts = {".md", ".txt", ".pdf", ".docx", ".markdown"}
    if ext not in allowed_exts:
        raise HTTPException(
            status_code=400,
            detail=f"不支持的文件类型: {ext}。支持: {', '.join(sorted(allowed_exts))}",
        )

    # 限制大小（50MB）
    max_size = 50 * 1024 * 1024
    content = await file.read()
    if len(content) > max_size:
        raise HTTPException(status_code=400, detail=f"文件过大（>{max_size // 1024 // 1024}MB）")

    # 存到 manuals/（去重：同名加时间戳）
    MANUALS_DIR.mkdir(parents=True, exist_ok=True)
    target = MANUALS_DIR / filename
    if target.exists():
        stem = target.stem
        suffix = target.suffix
        target = MANUALS_DIR / f"{stem}_{int(time.time())}{suffix}"

    try:
        target.write_bytes(content)
    except Exception as e:
        logger.error(f"保存知识文件失败: {e}")
        raise HTTPException(status_code=500, detail=f"保存失败: {e}")

    # U4: 解析 + 索引
    section_count = 0
    parsed_md = None
    indexed_in_milvus = False

    if ext in {".md", ".markdown", ".txt"}:
        # 纯文本：直接解析
        try:
            text = content.decode("utf-8", errors="ignore")
            if ext in {".md", ".markdown"}:
                import re
                sections = re.split(r"(?=^## )", text, flags=re.MULTILINE)
                section_count = sum(1 for s in sections if len(s.strip()) > 20)
            else:
                section_count = max(1, text.count("\n\n") + 1)
        except Exception:
            section_count = 0
    else:
        # .pdf / .docx：解析 + 生成 .md 副本（给 keyword_fallback 用）
        try:
            from app.services.document_parser import DocumentParser
            parser = DocumentParser()
            chunks = parser.parse(str(target))
            section_count = len(chunks)

            # 生成 .md 副本（按 ## 章节拼接）
            if chunks:
                md_lines = [f"# {target.stem}（自动解析）", ""]
                for i, ch in enumerate(chunks):
                    title = ch.metadata.get("section_title", f"段落 {i+1}") if hasattr(ch, "metadata") else f"段落 {i+1}"
                    md_lines.append(f"## {title}")
                    md_lines.append("")
                    md_lines.append(ch.content)
                    md_lines.append("")
                parsed_md = MANUALS_DIR / f"{target.stem}.md"
                parsed_md.write_text("\n".join(md_lines), encoding="utf-8")
                logger.info(f"✅ 解析 {filename} → {parsed_md.name}（{section_count} 段）")
        except Exception as e:
            logger.warning(f"解析 {filename} 失败: {e}")
            section_count = 0

    # 尝试 Milvus 索引（如果可用）
    if section_count > 0 and ext in {".pdf", ".docx"}:
        try:
            from app.services.vector_indexer import MilvusIndexer
            indexer = MilvusIndexer()
            indexer._ensure_connected()
            if indexer._collection is not None:
                # 单独索引这一个文件
                from app.services.document_parser import DocumentParser
                parser = DocumentParser()
                chunks = parser.parse(str(target))
                if chunks:
                    indexer.index_chunks(chunks, doc_type="manual_upload")
                    indexed_in_milvus = True
                    logger.info(f"✅ Milvus 索引完成: {filename}（{len(chunks)} 段）")
        except Exception as e:
            logger.warning(f"Milvus 索引失败（仅 keyword_fallback）: {e}")

    searchable_now = ext in {".md", ".txt", ".markdown"} or parsed_md is not None

    logger.info(
        f"✅ 知识文档已保存: {target.name} ({len(content)} bytes, "
        f"sections={section_count}, milvus={indexed_in_milvus})"
    )

    return {
        "success": True,
        "filename": target.name,
        "path": str(target),
        "md_copy": parsed_md.name if parsed_md else None,
        "size_kb": round(len(content) / 1024, 1),
        "section_count": section_count,
        "indexed_in_milvus": indexed_in_milvus,
        "searchable_now": searchable_now,
        "message": (
            f"已保存 {target.name}（{section_count} 段），"
            f"已 Milvus 索引" if indexed_in_milvus else
            f"已保存 {target.name}（{section_count} 段），"
            f"关键词搜索立即可用" + ("（.md 副本可被 fallback 搜到）" if parsed_md else "")
        )
    }


@router.get("/manuals")
async def list_manuals():
    """列出所有手册（已上传 + 内置）"""
    MANUALS_DIR.mkdir(parents=True, exist_ok=True)
    files = []
    for p in sorted(MANUALS_DIR.glob("*")):
        if p.is_file():
            files.append({
                "name": p.name,
                "size_kb": round(p.stat().st_size / 1024, 1),
                "mtime": p.stat().st_mtime,
            })
    return {"manuals": files, "total": len(files)}


@router.delete("/manuals/{filename}")
async def delete_manual(filename: str):
    """删除上传的手册"""
    target = MANUALS_DIR / filename
    if not target.exists():
        raise HTTPException(status_code=404, detail="文件不存在")
    if not target.is_file():
        raise HTTPException(status_code=400, detail="不是文件")
    target.unlink()
    return {"deleted": filename}


@router.post("/import/all")
async def import_all():
    """一键导入所有内置知识"""
    manuals = await _service.import_manuals(str(MANUALS_DIR))
    cases = await _service.import_cases(str(CASES_FILE))
    sops = await _service.import_sops(str(SOPS_FILE))
    return {
        "manuals": manuals,
        "cases_imported": cases,
        "sops_imported": sops,
    }


@router.get("/stats")
async def stats():
    """知识库统计"""
    return await _service.stats()
