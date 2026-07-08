"""
PDF-A 单元测试：pdf_loader / structure_detector / document_parser 升级版

覆盖：
1. pdf_loader.PageDoc dataclass
2. structure_detector 标题识别（中文/数字/英文）
3. document_parser 新 metadata 字段（PDF-A.5 透传）
4. vector_indexer 新 schema 字段
"""
import pytest
from pathlib import Path

from app.services.pdf_loader import (
    PageDoc, PdfplumberPdfLoader, load_pdf_pages,
)
from app.services.structure_detector import (
    Section, StructureDetector, OutlineItem, TableDigest,
    RE_CHAPTER_CN, RE_NUMBERED, RE_ALL_CAPS_EN,
)
from app.services.document_parser import DocumentParser, DocumentChunk


# ============================================================
# pdf_loader 单元测试
# ============================================================
class TestPdfLoaderCore:
    def test_page_doc_dataclass(self):
        """PageDoc 基本属性"""
        p = PageDoc(
            page_number=1,
            text="hello world",
            body_text="hello world",
            header_text="",
            footer_text="",
            tables=[],
            body_font_size=11.0,
            is_likely_scanned=False,
        )
        assert p.page_number == 1
        assert p.body_text == "hello world"
        assert p.tables == []
        assert p.is_likely_scanned is False
        p_dict = p.to_dict()
        assert "page_number" in p_dict
        assert "is_likely_scanned" in p_dict

    def test_loader_raises_on_missing(self, tmp_path):
        """不存在的 PDF → FileNotFoundError"""
        with pytest.raises(FileNotFoundError):
            PdfplumberPdfLoader().load(tmp_path / "nope.pdf")

    def test_table_to_markdown(self):
        """table_to_markdown 序列化"""
        table = [["序号", "现象", "处置"], ["1", "温度高", "降速"], ["2", "异响", "停车"]]
        md = PdfplumberPdfLoader.table_to_markdown(table)
        assert "| 序号 | 现象 | 处置 |" in md
        assert "| --- | --- | --- |" in md
        assert "| 1 | 温度高 | 降速 |" in md
        # 列数对不齐：补空列
        ragged = [["a", "b", "c"], ["x", "y"]]
        md2 = PdfplumberPdfLoader.table_to_markdown(ragged)
        assert "| x | y |  |" in md2


# ============================================================
# structure_detector 单元测试
# ============================================================
class TestStructureDetectorCore:
    def test_chapter_pattern_cn(self):
        """中文「第 X 章 / 节」应被识别为标题"""
        from app.services.structure_detector import RE_CHAPTER_CN
        assert RE_CHAPTER_CN.match("第3章 液压系统故障")
        assert RE_CHAPTER_CN.match("第 5 节 油温异常")
        assert RE_CHAPTER_CN.match("第一章 概述")
        assert not RE_CHAPTER_CN.match("这是普通段落不是标题")

    def test_numbered_pattern(self):
        """数字编号（1., 1.2.3）应被识别为标题"""
        from app.services.structure_detector import RE_NUMBERED
        assert RE_NUMBERED.match("1. 概述")
        assert RE_NUMBERED.match("1.2.3 油温诊断")
        assert not RE_NUMBERED.match("这是正文，不是标题")

    def test_all_caps_pattern(self):
        """全大写英文标题"""
        from app.services.structure_detector import RE_ALL_CAPS_EN
        assert RE_ALL_CAPS_EN.match("INTRODUCTION")
        assert RE_ALL_CAPS_EN.match("SAFETY PRECAUTIONS")
        assert not RE_ALL_CAPS_EN.match("Mixed Case Title")
        assert not RE_ALL_CAPS_EN.match("CHAPTER 1: TOO LONG TO BE ALL CAPS LONGER LINE")

    def test_detect_synthetic_pages(self):
        """用合成 PageDoc 喂入 detect()"""
        pages = [
            PageDoc(
                page_number=1,
                text="第1章 系统概述\n\n本章介绍工业机器人常见故障及处理流程。",
                body_text="第1章 系统概述\n\n本章介绍工业机器人常见故障及处理流程。",
                tables=[],
                body_font_size=11.0,
            ),
            PageDoc(
                page_number=2,
                text="1.1 故障分类\n\n按故障部位分类。",
                body_text="1.1 故障分类\n\n按故障部位分类。",
                tables=[],
                body_font_size=11.0,
            ),
            PageDoc(
                page_number=3,
                text="常见故障\n\n- 油温高\n- 异响",
                body_text="常见故障\n\n- 油温高\n- 异响",
                tables=[],
                body_font_size=11.0,
            ),
        ]
        detector = StructureDetector()
        sections = detector.detect(pages)
        # 至少应识别 2 个标题
        headings = [s for s in sections if s.level >= 1]
        assert len(headings) >= 2
        # 第一个标题应是「第1章」
        assert "系统概述" in headings[0].title or "第1章" in headings[0].title
        # 后续可构建大纲
        outline = detector.build_outline(sections)
        assert isinstance(outline, list)

    def test_detect_with_table(self):
        """带表格的 PageDoc 应被识别为表格摘要"""
        pages = [
            PageDoc(
                page_number=2,
                text="数据表\n\n表内容: 见下",
                body_text="数据表\n\n表内容: 见下",
                tables=[[["序号", "现象"], ["1", "温度高"], ["2", "异响"]]],
                body_font_size=11.0,
            ),
        ]
        detector = StructureDetector()
        sections = detector.detect(pages)
        digests = detector.build_tables_digest(sections)
        assert len(digests) == 1
        assert digests[0].page == 2
        assert digests[0].rows == 3
        assert digests[0].cols == 2


