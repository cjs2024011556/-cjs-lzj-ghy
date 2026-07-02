"""
故障图谱服务（创新杀手锏）

设计：先用 NetworkX 实现（无需 Neo4j 安装），数据结构与 Neo4j 一致，
     后续可平滑迁移到 Neo4j（节点/关系 schema 完全兼容 Cypher）

节点类型 (NodeType)：
- Device: 设备（焊接机器人/AGV/冲压机/机器视觉）
- Part:   部件（焊枪/编码器/电池/光源等）
- Fault:  故障（虚焊/激光雷达脏污/离合器打滑等）
- Case:   案例（CASE-2026-001 ...）
- SOP:    标准化作业（SOP-RBT-001 ...）
- Tool:   工具（扭力扳手/示波器/兆欧表等）

关系类型 (RelType)：
- HAS_PART:    Device → Part
- CAUSES:      Part → Fault
- HAS_FAULT:   Device → Fault
- RESOLVED_BY: Case → SOP
- REQUIRES:    SOP → Tool
- APPEARS_IN:  Fault → Case
"""
import json
import re
from pathlib import Path
from typing import Dict, List, Any, Optional, Set
from collections import defaultdict
import networkx as nx

from app.core.logger import logger
from app.core.config import GRAPH_FILE, DATA_DIR


# ---- 节点类型 & 关系类型 ----
class NodeType:
    DEVICE = "Device"
    PART = "Part"
    FAULT = "Fault"
    CASE = "Case"
    SOP = "SOP"
    TOOL = "Tool"


class RelType:
    HAS_PART = "HAS_PART"
    CAUSES = "CAUSES"
    HAS_FAULT = "HAS_FAULT"
    RESOLVED_BY = "RESOLVED_BY"
    REQUIRES = "REQUIRES"
    APPEARS_IN = "APPEARS_IN"


# 节点展示色（按类型）
NODE_COLORS = {
    NodeType.DEVICE: "#00d4ff",   # 蓝
    NodeType.PART:   "#ffb84d",   # 橙
    NodeType.FAULT:  "#ff4757",   # 红
    NodeType.CASE:   "#00d97e",   # 绿
    NodeType.SOP:    "#a855f7",   # 紫
    NodeType.TOOL:   "#94a3b8",   # 灰
}


