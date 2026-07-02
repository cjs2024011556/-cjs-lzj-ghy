"""
文档解析服务
支持: PDF、Word、Markdown、TXT、图片（OCR）
"""
import re
from pathlib import Path
from typing import List, Dict, Any
from loguru import logger

from app.core.config import settings


class DocumentChunk:
    """文档分块"""
    def __init__(self, content: str, metadata: Dict[str, Any] = None):
        self.content = content
        self.metadata = metadata or {}
        self.chunk_id = ""

    def __repr__(self):
        return f"<DocumentChunk id={self.chunk_id} len={len(self.content)}>"


class DocumentParser:
    """文档解析器

    流程: 加载 → 提取文本 → 切块 → 输出
    """

    def __init__(self, chunk_size: int = 500, chunk_overlap: int = 50):
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap

    def parse(self, file_path: str) -> List[DocumentChunk]:
        """主入口"""
        path = Path(file_path)
        if not path.exists():
            raise FileNotFoundError(f"文件不存在: {file_path}")

        suffix = path.suffix.lower()
        if suffix == ".pdf":
            text = self._parse_pdf(path)
        elif suffix in (".docx", ".doc"):
            text = self._parse_word(path)
        elif suffix in (".md", ".markdown"):
            text = self._parse_markdown(path)
        elif suffix in (".txt",):
            text = path.read_text(encoding="utf-8")
        elif suffix in (".jpg", ".jpeg", ".png", ".bmp", ".webp"):
            text = self._parse_image(path)
        else:
            raise ValueError(f"不支持的文件类型: {suffix}")

        logger.info(f"解析完成: {path.name}, 文本长度: {len(text)}")
        chunks = self._split_into_chunks(text, source=str(path))
        logger.info(f"切分完成: {len(chunks)} 个块")
        return chunks

    def _parse_pdf(self, path: Path) -> str:
        """PDF 解析（优先 pdftotext，回退 pypdf）"""
        try:
            import pdfplumber
            with pdfplumber.open(path) as pdf:
                pages = []
                for page in pdf.pages:
                    text = page.extract_text() or ""
                    pages.append(text)
                return "\n\n".join(pages)
        except ImportError:
            try:
                from pypdf import PdfReader
                reader = PdfReader(str(path))
                return "\n\n".join([p.extract_text() for p in reader.pages])
            except ImportError:
                raise ImportError("请安装 pdfplumber 或 pypdf: pip install pdfplumber pypdf")

    def _parse_word(self, path: Path) -> str:
        """Word 解析"""
        try:
            from docx import Document
        except ImportError:
            raise ImportError("请安装 python-docx: pip install python-docx")
        doc = Document(str(path))
        paragraphs = [p.text for p in doc.paragraphs if p.text.strip()]
        # 也处理表格
        for table in doc.tables:
            for row in table.rows:
                for cell in row.cells:
                    if cell.text.strip():
                        paragraphs.append(cell.text)
        return "\n\n".join(paragraphs)

    def _parse_markdown(self, path: Path) -> str:
        """Markdown 解析（保留结构）"""
        return path.read_text(encoding="utf-8")

    def _parse_image(self, path: Path) -> str:
        """图像 OCR（使用多模态 LLM）"""
        from app.llm.factory import get_model_adapter
        import asyncio

        async def _ocr():
            adapter = get_model_adapter()
            return await adapter.parse_document(str(path))

        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                # 在异步上下文中
                return asyncio.create_task(_ocr())
            else:
                return loop.run_until_complete(_ocr())
        except RuntimeError:
            return asyncio.run(_ocr())

    def _split_into_chunks(self, text: str, source: str) -> List[DocumentChunk]:
        """智能切块：基于段落 + 长度控制"""
        # 1. 先按段落切
        paragraphs = [p.strip() for p in re.split(r'\n\s*\n', text) if p.strip()]
        chunks: List[DocumentChunk] = []
        current = ""
        chunk_idx = 0

        for para in paragraphs:
            # 单段超长：按句子切
            if len(para) > self.chunk_size:
                if current:
                    chunks.append(self._make_chunk(current, source, chunk_idx))
                    chunk_idx += 1
                    current = ""
                # 按句子切
                sentences = re.split(r'([。！？；\.!?;])', para)
                buf = ""
                for s in sentences:
                    buf += s
                    if len(buf) >= self.chunk_size:
                        chunks.append(self._make_chunk(buf, source, chunk_idx))
                        chunk_idx += 1
                        buf = ""
                if buf:
                    current = buf
                continue

            # 累积段落
            if len(current) + len(para) > self.chunk_size and current:
                chunks.append(self._make_chunk(current, source, chunk_idx))
                chunk_idx += 1
                # 保留 overlap
                if self.chunk_overlap > 0 and len(current) > self.chunk_overlap:
                    current = current[-self.chunk_overlap:] + "\n\n" + para
                else:
                    current = para
            else:
                current = current + "\n\n" + para if current else para

        if current:
            chunks.append(self._make_chunk(current, source, chunk_idx))
            chunk_idx += 1

        return chunks

    def _make_chunk(self, content: str, source: str, idx: int) -> DocumentChunk:
        """构造一个分块"""
        return DocumentChunk(
            content=content.strip(),
            metadata={
                "source": source,
                "chunk_index": idx,
                "length": len(content),
            }
        )


def parse_document(file_path: str) -> List[DocumentChunk]:
    """便捷函数"""
    parser = DocumentParser()
    return parser.parse(file_path)
