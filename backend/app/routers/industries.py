"""行业分类 (IndustryCategory) 管理路由。

数据来源：GB/T 4754-2017《国民经济行业分类》，收录制造业完整三级分类：
    大类(2位) → 中类(3位) → 小类(4位)，共 819 个节点。
静态数据随代码走（backend/app/data/industry_categories.json），可离线浏览、可重复初始化。

数据模型：
    (:IndustryCategory {code, name, level, level_name, parent_code, order})
        -[:PARENT_OF]-> (:IndustryCategory)
    (:Company)-[:IN_INDUSTRY]->(:IndustryCategory)

统计口径：
    company_count        —— 直接挂在该分类节点上的企业数
    company_count_total  —— 含全部子分类的企业数（父级自动汇总）

API 设计：
- GET    /api/industries                     分类列表（可过滤层级/父级/关键词）
- GET    /api/industries/tree                完整分类树（嵌套 children）
- GET    /api/industries/stats               统计（各级数量 + 已挂企业数）
- GET    /api/industries/catalog             静态目录元信息（不依赖 Neo4j）
- POST   /api/industries/seed                把静态数据写入 Neo4j（可 reset）
- GET    /api/industries/{code}              分类详情（路径 + 子节点 + 企业）
- GET    /api/industries/{code}/companies    该分类（含子级）下的企业
- GET    /api/companies/{id}/industries      企业所属分类
- PUT    /api/companies/{id}/industries      设置企业所属分类（整体替换）
"""
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, HTTPException, Query

from .. import neo4j_manager
from ..schemas import (
    CompanyIndustriesIn,
    CompanyRef,
    IndustryCategoryDetail,
    IndustryCategoryNode,
    IndustryCategoryOut,
    IndustryCategoryRef,
    IndustrySeedResult,
    IndustryStats,
)


router = APIRouter(prefix="/api", tags=["industries"])

_DATA_FILE = (
    Path(__file__).resolve().parent.parent / "data" / "industry_categories.json"
)


# ---------------------------- 静态目录 ----------------------------

def _catalog() -> dict:
    """加载静态分类目录。

    不做 in-process 缓存：JSON 仅 ~300KB，每次读毫秒级；缓存反而会让「修改 JSON
    后不重启 uvicorn 就看不到新数据」的坑难以排查。
    """
    with _DATA_FILE.open(encoding="utf-8") as f:
        return json.load(f)


def _catalog_items() -> list[dict]:
    return _catalog()["items"]


def _catalog_index() -> dict[str, dict]:
    return {it["code"]: it for it in _catalog_items()}


def _path_of(code: str) -> list[IndustryCategoryRef]:
    """沿 parent_code 上溯，返回 大类 → … → 自身 的路径。"""
    index = _catalog_index()
    chain: list[IndustryCategoryRef] = []
    cur = index.get(code)
    seen: set[str] = set()
    while cur is not None and cur["code"] not in seen:
        seen.add(cur["code"])
        chain.append(
            IndustryCategoryRef(
                code=cur["code"],
                name=cur["name"],
                level=cur["level"],
                level_name=cur.get("level_name", ""),
            )
        )
        parent = cur.get("parent_code")
        cur = index.get(parent) if parent else None
    chain.reverse()
    return chain


def descendant_codes(code: str) -> list[str]:
    """返回 code 自身 + 全部子孙 code（基于静态目录）。

    用于「含子级」筛选：企业挂在小类，按大类筛选时要把子类一并纳入。
    """
    items = _catalog_items()
    children_of: dict[str, list[str]] = {}
    for it in items:
        parent = it.get("parent_code")
        if parent:
            children_of.setdefault(parent, []).append(it["code"])

    out: list[str] = []
    seen: set[str] = set()
    stack = [code]
    while stack:
        cur = stack.pop()
        if cur in seen:
            continue
        seen.add(cur)
        out.append(cur)
        stack.extend(children_of.get(cur, []))
    return out


# ---------------------------- 内部工具 ----------------------------

def _row_to_ref(row: dict) -> IndustryCategoryRef:
    return IndustryCategoryRef(
        code=row["code"],
        name=row["name"],
        level=row.get("level") or 3,
        level_name=row.get("level_name") or "",
    )


