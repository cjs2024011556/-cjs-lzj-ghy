"""
PDF 章节结构识别器

输入：List[PageDoc]（来自 PdfplumberPdfLoader）
输出：List[Section]（按阅读顺序）

聚群 A 阶段产物：
- 字号启发式（最大字号作正文字号，比正文字号显著大即标题）
- 数字模式（1., 1.2.3, §3）
- 中文（第 X 章 / 第 X 节 / 附 X）
- 章节树：H1 + H2 路径作为 chapter 元数据
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from loguru import logger

# 复用 PageDoc（避免反向导入）
from app.services.pdf_loader import PageDoc


# ============================================================
# 数据结构
# ============================================================
@dataclass
class Section:
    """识别出的章节"""
    level: int                                    # 0=body / 1=H1 / 2=H2 / 3=H3
    title: str                                    # 章节标题文本
    chapter: str = ""                             # 父级章节路径（"第3章 液压系统 / 3.2 油温异常"）
    page_start: int = 0                           # 起始页
    page_end: int = 0                             # 终止页
    body_text: str = ""                           # 章节正文（不含标题）
    lines: List[Tuple[int, str]] = field(default_factory=list)  # 原始 (页号, 行)
    tables: List[Tuple[int, List[List[str]]]] = field(default_factory=list)  # (页号, 表)

    @property
    def has_body(self) -> bool:
        return bool(self.body_text.strip())

    @property
    def table_count(self) -> int:
        return len(self.tables)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "level": self.level,
            "title": self.title,
            "chapter": self.chapter,
            "page_start": self.page_start,
            "page_end": self.page_end,
            "has_body": self.has_body,
            "table_count": self.table_count,
        }


@dataclass
class OutlineItem:
    """目录条目（用于 KnowledgeAdmin「目录」Tab）"""
    level: int
    title: str
    page_start: int


@dataclass
class TableDigest:
    """表格摘要（用于 KnowledgeAdmin「表格清单」Tab）"""
    page: int
    rows: int
    cols: int
    preview: str   # 前 100 字符（前 2 行拼接）


# ============================================================
# 标题识别正则
# ============================================================
RE_CHAPTER_CN = re.compile(r'^第\s*[一二三四五六七八九十百千零〇\d]+\s*[章节篇部]\s*[：: \.]*\S+')   # 第3章 / 第 5 节
RE_APPENDIX = re.compile(r'^附\s*[录件]?\s*[A-Za-z零一二三四五六七八九十]?')                    # 附录A
RE_SECTION_SIGN = re.compile(r'^§\s*\d+(\.\d+)*\s+\S')                                        # §3.2 油温
RE_NUMBERED = re.compile(r'^\d+(\.\d+)*\.?\s+\S+')                                            # 1. / 1.2.3 标题
RE_ALL_CAPS_EN = re.compile(r'^[A-Z][A-Z0-9 \-\(\)]{2,79}$')                                # ALL CAPS

CHINESE_NUM_MAP = {
    '一': 1, '二': 2, '三': 3, '四': 4, '五': 5, '六': 6, '七': 7,
    '八': 8, '九': 9, '十': 10, '零': 0, '百': 100, '千': 1000, '〇': 0,
}


# ============================================================
# 主类
# ============================================================
class StructureDetector:
    """章节/标题/层次识别"""

    # 字号启发式阈值：标题字号 > 正文字号 × RATIO
    TITLE_FONT_RATIO = 1.30

    # 标题长度上限（避免把长段落误判成标题）
    TITLE_MAX_LEN = 80

    # 跳过认为是 footer 用的页眉页脚（典型页眉模式：纯数字 / "—X—"）
    RE_HEADER_PATTERNS = [
        re.compile(r'^\s*\d+\s*$'),                    # 单独页码
        re.compile(r'^—\s*\d+\s*—\s*$'),               # "— 12 —"
        re.compile(r'^\s*\d+\s*/\s*\d+\s*$'),          # "12 / 56"
    ]

    def __init__(self, body_font_size_override: Optional[float] = None):
        """
        Args:
            body_font_size_override: 强制使用一个正文字号（忽略 page 统计）
        """
        self.body_font_size_override = body_font_size_override
        # 跨章节上下文
        self._h1_path: List[str] = []   # 当前活跃 H1 栈（支持嵌套后回退）

    # ============================================================
    # 主入口
    # ============================================================
    def detect(self, pages: List[PageDoc]) -> List[Section]:
        """提取章节 + 树状结构

        流程：
        1. 顺序遍历 pages，行级收集
        2. 识别 Title（按多种 heuristic）
        3. 把标题间的行聚成 Section.body_text
        4. 输出：List[Section]
        """
        sections: List[Section] = []
        current_section = Section(level=0, title="(前言)", page_start=1, page_end=1)
        h1_path: List[str] = []

        for page in pages:
            page_num = page.page_number
            body_lines = page.body_text.splitlines() if page.body_text else []

            for raw_line in body_lines:
                line = raw_line.rstrip()
                if not line.strip():
                    continue
                title_info = self._detect_title(line, page.body_font_size)
                if title_info:
                    level, title = title_info
                    # 完成上一节
                    current_section.page_end = page_num - 1 if current_section.page_start else page_num
                    current_section.chapter = self._build_chapter_path(h1_path)
                    if current_section.title or current_section.has_body:
                        sections.append(current_section)

                    # 更新层级栈
                    if level == 1:
                        h1_path = [title]
                    elif level == 2:
                        if len(h1_path) > 1:
                            h1_path = h1_path[:1] + [title]
                        else:
                            h1_path = [title]
                    elif level == 3:
                        # H3 仍归到最近一级父章节下
                        pass

                    current_section = Section(
                        level=level,
                        title=title,
                        page_start=page_num,
                        page_end=page_num,
                        lines=[(page_num, line)],
                    )
                else:
                    # 普通正文行
                    current_section.lines.append((page_num, line))

            # 表格归入当前章节
            for table in page.tables:
                current_section.tables.append((page_num, table))

        # 收尾
        current_section.page_end = pages[-1].page_number if pages else current_section.page_start
        current_section.chapter = self._build_chapter_path(h1_path)
        if current_section.title or current_section.has_body:
            sections.append(current_section)

        # 二次遍历：填正文
        for sec in sections:
            sec.body_text = "\n".join(line for _, line in sec.lines)

        logger.info(
            f"🧭 StructureDetector: 识别 {sum(1 for s in sections if s.level >= 1)} 个标题，"
            f"{len(sections)} 个章节, {sum(s.table_count for s in sections)} 张表"
        )
        return sections

    # ============================================================
    # 标题判定
    # ============================================================
    def _detect_title(
        self, line: str, body_font_size: float
    ) -> Optional[Tuple[int, str]]:
        """识别单行是否为标题

        Returns: (level, title) 或 None
        """
        line_stripped = line.strip()
        if not line_stripped:
            return None
        if len(line_stripped) > self.TITLE_MAX_LEN:
            return None
        # 过滤页眉页脚常见模式
        for pat in self.RE_HEADER_PATTERNS:
            if pat.match(line_stripped):
                return None

        # 1. 中文「第 X 章 / 第 X 节 / 第 X 篇」
        if RE_CHAPTER_CN.match(line_stripped):
            level = self._chapter_level_cn(line_stripped)
            return (level, line_stripped)

        # 2. 附录
        if RE_APPENDIX.match(line_stripped):
            return (1, line_stripped)

        # 3. §3.2 / §3
        if RE_SECTION_SIGN.match(line_stripped):
            return (2, line_stripped)

        # 4. 纯数字编号（1.2.3 等）
        m = RE_NUMBERED.match(line_stripped)
        if m:
            depth = m.group(0).count('.') + (1 if m.group(0)[0].isdigit() else 0)
            # depth=1 → H2, depth≥2 → H3
            level = min(3, max(2, depth + 1))
            return (level, line_stripped)

        # 5. 全大写英文（限制长度 + 80）
        if RE_ALL_CAPS_EN.match(line_stripped) and len(line_stripped) <= 80:
            return (1, line_stripped)

        return None

    def _chapter_level_cn(self, line: str) -> int:
        """根据「第 X 章 / 节 / 篇」识别层级"""
        if '章' in line or '篇' in line or '部' in line:
            return 1
        if '节' in line:
            return 2
        return 2

    def _build_chapter_path(self, h1_path: List[str]) -> str:
        return " / ".join(h1_path)

    # ============================================================
    # 章节统计产物
    # ============================================================
    def build_outline(self, sections: List[Section]) -> List[OutlineItem]:
        """提取大纲（用于 KnowledgeAdmin 目录 Tab）"""
        items: List[OutlineItem] = []
        for sec in sections:
            if sec.level >= 1 and sec.title:
                items.append(OutlineItem(
                    level=sec.level,
                    title=sec.title,
                    page_start=sec.page_start,
                ))
        return items

    def build_tables_digest(
        self, sections: List[Section]
    ) -> List[TableDigest]:
        """提取表格摘要（用于 KnowledgeAdmin 表格清单 Tab）"""
        digests: List[TableDigest] = []
        for sec in sections:
            for page_num, table in sec.tables:
                if not table:
                    continue
                rows = len(table)
                cols = max(len(r) for r in table) if table else 0
                preview_lines = []
                for r in table[:2]:
                    preview_lines.append(" | ".join((c or "")[:30] for c in r))
                preview = "  •  ".join(preview_lines)[:120]
                digests.append(TableDigest(
                    page=page_num, rows=rows, cols=cols, preview=preview
                ))
        return digests


# ============================================================
# 便捷函数
# ============================================================
def detect_structure(pages: List[PageDoc]) -> List[Section]:
    return StructureDetector().detect(pages)
