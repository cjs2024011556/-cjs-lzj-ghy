"""
文档解析器单元测试
"""
import pytest
from pathlib import Path

from app.services.document_parser import DocumentParser


class TestDocumentParser:
    def setup_method(self):
        self.parser = DocumentParser(chunk_size=200, chunk_overlap=20)

    def test_parse_markdown(self, sample_data_dir):
        md_file = sample_data_dir / "manuals" / "液压系统检修手册.md"
        if not md_file.exists():
            pytest.skip("样例文件不存在")

        chunks = self.parser.parse(str(md_file))
        assert len(chunks) > 0
        assert all(c.content for c in chunks)
        # 检查元数据
        for chunk in chunks:
            assert "source" in chunk.metadata
            assert "chunk_index" in chunk.metadata

    def test_parse_nonexistent_file(self):
        with pytest.raises(FileNotFoundError):
            self.parser.parse("/nonexistent/file.md")

    def test_parse_unsupported_format(self, tmp_path):
        f = tmp_path / "test.xyz"
        f.write_text("test")
        with pytest.raises(ValueError):
            self.parser.parse(str(f))

    def test_chunk_size(self):
        """分块大小控制"""
        long_text = "这是测试句子。" * 200  # 600 字符
        chunks = self.parser._split_into_chunks(long_text, source="test")
        for chunk in chunks:
            # 块大小不应远超 chunk_size + overlap
            assert len(chunk.content) <= self.parser.chunk_size + self.parser.chunk_overlap + 100
