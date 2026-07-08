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
import json

from app.services.knowledge_service import KnowledgeService
from app.core.config import settings, MANUALS_DIR, CASES_FILE, SOPS_FILE
from app.core.logger import logger
# H-Fix-3: 上传/删除文件后失效关键词 fallback 缓存
from app.api.v1.chat import invalidate_keyword_cache

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
    # FIX-Upload-1: 复用上面的 chunks，不再重复 parse（PDF parse 一次要 9s+）
    if section_count > 0 and ext in {".pdf", ".docx"} and chunks:
        try:
            from app.services.vector_indexer import MilvusIndexer
            indexer = MilvusIndexer()
            indexer._ensure_connected()
            if indexer._collection is not None:
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

    # H-Fix-3: 让 keyword_fallback 下次重新读磁盘，命中新文件
    invalidate_keyword_cache()

    # PDF-A.6: 快速结构摘要（仅写占位，避免上传时再 parse 一次）
    # 完整结构在 GET /manuals/{name}/structure 时按需构建
    structure_info = _build_structure_summary_quick(target, ext, section_count)

    return {
        "success": True,
        "filename": target.name,
        "path": str(target),
        "md_copy": parsed_md.name if parsed_md else None,
        "size_kb": round(len(content) / 1024, 1),
        "section_count": section_count,
        "indexed_in_milvus": indexed_in_milvus,
        "searchable_now": searchable_now,
        # PDF-A.6
        "structure": structure_info,
        "message": (
            f"已保存 {target.name}（{section_count} 段），"
            f"已 Milvus 索引" if indexed_in_milvus else
            f"已保存 {target.name}（{section_count} 段），"
            f"关键词搜索立即可用" + ("（.md 副本可被 fallback 搜到）" if parsed_md else "")
        )
    }


