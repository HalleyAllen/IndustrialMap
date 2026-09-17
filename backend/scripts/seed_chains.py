"""一键灌入「产业链」(Chain / Stage) 到 Neo4j。

使用方式（在 backend/ 目录下）：

    # 默认：灌入/更新 5 条产业链及其环节（不碰企业数据）
    python -m scripts.seed_chains

    # 关联模式：根据 companies 列表，把匹配到的企业挂在对应环节上
    # 企业按名称精确匹配 Company.name；若企业不存在则记录在 missed_companies.txt
    python -m scripts.seed_chains --link

    # 重置：清空所有 Chain/Stage 节点 + IN_STAGE/UPSTREAM_OF/HAS_STAGE 关系，
    # 然后重新灌入（不动 Company 节点）
    python -m scripts.seed_chains --reset

行为
----
- MERGE 按 slug 创建/更新 Chain 节点；
- MERGE 按 (chain_slug, code) 创建/更新 Stage 节点；
- HAS_STAGE 关系携带 order；
- UPSTREAM_OF 关系由 Stage 之间的 upstream 字段生成；
- 默认不挂企业；`--link` 模式按企业名称匹配 Company → IN_STAGE。
"""
from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

_BACKEND_DIR = Path(__file__).resolve().parent.parent
if str(_BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(_BACKEND_DIR))

from scripts.chains import CHAINS, ChainDef, StageDef  # noqa: E402


async def reset_chain_data(session) -> tuple[int, int]:
    """删除所有 Chain/Stage 节点 + 相关关系，返回 (nodes_deleted, rels_deleted)。"""
    # 先删除相关关系
    rel_run = await session.run(
        """
        MATCH ()-[r]->()
        WHERE type(r) IN ['HAS_STAGE', 'UPSTREAM_OF', 'IN_STAGE']
        DELETE r
        RETURN count(r) AS rc
        """
    )
    rel_record = await rel_run.single()
    rels_deleted = rel_record["rc"] if rel_record else 0

    # 再删除 Chain/Stage 节点
    node_run = await session.run(
        """
        MATCH (n)
        WHERE n:Chain OR n:Stage
        DETACH DELETE n
        RETURN count(n) AS nc
        """
    )
    node_record = await node_run.single()
    nodes_deleted = node_record["nc"] if node_record else 0

    return nodes_deleted, rels_deleted


async def seed_chain(session, chain: ChainDef) -> None:
    """灌入单条产业链及其全部环节。"""
    await session.run(
        """
        MERGE (ch:Chain {slug: $slug})
        SET ch.name = $name,
            ch.icon = $icon,
            ch.color = $color,
            ch.description = $description
        """,
        slug=chain["slug"],
        name=chain["name"],
        icon=chain["icon"],
        color=chain["color"],
        description=chain["description"],
    )

    # 先按 code 删除此次不属于该链的 stage（防止删环节后残留）
    # 不主动删 stage — seed 时不传就保留

    # 创建环节
    for stage in chain["stages"]:
        await session.run(
            """
            MERGE (s:Stage {chain_slug: $chain_slug, code: $code})
            SET s.name = $name,
                s.description = $description,
                s.level = $level,
                s.order = $order
            WITH s
            MATCH (ch:Chain {slug: $chain_slug})
            MERGE (ch)-[r:HAS_STAGE]->(s)
            SET r.order = $order
            """,
            chain_slug=chain["slug"],
            code=stage["code"],
            name=stage["name"],
            description=stage.get("description", ""),
            level=stage.get("level", "middle"),
            order=stage["order"],
        )

    # 上下游关系（UPSTREAM_OF）：在 cypher 内 link 所有 stage 对
    upstream_pairs: list[tuple[str, str]] = []
    for stage in chain["stages"]:
        for up_code in stage.get("upstream", []):
            upstream_pairs.append((up_code, stage["code"]))

    if upstream_pairs:
        # 批量建关系
        await session.run(
            """
            UNWIND $pairs AS pair
            MATCH (a:Stage {chain_slug: $chain_slug, code: pair[0]})
            MATCH (b:Stage {chain_slug: $chain_slug, code: pair[1]})
            MERGE (a)-[:UPSTREAM_OF]->(b)
            """,
            chain_slug=chain["slug"],
            pairs=upstream_pairs,
        )


