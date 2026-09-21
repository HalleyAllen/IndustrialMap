"""企业批量导入路由。

两阶段流程（先自检、后落库，避免误写）：
  1. ``POST /api/import/companies/preview`` —— 解析文件 + 重复自检，**不写库**
  2. ``POST /api/import/companies/commit``  —— 依据同一份文件与策略，确认后写入

重复自检分三类：
  - **库内重复**：规范化名称与 Neo4j 中已有企业相同
  - **文件内重复**：同一文件内同名多次出现，仅首次计入待导入
  - **无效行**：名称为空或超过 200 字符

冲突策略 ``on_duplicate``：
  - ``skip``      跳过库中已存在的企业（默认）
  - ``update``    保留原有主题，追加上文件中的主题
  - ``overwrite`` 用文件中的主题替换原有主题

文件格式：CSV / TXT，UTF-8（含 BOM）或 GB18030 自动识别，
分隔符在 ``,`` / ``\\t`` / ``;`` / ``|`` 间自动嗅探。
第 1 列为必填的企业名称；第 2 列可选，为主题（slug 或中文名，
多个用 ``,`` ``|`` ``;`` ``、`` ``/`` 分隔），与默认主题取并集。
"""
from __future__ import annotations

import csv
import io
import json
import re
import time
import uuid
from typing import Optional

from fastapi import APIRouter, File, Form, HTTPException, UploadFile

from .. import neo4j_manager
from ..schemas import (
    ImportCommitOut,
    ImportIssueRow,
    ImportNewRow,
    ImportPreviewOut,
    ThemeRef,
)


router = APIRouter(prefix="/api/import", tags=["import"])

_MAX_NAME_LEN = 200
_MAX_UPLOAD_BYTES = 10 * 1024 * 1024
_BATCH_SIZE = 500
_THEME_SPLIT = re.compile(r"[|;；、,，/]")
_DEFAULT_COLOR = "#3b82f6"
# 首行若整格命中这些词，视为表头而非企业名
_HEADER_TOKENS = {
    "企业名称", "企业名", "企业", "公司名称", "公司名称全称", "公司", "名称",
    "name", "company", "company_name", "company name", "enterprise",
    "enterprise_name", "enterprise name",
}
_ALLOWED_ON_DUPLICATE = ("skip", "update", "overwrite")


# ---------------------------- 文本解析 ----------------------------

def _normalize(name: str) -> str:
    """名称规范化，仅用于重复判定，绝不回写数据库。"""
    s = name.replace("\u3000", " ")
    s = re.sub(r"\s+", " ", s)
    return s.strip().casefold()


def _decode(raw: bytes) -> tuple[str, str]:
    """按 UTF-8(BOM) → UTF-8 → GB18030 顺序尝试解码。"""
    for enc in ("utf-8-sig", "utf-8", "gb18030"):
        try:
            return raw.decode(enc), enc
        except UnicodeDecodeError:
            continue
    return raw.decode("utf-8", errors="replace"), "utf-8(replace)"


def _sniff_delimiter(text: str) -> str:
    """嗅探分隔符；单列文件会失败，退回逗号。"""
    sample = "\n".join(text.splitlines()[:20])
    if not sample.strip():
        return ","
    try:
        return csv.Sniffer().sniff(sample, delimiters=",\t;|").delimiter
    except csv.Error:
        return ","


def _looks_like_header(row: list[str]) -> bool:
    if not row:
        return False
    first = row[0].replace("\u3000", " ").strip().casefold()
    return first in _HEADER_TOKENS


def _split_theme_cell(cell: str) -> list[str]:
    return [p.strip() for p in _THEME_SPLIT.split(cell) if p.strip()]


def _parse_rows(text: str, delimiter: str) -> tuple[list[dict], bool]:
    """解析为 ``[{line, name, theme_tokens}]``；行号为文件原始行号。"""
    rows: list[dict] = []
    header_skipped = False
    reader = csv.reader(io.StringIO(text), delimiter=delimiter)
    for idx, raw in enumerate(reader, start=1):
        if not raw or not "".join(raw).strip():
            continue  # 空行不计入
        if idx == 1 and _looks_like_header(raw):
            header_skipped = True
            continue
        theme_tokens = _split_theme_cell(raw[1]) if len(raw) > 1 else []
        rows.append(
            {"line": idx, "name": raw[0].strip(), "theme_tokens": theme_tokens}
        )
    return rows, header_skipped


