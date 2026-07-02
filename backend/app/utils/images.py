"""
图像处理工具
"""
import base64
from pathlib import Path
from typing import Final

# 通用 MIME 映射（多模态 LLM 支持的图像格式）
_IMAGE_MIMES: Final[dict[str, str]] = {
    "jpg": "image/jpeg",
    "jpeg": "image/jpeg",
    "png": "image/png",
    "bmp": "image/bmp",
    "webp": "image/webp",
    "gif": "image/gif",
}


def encode_image_data_uri(image_path: str | Path) -> str:
    """将图像文件编码为 base64 data URI

    例: data:image/jpeg;base64,/9j/4AAQ...

    抛出:
        FileNotFoundError: 文件不存在
        ValueError: 不支持的图像格式
    """
    path = Path(image_path)
    if not path.exists():
        raise FileNotFoundError(f"图像文件不存在: {image_path}")

    suffix = path.suffix.lower().lstrip(".")
    mime = _IMAGE_MIMES.get(suffix)
    if mime is None:
        raise ValueError(f"不支持的图像格式: .{suffix}")

    encoded = base64.b64encode(path.read_bytes()).decode("utf-8")
    return f"data:{mime};base64,{encoded}"
