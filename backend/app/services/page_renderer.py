"""
PDF 页面渲染器 — 把 PDF 页面转 PNG（用于聚群 B 多模态理解）

输入：PDF 文件路径 + 页码
输出：PNG bytes（200 dpi，Jpeg 压缩可选）

聚群 B 用途：
- 扫描页 OCR 兜底（聚群 A 已有 is_likely_scanned 启发）
- 图表页视觉理解（VL 模型解读）
- 缓存：按 (path, mtime, page_num, dpi) 缓存 PNG bytes

为什么选 pymupdf：
- 纯 Python wheel，Windows/Linux/LoongArch 都装得上
- 比 pdf2image 少一个 poppler 依赖
- 速度比 pdfplumber 渲染快 3-5x
"""
from __future__ import annotations

import hashlib
from collections import OrderedDict
from pathlib import Path
from typing import Dict, Optional

from loguru import logger

try:
    import fitz  # pymupdf
    _HAS_PYMUPDF = True
except ImportError:
    _HAS_PYMUPDF = False


# ============================================================
# 缓存（按 (path, mtime, page_num, dpi) → PNG bytes）
# ============================================================
_RENDER_CACHE: "OrderedDict[tuple, bytes]" = OrderedDict()
_CACHE_MAX = 64  # 最多缓存 64 页（每页 ~500KB ≈ 32MB 上限）


def _cache_key(pdf_path: str, mtime: float, page_num: int, dpi: int) -> tuple:
    return (str(Path(pdf_path).resolve()), mtime, page_num, dpi)


def _cache_get(key: tuple) -> Optional[bytes]:
    if key in _RENDER_CACHE:
        _RENDER_CACHE.move_to_end(key)
        return _RENDER_CACHE[key]
    return None


def _cache_put(key: tuple, value: bytes) -> None:
    _RENDER_CACHE[key] = value
    while len(_RENDER_CACHE) > _CACHE_MAX:
        _RENDER_CACHE.popitem(last=False)


def clear_cache() -> None:
    """清空渲染缓存（测试用 / 文档大改时）"""
    _RENDER_CACHE.clear()


# ============================================================
# 主类
# ============================================================
class PageRenderer:
    """PDF → PNG 渲染器

    用法：
        renderer = PageRenderer(dpi=200)
        png_bytes = renderer.render_page("manual.pdf", 23)  # 1-based
        all_pages = renderer.render_all_pages("manual.pdf")
        n = renderer.get_page_count("manual.pdf")
    """

    DEFAULT_DPI = 200  # 工业手册通常 150-200 dpi 即可，超过 300 收益递减

    def __init__(self, dpi: int = DEFAULT_DPI, use_cache: bool = True):
        if not _HAS_PYMUPDF:
            raise ImportError("请安装 pymupdf: pip install pymupdf")
        self.dpi = dpi
        self.zoom = dpi / 72.0  # PDF 内部用 72 dpi 作基准
        self.use_cache = use_cache

    def get_page_count(self, pdf_path: str | Path) -> int:
        """返回 PDF 总页数"""
        path = Path(pdf_path)
        if not path.exists():
            raise FileNotFoundError(f"PDF 文件不存在: {pdf_path}")
        doc = fitz.open(str(path))
        try:
            n = len(doc)
        finally:
            doc.close()
        return n

    def render_page(
        self,
        pdf_path: str | Path,
        page_num: int,
        dpi: Optional[int] = None,
    ) -> bytes:
        """渲染单页为 PNG bytes

        Args:
            pdf_path: PDF 文件路径
            page_num: 1-based 页码
            dpi: 覆盖默认 dpi（None 用 self.dpi）

        Returns:
            PNG 图片 bytes
        """
        path = Path(pdf_path)
        if not path.exists():
            raise FileNotFoundError(f"PDF 文件不存在: {pdf_path}")

        actual_dpi = dpi or self.dpi
        mtime = path.stat().st_mtime
        cache_key = _cache_key(str(path), mtime, page_num, actual_dpi)

        if self.use_cache:
            cached = _cache_get(cache_key)
            if cached is not None:
                return cached

        doc = fitz.open(str(path))
        try:
            if page_num < 1 or page_num > len(doc):
                raise ValueError(f"页码 {page_num} 越界 [1, {len(doc)}]")
            page = doc[page_num - 1]
            mat = fitz.Matrix(actual_dpi / 72.0, actual_dpi / 72.0)
            pix = page.get_pixmap(matrix=mat, alpha=False)
            png_bytes = pix.tobytes("png")
        finally:
            doc.close()

        if self.use_cache:
            _cache_put(cache_key, png_bytes)

        return png_bytes

    def render_all_pages(
        self,
        pdf_path: str | Path,
        dpi: Optional[int] = None,
    ) -> Dict[int, bytes]:
        """一次性渲染所有页（不缓存，因为可能 OOM）

        Returns:
            {page_num: png_bytes}
        """
        path = Path(pdf_path)
        if not path.exists():
            raise FileNotFoundError(f"PDF 文件不存在: {pdf_path}")

        actual_dpi = dpi or self.dpi
        doc = fitz.open(str(path))
        result: Dict[int, bytes] = {}
        try:
            zoom = actual_dpi / 72.0
            mat = fitz.Matrix(zoom, zoom)
            for i in range(len(doc)):
                pix = doc[i].get_pixmap(matrix=mat, alpha=False)
                result[i + 1] = pix.tobytes("png")
        finally:
            doc.close()
        logger.info(
            f"🖼️ PageRenderer: {path.name} 渲染 {len(result)} 页 "
            f"@ {actual_dpi} dpi ({sum(len(v) for v in result.values()) // 1024} KB)"
        )
        return result

    def render_pages(
        self,
        pdf_path: str | Path,
        page_nums: list[int],
        dpi: Optional[int] = None,
    ) -> Dict[int, bytes]:
        """渲染指定页码列表（带缓存）"""
        return {
            n: self.render_page(pdf_path, n, dpi=dpi)
            for n in page_nums
        }


# ============================================================
# 辅助函数
# ============================================================
def hash_png(png_bytes: bytes) -> str:
    """计算 PNG 字节的 SHA-256 哈希（用于 VL 结果缓存）"""
    return hashlib.sha256(png_bytes).hexdigest()[:16]


def encode_png_to_data_uri(png_bytes: bytes) -> str:
    """PNG bytes → base64 data URI（VL 模型调用需要）"""
    import base64
    b64 = base64.b64encode(png_bytes).decode("ascii")
    return f"data:image/png;base64,{b64}"


# ============================================================
# 便捷函数
# ============================================================
def render_pdf_page(pdf_path: str | Path, page_num: int, dpi: int = 200) -> bytes:
    """便捷函数：渲染单页"""
    return PageRenderer(dpi=dpi).render_page(pdf_path, page_num)