async def _fetch_categories(session) -> list[dict]:
    """读取全部分类节点 + 三类企业统计（直接 / 含子级 / 子节点数）。"""
    base = await session.run(
        """
        MATCH (n:IndustryCategory)
        RETURN n.code AS code,
               n.name AS name,
               coalesce(n.level, 3) AS level,
               coalesce(n.level_name, '') AS level_name,
               n.parent_code AS parent_code,
               coalesce(n.order, 0) AS order
        """
    )
    rows: dict[str, dict] = {}
    async for r in base:
        d = r.data()
        d["company_count"] = 0
        d["desc_count"] = 0
        d["child_count"] = 0
        rows[d["code"]] = d

    if not rows:
        return []

    # 直接挂载的企业数
    direct = await session.run(
        """
        MATCH (c:Company)-[:IN_INDUSTRY]->(n:IndustryCategory)
        RETURN n.code AS code, count(DISTINCT c) AS cnt
        """
    )
    async for r in direct:
        if r["code"] in rows:
            rows[r["code"]]["company_count"] = r["cnt"]

    # 子级（不含自身）挂载的企业数
    desc = await session.run(
        """
        MATCH (n:IndustryCategory)-[:PARENT_OF*1..2]->(d:IndustryCategory)
              <-[:IN_INDUSTRY]-(c:Company)
        RETURN n.code AS code, count(DISTINCT c) AS cnt
        """
    )
    async for r in desc:
        if r["code"] in rows:
            rows[r["code"]]["desc_count"] = r["cnt"]

    # 直接子节点数
    children = await session.run(
        """
        MATCH (p:IndustryCategory)-[:PARENT_OF]->(ch:IndustryCategory)
        RETURN p.code AS code, count(DISTINCT ch) AS cnt
        """
    )
    async for r in children:
        if r["code"] in rows:
            rows[r["code"]]["child_count"] = r["cnt"]

    out: list[dict] = []
    for d in rows.values():
        direct_cnt = d["company_count"]
        out.append(
            {
                "code": d["code"],
                "name": d["name"],
                "level": d["level"],
                "level_name": d["level_name"],
                "parent_code": d["parent_code"],
                "order": d["order"],
                "company_count": direct_cnt,
                "company_count_total": direct_cnt + d["desc_count"],
                "has_children": d["child_count"] > 0,
            }
        )
    out.sort(key=lambda x: (x["level"], x["order"], x["code"]))
    return out


def _build_tree(rows: list[dict]) -> list[IndustryCategoryNode]:
    """把扁平分类列表组装成嵌套树。"""
    nodes: dict[str, IndustryCategoryNode] = {
        r["code"]: IndustryCategoryNode(**r, children=[]) for r in rows
    }
    roots: list[IndustryCategoryNode] = []
    for r in rows:
        node = nodes[r["code"]]
        parent = r.get("parent_code")
        if parent and parent in nodes:
            nodes[parent].children.append(node)
        else:
            roots.append(node)

    def sort_rec(items: list[IndustryCategoryNode]) -> None:
        items.sort(key=lambda n: (n.order, n.code))
        for n in items:
            sort_rec(n.children)

    sort_rec(roots)
    return roots


async def validate_industry_codes(session, codes: list[str]) -> None:
    """校验 codes 在 Neo4j 中都存在（去重后比对）。"""
    if not codes:
        return
    unique = sorted(set(codes))
    result = await session.run(
        "MATCH (n:IndustryCategory) WHERE n.code IN $codes RETURN n.code AS code",
        codes=unique,
    )
    found = {r["code"] async for r in result}
    missing = [c for c in unique if c not in found]
    if missing:
        raise HTTPException(
            status_code=400,
            detail=(
                f"以下行业分类不存在：{', '.join(missing)}。"
                "请先到「行业分类」页面初始化国标分类数据。"
            ),
        )


# ---------------------------- 静态元信息 ----------------------------

@router.get("/industries/catalog")
async def industry_catalog() -> dict:
    """返回静态目录元信息（不依赖 Neo4j，未初始化时前端也能展示规模）。"""
    cat = _catalog()
    return {
        "standard": cat["standard"],
        "standard_name": cat["standard_name"],
        "scope_code": cat["scope_code"],
        "scope_name": cat["scope_name"],
        "counts": cat["counts"],
    }


# ---------------------------- 统计 ----------------------------

