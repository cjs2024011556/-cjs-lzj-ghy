"""
从案例 + 手册 + SOP 构建故障图谱
用法: python -m scripts.build_graph
"""
import json
import re
import sys
from pathlib import Path
from collections import defaultdict

# 把项目根加入 path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.services.graph_service import (
    GraphService, NodeType, RelType, get_graph_service
)
from app.core.config import CASES_FILE, SOPS_FILE, MANUALS_DIR
from app.core.logger import logger, setup_logger


def extract_fault_keywords(text: str) -> list[str]:
    """从文本中提取故障关键词（粗粒度，按标点和动词切分）"""
    if not text:
        return []
    # 常见故障动词
    fault_verbs = r'(虚焊|打滑|异响|泄漏|磨损|断裂|失效|粘连|堵塞|烧毁|过热|欠压|过压|偏移|失准|报警|断裂|老化|松动|污染|锈蚀|变形|卡滞|异常|错误|故障|损坏|降低|升高|失败|脱落|脱落|噪声|振动)'
    matches = re.findall(fault_verbs, text)
    return list(set(matches))


def build():
    setup_logger()
    logger.info("=" * 50)
    logger.info("  故障图谱构建器")
    logger.info("=" * 50)

    gs = get_graph_service()
    gs.clear()

    # ---- 1. 加载案例 ----
    logger.info("\n[1/4] 加载案例...")
    cases = json.loads(CASES_FILE.read_text(encoding="utf-8"))
    for c in cases:
        case_id = c["case_id"]
        device_type = c["equipment_type"]
        device_model = c.get("equipment_model", "")

        # 案例节点
        gs.add_node(case_id, NodeType.CASE, c["title"], submitter=c.get("submitter", ""))

        # 设备节点（合并同类型）
        device_id = f"device:{device_type}"
        gs.add_node(device_id, NodeType.DEVICE, device_type, model_count=0)
        gs.add_node(f"model:{device_model}", NodeType.DEVICE, device_model, parent=device_id) if device_model else None
        # 如果是具体型号，也作为子节点
        if device_model:
            model_id = f"model:{device_model}"
            gs.add_node(model_id, NodeType.DEVICE, device_model)
            gs.add_edge(device_id, model_id, RelType.HAS_PART)

        # 案例 → 设备
        gs.add_edge(case_id, device_id, RelType.HAS_FAULT)

        # 提取故障关键词 → Fault 节点
        full_text = " ".join([
            c.get("title", ""),
            c.get("fault_description", ""),
            c.get("root_cause", ""),
            c.get("solution", ""),
            " ".join(c.get("tags", [])),
        ])
        faults = extract_fault_keywords(full_text)
        for f in faults:
            fault_id = f"fault:{f}"
            gs.add_node(fault_id, NodeType.FAULT, f)
            # 设备 → 故障
            gs.add_edge(device_id, fault_id, RelType.HAS_FAULT, weight=1)
            # 案例 → 故障
            gs.add_edge(case_id, fault_id, RelType.APPEARS_IN, weight=1)

    logger.info(f"  案例: {len(cases)} 个 → 节点 / 关系已添加")

    # ---- 2. 加载 SOP ----
    logger.info("\n[2/4] 加载 SOP...")
    sops = json.loads(SOPS_FILE.read_text(encoding="utf-8"))
    for s in sops:
        sop_id = s["sop_id"]
        gs.add_node(sop_id, NodeType.SOP, s["name"], level=s.get("maintenance_level", ""))

        # SOP → 设备
        device_id = f"device:{s['equipment_type']}"
        gs.add_edge(sop_id, device_id, RelType.HAS_PART)

        # SOP → 工具
        for tool in s.get("tools", []):
            tool_id = f"tool:{tool}"
            gs.add_node(tool_id, NodeType.TOOL, tool)
            gs.add_edge(sop_id, tool_id, RelType.REQUIRES, weight=1)

    logger.info(f"  SOP: {len(sops)} 个")

    # ---- 3. 匹配案例 → SOP ----
    logger.info("\n[3/4] 关联案例与 SOP...")
    case_sop_count = 0
    for c in cases:
        # 按设备类型匹配 SOP
        matching_sops = [s for s in sops if s["equipment_type"] == c["equipment_type"]]
        if matching_sops:
            # 优先选 level_2 或 overhaul（最详尽）
            best_sop = sorted(
                matching_sops,
                key=lambda s: {"overhaul": 3, "level_2": 2, "level_1": 1, "daily": 0}.get(s.get("maintenance_level", ""), 0),
                reverse=True,
            )[0]
            gs.add_edge(c["case_id"], best_sop["sop_id"], RelType.RESOLVED_BY, weight=1)
            case_sop_count += 1
    logger.info(f"  案例-SOP 关联: {case_sop_count} 个")

    # ---- 4. 保存 ----
    logger.info("\n[4/4] 保存图谱...")
    gs.save()

    stats = gs.stats()
    logger.info("\n" + "=" * 50)
    logger.info("  构建完成")
    logger.info(f"  节点: {stats['total_nodes']}")
    logger.info(f"  关系: {stats['total_edges']}")
    logger.info(f"  节点类型: {stats['node_types']}")
    logger.info(f"  关系类型: {stats['rel_types']}")
    logger.info("=" * 50)


if __name__ == "__main__":
    build()