class GraphService:
    """故障图谱服务 - 单例"""

    _instance: Optional["GraphService"] = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return
        self.graph: nx.DiGraph = nx.DiGraph()
        self._file_path = GRAPH_FILE
        self._load()
        self._initialized = True

    # ========== 持久化 ==========

    def _load(self):
        """从 JSON 加载图谱（Neo4j 兼容格式）"""
        if not self._file_path.exists():
            logger.info(f"图谱文件不存在: {self._file_path}，将自动构建")
            return
        try:
            data = json.loads(self._file_path.read_text(encoding="utf-8"))
            self.graph = nx.node_link_graph(data, edges="links")
            logger.info(f"图谱已加载: {self.graph.number_of_nodes()} 节点 / {self.graph.number_of_edges()} 关系")
        except Exception as e:
            logger.warning(f"图谱加载失败: {e}")

    def save(self):
        """保存图谱到 JSON（Neo4j 兼容）"""
        self._file_path.parent.mkdir(parents=True, exist_ok=True)
        data = nx.node_link_data(self.graph, edges="links")
        self._file_path.write_text(
            json.dumps(data, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        logger.info(f"图谱已保存: {self.graph.number_of_nodes()} 节点 / {self.graph.number_of_edges()} 关系")

    # ========== CRUD ==========

    def add_node(self, node_id: str, node_type: str, label: str, **attrs) -> None:
        """添加节点"""
        self.graph.add_node(
            node_id,
            type=node_type,
            label=label,
            color=NODE_COLORS.get(node_type, "#999"),
            **attrs,
        )

    def add_edge(self, source: str, target: str, rel_type: str, weight: float = 1.0, **attrs) -> None:
        """添加关系（重复关系会累加 weight）"""
        if self.graph.has_edge(source, target):
            self.graph[source][target]["weight"] += weight
        else:
            self.graph.add_edge(source, target, type=rel_type, weight=weight, **attrs)

    def clear(self):
        """清空图谱"""
        self.graph.clear()

    # ========== 查询 ==========

    def get_subgraph(self, node_ids: List[str], depth: int = 1) -> Dict[str, Any]:
        """获取以指定节点为中心、深度 depth 的子图"""
        # 找所有相关节点（BFS）
        visited: Set[str] = set()
        for nid in node_ids:
            if nid in self.graph:
                visited.add(nid)
                # 双向 BFS
                for _ in range(depth):
                    new_nodes: Set[str] = set()
                    for n in visited:
                        # 出边
                        for _, t in self.graph.out_edges(n):
                            if t not in visited:
                                new_nodes.add(t)
                        # 入边
                        for s, _ in self.graph.in_edges(n):
                            if s not in visited:
                                new_nodes.add(s)
                    visited.update(new_nodes)

        # 提取子图
        sub = self.graph.subgraph(visited).copy()
        return self._to_vis_format(sub)

    def find_related(self, keywords: List[str], max_hops: int = 2) -> Dict[str, Any]:
        """根据关键词找相关节点（模糊匹配 label）"""
        matched: Set[str] = set()
        for kw in keywords:
            kw_lower = kw.lower().strip()
            if not kw_lower:
                continue
            for node_id, attrs in self.graph.nodes(data=True):
                label = (attrs.get("label", "") or "").lower()
                if kw_lower in label or kw_lower in node_id.lower():
                    matched.add(node_id)

        if not matched:
            return {"nodes": [], "edges": [], "matched_keywords": keywords, "matched_count": 0}

        # 扩展子图
        visited: Set[str] = set(matched)
        for _ in range(max_hops):
            new_nodes: Set[str] = set()
            for n in visited:
                for _, t in self.graph.out_edges(n):
                    if t not in visited:
                        new_nodes.add(t)
                for s, _ in self.graph.in_edges(n):
                    if s not in visited:
                        new_nodes.add(s)
            if not new_nodes:
                break
            visited.update(new_nodes)

        sub = self.graph.subgraph(visited).copy()
        result = self._to_vis_format(sub)
        result["matched_keywords"] = keywords
        result["matched_count"] = len(matched)
        return result

    def get_full_graph(self, max_nodes: int = 200) -> Dict[str, Any]:
        """返回整图（限制节点数，避免前端卡顿）"""
        if self.graph.number_of_nodes() <= max_nodes:
            return self._to_vis_format(self.graph)
        # 取度数最高的 max_nodes 个节点
        nodes_sorted = sorted(
            self.graph.nodes(),
            key=lambda n: self.graph.degree(n),
            reverse=True,
        )[:max_nodes]
        sub = self.graph.subgraph(nodes_sorted).copy()
        return self._to_vis_format(sub)

    def stats(self) -> Dict[str, Any]:
        """图谱统计"""
        type_count: Dict[str, int] = defaultdict(int)
        for _, attrs in self.graph.nodes(data=True):
            type_count[attrs.get("type", "Unknown")] += 1

        rel_count: Dict[str, int] = defaultdict(int)
        for _, _, attrs in self.graph.edges(data=True):
            rel_count[attrs.get("type", "Unknown")] += 1

        return {
            "total_nodes": self.graph.number_of_nodes(),
            "total_edges": self.graph.number_of_edges(),
            "node_types": dict(type_count),
            "rel_types": dict(rel_count),
            "density": round(nx.density(self.graph), 4) if self.graph.number_of_nodes() > 0 else 0,
        }

    # ========== 工具 ==========

    def _to_vis_format(self, g: nx.DiGraph) -> Dict[str, Any]:
        """转换为前端 vis.js / cytoscape 友好的格式"""
        nodes = []
        for n, attrs in g.nodes(data=True):
            nodes.append({
                "id": n,
                "label": attrs.get("label", n),
                "type": attrs.get("type", "Unknown"),
                "color": attrs.get("color", "#999"),
                "title": f"{attrs.get('type', 'Unknown')}: {attrs.get('label', n)}",
                "value": g.degree(n),  # 节点大小 = 度数
            })

        edges = []
        for s, t, attrs in g.edges(data=True):
            edges.append({
                "source": s,
                "target": t,
                "label": attrs.get("type", ""),
                "weight": attrs.get("weight", 1),
                "arrows": "to",
            })

        return {"nodes": nodes, "edges": edges}


# 单例
_graph_service: Optional[GraphService] = None


def get_graph_service() -> GraphService:
    global _graph_service
    if _graph_service is None:
        _graph_service = GraphService()
    return _graph_service
