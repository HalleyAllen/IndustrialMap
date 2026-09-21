"""一次性同步：把 Neo4j 中 IndustryCategory 节点的字段对齐到 industry_categories.json。

历史背景：
* 重构 3300326 把 JSON 改成三级（大类=1 / 中类=2 / 小类=3）并删掉门类
* 但 Neo4j 中旧 seed 数据保留旧编码（大类=2 / 中类=3 / 小类=4）以及「C 制造业」门类
* seed 用 MERGE 写入，不会清理 JSON 中已不存在的旧节点
* 结果：tree API 仍能跑（门类删后），但 stats API 显示的 level1/2/3 全错位（level1=0）

本脚本做的事（按顺序）：
  1. 读 JSON 得到「合法 codes 集合」和「code -> JSON 字段」映射
  2. 列出 Neo4j 中两类问题节点：
     a) orphan  — code 不在 JSON 里                 → 待 DELETE
     b) stale   — code 在 JSON 里，但 level/level_name/name 与 JSON 不一致 → 待 SET

默认 dry-run；加 --apply 才会真正改动。

不插入 JSON 中有但 Neo4j 中没有的新节点（seed API 仍可补齐）。
企业 / 关系不动；orphan 删除会一并解除挂在孤儿上的 IN_INDUSTRY 关系（企业本身保留）。

用法（cd backend）：
    python _fix_industries_db_sync.py            # 预览
    python _fix_industries_db_sync.py --apply    # 真正执行
"""
from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))  # 让 `from app import ...` 可用

from app import neo4j_manager, settings_db  # noqa: E402


def load_json_index() -> tuple[set[str], dict[str, dict]]:
    data = json.loads(
        (ROOT / "app" / "data" / "industry_categories.json").read_text(encoding="utf-8")
    )
    items = data["items"]
    codes = {it["code"] for it in items}
    by_code = {it["code"]: it for it in items}
    return codes, by_code


async def fetch_neo4j(driver, database: str) -> list[dict]:
    async with driver.session(database=database) as s:
        r = await s.run(
            """
            MATCH (n:IndustryCategory)
            RETURN n.code AS code,
                   n.level AS level,
                   coalesce(n.level_name,'') AS level_name,
                   n.name AS name,
                   coalesce(n.order, 0) AS order,
                   n.parent_code AS parent_code
            ORDER BY code
            """
        )
        return [rec.data() async for rec in r]


def diff(neo_rows: list[dict], valid_codes: set[str], json_by_code: dict[str, dict]):
    orphans: list[dict] = []
    stale: list[dict] = []
    for row in neo_rows:
        code = row["code"]
        if code not in valid_codes:
            orphans.append(row)
            continue
        ref = json_by_code[code]
        new_level = ref["level"]
        new_level_name = ref.get("level_name", "")
        new_name = ref["name"]
        new_order = ref.get("order", 0)
        new_parent = ref.get("parent_code")
        if (
            row["level"] != new_level
            or row["level_name"] != new_level_name
            or row["name"] != new_name
            or row["order"] != new_order
            or row["parent_code"] != new_parent
        ):
            stale.append(
                {
                    "code": code,
                    "old": row,
                    "new": {
                        "level": new_level,
                        "level_name": new_level_name,
                        "name": new_name,
                        "order": new_order,
                        "parent_code": new_parent,
                    },
                }
            )
    return orphans, stale