def _parse_slug_param(raw: Optional[str]) -> list[str]:
    """解析表单里的默认主题：支持 JSON 数组或逗号分隔。"""
    if not raw:
        return []
    value = raw.strip()
    if value.startswith("["):
        try:
            parsed = json.loads(value)
            if isinstance(parsed, list):
                return [str(x).strip() for x in parsed if str(x).strip()]
        except ValueError:
            pass
    return [p.strip() for p in value.split(",") if p.strip()]


# ---------------------------- 库侧读取 ----------------------------

def _clean_themes(raw: Optional[list[dict]]) -> list[ThemeRef]:
    out: list[ThemeRef] = []
    for t in raw or []:
        if not t or not t.get("slug"):
            continue
        out.append(
            ThemeRef(
                slug=t["slug"],
                name=t.get("name") or t["slug"],
                icon=t.get("icon") or "",
                color=t.get("color") or _DEFAULT_COLOR,
            )
        )
    return out


async def _load_db_companies(session) -> tuple[dict[str, dict], int]:
    """返回 ``({规范化名: {id, name, themes}}, 库内重名组数)``。

    一次拉全量再在内存建索引，避免逐行查询。
    同规范化名出现多次时保留第一个（按 id 排序保证结果稳定），
    重名组数用于提示历史脏数据。
    """
    result = await session.run(
        """
        MATCH (c:Company)
        OPTIONAL MATCH (c)-[:BELONGS_TO]->(t:Theme)
        WITH c, collect(DISTINCT {
            slug: t.slug, name: t.name,
            icon: coalesce(t.icon, ''), color: coalesce(t.color, '#3b82f6')
        }) AS themes
        RETURN c.id AS id, c.name AS name, themes
        ORDER BY c.id
        """
    )
    index: dict[str, dict] = {}
    key_hits: dict[str, int] = {}
    async for r in result:
        key = _normalize(r["name"] or "")
        if not key:
            continue
        key_hits[key] = key_hits.get(key, 0) + 1
        index.setdefault(
            key,
            {"id": r["id"], "name": r["name"], "themes": _clean_themes(r["themes"])},
        )
    dup_groups = sum(1 for n in key_hits.values() if n > 1)
    return index, dup_groups


async def _load_themes(session) -> tuple[dict[str, ThemeRef], dict[str, str]]:
    """返回 ``(by_slug, by_normalized_name → slug)``。"""
    result = await session.run(
        """
        MATCH (t:Theme)
        RETURN t.slug AS slug, t.name AS name,
               coalesce(t.icon, '') AS icon,
               coalesce(t.color, '#3b82f6') AS color
        """
    )
    by_slug: dict[str, ThemeRef] = {}
    by_name: dict[str, str] = {}
    async for r in result:
        ref = ThemeRef(
            slug=r["slug"], name=r["name"], icon=r["icon"], color=r["color"]
        )
        by_slug[r["slug"]] = ref
        by_name[_normalize(r["name"] or "")] = r["slug"]
        by_name.setdefault(_normalize(r["slug"] or ""), r["slug"])
    return by_slug, by_name


def _resolve_themes(
    tokens: list[str],
    default_slugs: list[str],
    by_slug: dict[str, ThemeRef],
    by_name: dict[str, str],
) -> tuple[list[str], list[str]]:
    """把 token（slug 或中文名）解析为合法 slug 列表，返回 (slugs, 未知项)。"""
    slugs: list[str] = []
    unknown: list[str] = []

    for s in default_slugs:
        if s in by_slug:
            slugs.append(s)
        else:
            unknown.append(s)

    for tk in tokens:
        key = tk.strip()
        if not key:
            continue
        if key in by_slug:
            slugs.append(key)
            continue
        mapped = by_name.get(_normalize(key))
        if mapped:
            slugs.append(mapped)
        else:
            unknown.append(key)

    return sorted(set(slugs)), sorted(set(unknown))


# ---------------------------- 核心分析 ----------------------------

