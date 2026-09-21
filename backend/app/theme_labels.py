"""产业主题标签工具（2026 二次改造）。

新模型：产业主题不再是关系，而是直接作为 **企业节点的 Neo4j 标签**：

    (:Company:`新能源`:`储能` {id, name})

Theme 节点保留，但只作为**配置注册表**存在（slug 唯一，承载 name /
icon / color / category / description 等元数据），企业不再与 Theme 建关系。

安全性：Cypher **不支持参数化标签**，只能把 slug 拼进语句文本。因此：
1. 任何 slug 使用前必须通过白名单校验（即存在于 Theme 注册表）；
2. 拼接前对反引号做转义（`` → ````），防注入。

读取方向：企业所属主题 = `labels(c)` 与注册表 slug 集合的交集。
"""
from __future__ import annotations

from fastapi import HTTPException

from .schemas import ThemeRef


# ---------------------------- 转义与拼接 ----------------------------

def escape_label(slug: str) -> str:
    """转义 Cypher 标签中的反引号。slug 必须已通过白名单校验。"""
    return slug.replace("`", "``")


def label_set_clause(slugs: list[str], variable: str = "c") -> str:
    """生成 ` SET c:`a`:`b`` 片段；空列表返回空串（语句仍合法）。"""
    if not slugs:
        return ""
    return " SET " + ":".join(f"{variable}:`{escape_label(s)}`" for s in slugs)


def label_remove_clause(slugs: list[str], variable: str = "c") -> str:
    """生成 ` REMOVE c:`a`:`b`` 片段；对节点没有的标签 REMOVE 是无害的空操作。"""
    if not slugs:
        return ""
    return " REMOVE " + ":".join(f"{variable}:`{escape_label(s)}`" for s in slugs)


# ---------------------------- 注册表 ----------------------------

async def load_theme_registry(session) -> dict[str, ThemeRef]:
    """拉取全部 Theme 节点，返回 {slug: ThemeRef}。Theme 只作为配置注册表。"""
    result = await session.run(
        """
        MATCH (t:Theme)
        RETURN t.slug AS slug, t.name AS name,
               coalesce(t.icon, '') AS icon,
               coalesce(t.color, '#3b82f6') AS color
        """
    )
    registry: dict[str, ThemeRef] = {}
    async for r in result:
        registry[r["slug"]] = ThemeRef(
            slug=r["slug"], name=r["name"], icon=r["icon"], color=r["color"]
        )
    return registry


def validate_slugs(registry: dict[str, ThemeRef], slugs: list[str]) -> list[str]:
    """白名单校验：slug 必须存在于注册表，否则 400。返回去重排序后的列表。"""
    unique = sorted(set(slugs))
    missing = [s for s in unique if s not in registry]
    if missing:
        raise HTTPException(
            status_code=400,
            detail=f"以下主题不存在：{', '.join(missing)}",
        )
    return unique


def refs_from_labels(
    labels: list[str], registry: dict[str, ThemeRef]
) -> list[ThemeRef]:
    """把企业节点上的标签（已过滤）映射回 ThemeRef 列表，按 slug 排序。"""
    out = [registry[l] for l in sorted(set(labels)) if l in registry]
    return out


def theme_label_filter_expr(variable: str = "c") -> str:
    """读取企业标签时的列表推导（配合 $themeLabels 参数使用）。

    过滤掉 'Company' 等非主题标签，且只保留注册表内的 slug，
    防止节点上历史遗留的杂标签混进主题。
    """
    return f"[l IN labels({variable}) WHERE l IN $themeLabels]"
