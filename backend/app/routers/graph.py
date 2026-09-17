"""图谱查询路由：返回前端图谱可视化所需的节点和边。

数据模型（2026 改造后）：
- 节点：Company + Theme
- 关系：(Company)-[:BELONGS_TO]->(Theme)
- 企业关系：(Company)-[SUPPLIES / PARTNER_OF / ...]->(Company)
"""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, HTTPException, Query

from .. import neo4j_manager
from ..schemas import GraphData, GraphEdge, GraphNode, GraphStats, ThemeRef


router = APIRouter(prefix="/api/graph", tags=["graph"])


# ---------------------------- 内部辅助 ----------------------------

def _themes_of(record_themes: Optional[list[dict]]) -> list[ThemeRef]:
    """Cypher 返回的 themes 列表（dict）→ ThemeRef。"""
    out: list[ThemeRef] = []
    if not record_themes:
        return out
    for t in record_themes:
        if not t or not t.get("slug"):
            continue
        out.append(
            ThemeRef(
                slug=t["slug"],
                name=t.get("name") or t["slug"],
                icon=t.get("icon") or "",
                color=t.get("color") or "#3b82f6",
            )
        )
    return out


async def _fetch_themes_for(session, company_id: str) -> list[ThemeRef]:
    """获取指定企业所属主题列表（按 slug 排序）。"""
    result = await session.run(
        """
        MATCH (c:Company {id: $id})-[:BELONGS_TO]->(t:Theme)
        RETURN t.slug AS slug, t.name AS name,
               coalesce(t.icon, '') AS icon,
               coalesce(t.color, '#3b82f6') AS color
        ORDER BY t.slug
        """,
        id=company_id,
    )
    out: list[ThemeRef] = []
    async for r in result:
        out.append(ThemeRef(slug=r["slug"], name=r["name"], icon=r["icon"], color=r["color"]))
    return out


# ---------------------------- 统计 ----------------------------

@router.get("/stats", response_model=GraphStats)
async def graph_stats() -> GraphStats:
    """返回企业 / 主题 / 关系总数 + 产业链/环节统计。"""
    session = await neo4j_manager.get_session()
    try:
        result = await session.run(
            """
            MATCH (c:Company) WITH count(c) AS cc
            MATCH (t:Theme) WITH cc, count(t) AS tc
            MATCH ()-[r]->() WHERE type(r) <> 'BELONGS_TO'
                AND type(r) <> 'HAS_STAGE'
                AND type(r) <> 'UPSTREAM_OF'
                AND type(r) <> 'IN_STAGE'
                WITH cc, tc, count(r) AS rc
            MATCH (ch:Chain) WITH cc, tc, rc, count(ch) AS chc
            MATCH (s:Stage) WITH cc, tc, rc, chc, count(s) AS sc
            RETURN cc AS company_count,
                   tc AS theme_count,
                   rc AS relation_count,
                   chc AS chain_count,
                   sc AS stage_count
            """
        )
        record = await result.single()
    finally:
        await session.close()
    if record is None:
        return GraphStats()
    return GraphStats(
        company_count=record["company_count"],
        theme_count=record["theme_count"],
        relation_count=record["relation_count"],
        chain_count=record["chain_count"],
        stage_count=record["stage_count"],
    )


# ---------------------------- 全图 / 按主题过滤 ----------------------------