async def run(apply: bool) -> int:
    valid_codes, json_by_code = load_json_index()
    print(f"JSON 合法 codes: {len(valid_codes)} 项")

    cfg = settings_db.get_neo4j_settings()
    if cfg is None:
        print("ERROR: Neo4j 未配置，请先在 Web UI「数据库配置」页填写。", file=sys.stderr)
        return 1
    print(f"目标 Neo4j: {cfg['uri']} (database={cfg['database']})")

    driver = await neo4j_manager.get_driver()
    if driver is None:
        print("ERROR: 无法建立 Neo4j 连接。", file=sys.stderr)
        return 1

    try:
        neo_rows = await fetch_neo4j(driver, cfg["database"])
        print(f"Neo4j 现存 IndustryCategory 节点: {len(neo_rows)} 个")

        orphans, stale = diff(neo_rows, valid_codes, json_by_code)
        print()
        print(f"[1] orphan (不在 JSON 中): {len(orphans)} 个 — 待 DELETE")
        for row in orphans:
            print(
                f"    - {row['code']:<6} level={row['level']}  "
                f"level_name={row['level_name']!r}  {row['name']}"
            )
        print()
        print(f"[2] stale (字段与 JSON 不一致): {len(stale)} 个 — 待 SET")
        # 只打印变化字段，避免刷屏
        for it in stale[:5]:
            o, n, code = it["old"], it["new"], it["code"]
            print(f"    - {code}")
            for k in ("level", "level_name", "name", "order", "parent_code"):
                if o[k] != n[k]:
                    print(f"        {k}: {o[k]!r} -> {n[k]!r}")
        if len(stale) > 5:
            print(f"    ... 省略 {len(stale) - 5} 个")
            # 统计哪些字段不一致
            from collections import Counter
            c = Counter()
            for it in stale:
                o, n = it["old"], it["new"]
                for k in ("level", "level_name", "name", "order", "parent_code"):
                    if o[k] != n[k]:
                        c[k] += 1
            print("    字段不一致统计:", dict(c))

        if not apply:
            if not orphans and not stale:
                print()
                print("无任何差异，无需修改。")
                return 0
            print()
            print("(dry-run，未改动。追加 --apply 真正执行。)")
            return 0

        # 真正执行
        async with driver.session(database=cfg["database"]) as s:
            # (1) 删除 orphan（DETACH 解除企业关联）
            if orphans:
                codes = [row["code"] for row in orphans]
                r = await s.run(
                    """
                    MATCH (n:IndustryCategory) WHERE n.code IN $codes
                    OPTIONAL MATCH (c:Company)-[r:IN_INDUSTRY]->(n)
                    WITH n, count(DISTINCT c) AS cc
                    DETACH DELETE n
                    RETURN count(*) AS deleted, sum(cc) AS unlinked
                    """,
                    codes=codes,
                )
                rec = (await r.single()).data()
                print(
                    f"\n[1] 已删除 {rec['deleted']} 个 orphan，"
                    f"解除 {rec['unlinked']} 家企业的分类关联（企业本身未删除）"
                )

            # (2) 按 JSON 重新对齐 stale 节点的字段
            if stale:
                # 用 UNWIND 批量写，比一条一条 SET 快
                payload = [
                    {
                        "code": it["code"],
                        "level": it["new"]["level"],
                        "level_name": it["new"]["level_name"],
                        "name": it["new"]["name"],
                        "order": it["new"]["order"],
                        "parent_code": it["new"]["parent_code"],
                    }
                    for it in stale
                ]
                r = await s.run(
                    """
                    UNWIND $rows AS row
                    MATCH (n:IndustryCategory {code: row.code})
                    SET n.level        = row.level,
                        n.level_name   = row.level_name,
                        n.name         = row.name,
                        n.order        = row.order,
                        n.parent_code  = row.parent_code
                    RETURN count(n) AS updated
                    """,
                    rows=payload,
                )
                updated = (await r.single()).data()["updated"]
                print(f"[2] 已更新 {updated} 个节点的字段")

        # 校验
        async with driver.session(database=cfg["database"]) as s:
            r = await s.run(
                """
                MATCH (n:IndustryCategory)
                WITH n.level AS lv, count(*) AS c
                RETURN collect({level: lv, count: c}) AS dist, sum(c) AS total
                """
            )
            rec = (await r.single()).data()
            dist = {it["level"]: it["count"] for it in rec["dist"]}
            print(
                f"\n校验：清理后 IndustryCategory 总数 = {rec['total']}；"
                f"按 level 分布 = {dist}"
            )
    finally:
        await driver.close()

    return 0


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--apply", action="store_true", help="真正执行修改")
    code = asyncio.run(run(p.parse_args().apply))
    sys.exit(code)


if __name__ == "__main__":
    main()