@router.get("/industries/stats", response_model=IndustryStats)
async def industry_stats() -> IndustryStats:
    """行业分类统计：各级节点数量 + 已挂企业数。"""
    cat = _catalog()
    counts = cat["counts"]
    session = await neo4j_manager.get_session()
    try:
        node_run = await session.run(
            """
            MATCH (n:IndustryCategory)
            WITH coalesce(n.level, 3) AS lv, count(*) AS c
            RETURN collect({level: lv, count: c}) AS dist,
                   sum(c) AS total
            """
        )
        node_rec = await node_run.single()

        link_run = await session.run(
            """
            MATCH (c:Company)-[r:IN_INDUSTRY]->(:IndustryCategory)
            RETURN count(DISTINCT c) AS cc, count(r) AS rc
            """
        )
        link_rec = await link_run.single()
    finally:
        await session.close()

    dist = {
        item["level"]: item["count"] for item in (node_rec["dist"] if node_rec else [])
    }
    total = (node_rec["total"] if node_rec else 0) or 0

    return IndustryStats(
        standard=cat["standard"],
        standard_name=cat["standard_name"],
        scope_name=cat["scope_name"],
        seeded=total > 0,
        total=total,
        level1=dist.get(1, 0),
        level2=dist.get(2, 0),
        level3=dist.get(3, 0),
        linked_company_count=(link_rec["cc"] if link_rec else 0) or 0,
        relation_count=(link_rec["rc"] if link_rec else 0) or 0,
        expected_total=counts["total"],
        expected_counts=dict(counts),
    )


# ---------------------------- 初始化 ----------------------------

@router.post("/industries/seed", response_model=IndustrySeedResult)
async def seed_industries(
    reset: bool = Query(
        False,
        description="是否先清空已有分类节点（会解除企业关联，但不会删除企业）",
    ),
) -> IndustrySeedResult:
    """把静态国标分类写入 Neo4j。幂等：重复执行会更新已有节点。"""
    started = time.perf_counter()
    items = _catalog_items()
    cat = _catalog()

    unlinked = 0
    session = await neo4j_manager.get_session()
    try:
        if reset:
            probe = await session.run(
                """
                MATCH (c:Company)-[:IN_INDUSTRY]->(:IndustryCategory)
                RETURN count(DISTINCT c) AS cc
                """
            )
            probe_rec = await probe.single()
            unlinked = (probe_rec["cc"] if probe_rec else 0) or 0
            await session.run("MATCH (n:IndustryCategory) DETACH DELETE n")

        node_run = await session.run(
            """
            UNWIND $items AS it
            MERGE (n:IndustryCategory {code: it.code})
            SET n.name = it.name,
                n.level = it.level,
                n.level_name = it.level_name,
                n.order = it.order,
                n.parent_code = it.parent_code
            """,
            items=items,
        )
        node_summary = await node_run.consume()

        rel_run = await session.run(
            """
            UNWIND $items AS it
            WITH it WHERE it.parent_code IS NOT NULL
            MATCH (p:IndustryCategory {code: it.parent_code})
            MATCH (n:IndustryCategory {code: it.code})
            MERGE (p)-[:PARENT_OF]->(n)
            """,
            items=items,
        )
        rel_summary = await rel_run.consume()

        # 用 OPTIONAL MATCH 保证「没有层级关系时」也能返回一行；
        # 若写成连续 MATCH，关系为空时整条查询返回 0 行，计数会变成 None。
        total_run = await session.run(
            """
            MATCH (n:IndustryCategory)
            WITH count(n) AS nc
            OPTIONAL MATCH (:IndustryCategory)-[r:PARENT_OF]->(:IndustryCategory)
            RETURN nc AS node_count, count(r) AS relation_count
            """
        )
        total_rec = await total_run.single()
        node_count = (total_rec["node_count"] if total_rec else 0) or 0
        relation_count = (total_rec["relation_count"] if total_rec else 0) or 0
    finally:
        await session.close()

    return IndustrySeedResult(
        reset=reset,
        node_count=node_count,
        relation_count=relation_count,
        created_nodes=node_summary.counters.nodes_created,
        created_relations=rel_summary.counters.relationships_created,
        unlinked_companies=unlinked,
        duration_ms=int((time.perf_counter() - started) * 1000),
        counts=cat["counts"],
    )


