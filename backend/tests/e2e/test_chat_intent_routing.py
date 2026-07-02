"""
E2E Test 1: 闲聊 vs 检修 — 意图路由正确性

业务规则（来自 app/api/v1/chat.py）：
- 闲聊（"你好"）→ intent=casual, used_rag=False, sources=[]
- 检修（"焊接机器人飞溅大"）→ intent=maintenance, used_rag=True, sources 非空

依赖 LLM 云端适配器（DASHSCOPE_API_KEY 必须可用），否则整个模块 skip。
"""
import os
import pytest

from app.core.config import settings


# === Module-level guard：缺 key 则整模块 skip ===
SKIP_IF_NO_LLM = not settings.CLOUD_LLM.api_key
pytestmark = pytest.mark.skipif(
    SKIP_IF_NO_LLM,
    reason="DASHSCOPE_API_KEY 未配置，跳过 LLM 依赖的 e2e 测试",
)


class TestCasualIntent:
    """闲聊类问题：不走 RAG"""

    @pytest.mark.parametrize("message", [
        "你好",
        "今天天气怎么样",
        "你会什么",
        "你是谁",
    ])
    def test_casual_no_rag(self, client, message):
        r = client.post("/api/v1/chat", json={"message": message, "top_k": 5})
        assert r.status_code == 200, r.text
        data = r.json()

        # 闲聊意图校验
        assert data["intent"] == "casual", f"'{message}' 应被识别为 casual，实际: {data['intent']}"
        # 不走 RAG
        assert data["used_rag"] is False, f"'{message}' 不应触发 RAG"
        # 没来源
        assert data["sources"] == [], f"'{message}' 不应有 sources"
        # 给了答案（可能有引导用户描述具体设备的提示）
        assert data["answer"], f"'{message}' 应有非空答案"
        # 响应结构完整
        assert "latency_ms" in data
        assert "model" in data


class TestMaintenanceIntent:
    """检修类问题：必须走 RAG"""

    def test_welding_sparks_rag(self, client):
        r = client.post("/api/v1/chat", json={
            "message": "焊接机器人飞溅大怎么处理",
            "top_k": 5,
        })
        assert r.status_code == 200, r.text
        data = r.json()

        # 检修意图
        assert data["intent"] == "maintenance", f"应识别为 maintenance，实际: {data['intent']}"
        # 走了 RAG
        assert data["used_rag"] is True, "检修问题应触发 RAG"
        # 有来源
        assert len(data["sources"]) > 0, "RAG 命中后必须有 sources"
        # 来源结构完整
        for src in data["sources"]:
            assert "chunk_id" in src
            assert "content" in src
            assert "score" in src
            assert src["content"], "source content 不应为空"
            assert src["score"] >= 0
        # 答案非空（应基于参考回答）
        assert data["answer"], "应给出基于 RAG 的答案"
        # 置信度合理
        assert data["confidence"] >= 0.0
        # latencies 应有数据
        assert data["retrieval_latency_ms"] >= 0
        assert data["latency_ms"] >= data["retrieval_latency_ms"]


class TestRoutingEdgeCases:
    """路由边界：参数校验 + 异常路径"""

    def test_empty_message_rejected(self, client):
        r = client.post("/api/v1/chat", json={"message": "", "top_k": 5})
        # Pydantic min_length=1 应触发 422
        assert r.status_code == 422

    def test_too_long_message_rejected(self, client):
        r = client.post("/api/v1/chat", json={"message": "x" * 3000, "top_k": 5})
        assert r.status_code == 422

    def test_top_k_out_of_range(self, client):
        r = client.post("/api/v1/chat", json={"message": "测试", "top_k": 100})
        assert r.status_code == 422  # ge=1, le=10

    def test_history_routed(self, client):
        """多轮对话历史不影响当前轮意图"""
        r = client.post("/api/v1/chat", json={
            "message": "还有别的建议吗",
            "history": [
                {"role": "user", "content": "焊接机器人故障"},
                {"role": "assistant", "content": "请描述具体现象..."},
            ],
            "top_k": 5,
        })
        assert r.status_code == 200
        data = r.json()
        # 多轮上下文不影响单轮意图识别结果存在
        assert data["intent"] in ("casual", "maintenance")