# ============================================================
# document_parser 新 metadata 测试
# ============================================================
class TestDocumentParserMetadata:
    def test_make_chunk_includes_all_structured_fields(self):
        """_make_chunk 包含聚群 A 8 字段"""
        parser = DocumentParser()
        chunk = parser._make_chunk(
            content="测试内容",
            source="test.pdf",
            idx=0,
            page_number=12,
            page_end=14,
            chapter="第3章 液压",
            section_title="3.2 油温异常",
            section_type="text",
            section_level=2,
            doc_id="abc123",
        )
        m = chunk.metadata
        # 全部聚群 A 字段
        for key in ("page_number", "page_end", "chapter", "section_title",
                    "section_type", "section_level", "doc_id", "keywords"):
            assert key in m, f"缺失字段 {key}"
        assert m["page_number"] == 12
        assert m["page_end"] == 14
        assert m["section_type"] == "text"
        assert m["section_level"] == 2

    def test_make_chunk_table_type(self):
        """表格 chunk 标记 section_type=table"""
        parser = DocumentParser()
        chunk = parser._make_chunk(
            content="| A | B |\n|---|---|\n| 1 | 2 |",
            source="x.pdf",
            idx=0,
            section_type="table",
        )
        assert chunk.metadata["section_type"] == "table"

    def test_make_chunk_heading_type(self):
        """heading chunk 标记"""
        parser = DocumentParser()
        chunk = parser._make_chunk(
            content="第3章 液压系统",
            source="x.pdf",
            idx=0,
            section_type="heading",
            section_level=1,
        )
        assert chunk.metadata["section_level"] == 1
        assert chunk.metadata["section_type"] == "heading"

    def test_keywords_extraction_works(self):
        """_extract_keywords 不报错"""
        result = DocumentParser._extract_keywords(
            "液压系统故障诊断与维修流程",
            topk=5
        )
        # 即便 jieba 不在，最多返回前 60 字符
        assert isinstance(result, str)
        assert len(result) >= 0

    def test_old_text_split_still_works(self):
        """旧版 _split_into_chunks 兼容非 PDF 路径"""
        parser = DocumentParser(chunk_size=100, chunk_overlap=10)
        text = "# 标题1\n\n正文段落1。" * 20
        chunks = parser._split_into_chunks(text, source="test.md")
        assert len(chunks) > 0
        # 旧字段保留
        for c in chunks:
            assert "source" in c.metadata
            assert "chunk_index" in c.metadata
            assert "length" in c.metadata


