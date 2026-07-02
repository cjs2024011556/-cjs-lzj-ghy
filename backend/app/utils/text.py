"""
文本工具：关键词提取（中文滑窗 + 标点切分）
- 被 _keyword_fallback 和未来其他模块共用
"""
import re
from typing import List, Set


# 标点切分 regex（中文全角 + ASCII 标点 + 空格）
_DELIMITER_RE = re.compile(
    r'[\s,，、。？?！!；;：（）()【】\[\]\\/\\\.\-]+'
)

# 标点 + 非中文英数字清理 regex（用于滑窗）
_NON_CN_RE = re.compile(r'[^一-鿿0-9a-zA-Z]+')

# 至少含一个中文
_HAS_CN_RE = re.compile(r'[一-鿟]')


def extract_keywords(query: str, window_sizes: tuple = (2, 3, 4)) -> List[str]:
    """提取检索关键词（中文 2-4 字滑窗 + 标点切分）

    例：
      "焊接机器人飞溅大怎么处理？" →
      ['焊接', '接机', '机器人', '飞溅', '怎么处理', '焊接机器人', '接机器人', '机器人飞', '人飞溅', ...]

    Args:
        query: 用户原始查询
        window_sizes: 滑窗长度元组

    Returns:
        关键词列表（去重）
    """
    keywords: Set[str] = set()

    # 1) 标点切分（保留完整词）
    for w in _DELIMITER_RE.split(query):
        if len(w) >= 2:
            keywords.add(w)

    # 2) 中文滑窗（按 2-4 字生成子串）
    clean_q = _NON_CN_RE.sub('', query)
    for n in window_sizes:
        if len(clean_q) < n:
            continue
        for i in range(len(clean_q) - n + 1):
            sub = clean_q[i:i + n]
            if _HAS_CN_RE.search(sub):
                keywords.add(sub)

    return list(keywords)
