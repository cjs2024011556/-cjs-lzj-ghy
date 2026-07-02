"""
E2E Test 2: RAG 完整链路 — 上传 → 检索 → 流式回答

核心验证：
1. 上传 MD 后能立即被搜到（关键词 fallback 或 Milvus）
2. sources 排序合理（高分在前）
3. SSE 流式端点输出符合协议（intent → sources → delta... → done）
"""
import io
import json

import pytest

from app.core.config import settings


SKIP_IF_NO_LLM = not settings.CLOUD_LLM.api_key
pytestmark = pytest.mark.skipif(
    SKIP_IF_NO_LLM,
    reason="DASHSCOPE_API_KEY 未配置，跳过 LLM 依赖的 e2e 测试",
)


WELDING_KEYWORDS = ["焊接", "飞溅", "焊接机器人", "焊枪", "保护气体"]


def _has_welding_content(content: str) -> bool:
    """命中判断：内容中至少有 1 个焊接相关关键词"""
    return any(kw in content for kw in WELDING_KEYWORDS)


class TestUploadThenAsk:
    """上传 → 提问 → 命中"""

    def test_md_upload_then_keyword_retrieval(self, client, temp_manuals_dir, sample_md_text):
        # 1. 上传 MD（multipart/form-data）
        md_file = ("焊接机器人手册.md", sample_md_text.encode("utf-8"), "text/markdown")
        r = client.post("/api/v1/knowledge/upload", files={"file": md_file})
        assert r.status_code == 200, r.text
        upload_data = r.json()
        assert upload_data["success"] is True
        assert upload_data["filename"].endswith(".md")
        assert upload_data["section_count"] > 0
        # .md 原生被搜
        assert upload_data["searchable_now"] is True
        # 临时目录里有这个文件
        assert any(p.name.endswith(".md") for p in temp_manuals_dir.iterdir())

        # 2. 立即问焊接问题（不重启服务、不重 build 索引）
        r2 = client.post("/api/v1/chat", json={
            "message": "焊接机器人飞溅大怎么处理",
            "top_k": 5,
        })
        assert r2.status_code == 200, r2.text
        data = r2.json()

        # 3. 验证命中
        assert data["intent"] == "maintenance"
        assert data["used_rag"] is True
        assert len(data["sources"]) > 0, "应至少命中 1 个来源"

        # 4. 至少有一个 source 提及焊接关键词
        welding_hit = any(
            _has_welding_content(src.get("content", ""))
            for src in data["sources"]
        )
        assert welding_hit, f"应有焊接相关 source。实际: {[s.get('content', '')[:80] for s in data['sources']]}"

        # 5. sources 按 score 降序
        scores = [s["score"] for s in data["sources"]]
        assert scores == sorted(scores, reverse=True), f"sources 未按 score 降序: {scores}"


class TestSSEStreamingProtocol:
    """SSE 流式端点的协议合规性"""

    def test_stream_basic_protocol(self, client):
        """SSE 应输出 intent → sources → delta... → done 事件"""
        r = client.post("/api/v1/chat/stream", json={
            "message": "焊接机器人飞溅大怎么处理",
            "top_k": 5,
        })

        assert r.status_code == 200
        assert "text/event-stream" in r.headers.get("content-type", "")

        # 一次性读完整个 response body（TestClient 不会真的流式，已经缓冲完整）
        # 用原始字节按 \n\n 切块（每个 SSE event 以空行结束）
        raw = r.content
        if isinstance(raw, bytes):
            raw = raw.decode("utf-8", errors="ignore")

        # 解析 SSE event: data: 协议
        events: list[tuple[str, dict]] = []
        event_name = ""
        for chunk in raw.split("\n\n"):
            if not chunk.strip():
                continue
            for line in chunk.splitlines():
                line = line.strip()
                if not line:
                    continue
                if line.startswith("event: "):
                    event_name = line[len("event: "):].strip()
                elif line.startswith("data: "):
                    event_data = json.loads(line[len("data: "):])
                    events.append((event_name, event_data))

        # 第一个事件应是 intent
        assert len(events) > 0
        first_evt, first_data = events[0]
        assert first_evt == "intent"
        assert first_data["intent"] in ("casual", "maintenance")

        # 至少有一个 delta 事件（流式输出）
        delta_events = [e for e in events if e[0] == "delta"]
        assert len(delta_events) > 0, "应至少有 1 个 delta 事件"

        # 最后应是 done
        last_evt, last_data = events[-1]
        assert last_evt == "done", f"最后事件应是 done，实际: {last_evt}"
        assert "latency_ms" in last_data
        assert "model" in last_data
        assert "used_rag" in last_data
        assert "total_chars" in last_data
        assert last_data["total_chars"] > 0, "应至少有一些字符被吐出"

        # delta 拼起来 ≈ done.total_chars
        delta_chars = sum(len(d.get("content", "")) for _, d in delta_events)
        assert abs(delta_chars - last_data["total_chars"]) <= 10, (
            f"delta 拼接={delta_chars} 与 done.total_chars={last_data['total_chars']} 不符"
        )


class TestRAGLatency:
    """性能：单次问答不应过长（看后端报告，不依赖测试机网络）"""

    def test_backend_latency_reasonable(self, client):
        """后端报告的 latency_ms 应 ≤ 60s（qwen-flash + 关键词 fallback 的合理范围）"""
        r = client.post("/api/v1/chat", json={
            "message": "焊接机器人飞溅大怎么处理",
            "top_k": 5,
        })
        assert r.status_code == 200
        data = r.json()
        backend_latency_ms = data["latency_ms"]
        # 60s 是宽松阈值（Milvus 不可用 + 长上下文 + 网络抖动仍可接受）
        assert backend_latency_ms < 60_000, (
            f"后端报告 latency={backend_latency_ms}ms 超过 60s 阈值"
        )
        # retrieval_latency 应在总时间的一部分
        assert data["retrieval_latency_ms"] >= 0
        assert data["latency_ms"] >= data["retrieval_latency_ms"] - 100, (
            f"总 latency 不应 < retrieval latency: {data}"
        )