# ============================================================
# vector_indexer 新 schema 字段
# ============================================================
class TestVectorIndexerSchemaFields:
    def test_expected_fields_completeness(self):
        """EXPECTED_FIELDS 必须包含全部聚群 A 字段"""
        from app.services.vector_indexer import EXPECTED_FIELDS
        required = {
            "page_number", "page_end", "chapter", "section_title",
            "section_type", "section_level", "doc_id", "keywords",
        }
        assert required.issubset(EXPECTED_FIELDS), \
            f"缺失字段: {required - EXPECTED_FIELDS}"

    def test_extract_field_names(self):
        """_extract_field_names 从 Milvus desc 中提取字段名"""
        from app.services.vector_indexer import MilvusIndexer
        desc = {
            "fields": [
                {"name": "id", "type": {"params": {}}},
                {"name": "page_number", "type": {"params": {}}},
                {"name": "chapter", "type": {"params": {}}},
            ]
        }
        names = MilvusIndexer._extract_field_names(desc)
        assert "id" in names
        assert "page_number" in names
        assert "chapter" in names


# ============================================================
# Pipeline 集成测试（用真实 markdown 文件）
# ============================================================
class TestPipelineMarkdownFallback:
    def test_markdown_uses_old_path(self, tmp_path):
        """MD 文件走旧路径，metadata 字段齐全（page_number=0、doc_id=md:xxx）"""
        md = tmp_path / "test手册.md"
        md.write_text(
            "# 第一章 概述\n\n这是介绍内容。\n\n## 1.1 背景\n\n这是正文。",
            encoding="utf-8",
        )
        parser = DocumentParser()
        chunks = parser.parse(str(md))
        assert len(chunks) > 0
        for c in chunks:
            # 字段全部存在（即便空值）
            assert "page_number" in c.metadata
            assert "section_title" in c.metadata
            assert "doc_id" in c.metadata
            # MD 路径 page_number 应为 0（PDF-A.3 兼容）
            assert c.metadata["page_number"] == 0


# ============================================================
# 模块导入测试
# ============================================================
def test_imports_no_circular():
    """确保新模块可正常导入"""
    from app.services.pdf_loader import PdfplumberPdfLoader
    from app.services.structure_detector import StructureDetector
    from app.services.document_parser import DocumentParser
    from app.services.vector_indexer import MilvusIndexer
    assert PdfplumberPdfLoader is not None
    assert StructureDetector is not None
    assert DocumentParser is not None
    assert MilvusIndexer is not None


# ============================================================
# 聚群 B 测试：page_renderer / image_describer / VL 集成
# ============================================================
class TestPageRenderer:
    def test_renderer_imports(self):
        """pymupdf 已装 + PageRenderer 可实例化"""
        from app.services.page_renderer import PageRenderer, _HAS_PYMUPDF
        assert _HAS_PYMUPDF is True
        r = PageRenderer(dpi=150)
        assert r.dpi == 150

    def test_render_synthetic_pdf(self, tmp_path):
        """合成 2 页 PDF → 渲染第 1 页 → 拿到 PNG bytes"""
        import fitz
        from app.services.page_renderer import PageRenderer

        pdf_path = tmp_path / "_test.pdf"
        doc = fitz.open()
        for i in range(2):
            p = doc.new_page()
            p.insert_text((50, 50), f"Page {i+1} content")
        doc.save(str(pdf_path))
        doc.close()

        r = PageRenderer(dpi=120)
        assert r.get_page_count(str(pdf_path)) == 2

        png = r.render_page(str(pdf_path), 1)
        assert isinstance(png, bytes)
        assert png.startswith(b"\x89PNG\r\n\x1a\n")  # PNG 头
        assert len(png) > 1000

    def test_render_cache_hit(self, tmp_path):
        """同页重复渲染 → 缓存命中（字节完全一致）"""
        import fitz
        from app.services.page_renderer import PageRenderer

        pdf_path = tmp_path / "_test.pdf"
        doc = fitz.open()
        doc.new_page().insert_text((50, 50), "cache test")
        doc.save(str(pdf_path))
        doc.close()

        r = PageRenderer(dpi=100)
        png1 = r.render_page(str(pdf_path), 1)
        png2 = r.render_page(str(pdf_path), 1)
        assert png1 == png2  # 缓存命中 → 字节一致