def _build_structure_summary_quick(target: Path, ext: str, section_count: int) -> dict:
    """FIX-Upload-1: 上传时只写最小元数据（避免再 parse 一次 PDF）

    完整结构（章节树 + 表格清单）由 GET /manuals/{name}/structure 时按需构建。
    """
    if ext not in {".pdf", ".md", ".markdown"}:
        return None
    struct = {
        "outline": [],
        "tables": [],
        "page_count": 0,
        "chunk_count": section_count,
        "cached_at": time.time(),
        "pending": True,  # 标记：完整结构待首次访问时构建
    }
    try:
        struct_path = target.parent / f"{target.stem}.structure.json"
        struct_path.write_text(
            json.dumps(struct, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        # 移除 pending 字段，返回给前端时用
        return {k: v for k, v in struct.items() if k != "pending"}
    except Exception as e:
        logger.warning(f"写结构占位失败: {e}")
        return None


def _build_structure_summary(target: Path, ext: str) -> dict:
    """PDF-A.6: 解析文档结构（章节树 + 表格清单），持久化 .structure.json

    - .pdf → PdfplumberPdfLoader + StructureDetector
    - .md  → 用 ##/### 简单解析
    - 其他 → 返回 None
    """
    try:
        if ext == ".pdf":
            from app.services.pdf_loader import PdfplumberPdfLoader
            from app.services.structure_detector import (
                StructureDetector, OutlineItem, TableDigest,
            )
            pages = PdfplumberPdfLoader().load(target)
            sections = StructureDetector().detect(pages)
            detector = StructureDetector()
            outline = [
                {"level": i.level, "title": i.title, "page_start": i.page_start}
                for i in detector.build_outline(sections)
            ]
            tables = [
                {"page": t.page, "rows": t.rows, "cols": t.cols, "preview": t.preview}
                for t in detector.build_tables_digest(sections)
            ]
            page_count = len(pages)
            chunk_count = 0  # 不知道精确 chunk 数（要重新走 _parse_pdf_structured）
        elif ext in {".md", ".markdown"}:
            text = target.read_text(encoding="utf-8", errors="ignore")
            outline, tables, page_count, chunk_count = [], [], 0, 0
            for line in text.splitlines():
                if line.startswith("### "):
                    outline.append({"level": 3, "title": line[4:].strip(), "page_start": 0})
                elif line.startswith("## "):
                    outline.append({"level": 2, "title": line[3:].strip(), "page_start": 0})
                elif line.startswith("# "):
                    outline.append({"level": 1, "title": line[2:].strip(), "page_start": 0})
        else:
            return None

        struct = {
            "outline": outline,
            "tables": tables,
            "page_count": page_count,
            "chunk_count": chunk_count,
            "cached_at": time.time(),
        }
        # 持久化到磁盘
        struct_path = target.parent / f"{target.stem}.structure.json"
        struct_path.write_text(
            json.dumps(struct, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        return struct
    except Exception as e:
        logger.warning(f"⚠️ 结构解析失败 {target.name}: {e}")
        return None


def _read_structure_summary(filename: str) -> dict | None:
    """读取持久化的结构摘要（.structure.json）"""
    struct_path = MANUALS_DIR / f"{Path(filename).stem}.structure.json"
    if not struct_path.exists():
        return None
    try:
        return json.loads(struct_path.read_text(encoding="utf-8"))
    except Exception:
        return None


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
    # H-Fix-3: 让 keyword_fallback 下次重新读磁盘，移除已删条目
    invalidate_keyword_cache()
    return {"deleted": filename}


@router.get("/manuals/{filename}/content")
async def get_manual_content(filename: str):
    """FEAT: 查看上传手册的内容

    - .md / .txt / .markdown：直接返回 UTF-8 文本
    - .pdf / .docx：用 DocumentParser 解析后返回 Markdown 文本
    - 限制最大返回 200KB（防止巨大文档卡死前端）
    """
    target = MANUALS_DIR / filename
    if not target.exists():
        raise HTTPException(status_code=404, detail="文件不存在")
    if not target.is_file():
        raise HTTPException(status_code=400, detail="不是文件")

    ext = target.suffix.lower()
    MAX_RETURN_BYTES = 200 * 1024
    truncated = False

    try:
        if ext in {".md", ".txt", ".markdown"}:
            text = target.read_text(encoding="utf-8", errors="ignore")
        elif ext == ".pdf":
            from app.services.document_parser import DocumentParser
            chunks = DocumentParser().parse(str(target))
            text = "\n\n---\n\n".join(c.content for c in chunks) if chunks else target.read_text(encoding="utf-8", errors="ignore")
        elif ext in {".docx", ".doc"}:
            from app.services.document_parser import DocumentParser
            chunks = DocumentParser().parse(str(target))
            text = "\n\n---\n\n".join(c.content for c in chunks) if chunks else target.read_text(encoding="utf-8", errors="ignore")
        else:
            # 其他类型：尝试按文本读
            text = target.read_text(encoding="utf-8", errors="ignore")
    except Exception as e:
        logger.error(f"读取手册 {filename} 失败: {e}")
        raise HTTPException(status_code=500, detail=f"读取失败: {e}")

    if len(text.encode("utf-8")) > MAX_RETURN_BYTES:
        text = text.encode("utf-8")[:MAX_RETURN_BYTES].decode("utf-8", errors="ignore")
        truncated = True

    return {
        "filename": filename,
        "ext": ext,
        "size_kb": round(target.stat().st_size / 1024, 1),
        "content": text,
        "truncated": truncated,
    }


# ============================================================
# PDF-A.6: 新增端点 — 结构摘要 + 重建索引
# ============================================================
@router.get("/manuals/{filename}/structure")
async def get_manual_structure(filename: str):
    """PDF-A.6: 获取手册结构化摘要（章节树 + 表格清单 + 元数据）

    Returns:
        {
            "filename": "焊接工艺手册.pdf",
            "outline": [{"level": 1, "title": "第1章 液压系统", "page_start": 1}, ...],
            "tables": [{"page": 23, "rows": 4, "cols": 3, "preview": "..."}, ...],
            "page_count": 56,
            "chunk_count": 184,
            "cached": true | false
        }

    若 .structure.json 不存在（首次上传没缓存），会即时构建一次并写入磁盘。
    """
    target = MANUALS_DIR / filename
    if not target.exists():
        raise HTTPException(status_code=404, detail="文件不存在")
    ext = target.suffix.lower()

    # 优先读缓存
    cached = _read_structure_summary(filename)
    if cached:
        # FIX-Upload-1: 如果是 quick 占位（pending=True 或 outline 为空），
        # 触发完整构建
        if cached.get("pending") or (
            not cached.get("outline") and not cached.get("tables")
            and ext == ".pdf"
        ):
            logger.info(f"结构占位 → 触发完整构建: {filename}")
            full = _build_structure_summary(target, ext)
            if full:
                cached = full
                cached["cached"] = True  # 标记为已缓存
        return {
            "filename": filename,
            "ext": ext,
            "outline": cached.get("outline", []),
            "tables": cached.get("tables", []),
            "page_count": cached.get("page_count", 0),
            "chunk_count": cached.get("chunk_count", 0),
            "cached": True,
        }

    # 没缓存：即时构建
    summary = _build_structure_summary(target, ext)
    if summary is None:
        return {
            "filename": filename,
            "ext": ext,
            "outline": [],
            "tables": [],
            "page_count": 0,
            "chunk_count": 0,
            "cached": False,
            "note": "此文件类型暂不支持结构解析",
        }

    return {
        "filename": filename,
        "ext": ext,
        "outline": summary.get("outline", []),
        "tables": summary.get("tables", []),
        "page_count": summary.get("page_count", 0),
        "chunk_count": summary.get("chunk_count", 0),
        "cached": False,
    }


@router.post("/manuals/{filename}/reindex")
async def reindex_manual(filename: str):
    """PDF-A.6: 重建单本手册的索引（删除旧 Milvus chunks → 重走流水线）"""
    from app.services.vector_indexer import MilvusIndexer
    target = MANUALS_DIR / filename
    if not target.exists():
        raise HTTPException(status_code=404, detail="文件不存在")
    if target.suffix.lower() not in {".pdf", ".docx", ".doc"}:
        raise HTTPException(status_code=400, detail="仅支持 PDF / Word 重建索引")

    try:
        # 1. 删除旧
        indexer = MilvusIndexer()
        indexer._ensure_connected()
        deleted = await indexer.delete_by_source(str(target))
        invalidate_keyword_cache()

        # 2. 重新解析 + 索引
        from app.services.document_parser import DocumentParser
        chunks = DocumentParser().parse(str(target))
        if not chunks:
            return {"reindexed": 0, "deleted": deleted, "filename": filename}

        inserted = await indexer.index_chunks(chunks, doc_type="manual_upload")
        return {
            "reindexed": inserted,
            "deleted": deleted,
            "filename": filename,
            "success": True,
        }
    except Exception as e:
        logger.exception(f"重建索引失败: {filename}")
        raise HTTPException(status_code=500, detail=f"重建失败: {e}")


@router.post("/reindex")
async def reindex_all():
    """PDF-A.6: 重建 manuals 目录全部 PDF/Word 的 Milvus 索引

    步骤：
    1. 删 a1_knowledge collection
    2. 重建（新 schema 字段）
    3. 遍历 manuals 目录逐个重新解析 + 索引
    """
    try:
        from app.services.vector_indexer import MilvusIndexer
        from app.services.document_parser import DocumentParser

        indexer = MilvusIndexer()
        indexer._ensure_connected()
        # 触发 schema 自检（不匹配自动重建）
        total = 0
        results = []

        for path in sorted(MANUALS_DIR.glob("*")):
            if not path.is_file():
                continue
            ext = path.suffix.lower()
            if ext not in {".pdf", ".docx", ".doc"}:
                continue
            try:
                chunks = DocumentParser().parse(str(path))
                if not chunks:
                    continue
                inserted = await indexer.index_chunks(chunks, doc_type="manual_upload")
                total += inserted
                results.append({
                    "filename": path.name,
                    "chunks": inserted,
                    "ok": True,
                })
                logger.info(
                    f"✅ Reindex {path.name}: {inserted} chunks"
                )
            except Exception as e:
                results.append({
                    "filename": path.name,
                    "ok": False,
                    "error": str(e),
                })
                logger.warning(f"⚠️ 重建 {path.name} 失败: {e}")

        invalidate_keyword_cache()
        return {
            "success": True,
            "total_chunks": total,
            "files": results,
        }
    except Exception as e:
        logger.exception("全量重建索引失败")
        raise HTTPException(status_code=500, detail=f"全量重建失败: {e}")


# ============================================================
# PDF-B.6: 新增端点 — 视觉重分析（聚群 B 多模态增强）
# ============================================================
@router.post("/manuals/{filename}/re-analyze")
async def reanalyze_manual(filename: str, force: bool = False):
    """PDF-B.6: 视觉重分析（聚群 B）

    对已上传的 PDF 重新跑一遍 VL 增强流程：
    1. 删除该 PDF 在 Milvus 的旧 chunks
    2. 用 parse_pdf_with_vl 重解析（含 image_description / image_facts）
    3. 重新插入

    Args:
        filename: PDF 文件名
        force: True 时强制启用 VL（否则只在文字 < 30 字符的页触发）

    Returns:
        {reindexed, deleted, vl_pages_processed, filename}
    """
    target = MANUALS_DIR / filename
    if not target.exists():
        raise HTTPException(status_code=404, detail="文件不存在")
    if target.suffix.lower() != ".pdf":
        raise HTTPException(status_code=400, detail="仅支持 PDF 视觉重分析")

    try:
        from app.services.vector_indexer import MilvusIndexer
        from app.services.document_parser import DocumentParser

        indexer = MilvusIndexer()
        indexer._ensure_connected()
        deleted = await indexer.delete_by_source(str(target))
        invalidate_keyword_cache()

        parser = DocumentParser()
        chunks = await parser.parse_pdf_with_vl(
            str(target),
            enable_vl=True,
            trigger_on_scanned=force or True,
            trigger_on_table_pages=force,
        )
        if not chunks:
            return {
                "reindexed": 0, "deleted": deleted,
                "vl_pages_processed": 0, "filename": filename,
            }
        inserted = await indexer.index_chunks(chunks, doc_type="manual_upload")
        vl_pages = sum(
            1 for c in chunks if c.metadata.get("image_description")
        )
        return {
            "reindexed": inserted,
            "deleted": deleted,
            "vl_pages_processed": vl_pages,
            "filename": filename,
            "success": True,
        }
    except Exception as e:
        logger.exception(f"视觉重分析失败: {filename}")
        raise HTTPException(status_code=500, detail=f"视觉重分析失败: {e}")


@router.post("/re-analyze-all")
async def reanalyze_all(force: bool = False):
    """PDF-B.6: 全量视觉重分析（聚群 B）

    对 manuals 目录下所有 PDF 重新跑 VL 增强。耗时较长（每页 ~2-3s）。
    """
    from app.services.vector_indexer import MilvusIndexer
    from app.services.document_parser import DocumentParser

    try:
        indexer = MilvusIndexer()
        indexer._ensure_connected()

        total_chunks = 0
        total_vl_pages = 0
        results = []
        for path in sorted(MANUALS_DIR.glob("*.pdf")):
            if not path.is_file():
                continue
            try:
                # 先删旧
                deleted = await indexer.delete_by_source(str(path))
                # 再跑 VL
                parser = DocumentParser()
                chunks = await parser.parse_pdf_with_vl(
                    str(path),
                    enable_vl=True,
                    trigger_on_scanned=force or True,
                    trigger_on_table_pages=force,
                )
                if not chunks:
                    results.append({
                        "filename": path.name, "ok": True,
                        "chunks": 0, "vl_pages": 0,
                    })
                    continue
                inserted = await indexer.index_chunks(chunks, doc_type="manual_upload")
                vl_pages = sum(
                    1 for c in chunks if c.metadata.get("image_description")
                )
                total_chunks += inserted
                total_vl_pages += vl_pages
                results.append({
                    "filename": path.name, "ok": True,
                    "chunks": inserted, "vl_pages": vl_pages,
                })
                logger.info(
                    f"🖼️ Re-analyze {path.name}: {inserted} chunks, "
                    f"{vl_pages} 页经 VL 增强"
                )
            except Exception as e:
                results.append({
                    "filename": path.name, "ok": False, "error": str(e),
                })
                logger.warning(f"⚠️ 视觉重分析 {path.name} 失败: {e}")

        invalidate_keyword_cache()
        return {
            "success": True,
            "total_chunks": total_chunks,
            "total_vl_pages": total_vl_pages,
            "files": results,
        }
    except Exception as e:
        logger.exception("全量视觉重分析失败")
        raise HTTPException(status_code=500, detail=f"全量视觉重分析失败: {e}")


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
