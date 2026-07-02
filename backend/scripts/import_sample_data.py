"""
一键导入内置数据脚本
用法: python -m scripts.import_sample_data
"""
import asyncio
import sys
from pathlib import Path

# 把项目根目录加入 path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.services.knowledge_service import KnowledgeService
from app.core.logger import logger, setup_logger
from app.llm.factory import get_model_adapter


async def main():
    setup_logger()
    logger.info("=" * 50)
    logger.info("  A1 设备检修智能系统 - 数据导入")
    logger.info("=" * 50)

    # 初始化模型
    logger.info("初始化模型适配器...")
    adapter = get_model_adapter()
    healthy = await adapter.health_check()
    if not healthy:
        logger.warning("⚠️  LLM 健康检查失败，但可以继续（向量化不依赖 LLM）")

    service = KnowledgeService()

    # 1. 导入手册
    logger.info("\n[1/3] 导入检修手册...")
    manuals_dir = Path(__file__).parent.parent / "data" / "raw" / "manuals"
    if manuals_dir.exists():
        results = await service.import_manuals(str(manuals_dir))
        for name, count in results.items():
            logger.info(f"  📄 {name}: {count} chunks")
    else:
        logger.warning(f"  手册目录不存在: {manuals_dir}")

    # 2. 导入案例
    logger.info("\n[2/3] 导入故障案例...")
    cases_file = Path(__file__).parent.parent / "data" / "raw" / "cases" / "fault_cases.json"
    if cases_file.exists():
        count = await service.import_cases(str(cases_file))
        logger.info(f"  📋 案例导入: {count} 条")
    else:
        logger.warning(f"  案例文件不存在: {cases_file}")

    # 3. 导入 SOP
    logger.info("\n[3/3] 导入 SOP...")
    sops_file = Path(__file__).parent.parent / "data" / "raw" / "sops" / "sop_library.json"
    if sops_file.exists():
        count = await service.import_sops(str(sops_file))
        logger.info(f"  📑 SOP 导入: {count} 条")
    else:
        logger.warning(f"  SOP 文件不存在: {sops_file}")

    # 统计
    stats = await service.stats()
    logger.info("\n" + "=" * 50)
    logger.info("  导入完成！")
    logger.info(f"  知识库 chunks: {stats['total_chunks']}")
    logger.info(f"  案例总数: {stats['total_cases']}")
    logger.info(f"  待审核: {stats['pending_cases']}, 已通过: {stats['approved_cases']}")
    logger.info("=" * 50)


if __name__ == "__main__":
    asyncio.run(main())