class TestImageDescriber:
    def test_image_description_dataclass(self):
        """ImageDescription 数据类 + chunk metadata 转换"""
        from app.services.image_describer import ImageDescription
        d = ImageDescription(
            description="液压回路图",
            facts=["油压上限 25MPa", "电机 7.5kW"],
            page_number=23,
        )
        assert d.is_empty() is False
        meta = d.as_chunk_metadata()
        assert "image_description" in meta
        assert "image_facts" in meta
        assert "25MPa" in meta["image_facts"]

    def test_image_description_empty(self):
        """空 description 检测"""
        from app.services.image_describer import ImageDescription
        d = ImageDescription()
        assert d.is_empty() is True

    def test_parse_response_valid_json(self):
        """VL 标准 JSON 响应解析"""
        from app.services.image_describer import _parse_response
        content = '{"description": "电路图", "facts": ["U=220V", "I=5A"]}'
        d = _parse_response(content)
        assert d.description == "电路图"
        assert d.facts == ["U=220V", "I=5A"]

    def test_parse_response_markdown_wrapped(self):
        """VL 响应带 ```json 包裹时也能解析"""
        from app.services.image_describer import _parse_response
        content = '```json\n{"description": "图A", "facts": ["a", "b"]}\n```'
        d = _parse_response(content)
        assert d.description == "图A"
        assert d.facts == ["a", "b"]

    def test_parse_response_fallback(self):
        """非 JSON 时按行号 fallback 提 facts"""
        from app.services.image_describer import _parse_response
        content = "1. 油温 80°C\n2. 油压 25MPa\n3. 流量 30L/min"
        d = _parse_response(content)
        # fallback 应至少提取 1 条 fact
        assert len(d.facts) >= 1

    def test_mock_describer_caches(self):
        """MockImageDescriber 缓存机制"""
        import asyncio
        from app.services.image_describer import MockImageDescriber, clear_cache
        clear_cache()

        async def t():
            mock = MockImageDescriber(
                mock_description="mock 描述",
                mock_facts=["fact1", "fact2"],
            )
            png = b"fake_png_1"
            r1 = await mock.describe(png, page_number=3)
            assert r1.description == "mock 描述"
            assert r1.cached is False

            r2 = await mock.describe(png, page_number=3)
            assert r2.cached is True  # 二次访问命中缓存
        asyncio.run(t())


class TestDocumentParserVLPipeline:
    def test_make_chunk_accepts_vl_fields(self):
        """_make_chunk 支持 image_description / image_facts 参数"""
        parser = DocumentParser()
        chunk = parser._make_chunk(
            content="x",
            source="x.pdf",
            idx=0,
            image_description="液压回路图",
            image_facts="油压25MPa,电机7.5kW",
        )
        assert chunk.metadata["image_description"] == "液压回路图"
        assert "25MPa" in chunk.metadata["image_facts"]

    def test_enrich_chunks_with_vl_skips_normal_pages(self, tmp_path):
        """非扫描页（文本够长）应跳过 VL"""
        import asyncio
        from app.services.document_parser import DocumentParser
        from app.services.image_describer import MockImageDescriber

        # 合成 1 页有内容的 PDF
        import fitz
        pdf_path = tmp_path / "_normal.pdf"
        doc = fitz.open()
        p = doc.new_page()
        p.insert_text((50, 50), "正常文字页，含有大量关于液压系统的中文描述内容。" * 5)
        doc.save(str(pdf_path))
        doc.close()

        async def t():
            parser = DocumentParser()
            chunks = parser._parse_pdf_structured(pdf_path)
            assert len(chunks) > 0
            # 文本够长 → 不触发 VL
            mock = MockImageDescriber()
            result = await parser._enrich_chunks_with_vl(chunks, pdf_path, describer=mock)
            for c in result:
                assert c.metadata.get("image_description", "") == ""
        asyncio.run(t())

    def test_enrich_chunks_triggers_vl_on_scanned(self, tmp_path):
        """扫描页（短文本 + 图）应触发 VL 并填充字段"""
        import asyncio
        import fitz
        from app.services.document_parser import DocumentParser
        from app.services.image_describer import MockImageDescriber

        # 合成 1 页极短文本 + 1 张大图（模拟扫描）
        pdf_path = tmp_path / "_scanned.pdf"
        doc = fitz.open()
        p = doc.new_page()
        # 在页面中央放一个简单的矩形作为"图"
        p.draw_rect((50, 50, 300, 200), color=(0, 0, 0))
        p.insert_text((50, 250), "图")  # 极短文字
        doc.save(str(pdf_path))
        doc.close()

        async def t():
            parser = DocumentParser()
            chunks = parser._parse_pdf_structured(pdf_path)
            mock = MockImageDescriber(
                mock_description="扫描的故障图",
                mock_facts=["报警 E001", "油温高"],
            )
            result = await parser._enrich_chunks_with_vl(
                chunks, pdf_path,
                describer=mock,
                trigger_on_scanned=True,
                vl_dpi=100,
            )
            # 至少有一个 chunk 被 VL 增强
            enriched = [c for c in result if c.metadata.get("image_description")]
            assert len(enriched) >= 1
            assert enriched[0].metadata["image_description"] == "扫描的故障图"
        asyncio.run(t())


