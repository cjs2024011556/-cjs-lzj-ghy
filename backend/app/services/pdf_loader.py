"""
PDF 页级加载器 — 保留页边界 / 表格 / 页眉页脚

输入：PDF 文件路径
输出：List[PageDoc]，每页包含正文 + 表格 + 元数据，供后续 StructureDetector 使用

聚群 A 阶段产物：只做 PDF（其它格式走 document_parser 旧路径）
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from loguru import logger


@dataclass
class PageDoc:
    """单页文档（PDF 结构化解析的中介对象）"""
    page_number: int                       # 1-based
    text: str                              # 抽取出来的全文（含头部尾部）
    body_text: str                         # 去掉页眉页脚后的正文
    header_text: str = ""                  # 识别出的页眉
    footer_text: str = ""                  # 识别出的页脚
    tables: List[List[List[str]]] = field(default_factory=list)   # 抽出的表格（嵌套 List）
    font_size_histogram: Dict[float, int] = field(default_factory=dict)  # 字号频次
    body_font_size: float = 11.0           # 估算的正文字号
    is_likely_scanned: bool = False        # 文字极少（扫描件启发）

    def to_dict(self) -> Dict[str, Any]:
        return {
            "page_number": self.page_number,
            "text": self.text,
            "body_text": self.body_text,
            "header_text": self.header_text,
            "footer_text": self.footer_text,
            "tables": self.tables,
            "body_font_size": self.body_font_size,
            "is_likely_scanned": self.is_likely_scanned,
        }


# ============================================================
# 主类
# ============================================================
class PdfplumberPdfLoader:
    """PDF → List[PageDoc]

    Strategy:
    - 用 pdfplumber.open() 逐页
    - 每页调 page.extract_text()，但**额外抽页眉页脚 + 表格**
    - 字号频次统计 → 给 StructureDetector 用
    """

    # 页眉页脚启发式（72 = 1 inch 在 pdfplumber 中）
    HEADER_MARGIN_PX = 60   # 顶部 60px 区域视为页眉
    FOOTER_MARGIN_PX = 60   # 底部 60px 区域视为页脚
    HEADER_FOOTER_FONT_RATIO = 0.85  # 比正文字号 < 85% 才算页眉页脚
    TABLE_TEXT_GAP = '\n| '  # 表格序列化到 markdown 的行前缀

    def __init__(self, min_table_rows: int = 2, min_table_cols: int = 2):
        self.min_table_rows = min_table_rows
        self.min_table_cols = min_table_cols
        self._skipped = False

    def load(self, file_path: str | Path) -> List[PageDoc]:
        """主入口：返回所有页的 PageDoc 列表"""
        path = Path(file_path)
        if not path.exists():
            raise FileNotFoundError(f"PDF 文件不存在: {file_path}")

        try:
            import pdfplumber
        except ImportError as exc:
            raise ImportError("请安装 pdfplumber: pip install pdfplumber") from exc

        # FIX-2026-07: 记住当前路径供 pypdf fallback 使用
        self._current_path = path

        # 解密：若 PDF 已加密，pdfplumber 会自动尝试空密码
        pages: List[PageDoc] = []
        with pdfplumber.open(str(path)) as pdf:
            for idx, page in enumerate(pdf.pages, start=1):
                try:
                    page_doc = self._extract_page(page, idx)
                    pages.append(page_doc)
                except Exception as e:
                    # 单页失败不阻塞整本（工业 PDF 偶有脏页）
                    logger.warning(f"⚠️ 第 {idx} 页解析失败: {e} — 跳过")
                    continue

        logger.info(
            f"📄 PdfplumberPdfLoader 完成 {path.name}: "
            f"{len(pages)} 页, 平均正文 {sum(len(p.body_text) for p in pages) // max(1, len(pages))} 字/页"
        )
        return pages

    # ============================================================
    # 单页内部：提取 / 切分 / 表格识别 / 页眉页脚判定
    # ============================================================
    def _extract_page(self, page, page_num: int) -> PageDoc:
        """单页全流程"""
        # 1. 全文
        full_text = page.extract_text() or ""
        # FIX-2026-07: pdfplumber 对部分 PDF（字符位置有 transform / 负 top）
        # 排序异常时，文本会按字符竖排。需要兜底：用 pypdf 重新提取并对比长度。
        if len(full_text) > 0 and self._looks_broken(full_text):
            logger.debug(
                f"第 {page_num} 页 pdfplumber 文本异常（疑似 transform 问题），"
                f"fallback 到 pypdf"
            )
            fallback = self._extract_text_with_pypdf(page_num)
            if fallback and not self._looks_broken(fallback):
                full_text = fallback

        # 2. 字号直方图（结构化字段，非索引用）
        size_hist = self._build_font_size_histogram(page)

        # 3. 正文字号估测（出现频次最高的字号，且出现 ≥30% 总字）
        body_size = self._estimate_body_font_size(size_hist)

        # 4. 提取表格（pdfplumber.find_tables）
        tables = self._extract_tables(page)

        # 5. 切页眉页脚（按字号 + 顶部/底部区域）
        header_text, footer_text, body_text = self._strip_header_footer(
            page, full_text, body_size
        )

        # 6. 扫描页启发式：body_text 极短但有图
        is_scanned = (
            len(body_text.strip()) < 50 and not tables and self._has_images(page)
        )

        return PageDoc(
            page_number=page_num,
            text=full_text,
            body_text=body_text,
            header_text=header_text,
            footer_text=footer_text,
            tables=tables,
            font_size_histogram=size_hist,
            body_font_size=body_size,
            is_likely_scanned=is_scanned,
        )

    @staticmethod
    def _looks_broken(text: str) -> bool:
        """检测 pdfplumber 文本是否被按字符竖排破坏

        启发：连续超过 8 个单字符「行」+ 中文字符多 + 整体行数过多
        """
        if not text:
            return True
        lines = text.splitlines()
        if len(lines) > 200:  # 行数爆炸 = 排序乱
            single_char_lines = sum(1 for l in lines if len(l.strip()) == 1)
            if single_char_lines > 20 and single_char_lines / len(lines) > 0.10:
                return True
        return False

    def _extract_text_with_pypdf(self, page_num: int) -> str:
        """用 pypdf 提取单页文本（兜底）"""
        try:
            from pypdf import PdfReader
            if not hasattr(self, "_pypdf_reader"):
                import os
                self._pypdf_reader = PdfReader(os.fspath(self._current_path))
            page = self._pypdf_reader.pages[page_num - 1]
            return page.extract_text() or ""
        except Exception as e:
            logger.debug(f"pypdf fallback 失败: {e}")
            return ""

    # ============================================================
    # 表格识别
    # ============================================================
    def _extract_tables(self, page) -> List[List[List[str]]]:
        """用 pdfplumber.find_tables 识别表格

        Returns: List of [ [ ["cell11", "cell12"], ... ] ... ]
        """
        tables_data: List[List[List[str]]] = []
        try:
            found = page.find_tables()
        except Exception as e:
            logger.debug(f"find_tables 失败，回退空: {e}")
            return tables_data

        for t in found:
            try:
                rows = t.extract()
                if not rows:
                    continue
                # 过滤全空行
                rows = [r for r in rows if any(cell and str(cell).strip() for cell in r)]
                # 行数 / 列数 阈值过滤（避免偶发"假表格" — 比如两栏文字流）
                if len(rows) < self.min_table_rows:
                    continue
                if max(len(r) for r in rows) < self.min_table_cols:
                    continue
                # 转 str 化（pdfplumber 可能返回 None）
                normalized = [[str(cell) if cell else "" for cell in row] for row in rows]
                tables_data.append(normalized)
            except Exception as e:
                logger.debug(f"单表提取失败跳过: {e}")
                continue

        return tables_data

    # ============================================================
    # 字号统计
    # ============================================================
    def _build_font_size_histogram(self, page) -> Dict[float, int]:
        """统计 page.chars 里的字号分布"""
        hist: Dict[float, int] = {}
        try:
            chars = page.chars
        except Exception:
            return hist
        for c in chars:
            sz = round(c.get("size", 0), 1)
            if sz <= 0:
                continue
            hist[sz] = hist.get(sz, 0) + 1
        return hist

    def _estimate_body_font_size(self, hist: Dict[float, int]) -> float:
        """取出现频次最高的字号作为 body_size（工业手册通常正文为大字号）"""
        if not hist:
            return 11.0  # 默认 11pt
        # 频次最高的字号
        return max(hist.items(), key=lambda x: x[1])[0]

    # ============================================================
    # 页眉页脚切分
    # ============================================================
    def _strip_header_footer(
        self, page, full_text: str, body_size: float
    ) -> Tuple[str, str, str]:
        """从 full_text 中切出 header / footer / body 三段

        策略：
        - 用 page.chars 按 top0（上边距）划分 header zone vs footer zone vs body zone
        - header/footer 字号必须 < body_size × 0.85
        - 抽出来后从 full_text 里删除（按完整行匹配删除）
        """
        try:
            page_height = page.height
            chars = page.chars
        except Exception:
            return "", "", full_text

        header_chars = []
        footer_chars = []
        body_chars = []
        for c in chars:
            sz = c.get("size", 0)
            top = c.get("top", 0)
            if top < self.HEADER_MARGIN_PX and sz < body_size * self.HEADER_FOOTER_FONT_RATIO:
                header_chars.append(c)
            elif top > page_height - self.FOOTER_MARGIN_PX and sz < body_size * self.HEADER_FOOTER_FONT_RATIO:
                footer_chars.append(c)
            else:
                body_chars.append(c)

        header_text = self._chars_to_line(header_chars).strip()
        footer_text = self._chars_to_line(footer_chars).strip()

        # 从 full_text 中删除 header/footer（按行删除，保留空行结构）
        body_text = full_text
        for hf in (header_text, footer_text):
            if hf:
                # 整行匹配；多行页眉按 \n 切
                for line in hf.splitlines():
                    body_text = body_text.replace(line + "\n", "")
                    body_text = body_text.replace(line, "")

        return header_text, footer_text, body_text.strip()

    def _chars_to_line(self, chars: List[Dict]) -> str:
        """把一组 pdfplumber chars 拼成字符串（按 top 排序，按 x 排序）"""
        if not chars:
            return ""
        # 按行分组（同 top）
        lines: Dict[float, List[Dict]] = {}
        for c in chars:
            top_key = round(c.get("top", 0), 0)
            lines.setdefault(top_key, []).append(c)
        out_lines = []
        for top in sorted(lines.keys()):
            row = sorted(lines[top], key=lambda c: c.get("x0", 0))
            line = "".join(c.get("text", "") for c in row)
            out_lines.append(line)
        return "\n".join(out_lines)

    # ============================================================
    # 扫描件启发
    # ============================================================
    def _has_images(self, page) -> bool:
        try:
            return len(page.images) > 0
        except Exception:
            return False

    # ============================================================
    # 表格 → Markdown 序列化（供 chunk 内容用）
    # ============================================================
    @staticmethod
    def table_to_markdown(table: List[List[str]]) -> str:
        """二维表 → Markdown 表格字符串

        Example:
        | 列1 | 列2 |
        | --- | --- |
        | a   | b   |
        """
        if not table:
            return ""
        rows = [[c.replace("|", "\\|").strip() for c in row] for row in table]
        # 表头：第一行
        header = rows[0]
        sep = ["---"] * len(header)
        body_rows = rows[1:] if len(rows) > 1 else []
        lines = [
            "| " + " | ".join(header) + " |",
            "| " + " | ".join(sep) + " |",
        ]
        for r in body_rows:
            # 补齐列数（避免渲染错位）
            r = r + [""] * (len(header) - len(r))
            lines.append("| " + " | ".join(r) + " |")
        return "\n".join(lines)


# ============================================================
# 便捷函数
# ============================================================
def load_pdf_pages(file_path: str | Path) -> List[PageDoc]:
    """便捷函数"""
    return PdfplumberPdfLoader().load(file_path)
