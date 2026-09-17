"""图谱查询路由：返回前端图谱可视化所需的节点和边。"""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, HTTPException, Query

from .. import neo4j_manager
from ..schemas import GraphData, GraphEdge, GraphNode, GraphStats


router = APIRouter(prefix="/api/graph", tags=["graph"])


@router.get("/stats", response_model=GraphStats)
async def graph_stats() -> GraphStats:
    """返回企业/行业/关系总数。"""
    session = await neo4j_manager.get_session()
    try:
        result = await session.run(
            """
            MATCH (c:Company) WITH count(c) AS cc
            MATCH (i:Industry) WITH cc, count(i) AS ic
            MATCH ()-[r]-() WITH cc, ic, count(r) AS rc
            RETURN cc AS company_count, ic AS industry_count, rc AS relation_count
            """
        )
        record = await result.single()
    finally:
        await session.close()
    if record is None:
        return GraphStats(company_count=0, industry_count=0, relation_count=0)
    return GraphStats(
        company_count=record["company_count"],
        industry_count=record["industry_count"],
        relation_count=record["relation_count"],
    )


@router.get("/full", response_model=GraphData)
async def full_graph(
    industry_code: Optional[str] = Query(None, description="按行业筛选（仅显示该行业的企业及其一跳关系）"),
    limit: int = Query(300, ge=1, le=2000),
) -> GraphData:
    """返回完整图谱（或按行业过滤后的一跳子图）。

    限制 limit 防止一次拉取过大；前端如需全量可分页或按需筛选。
    """
    session = await neo4j_manager.get_session()
    try:
        if industry_code:
            # 行业内的企业 + 这些企业之间的关系
            cypher = """
                MATCH (c:Company)-[:BELONGS_TO]->(i:Industry {code: $industry_code})
                WITH collect(c) AS companies
                UNWIND companies AS a
                OPTIONAL MATCH (a)-[r]->(b)
                WHERE b IN companies
                WITH companies, collect(DISTINCT {a: a, b: b, r: r}) AS edges
                RETURN companies, edges
            """
            result = await session.run(cypher, industry_code=industry_code)
            record = await result.single()
            if record is None:
                return GraphData(nodes=[], edges=[])
            companies = record["companies"]
            edges_raw = record["edges"]
            nodes: list[GraphNode] = []
            for c in companies:
                ind = await _industry_of(session, c)
                nodes.append(
                    GraphNode(
                        id=c["id"],
                        name=c["name"],
                        industry_code=ind[0] if ind else None,
                        industry_name=ind[1] if ind else None,
                    )
                )
            edges: list[GraphEdge] = []
            for item in edges_raw:
                if item["r"] is None:
                    continue
                edges.append(
                    GraphEdge(
                        id=f"{item['a']['id']}-{type(item['r']).__name__}-{item['b']['id']}",
                        source=item["a"]["id"],
                        target=item["b"]["id"],
                        type=type(item["r"]).__name__,
                    )
                )
            return GraphData(nodes=nodes, edges=edges)

        # 全图
        result = await session.run(
            """
            MATCH (c:Company)
            OPTIONAL MATCH (c)-[:BELONGS_TO]->(i:Industry)
            RETURN c.id AS id, c.name AS name,
                   i.code AS industry_code, i.name AS industry_name
            ORDER BY c.name LIMIT $limit
            """,
            limit=limit,
        )
        nodes = [
            GraphNode(
                id=r["id"],
                name=r["name"],
                industry_code=r["industry_code"],
                industry_name=r["industry_name"],
            )
            async for r in result
        ]
        node_ids = [n.id for n in nodes]
        if not node_ids:
            return GraphData(nodes=[], edges=[])
        result = await session.run(
            """
            MATCH (a:Company)-[r]->(b:Company)
            WHERE a.id IN $ids AND b.id IN $ids
            RETURN a.id AS src, b.id AS tgt, type(r) AS type
            """,
            ids=node_ids,
        )
        edges = [
            GraphEdge(
                id=f"{r['src']}-{r['type']}-{r['tgt']}",
                source=r["src"],
                target=r["tgt"],
                type=r["type"],
            )
            async for r in result
        ]
        return GraphData(nodes=nodes, edges=edges)
    finally:
        await session.close()


@router.get("/company/{company_id}", response_model=GraphData)
async def company_neighborhood(
    company_id: str,
    depth: int = Query(1, ge=1, le=3, description="向外扩展几跳"),
) -> GraphData:
    """返回某企业周边 N 跳的子图。"""
    session = await neo4j_manager.get_session()
    try:
        result = await session.run(
            f"""
            MATCH path = (c:Company {{id: $id}})-[*1..{depth}]-(n)
            WITH collect(DISTINCT n) + collect(DISTINCT c) AS ns
            UNWIND ns AS node
            WITH collect(DISTINCT node) AS nodes
            UNWIND nodes AS a
            OPTIONAL MATCH (a)-[r]->(b) WHERE b IN nodes
            RETURN a, b, type(r) AS t
            """,
            id=company_id,
        )
        records = [r async for r in result]
    finally:
        await session.close()
    if not records:
        raise HTTPException(status_code=404, detail="未找到该企业或无邻居")

    node_set: dict[str, GraphNode] = {}
    edges: list[GraphEdge] = []
    for r in records:
        a = r["a"]
        b = r["b"]
        for node in (a, b):
            if node is None:
                continue
            if "id" not in node:
                continue
            if node["id"] not in node_set:
                node_set[node["id"]] = GraphNode(id=node["id"], name=node.get("name", ""))
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


async def _industry_of(session, company) -> Optional[tuple[Optional[str], Optional[str]]]:
    """辅助：根据 Company 节点查询所属行业。"""
    result = await session.run(
        """
        MATCH (c:Company {id: $id})-[:BELONGS_TO]->(i:Industry)
        RETURN i.code AS code, i.name AS name
        """,
        id=company["id"],
    )
    record = await result.single()
    if record is None:
        return None
    return record["code"], record["name"]