class TestVectorIndexerSchemaBFields:
    def test_expected_fields_has_image_description(self):
        """EXPECTED_FIELDS 必须含聚群 B 2 字段"""
        from app.services.vector_indexer import EXPECTED_FIELDS
        assert "image_description" in EXPECTED_FIELDS
        assert "image_facts" in EXPECTED_FIELDS

    def test_total_field_count_19(self):
        """EXPECTED_FIELDS 共 19 字段（17+2）"""
        from app.services.vector_indexer import EXPECTED_FIELDS
        assert len(EXPECTED_FIELDS) == 19


class TestAPIModelsBFields:
    def test_retrieval_hit_has_vl_fields(self):
        """RetrievalHit Pydantic 加 image_description/image_facts"""
        try:
            from app.api.v1.retrieval import RetrievalHit
        except ImportError as e:
            pytest.skip(f"跳过（依赖未装: {e}）")
        h = RetrievalHit(
            chunk_id="x", content="y", source="z", doc_type="manual",
            equipment_type="", equipment_model="", score=0.5, chunk_index=0,
            image_description="desc", image_facts="fact1,fact2",
        )
        assert h.image_description == "desc"
        assert h.image_facts == "fact1,fact2"

    def test_chat_source_has_vl_fields(self):
        """ChatSource Pydantic 加 image_description/image_facts"""
        try:
            from app.api.v1.chat import ChatSource
        except ImportError as e:
            pytest.skip(f"跳过（依赖未装: {e}）")
        s = ChatSource(
            chunk_id="x", content="y", source="z", score=0.5,
            image_description="d", image_facts="f",
        )
        assert s.image_description == "d"


# ============================================================
# 聚群 C 测试：tools / BM25 / ReAct / eval
# ============================================================
class TestToolsFramework:
    def test_base_tool_to_openai_schema(self):
        """BaseTool 生成 OpenAI function calling 格式"""
        from app.services.tools import BaseTool
        class MyTool(BaseTool):
            name = "my_tool"
            description = "test"
            parameters = {"type": "object", "properties": {"q": {"type": "string"}}, "required": ["q"]}
            async def __call__(self, **kw):
                return "ok"
        t = MyTool()
        schema = t.to_openai_schema()
        assert schema["type"] == "function"
        assert schema["function"]["name"] == "my_tool"
        assert "q" in schema["function"]["parameters"]["properties"]

    def test_registry_register_and_execute(self):
        """注册表添加/查询/执行工具"""
        from app.services.tools import ToolRegistry, BaseTool
        class EchoTool(BaseTool):
            name = "echo"
            description = "echo input"
            parameters = {"type": "object", "properties": {"x": {"type": "string"}}, "required": ["x"]}
            async def __call__(self, x: str):
                return f"echo: {x}"
        reg = ToolRegistry()
        reg.register(EchoTool())
        assert "echo" in reg.list_names()
        # 同步执行（asyncio.run 由 pytest 异步 fixture 处理）
        import asyncio
        result = asyncio.run(reg.execute("echo", {"x": "hi"}))
        assert result["ok"] is True
        assert result["result"] == "echo: hi"

    def test_registry_unknown_tool(self):
        """执行未注册工具 → 友好错误"""
        from app.services.tools import ToolRegistry
        reg = ToolRegistry()
        import asyncio
        result = asyncio.run(reg.execute("not_exists", {}))
        assert result["ok"] is False
        assert "未注册" in result["error"]

    def test_default_registry_has_4_tools(self):
        """默认注册表含 4 工具（聚群 C 工具集）"""
        from app.services.tools import get_default_registry
        reg = get_default_registry()
        names = set(reg.list_names())
        assert "search_kb" in names
        assert "lookup_chunk" in names
        assert "describe_image" in names
        assert "query_graph" in names