# ---------------------------- 列表 / 树 ----------------------------

@router.get("/industries", response_model=list[IndustryCategoryOut])
async def list_industries(
    level: Optional[int] = Query(None, ge=1, le=3, description="只看某一层级"),
    parent_code: Optional[str] = Query(None, description="只看某节点的直接子节点"),
    keyword: Optional[str] = Query(None, description="按编码或名称模糊搜索"),
    only_linked: bool = Query(False, description="只看有企业挂载的分类"),
) -> list[IndustryCategoryOut]:
    """列出分类节点（带企业统计）。数据来自 Neo4j，未初始化则返回空。"""
    session = await neo4j_manager.get_session()
    try:
        rows = await _fetch_categories(session)
    finally:
        await session.close()

    if level is not None:
        rows = [r for r in rows if r["level"] == level]
    if parent_code is not None:
        rows = [r for r in rows if r["parent_code"] == parent_code]
    if keyword:
        kw = keyword.strip().lower()
        rows = [
            r
            for r in rows
            if kw in r["code"].lower() or kw in r["name"].lower()
        ]
    if only_linked:
        rows = [r for r in rows if r["company_count_total"] > 0]

    return [IndustryCategoryOut(**r) for r in rows]


@router.get("/industries/tree", response_model=list[IndustryCategoryNode])
async def industry_tree(
    only_linked: bool = Query(False, description="只保留有企业挂载的分支"),
) -> list[IndustryCategoryNode]:
    """完整分类树（嵌套 children），供前端树控件直接消费。"""
    session = await neo4j_manager.get_session()
    try:
        rows = await _fetch_categories(session)
    finally:
        await session.close()

    if only_linked:
        rows = [r for r in rows if r["company_count_total"] > 0]

    return _build_tree(rows)


# ---------------------------- 详情 ----------------------------

@router.get("/industries/{code}", response_model=IndustryCategoryDetail)
async def get_industry(
    code: str,
    company_limit: int = Query(200, ge=1, le=2000),
    include_descendants: bool = Query(
        True, description="企业列表是否包含子分类下的企业"
    ),
) -> IndustryCategoryDetail:
    """分类详情：大类→自身路径、直接子节点、关联企业。"""
    session = await neo4j_manager.get_session()
    try:
        rows = await _fetch_categories(session)
        by_code = {r["code"]: r for r in rows}
        row = by_code.get(code)
        if row is not None:
            detail = IndustryCategoryDetail(
                **row,
                path=_path_of(code),
                children=[
                    IndustryCategoryOut(**by_code[r["code"]])
                    for r in rows
                    if r["parent_code"] == code
                ],
                companies=[],
            )
        else:
            # 库里没有该节点：若是目录内合法编码则给出结构，否则 404
            static = _catalog_index().get(code)
            if static is None:
                raise HTTPException(status_code=404, detail=f"行业分类不存在: {code}")
            detail = IndustryCategoryDetail(
                code=static["code"],
                name=static["name"],
                level=static["level"],
                level_name=static.get("level_name", ""),
                parent_code=static.get("parent_code"),
                order=static.get("order", 0),
                company_count=0,
                company_count_total=0,
                has_children=any(
                    it["parent_code"] == code for it in _catalog_items()
                ),
                path=_path_of(code),
                children=[],
                companies=[],
            )

        if not include_descendants:
            comp_run = await session.run(
                """
                MATCH (c:Company)-[:IN_INDUSTRY]->(n:IndustryCategory {code: $code})
                RETURN c.id AS id, c.name AS name
                ORDER BY c.name
                LIMIT $limit
                """,
                code=code,
                limit=company_limit,
            )
        else:
            comp_run = await session.run(
                """
                MATCH (n:IndustryCategory {code: $code})
                      -[:PARENT_OF*0..2]->(d:IndustryCategory)
                      <-[:IN_INDUSTRY]-(c:Company)
                RETURN DISTINCT c.id AS id, c.name AS name
                ORDER BY c.name
                LIMIT $limit
                """,
                code=code,
                limit=company_limit,
            )
        companies = [
            CompanyRef(id=r["id"], name=r["name"]) async for r in comp_run
        ]
    finally:
        await session.close()

    detail.companies = companies
    return detail


