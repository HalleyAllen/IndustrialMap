"""一键灌入「产业主题」(Theme) 到 Neo4j。

使用方式（在 backend/ 目录下）：

    # 默认：灌入/更新 10 个产业主题（幂等）
    python -m scripts.seed_themes

    # 重置模式：先清空 Neo4j 中的所有 Industry 节点 + 历史 Industry 关系，
    # 然后再灌入 Theme。用于 2026 改造后的"清空重来"。
    python -m scripts.seed_themes --reset

行为：
- 默认：MERGE 按 slug 创建/更新 Theme 节点，不碰其他节点。
- `--reset`：先 `MATCH (n:Industry) DETACH DELETE n` 清空 Industry，
  再灌入 Theme。Company 节点不动（用户的核心数据保留）。

注意：
- 2026 改造后不再需要 `--category manufacturing/d/all`，相关脚本已删除。
- 灌入 Theme 不会自动给企业挂主题；企业的分类由用户在 UI 里手动选择。
- 通过 `app.settings_db.get_neo4j_settings()` 获取连接配置（管理员在 UI
  里填过的）。
"""
from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

_BACKEND_DIR = Path(__file__).resolve().parent.parent
if str(_BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(_BACKEND_DIR))

from scripts.themes import THEMES, ThemeDef  # noqa: E402


async def reset_industry_nodes(session) -> int:
    """删除所有 Industry 节点（DETACH DELETE）并返回删除数。"""
    result = await session.run(
        """
        MATCH (n:Industry)
        WITH n LIMIT 1000
        DETACH DELETE n
        RETURN count(n) AS deleted
        """
    )
    total = 0
    async for r in result:
        total += r["deleted"]
    return total


async def reset_company_industry_relations(session) -> int:
    """删除所有 (Company)-[BELONGS_TO]->(Industry) 关系（保留 Industry 节点）。
    兼容性保险：万一历史数据中有 Company 直接连到 Industry 的边。
    """
    result = await session.run(
        """
        MATCH ()-[r:BELONGS_TO]->(i:Industry)
        DELETE r
        RETURN count(r) AS deleted
        """
    )
    record = await result.single()
    return record["deleted"] if record else 0


async def seed_theme_node(session, theme: ThemeDef) -> None:
    """创建/更新 Theme 节点（MERGE 按 slug）。"""
    await session.run(
        """
        MERGE (t:Theme {slug: $slug})
        SET t.name = $name,
            t.icon = $icon,
            t.color = $color,
            t.category = $category,
            t.description = $description
        """,
        slug=theme["slug"],
        name=theme["name"],
        icon=theme["icon"],
        color=theme["color"],
        category=theme["category"],
        description=theme["description"],
    )


async def run(reset: bool) -> None:
    from app import neo4j_manager, settings_db  # type: ignore  # 懒导入

    cfg = settings_db.get_neo4j_settings()
    if cfg is None:
        print("错误：未配置 Neo4j，请先在「数据库配置」页填写连接信息")
        sys.exit(1)

    driver = await neo4j_manager.get_driver()
    if driver is None:
        print("错误：无法建立 Neo4j 连接（driver 为 None）")
        sys.exit(1)

    print(f"准备灌入 {len(THEMES)} 个产业主题")
    for t in THEMES:
        print(f"  · {t['icon']} {t['name']} ({t['slug']}) — color={t['color']}")

    session = driver.session(database=cfg["database"])
    try:
        # ====== 可选：重置旧数据 ======
        if reset:
            print()
            print("[reset] 正在清理 Industry 节点 + 历史 BELONGS_TO 关系...")
            rel_del = await reset_company_industry_relations(session)
            print(f"  已删除 Company-Industry 关联关系 {rel_del} 条")
            node_del = await reset_industry_nodes(session)
            # Neo4j 单事务删除大量节点可能分页，多跑几次
            while True:
                more = await reset_industry_nodes(session)
                if more == 0:
                    break
                node_del += more
            print(f"  已删除 Industry 节点 {node_del} 个")

        # ====== 灌入 Theme 节点 ======
        for t in THEMES:
            await seed_theme_node(session, t)

        print()
        print(f"成功：写入 {len(THEMES)} 个 Theme 节点")
        if reset:
            print()
            print("提示：")
            print("  - Industry 节点已清空")
            print("  - Company 节点未动；如需重新分类，请在「企业管理」页编辑")
            print("  - 旧 Theme 节点如不再需要，可手动调用 DELETE /api/themes/{slug}")
    finally:
        await session.close()
        await neo4j_manager.reset()


def main() -> None:
    parser = argparse.ArgumentParser(description="灌入产业主题（Theme）到 Neo4j")
    parser.add_argument(
        "--reset",
        action="store_true",
        help="清空 Neo4j 中所有 Industry 节点 + 历史 BELONGS_TO 关系（2026 改造用）",
    )
    args = parser.parse_args()
    asyncio.run(run(reset=args.reset))


if __name__ == "__main__":
    main()