class TestBM25Indexer:
    def test_bm25_search_basic(self):
        """BM25 基本检索：精确关键词命中分数 > 0"""
        from app.services.bm25_indexer import BM25Indexer
        idx = BM25Indexer()
        idx.add_chunks([
            {"chunk_id": "c1", "content": "液压系统油温过高可能导致密封损坏", "source": "m1"},
            {"chunk_id": "c2", "content": "电机轴承温度报警 E0123", "source": "m2"},
            {"chunk_id": "c3", "content": "更换周期 2000 小时", "source": "sop1"},
        ])
        results = idx.search("油温过高", top_k=3)
        assert len(results) > 0
        assert results[0]["chunk_id"] == "c1"

    def test_bm25_no_match(self):
        """无命中关键词 → 空结果"""
        from app.services.bm25_indexer import BM25Indexer
        idx = BM25Indexer()
        idx.add_chunks([{"chunk_id": "c1", "content": "液压系统"}])
        results = idx.search("完全不相关的关键词xyz123", top_k=3)
        assert results == []

    def test_bm25_filter(self):
        """filter_fn 过滤"""
        from app.services.bm25_indexer import BM25Indexer
        idx = BM25Indexer()
        idx.add_chunks([
            {"chunk_id": "c1", "content": "液压油温", "source": "m1"},
            {"chunk_id": "c2", "content": "油温异常", "source": "sop1"},
        ])
        results = idx.search("油温", top_k=3, filter_fn=lambda m: m["source"] == "m1")
        assert all(r["source"] == "m1" for r in results)


class TestReActAgent:
    def test_agent_event_dataclass(self):
        """AgentEvent 数据类"""
        from app.services.agent_service import AgentEvent
        ev = AgentEvent("tool_call", {"name": "search_kb", "id": "t1"})
        d = ev.to_dict()
        assert d["type"] == "tool_call"
        assert d["name"] == "search_kb"
        assert d["id"] == "t1"

    def test_agent_react_loop_mock(self):
        """ReAct 单步循环：mock LLM 返回 tool_call + 后续 content"""
        # 使用直接文件 import 绕开 app.llm 包级 dashscope 依赖
        import importlib.util
        spec = importlib.util.spec_from_file_location("_llm_base", "app/llm/base.py")
        llm_base = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(llm_base)
        ChatResponse = llm_base.ChatResponse
        ToolCall = llm_base.ToolCall

        from app.services.agent_service import AgentService
        from app.services.tools import get_default_registry
        from app.services.tools.kb_tools import SearchKBTool

        class MockAdapter:
            model_name = "mock"
            def __init__(self):
                self.call_count = 0
            async def chat(self, request):
                self.call_count += 1
                has_tool = any(m.role.value == "tool" for m in request.messages)
                if not has_tool and self.call_count == 1:
                    return ChatResponse(
                        content="让我查",
                        model="mock",
                        tool_calls=[ToolCall(id="t1", name="search_kb", arguments={"query": "电机"})],
                    )
                return ChatResponse(content="电机过热是轴承问题", model="mock")

        class FakeSearch(SearchKBTool):
            async def __call__(self, query, **kw):
                return {"hits": [{"content": "mock"}]}

        reg = get_default_registry()
        for n in ["search_kb", "lookup_chunk", "describe_image", "query_graph"]:
            reg.unregister(n)
        reg.register(FakeSearch())

        import asyncio
        async def t():
            agent = AgentService(registry=reg, max_steps=3)
            mock = MockAdapter()
            events = []
            async for ev in agent.run("电机过热", adapter=mock):
                events.append(ev)
            types = [e.type for e in events]
            assert "tool_call" in types
            assert "tool_result" in types
            assert "answer" in types
            assert "done" in types
        asyncio.run(t())

    def test_agent_loop_detection(self):
        """循环检测：3 次相同 tool_call → 终止"""
        import importlib.util
        spec = importlib.util.spec_from_file_location("_llm_base", "app/llm/base.py")
        llm_base = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(llm_base)
        ChatResponse = llm_base.ChatResponse
        ToolCall = llm_base.ToolCall

        from app.services.agent_service import AgentService
        from app.services.tools import get_default_registry
        from app.services.tools.kb_tools import SearchKBTool

        class LoopAdapter:
            model_name = "loop"
            async def chat(self, request):
                return ChatResponse(
                    content="查",
                    model="loop",
                    tool_calls=[ToolCall(id="t1", name="search_kb", arguments={"query": "x"})],
                )

        class FakeSearch(SearchKBTool):
            async def __call__(self, query, **kw):
                return {}

        reg = get_default_registry()
        for n in ["search_kb", "lookup_chunk", "describe_image", "query_graph"]:
            reg.unregister(n)
        reg.register(FakeSearch())

        import asyncio
        async def t():
            agent = AgentService(registry=reg, max_steps=5)
            events = []
            async for ev in agent.run("loop", adapter=LoopAdapter()):
                events.append(ev)
            # 应有 error + done（loop_detected=True）
            done_ev = next((e for e in events if e.type == "done"), None)
            assert done_ev is not None
            assert done_ev.data.get("loop_detected") is True
        asyncio.run(t())