async def _analyze(
    raw: bytes,
    file_name: str,
    default_slugs: list[str],
    read_theme_column: bool,
    on_duplicate: str,
) -> tuple[ImportPreviewOut, list[dict], list[dict]]:
    """解析 + 自检，返回 (预览报告, 待创建行, 待更新行)。"""
    text, encoding = _decode(raw)
    delimiter = _sniff_delimiter(text)
    parsed, header_skipped = _parse_rows(text, delimiter)

    preview = ImportPreviewOut(
        file_name=file_name,
        encoding=encoding,
        delimiter=delimiter,
        header_skipped=header_skipped,
        total_rows=len(parsed),
    )
    if not parsed:
        preview.notes.append("文件中没有解析到任何数据行")
        return preview, [], []

    session = await neo4j_manager.get_session()
    try:
        db_index, dup_groups = await _load_db_companies(session)
        by_slug, by_name = await _load_themes(session)
    finally:
        await session.close()
    preview.db_dup_names = dup_groups

    seen: dict[str, int] = {}
    new_candidates: list[dict] = []
    conflict_meta: list[dict] = []
    used_slugs: set[str] = set()
    unknown_tokens: set[str] = set()

    for row in parsed:
        name: str = row["name"]
        line: int = row["line"]

        if not name:
            preview.invalid_rows.append(
                ImportIssueRow(line=line, name="", reason="名称为空")
            )
            continue
        if len(name) > _MAX_NAME_LEN:
            preview.invalid_rows.append(
                ImportIssueRow(
                    line=line,
                    name=name[:60] + "…",
                    reason=f"名称超过 {_MAX_NAME_LEN} 字符（当前 {len(name)}）",
                )
            )
            continue

        norm = _normalize(name)
        if norm in seen:
            preview.file_dups.append(
                ImportIssueRow(
                    line=line,
                    name=name,
                    reason="文件内重复，已忽略（仅首次出现计入）",
                    first_line=seen[norm],
                )
            )
            continue
        seen[norm] = line

        tokens = row["theme_tokens"] if read_theme_column else []
        slugs, unknown = _resolve_themes(tokens, default_slugs, by_slug, by_name)
        unknown_tokens.update(unknown)
        used_slugs.update(slugs)

        hit = db_index.get(norm)
        if hit is not None:
            conflict_meta.append(
                {
                    "line": line,
                    "name": name,
                    "slugs": slugs,
                    "existing_id": hit["id"],
                    "existing_themes": hit["themes"],
                }
            )
            preview.conflicts.append(
                ImportIssueRow(
                    line=line,
                    name=name,
                    reason="库中已存在同名企业",
                    existing_id=hit["id"],
                    existing_themes=hit["themes"],
                )
            )
            continue

        new_candidates.append({"line": line, "name": name, "slugs": slugs})

    # ---- 按冲突策略决定实际写入范围 ----
    create_rows = [
        {"id": str(uuid.uuid4()), "name": c["name"], "slugs": c["slugs"]}
        for c in new_candidates
    ]
    update_rows: list[dict] = []
    skipped = 0

    if on_duplicate == "update":
        update_rows = [
            {"id": m["existing_id"], "name": m["name"], "slugs": m["slugs"]}
            for m in conflict_meta
        ]
    elif on_duplicate == "overwrite":
        update_rows = [
            {
                "id": m["existing_id"],
                "name": m["name"],
                "slugs": m["slugs"],
                "replace": True,
            }
            for m in conflict_meta
        ]
    else:  # skip
        skipped = len(conflict_meta)

    preview.new_count = len(new_candidates)
    preview.conflict_count = len(preview.conflicts)
    preview.file_dup_count = len(preview.file_dups)
    preview.invalid_count = len(preview.invalid_rows)
    preview.importable_count = len(create_rows) + len(update_rows)
    preview.new_rows = [
        ImportNewRow(line=c["line"], name=c["name"], theme_slugs=c["slugs"])
        for c in new_candidates
    ]
    preview.themes_used = [by_slug[s] for s in sorted(used_slugs) if s in by_slug]
    preview.unknown_themes = sorted(unknown_tokens)

    # ---- 提示信息 ----
    if on_duplicate == "skip" and skipped:
        preview.notes.append(f"按「跳过」策略，{skipped} 条库内重复不会被处理")
    if preview.db_dup_names:
        preview.notes.append(
            f"数据库中已有 {preview.db_dup_names} 组同名企业（历史数据），建议先清理"
        )
    if preview.unknown_themes:
        preview.notes.append(
            "以下主题在库中不存在，相关行不会被挂载主题："
            + "、".join(preview.unknown_themes)
        )
    unthemed = sum(1 for c in create_rows if not c["slugs"])
    if unthemed:
        preview.notes.append(f"{unthemed} 条新企业未指定主题，将以「未分类」导入")

    return preview, create_rows, update_rows


# ---------------------------- 端点 ----------------------------

