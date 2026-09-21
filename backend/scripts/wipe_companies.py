"""一次性清库脚本（2026 标签模型改造配套）。

用途：旧的 `(Company)-[:BELONGS_TO]->(Theme)` 关系模型改为「主题 = 企业节点标签」后，
清空全部存量企业数据（Company 节点及其所有关系），保留：
- Theme 注册表（配置：slug/name/icon/color/...）
- IndustryCategory 国标行业分类
- Chain / Stage 产业链结构

企业之后通过前端或 CSV 导入重录即可，导入时会直接打上主题标签。

用法（在 backend 目录）：
    python scripts/wipe_companies.py          # dry-run，只看会删什么
    python scripts/wipe_companies.py --commit  # 真正删除
"""
from __future__ import annotations

import asyncio
import sys
from pathlib import Path

# 允许 `python scripts/xxx.py` 直接运行：把 backend 目录加进 sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app import neo4j_manager  # noqa: E402


async def main(commit: bool) -> None:
    session = await neo4j_manager.get_session()
    try:
        # 先统计
        stats = await session.run(
            """
            OPTIONAL MATCH (c:Company) WITH count(c) AS companies
            OPTIONAL MATCH (t:Theme) WITH companies, count(t) AS themes
            OPTIONAL MATCH (c2:Company)-[r]-() WITH companies, themes, count(r) AS rels
            RETURN companies, themes, rels
            """
        )
        rec = await stats.single()
        print(
            f"当前库内：Company 节点 {rec['companies']} 个，"
            f"涉及关系 {rec['rels']} 条；Theme 注册表 {rec['themes']} 个（保留）"
        )

        if not commit:
            print("dry-run：以上 Company 节点及其关系将被删除。加 --commit 执行。")
            return

        result = await session.run("MATCH (c:Company) DETACH DELETE c")
        summary = await result.consume()
        print(
            f"已删除 {summary.counters.nodes_deleted} 个企业节点，"
            f"{summary.counters.relationships_deleted} 条关系。"
        )
    finally:
        await session.close()
        await neo4j_manager.reset()


if __name__ == "__main__":
    asyncio.run(main(commit="--commit" in sys.argv))
