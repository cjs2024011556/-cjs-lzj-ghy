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

    def get_node_neighborhood(self, node_id: str) -> Dict[str, Any]:
        """获取节点详情 + 1-hop 邻居（按方向 + 关系类型分组）

        用于 Graph.vue 双击节点后的右侧/底部详情面板，结构化展示「该节点与外部的连接」。

        Returns:
            {
                "node": { id, label, type, color, degree, attrs },
                "outgoing": [
                    {
                        "rel_type": "HAS_PART",
                        "count": 3,
                        "neighbors": [{ "id", "label", "type", "color" }, ...]
                    }, ...
                ],
                "incoming": [...],        # 同上结构，反向
                "summary": {
                    "total_out": int,
                    "total_in": int,
                    "total_unique_neighbors": int,
                    "by_rel_type": { rel_type: count }
                }
            }
        """
        if node_id not in self.graph:
            return {"node": None, "outgoing": [], "incoming": [], "summary": {}, "error": "节点不存在"}

        attrs = dict(self.graph.nodes[node_id])
        node = {
            "id": node_id,
            "label": attrs.get("label", node_id),
            "type": attrs.get("type", "Unknown"),
            "color": attrs.get("color", "#999"),
            "degree": self.graph.degree(node_id),
            "in_degree": self.graph.in_degree(node_id),
            "out_degree": self.graph.out_degree(node_id),
            # 透传其他自定义 attrs（如 description / case_id / sop_id ...）
            "attrs": {k: v for k, v in attrs.items() if k not in ("label", "type", "color")},
        }

        # 出边（this → X）
        out_groups: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
        for _, t, eattrs in self.graph.out_edges(node_id, data=True):
            rel_type = eattrs.get("type", "RELATED")
            if t in self.graph.nodes:
                t_attrs = self.graph.nodes[t]
                out_groups[rel_type].append({
                    "id": t,
                    "label": t_attrs.get("label", t),
                    "type": t_attrs.get("type", "Unknown"),
                    "color": t_attrs.get("color", "#999"),
                    "weight": eattrs.get("weight", 1),
                })

        # 入边（Y → this）
        in_groups: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
        for s, _, eattrs in self.graph.in_edges(node_id, data=True):
            rel_type = eattrs.get("type", "RELATED")
            if s in self.graph.nodes:
                s_attrs = self.graph.nodes[s]
                in_groups[rel_type].append({
                    "id": s,
                    "label": s_attrs.get("label", s),
                    "type": s_attrs.get("type", "Unknown"),
                    "color": s_attrs.get("color", "#999"),
                    "weight": eattrs.get("weight", 1),
                })

        # 排序：按 count 降序，同组内按 weight desc
        def _sort_group(groups: Dict[str, List[Dict[str, Any]]]) -> List[Dict[str, Any]]:
            result = []
            for rel_type, neighbors in groups.items():
                neighbors_sorted = sorted(neighbors, key=lambda x: -x.get("weight", 0))
                result.append({"rel_type": rel_type, "count": len(neighbors_sorted), "neighbors": neighbors_sorted})
            result.sort(key=lambda g: -g["count"])
            return result

        outgoing_sorted = _sort_group(out_groups)
        incoming_sorted = _sort_group(in_groups)

        # 摘要
        unique_neighbors: Set[str] = set()
        for t in self.graph.successors(node_id):
            unique_neighbors.add(t)
        for s in self.graph.predecessors(node_id):
            unique_neighbors.add(s)

        by_rel: Dict[str, int] = defaultdict(int)
        for _, _, eattrs in self.graph.edges(node_id, data=True):
            by_rel[eattrs.get("type", "RELATED")] += 1

        summary = {
            "total_out": self.graph.out_degree(node_id),
            "total_in": self.graph.in_degree(node_id),
            "total_unique_neighbors": len(unique_neighbors),
            "by_rel_type": dict(by_rel),
        }

        return {
            "node": node,
            "outgoing": outgoing_sorted,
            "incoming": incoming_sorted,
            "summary": summary,
        }

    def get_analytics(self) -> Dict[str, Any]:
        """图谱分析指标（企业用户视角）

        Returns:
            {
                "top_degree_centrality": [
                    { "id", "label", "type", "color", "degree" }, ...   # top 5 节点按度排序
                ],
                "connected_components": {
                    "count": int,                                      # 连通分量数（有向图弱连通）
                    "max_size": int,                                   # 最大分量节点数
                    "sizes_distribution": { "1": x, "2-5": y, ... }    # 分量大小分布
                },
                "node_type_density": {
                    "Device": 6, "Part": 18, ...
                },
                "rel_type_density": { "HAS_PART": 12, ... },
                "shortest_path_sample": {                              # 最大连通分量里的最短路径示例
                    "source": { id, label, type, color },
                    "target": { id, label, type, color },
                    "path": [{ id, label, type, color }, ...],
                    "length": int
                } | None,
            }
        """
        if self.graph.number_of_nodes() == 0:
            return {
                "top_degree_centrality": [],
                "connected_components": {"count": 0, "max_size": 0, "sizes_distribution": {}},
                "node_type_density": {},
                "rel_type_density": {},
                "shortest_path_sample": None,
            }

        # 1. 度中心度 Top 5
        degree_sorted = sorted(
            self.graph.degree(),
            key=lambda x: -x[1],
        )[:5]
        top_centrality = []
        for nid, deg in degree_sorted:
            attrs = self.graph.nodes[nid]
            top_centrality.append({
                "id": nid,
                "label": attrs.get("label", nid),
                "type": attrs.get("type", "Unknown"),
                "color": attrs.get("color", "#999"),
                "degree": deg,
            })

        # 2. 连通分量（无向视角，因为有向图弱连通更符合企业用户理解）
        undirected = self.graph.to_undirected()
        components = list(nx.connected_components(undirected))
        comp_sizes = sorted([len(c) for c in components], reverse=True)
        # 分布桶
        size_buckets = {"1": 0, "2-5": 0, "6-20": 0, "21-100": 0, "100+": 0}
        for s in comp_sizes:
            if s == 1: size_buckets["1"] += 1
            elif s <= 5: size_buckets["2-5"] += 1
            elif s <= 20: size_buckets["6-20"] += 1
            elif s <= 100: size_buckets["21-100"] += 1
            else: size_buckets["100+"] += 1
        components_info = {
            "count": len(components),
            "max_size": comp_sizes[0] if comp_sizes else 0,
            "sizes_distribution": {k: v for k, v in size_buckets.items() if v > 0},
        }

        # 3. 节点 / 关系类型密度
        type_count: Dict[str, int] = defaultdict(int)
        for _, attrs in self.graph.nodes(data=True):
            type_count[attrs.get("type", "Unknown")] += 1
        rel_count: Dict[str, int] = defaultdict(int)
        for _, _, attrs in self.graph.edges(data=True):
            rel_count[attrs.get("type", "Unknown")] += 1

        # 4. 最短路径示例：在最大连通分量里找一条跨度的最短路径
        # 思路：取最大连通分量的两个距离最远的节点 (eccentricity 最大 / diameter 端点)
        shortest_path_sample = None
        try:
            # 只在最大分量里找（避免全图 O(n²)）
            largest_cc = max(components, key=len)
            sub = self.graph.subgraph(largest_cc)
            if sub.number_of_nodes() >= 2:
                # 用 BFS 找一条"端到端"的路径（轻度启发：取度数最低的节点对中最远的一对）
                # 简化：取度最低节点 → 计算它到度最高节点的最短路径
                lowest_deg_node = min(sub.degree(), key=lambda x: x[1])[0]
                # BFS 到不同类型（跨设备类型）的节点更"有故事"
                path = None
                # 优先取一个不同类型的远端节点
                type_of_low = sub.nodes[lowest_deg_node].get("type")
                candidates = [
                    (n, d) for n, d in sub.degree()
                    if n != lowest_deg_node and sub.nodes[n].get("type") != type_of_low
                ]
                if candidates:
                    target_node = max(candidates, key=lambda x: x[1])[0]
                    try:
                        path = nx.shortest_path(sub, source=lowest_deg_node, target=target_node)
                    except nx.NetworkXNoPath:
                        path = None
                if path and len(path) >= 2:
                    shortest_path_sample = {
                        "source": {
                            "id": path[0],
                            "label": sub.nodes[path[0]].get("label", path[0]),
                            "type": sub.nodes[path[0]].get("type", "Unknown"),
                            "color": sub.nodes[path[0]].get("color", "#999"),
                        },
                        "target": {
                            "id": path[-1],
                            "label": sub.nodes[path[-1]].get("label", path[-1]),
                            "type": sub.nodes[path[-1]].get("type", "Unknown"),
                            "color": sub.nodes[path[-1]].get("color", "#999"),
                        },
                        "path": [
                            {
                                "id": nid,
                                "label": sub.nodes[nid].get("label", nid),
                                "type": sub.nodes[nid].get("type", "Unknown"),
                                "color": sub.nodes[nid].get("color", "#999"),
                            }
                            for nid in path
                        ],
                        "length": len(path) - 1,
                    }
        except Exception as e:
            logger.debug(f"计算最短路径示例失败（忽略）: {e}")

        return {
            "top_degree_centrality": top_centrality,
            "connected_components": components_info,
            "node_type_density": dict(type_count),
            "rel_type_density": dict(rel_count),
            "shortest_path_sample": shortest_path_sample,
        }


# 单例
_graph_service: Optional[GraphService] = None


def get_graph_service() -> GraphService:
    global _graph_service
    if _graph_service is None:
        _graph_service = GraphService()
    return _graph_service