@router.post("/companies/preview", response_model=ImportPreviewOut)
async def preview_companies_import(
    file: UploadFile = File(..., description="CSV / TXT 文件"),
    default_theme_slugs: str = Form("", description="JSON 数组或逗号分隔的主题 slug"),
    on_duplicate: str = Form("skip", description="skip / update / overwrite"),
    read_theme_column: bool = Form(True, description="是否读取第 2 列作为主题"),
) -> ImportPreviewOut:
    """自检：解析文件并与库中数据比对，返回重复/无效行报告，**不写库**。"""
    if on_duplicate not in _ALLOWED_ON_DUPLICATE:
        raise HTTPException(
            status_code=400,
            detail=f"on_duplicate 只能是 {'/'.join(_ALLOWED_ON_DUPLICATE)}",
        )
    raw = await file.read()
    if not raw:
        raise HTTPException(status_code=400, detail="文件内容为空")
    if len(raw) > _MAX_UPLOAD_BYTES:
        raise HTTPException(
            status_code=400,
            detail=f"文件过大（上限 {_MAX_UPLOAD_BYTES // 1024 // 1024} MB）",
        )

    preview, _, _ = await _analyze(
        raw=raw,
        file_name=file.filename or "",
        default_slugs=_parse_slug_param(default_theme_slugs),
        read_theme_column=read_theme_column,
        on_duplicate=on_duplicate,
    )
    return preview


@router.post("/companies/commit", response_model=ImportCommitOut)
async def commit_companies_import(
    file: UploadFile = File(...),
    default_theme_slugs: str = Form(""),
    on_duplicate: str = Form("skip"),
    read_theme_column: bool = Form(True),
) -> ImportCommitOut:
    """执行导入。会先用同一份文件重跑一次自检，再写入，避免预览与写入不一致。"""
    if on_duplicate not in _ALLOWED_ON_DUPLICATE:
        raise HTTPException(
            status_code=400,
            detail=f"on_duplicate 只能是 {'/'.join(_ALLOWED_ON_DUPLICATE)}",
        )
    raw = await file.read()
    if not raw:
        raise HTTPException(status_code=400, detail="文件内容为空")

    started = time.perf_counter()
    preview, create_rows, update_rows = await _analyze(
        raw=raw,
        file_name=file.filename or "",
        default_slugs=_parse_slug_param(default_theme_slugs),
        read_theme_column=read_theme_column,
        on_duplicate=on_duplicate,
    )

    result = ImportCommitOut(
        skipped=preview.conflict_count if on_duplicate == "skip" else 0
    )
    if not create_rows and not update_rows:
        result.duration_ms = int((time.perf_counter() - started) * 1000)
        return result

    session = await neo4j_manager.get_session()
    try:
        # 1) 新建企业节点（MERGE on id，天然幂等）
        for chunk in _chunks(create_rows, _BATCH_SIZE):
            res = await session.run(
                """
                UNWIND $rows AS row
                MERGE (c:Company {id: row.id})
                ON CREATE SET c.name = row.name
                """,
                rows=[{"id": r["id"], "name": r["name"]} for r in chunk],
            )
            summary = await res.consume()
            result.created += summary.counters.nodes_created

        from_statements = create_rows + update_rows

        # 2) overwrite 策略：先清空这些企业已有的主题关系
        if on_duplicate == "overwrite":
            ids = [r["id"] for r in update_rows]
            for chunk in _chunks(ids, _BATCH_SIZE):
                res = await session.run(
                    """
                    UNWIND $ids AS cid
                    MATCH (c:Company {id: cid})-[r:BELONGS_TO]->(:Theme)
                    DELETE r
                    """,
                    ids=chunk,
                )
                await res.consume()

        # 3) 建立主题关系（MERGE 保证重复执行不会新增）
        pairs = [
            {"cid": r["id"], "slug": s} for r in from_statements for s in r["slugs"]
        ]
        for chunk in _chunks(pairs, _BATCH_SIZE):
            res = await session.run(
                """
                UNWIND $pairs AS p
                MATCH (c:Company {id: p.cid})
                MATCH (t:Theme {slug: p.slug})
                MERGE (c)-[:BELONGS_TO]->(t)
                """,
                pairs=chunk,
            )
            summary = await res.consume()
            result.themes_linked += summary.counters.relationships_created

        result.updated = len(update_rows)
    finally:
        await session.close()

    result.duration_ms = int((time.perf_counter() - started) * 1000)
    return result


def _chunks(items: list, size: int):
    """把列表按 size 切片，避免单次 UNWIND 参数过大。"""
    for i in range(0, len(items), size):
        yield items[i : i + size]