class TestEvalFramework:
    def test_hit_rate_at_k(self):
        from app.services.eval.metrics import hit_rate_at_k
        r = [[1, 0], [0, 0], [1, 1]]
        assert hit_rate_at_k(r) == 2/3  # 2/3 题有命中

    def test_mrr(self):
        from app.services.eval.metrics import mrr
        r = [[1, 0, 0], [0, 1, 0], [0, 0, 0]]
        # 1.0 + 0.5 + 0 = 1.5 / 3 = 0.5
        assert abs(mrr(r) - 0.5) < 0.01

    def test_ndcg_perfect(self):
        from app.services.eval.metrics import ndcg_at_k
        r = [[3, 2, 1, 0, 0]]  # 完美排序
        assert abs(ndcg_at_k(r, k=5) - 1.0) < 0.01

    def test_citation_accuracy(self):
        from app.services.eval.metrics import citation_accuracy
        retrieved = [[12, 23], [10, 11]]
        gold = [[12, 13], [12]]
        # 第 1 题命中 12 ✓, 第 2 题未命中 12 ✗ → 1/2
        assert citation_accuracy(retrieved, gold) == 0.5

    def test_gold_set_load(self):
        """黄金集加载（默认 5 题）"""
        from app.services.eval.gold_set import load_gold_set, validate_gold_set
        gold = load_gold_set()
        assert len(gold) >= 5
        for g in gold:
            assert "query" in g
        errs = validate_gold_set(gold)
        assert errs == []  # 默认集合法

    def test_eval_runner_with_mock(self):
        """用 mock 检索跑评测"""
        import asyncio
        from app.services.eval.runner import EvalRunner

        async def mock_retrieval(query, top_k):
            # 简单 mock：query 命中关键词 → 返回高相关
            relevant = "电机" in query or "油温" in query
            if relevant:
                return [{
                    "chunk_id": f"c_{query}",
                    "content": "mock content",
                    "source": "manual",
                    "score": 0.9,
                    "page_number": 12,
                }]
            return []

        async def t():
            runner = EvalRunner(
                retrieval_fn=mock_retrieval,
                gold_set=[
                    {"query": "电机过热", "gold_chunk_ids": ["c_电机过热"], "gold_pages": [12]},
                    {"query": "完全无关的问题", "gold_chunk_ids": [], "gold_pages": []},
                ],
            )
            report = await runner.run(top_k=3)
            assert report["total"] == 2
            assert report["metrics"]["hit_rate_at_5"] == 0.5  # 1/2 命中
        asyncio.run(t())