async def link_companies(session, missed_log: list[str]) -> tuple[int, int]:
    """把所有 chains.py 中出现的企业名匹配 Company，挂到对应 Stage。

    返回 (linked, missed)
    """
    linked = 0
    missed = 0
    for chain in CHAINS:
        for stage in chain["stages"]:
            for cn in stage.get("companies", []):
                result = await session.run(
                    """
                    MATCH (c:Company {name: $name})
                    OPTIONAL MATCH (c)-[old:IN_STAGE]->()
                    DELETE old
                    WITH c
                    MATCH (s:Stage {chain_slug: $chain_slug, code: $code})
                    MERGE (c)-[:IN_STAGE]->(s)
                    RETURN c.id AS id
                    """,
                    name=cn,
                    chain_slug=chain["slug"],
                    code=stage["code"],
                )
                record = await result.single()
                if record is None:
                    missed += 1
                    missed_log.append(f"{cn} ({chain['slug']}/{stage['code']})")
                else:
                    linked += 1
    return linked, missed


async def run(reset: bool, link: bool) -> None:
    from app import neo4j_manager, settings_db  # type: ignore  # 懒导入

    cfg = settings_db.get_neo4j_settings()
    if cfg is None:
        print("错误：未配置 Neo4j，请先在「数据库配置」页填写连接信息")
        sys.exit(1)

    driver = await neo4j_manager.get_driver()
    if driver is None:
        print("错误：无法建立 Neo4j 连接（driver 为 None）")
        sys.exit(1)

    print(f"准备灌入 {len(CHAINS)} 条产业链")
    for c in CHAINS:
        n_stages = len(c["stages"])
        n_companies = sum(len(s.get("companies", [])) for s in c["stages"])
        print(
            f"  · {c['icon']} {c['name']} ({c['slug']}) — "
            f"{n_stages} 个环节, {n_companies} 家示范企业"
        )

    session = driver.session(database=cfg["database"])
    try:
        if reset:
            print()
            print("[reset] 清理 Chain / Stage / 关系...")
            nodes, rels = await reset_chain_data(session)
            print(f"  已删除 Chain/Stage 节点 {nodes} 个，相关关系 {rels} 条")

        for chain in CHAINS:
            await seed_chain(session, chain)

        # 关联企业
        missed_log: list[str] = []
        if link:
            print()
            print("[link] 匹配企业名 → Stage ...")
            linked, missed = await link_companies(session, missed_log)
            print(f"  已挂载 {linked} 家企业到 Stage")
            if missed:
                print(f"  ⚠️ 未找到 {missed} 家企业（已记录到 missed_companies.txt）")

        # 统计
        print()
        stats_run = await session.run(
            """
            MATCH (ch:Chain) WITH count(ch) AS chain_count
            MATCH (s:Stage) WITH chain_count, count(s) AS stage_count
            MATCH ()-[r:HAS_STAGE]->() WITH chain_count, stage_count, count(r) AS has_stage
            MATCH ()-[u:UPSTREAM_OF]->() WITH chain_count, stage_count, has_stage, count(u) AS upstream_of
            MATCH ()-[i:IN_STAGE]->() WITH chain_count, stage_count, has_stage, upstream_of, count(i) AS in_stage
            RETURN chain_count, stage_count, has_stage, upstream_of, in_stage
            """
        )
        s = await stats_run.single()
        if s:
            print(
                f"统计: {s['chain_count']} Chain, {s['stage_count']} Stage, "
                f"{s['has_stage']} HAS_STAGE, {s['upstream_of']} UPSTREAM_OF, "
                f"{s['in_stage']} IN_STAGE"
            )
    finally:
        await session.close()
        await neo4j_manager.reset()

    # 写入未匹配企业清单
    if link and missed_log:
        missed_path = _BACKEND_DIR / "missed_companies.txt"
        missed_path.write_text("\n".join(missed_log), encoding="utf-8")
        print(f"未匹配企业清单：{missed_path}")


def main() -> None:
    parser = argparse.ArgumentParser(description="灌入产业链到 Neo4j")
    parser.add_argument(
        "--reset",
        action="store_true",
        help="先清空 Chain/Stage 节点 + 关系（保留 Company）",
    )
    parser.add_argument(
        "--link",
        action="store_true",
        help="按名称匹配 Company → Stage（默认不挂企业）",
    )
    args = parser.parse_args()
    asyncio.run(run(reset=args.reset, link=args.link))


if __name__ == "__main__":
    main()