@router.get("/industries/{code}/companies", response_model=list[CompanyRef])
async def list_companies_in_industry(
    code: str,
    include_descendants: bool = Query(True, description="是否包含子分类下的企业"),
    limit: int = Query(500, ge=1, le=5000),
) -> list[CompanyRef]:
    """列出该分类下的企业（默认含子分类）。"""
    session = await neo4j_manager.get_session()
    try:
        exists = await session.run(
            "MATCH (n:IndustryCategory {code: $code}) RETURN n.code AS code",
            code=code,
        )
        if (await exists.single()) is None:
            raise HTTPException(
                status_code=404,
                detail=f"行业分类不存在: {code}（请先初始化国标分类数据）",
            )

        cypher = (
            """
            MATCH (n:IndustryCategory {code: $code})
                  -[:PARENT_OF*0..2]->(d:IndustryCategory)
                  <-[:IN_INDUSTRY]-(c:Company)
            RETURN DISTINCT c.id AS id, c.name AS name
            ORDER BY c.name
            LIMIT $limit
            """
            if include_descendants
            else """
            MATCH (c:Company)-[:IN_INDUSTRY]->(:IndustryCategory {code: $code})
            RETURN c.id AS id, c.name AS name
            ORDER BY c.name
            LIMIT $limit
            """
        )
        result = await session.run(cypher, code=code, limit=limit)
        companies = [CompanyRef(id=r["id"], name=r["name"]) async for r in result]
    finally:
        await session.close()
    return companies


# ---------------------------- 企业 ↔ 分类 ----------------------------

@router.get(
    "/companies/{company_id}/industries",
    response_model=list[IndustryCategoryRef],
)
async def get_company_industries(company_id: str) -> list[IndustryCategoryRef]:
    """查询企业挂载的行业分类。"""
    session = await neo4j_manager.get_session()
    try:
        ex = await session.run(
            "MATCH (c:Company {id: $id}) RETURN c.id AS id", id=company_id
        )
        if (await ex.single()) is None:
            raise HTTPException(status_code=404, detail=f"企业不存在: {company_id}")

        result = await session.run(
            """
            MATCH (c:Company {id: $id})-[:IN_INDUSTRY]->(n:IndustryCategory)
            RETURN n.code AS code, n.name AS name,
                   coalesce(n.level, 3) AS level,
                   coalesce(n.level_name, '') AS level_name
            ORDER BY n.code
            """,
            id=company_id,
        )
        return [_row_to_ref(r.data()) async for r in result]
    finally:
        await session.close()


@router.put(
    "/companies/{company_id}/industries",
    response_model=list[IndustryCategoryRef],
)
async def set_company_industries(
    company_id: str,
    payload: CompanyIndustriesIn,
) -> list[IndustryCategoryRef]:
    """整体替换企业的行业分类（传空数组即清空）。"""
    session = await neo4j_manager.get_session()
    try:
        ex = await session.run(
            "MATCH (c:Company {id: $id}) RETURN c.id AS id", id=company_id
        )
        if (await ex.single()) is None:
            raise HTTPException(status_code=404, detail=f"企业不存在: {company_id}")

        await validate_industry_codes(session, payload.industry_codes)

        result = await session.run(
            """
            MATCH (c:Company {id: $id})
            OPTIONAL MATCH (c)-[old:IN_INDUSTRY]->(:IndustryCategory)
            DELETE old
            WITH DISTINCT c
            UNWIND (CASE WHEN size($codes) = 0 THEN [null] ELSE $codes END) AS code
            OPTIONAL MATCH (n:IndustryCategory {code: code})
            FOREACH (_ IN CASE WHEN n IS NULL THEN [] ELSE [1] END |
                MERGE (c)-[:IN_INDUSTRY]->(n)
            )
            WITH DISTINCT c
            OPTIONAL MATCH (c)-[:IN_INDUSTRY]->(n2:IndustryCategory)
            RETURN collect(DISTINCT {
                code: n2.code, name: n2.name,
                level: coalesce(n2.level, 3),
                level_name: coalesce(n2.level_name, '')
            }) AS industries
            """,
            id=company_id,
            codes=sorted(set(payload.industry_codes)),
        )
        record = await result.single()
    finally:
        await session.close()

    if record is None:
        return []
    return [
        _row_to_ref(item)
        for item in (record["industries"] or [])
        if item and item.get("code")
    ]