@router.get("/full", response_model=GraphData)
async def full_graph(
    theme_slug: Optional[str] = Query(
        None, description="按主题筛选（仅显示属于该主题的企业及其一跳关系）"
    ),
    limit: int = Query(300, ge=1, le=2000),
) -> GraphData:
    """返回完整图谱（或按主题过滤后的一跳子图）。"""
    session = await neo4j_manager.get_session()
    try:
        if theme_slug:
            # 按主题过滤：先找出属于该主题的企业，再查这些企业之间的关系
            companies_result = await session.run(
                """
                MATCH (c:Company)-[:BELONGS_TO]->(t:Theme {slug: $slug})
                RETURN c.id AS id, c.name AS name
                ORDER BY c.name
                """,
                slug=theme_slug,
            )
            companies = [r async for r in companies_result]
            if not companies:
                return GraphData(nodes=[], edges=[])

            node_ids = [c["id"] for c in companies]
            # 一跳关系
            rel_result = await session.run(
                """
                MATCH (a:Company)-[r]->(b:Company)
                WHERE a.id IN $ids AND b.id IN $ids
                  AND type(r) <> 'BELONGS_TO'
                RETURN a.id AS src, b.id AS tgt, type(r) AS t
                """,
                ids=node_ids,
            )
            edges = [
                GraphEdge(
                    id=f"{r['src']}-{r['t']}-{r['tgt']}",
                    source=r["src"],
                    target=r["tgt"],
                    type=r["t"],
                )
                async for r in rel_result
            ]

            # 节点（含主题信息）
            nodes: list[GraphNode] = []
            for c in companies:
                themes = await _fetch_themes_for(session, c["id"])
                nodes.append(GraphNode(id=c["id"], name=c["name"], themes=themes))
            return GraphData(nodes=nodes, edges=edges)

        # 全图（按 limit 取前 N 个 + 它们之间的关系）
        result = await session.run(
            """
            MATCH (c:Company)
            RETURN c.id AS id, c.name AS name
            ORDER BY c.name
            LIMIT $limit
            """,
            limit=limit,
        )
        rows = [r async for r in result]
        if not rows:
            return GraphData(nodes=[], edges=[])
        node_ids = [r["id"] for r in rows]

        # 一次性收集所有节点的主题
        themes_result = await session.run(
            """
            MATCH (c:Company)-[:BELONGS_TO]->(t:Theme)
            WHERE c.id IN $ids
            RETURN c.id AS cid,
                   collect({
                       slug: t.slug, name: t.name,
                       icon: coalesce(t.icon, ''), color: coalesce(t.color, '#3b82f6')
                   }) AS themes
            """,
            ids=node_ids,
        )
        themes_by_cid: dict[str, list[ThemeRef]] = {}
        async for r in themes_result:
            themes_by_cid[r["cid"]] = _themes_of(r["themes"])

        nodes = [
            GraphNode(id=r["id"], name=r["name"], themes=themes_by_cid.get(r["id"], []))
            for r in rows
        ]

        # 企业之间的关系（排除 BELONGS_TO）
        rel_result = await session.run(
            """
            MATCH (a:Company)-[r]->(b:Company)
            WHERE a.id IN $ids AND b.id IN $ids
              AND type(r) <> 'BELONGS_TO'
            RETURN a.id AS src, b.id AS tgt, type(r) AS t
            """,
            ids=node_ids,
        )
        edges = [
            GraphEdge(
                id=f"{r['src']}-{r['t']}-{r['tgt']}",
                source=r["src"],
                target=r["tgt"],
                type=r["t"],
            )
            async for r in rel_result
        ]
        return GraphData(nodes=nodes, edges=edges)
    finally:
        await session.close()


# ---------------------------- 单企业 N 跳邻居 ----------------------------

@router.get("/company/{company_id}", response_model=GraphData)
async def company_neighborhood(
    company_id: str,
    depth: int = Query(1, ge=1, le=3, description="向外扩展几跳"),
) -> GraphData:
    """返回某企业周边 N 跳的子图（仅 Company 节点 + 它们之间的关系）。"""
    session = await neo4j_manager.get_session()
    try:
        result = await session.run(
            f"""
            MATCH path = (c:Company {{id: $id}})-[*1..{depth}]-(n)
            WHERE n:Company
            WITH collect(DISTINCT n) + collect(DISTINCT c) AS ns
            UNWIND ns AS node
            WITH collect(DISTINCT node) AS nodes
            UNWIND nodes AS a
            OPTIONAL MATCH (a)-[r]->(b)
            WHERE b IN nodes AND type(r) <> 'BELONGS_TO'
            RETURN a, b, type(r) AS t
            """,
            id=company_id,
        )
        records = [r async for r in result]
    finally:
        await session.close()
    if not records:
        raise HTTPException(status_code=404, detail="未找到该企业或无邻居")

    # 收集所有出现过的 Company id
    cids: set[str] = set()
    for r in records:
        if r["a"] is not None and "id" in r["a"]:
            cids.add(r["a"]["id"])
        if r["b"] is not None and "id" in r["b"]:
            cids.add(r["b"]["id"])
    cids.discard(None)  # type: ignore[arg-type]

    # 一次性批量取主题
    themes_by_cid: dict[str, list[ThemeRef]] = {}
    if cids:
        session2 = await neo4j_manager.get_session()
        try:
            tr = await session2.run(
                """
                MATCH (c:Company)-[:BELONGS_TO]->(t:Theme)
                WHERE c.id IN $ids
                RETURN c.id AS cid,
                       collect({
                           slug: t.slug, name: t.name,
                           icon: coalesce(t.icon, ''), color: coalesce(t.color, '#3b82f6')
                       }) AS themes
                """,
                ids=list(cids),
            )
            async for r in tr:
                themes_by_cid[r["cid"]] = _themes_of(r["themes"])
        finally:
            await session2.close()

    node_set: dict[str, GraphNode] = {}
    edges: list[GraphEdge] = []
    for r in records:
        a = r["a"]
        b = r["b"]
        for node in (a, b):
            if node is None or "id" not in node:
                continue
            nid = node["id"]
            if nid not in node_set:
                node_set[nid] = GraphNode(
                    id=nid,
                    name=node.get("name", ""),
                    themes=themes_by_cid.get(nid, []),
                )
        if b is not None and r["t"]:
            edges.append(
                GraphEdge(
                    id=f"{a['id']}-{r['t']}-{b['id']}",
                    source=a["id"],
                    target=b["id"],
                    type=r["t"],
                )
            )
    return GraphData(nodes=list(node_set.values()), edges=edges)