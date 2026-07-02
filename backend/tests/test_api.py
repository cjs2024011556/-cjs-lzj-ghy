"""
API 集成测试
使用 FastAPI TestClient
"""
import pytest
from fastapi.testclient import TestClient

from app.main import app


@pytest.fixture
def client():
    return TestClient(app)


class TestHealth:
    def test_health_check(self, client):
        r = client.get("/api/v1/health")
        assert r.status_code == 200
        data = r.json()
        assert data["status"] == "ok"
        assert "app" in data
        assert "llm_mode" in data

    def test_ping(self, client):
        r = client.get("/api/v1/health/ping")
        assert r.status_code == 200
        assert r.json() == {"pong": True}

    def test_root(self, client):
        r = client.get("/")
        assert r.status_code == 200
        data = r.json()
        assert "name" in data
        assert "status" in data


class TestLLMAdmin:
    def test_get_status(self, client):
        r = client.get("/api/v1/llm/status")
        assert r.status_code == 200
        data = r.json()
        assert "mode" in data
        assert "model" in data
        assert "available" in data


class TestRetrieval:
    def test_stats(self, client):
        r = client.get("/api/v1/retrieval/stats")
        # 可能 500（Milvus 未连接），不强制要求
        assert r.status_code in (200, 500)


class TestOperationGuide:
    def test_list_levels(self, client):
        r = client.get("/api/v1/operation-guide/levels")
        assert r.status_code == 200
        data = r.json()
        assert "levels" in data
        assert len(data["levels"]) >= 3

    def test_generate_guide_validation(self, client):
        """参数校验"""
        r = client.post("/api/v1/operation-guide/generate", json={})
        assert r.status_code == 422  # validation error


class TestKnowledge:
    def test_stats(self, client):
        r = client.get("/api/v1/knowledge/stats")
        assert r.status_code == 200

    def test_list_cases(self, client):
        r = client.get("/api/v1/knowledge/case/list")
        assert r.status_code == 200
        data = r.json()
        assert "cases" in data

    def test_submit_case(self, client):
        r = client.post("/api/v1/knowledge/case/submit", json={
            "title": "测试案例",
            "equipment_type": "液压系统",
            "fault_description": "测试故障",
            "solution": "测试方案",
            "tags": ["测试"],
        })
        assert r.status_code == 200
        data = r.json()
        assert data["case_id"].startswith("CASE-")
        assert data["status"] == "pending"

    def test_submit_feedback(self, client):
        r = client.post("/api/v1/knowledge/feedback", json={
            "query": "测试问题",
            "original_answer": "测试答案",
            "rating": 5,
        })
        assert r.status_code == 200
