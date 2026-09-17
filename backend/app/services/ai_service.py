"""AI 信息补全服务。

调用管理员在 Web 端配置的 LLM（任意 OpenAI 兼容协议的接口），
根据企业名称 + 已知字段推断并补全其它字段，再由调用方写回数据库。
"""
from __future__ import annotations

import json
import re
from typing import Any, Optional

import httpx

from .. import settings_db


SYSTEM_PROMPT = (
    "你是一名企业信息补全助手。根据用户给定的企业名称以及已知字段，"
    "用你掌握的知识补全缺失字段，并严格以 JSON 格式返回结果。不要输出任何额外说明。"
)

USER_TEMPLATE = """企业名称：{name}
{known}

请补全以下字段，以 JSON 形式返回：
{{
  "description": "<一句话中文简介，20-80字>",
  "website": "<官网域名，如 https://example.com；无则为空字符串>",
  "founded_year": <成立年份（整数），未知则填 null>,
  "address": "<注册或总部地址，未知则为空字符串>",
  "scale": "<small / medium / large 之一，未知则为空字符串>"
}}
"""


_JSON_BLOCK_RE = re.compile(r"\{.*\}", re.DOTALL)


def _extract_json(text: str) -> dict:
    """从模型返回文本中尽量安全地解析 JSON。"""
    # 优先尝试 ```json ... ``` 代码块
    fence = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL | re.IGNORECASE)
    candidate = fence.group(1) if fence else text
    # 否则抓取第一个 {...}
    if not candidate.strip().startswith("{"):
        m = _JSON_BLOCK_RE.search(text)
        if m:
            candidate = m.group(0)
    candidate = candidate.strip()
    return json.loads(candidate)


def _is_openai_native(provider: str) -> bool:
    """是否原生支持 response_format=json_object 的 provider。"""
    return provider.lower() in {"openai", "azure", "deepseek", "zhipu", "ollama"}


async def _call_chat(
    cfg: dict,
    messages: list[dict],
    *,
    json_mode: bool,
    timeout: float = 60.0,
) -> str:
    """调用任意 OpenAI 兼容的 /chat/completions 接口。"""
    base_url = cfg["base_url"].rstrip("/")
    url = f"{base_url}/chat/completions"
    headers = {
        "Authorization": f"Bearer {cfg['api_key']}",
        "Content-Type": "application/json",
    }
    body: dict[str, Any] = {
        "model": cfg["model"],
        "messages": messages,
        "temperature": cfg.get("temperature", 0.3),
    }
    if json_mode and _is_openai_native(cfg["provider"]):
        body["response_format"] = {"type": "json_object"}
    # 透传额外参数（max_tokens 等）
    for k, v in (cfg.get("extra") or {}).items():
        if k not in body:
            body[k] = v

    async with httpx.AsyncClient(timeout=timeout) as client:
        resp = await client.post(url, headers=headers, json=body)
        if resp.status_code >= 400:
            raise RuntimeError(
                f"AI 服务返回 {resp.status_code}: {resp.text[:500]}"
            )
        data = resp.json()

    try:
        return data["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError) as e:
        raise RuntimeError(f"AI 响应格式异常: {data} ({e})") from e


async def test_connection(
    provider: str,
    base_url: str,
    api_key: str,
    model: str,
    temperature: float = 0.3,
    extra: Optional[dict] = None,
) -> dict:
    """用 ping prompt 测试连通性，成功即代表配置可用。"""
    cfg = {
        "provider": provider,
        "base_url": base_url,
        "api_key": api_key,
        "model": model,
        "temperature": temperature,
        "extra": extra or {},
    }
    try:
        text = await _call_chat(
            cfg,
            [
                {"role": "system", "content": "你是连通性测试助手。"},
                {"role": "user", "content": "ping。请只回复一个字：pong"},
            ],
            json_mode=False,
            timeout=20.0,
        )
        return {"ok": True, "reply": text.strip()[:120]}
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "error": str(e)}


async def enrich_company(
    company: dict[str, Any],
    *,
    user_hint: Optional[str] = None,
) -> dict:
    """根据企业名称 + 已知字段推断缺失字段。

    `company` 形如：
        {"id": "...", "name": "...", "industry_name": "...", "address": "...",
         "description": "...", "founded_year": 2010, "website": "...", "scale": "..."}

    返回补全建议：
        {"description": "...", "website": "...", "founded_year": 2010,
         "address": "...", "scale": "...", "raw": "<模型原始输出>"}
    """
    cfg = settings_db.get_ai_settings()
    if cfg is None:
        raise RuntimeError("尚未配置 AI 服务，请先在「数据库配置」页填写")

    # 拼接已知字段给模型参考（缺什么补什么）
    known_lines = []
    field_map = [
        ("industry_name", "所属行业"),
        ("description", "简介"),
        ("address", "地址"),
        ("founded_year", "成立年份"),
        ("website", "官网"),
        ("scale", "规模"),
    ]
    for key, label in field_map:
        v = company.get(key)
        if v not in (None, "", 0):
            known_lines.append(f"已知{label}：{v}")
    if user_hint:
        known_lines.append(f"用户补充提示：{user_hint}")
    known = "\n".join(known_lines) if known_lines else "（无任何已知字段）"

    user_prompt = USER_TEMPLATE.format(name=company.get("name", ""), known=known)

    text = await _call_chat(
        cfg,
        [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ],
        json_mode=True,
    )

    try:
        data = _extract_json(text)
    except json.JSONDecodeError:
        # 兼容部分模型不严格遵守 JSON 的情况
        data = {
            "description": text.strip()[:200],
            "website": None,
            "founded_year": None,
            "address": None,
            "scale": None,
        }

    # 标准化字段
    def _clean_str(v: Any) -> Optional[str]:
        if v is None:
            return None
        s = str(v).strip()
        return s or None

    def _clean_year(v: Any) -> Optional[int]:
        try:
            if v is None or v == "":
                return None
            y = int(v)
            if 1700 <= y <= 2100:
                return y
            return None
        except (TypeError, ValueError):
            return None

    return {
        "description": _clean_str(data.get("description")),
        "website": _clean_str(data.get("website")),
        "founded_year": _clean_year(data.get("founded_year")),
        "address": _clean_str(data.get("address")),
        "scale": _clean_str(data.get("scale")),
        "raw": text,
    }