"""AI 服务模块（精简版）。

当前仅保留 LLM 连通性测试能力（`test_connection`），
供「系统配置 → AI 服务」页验证 OpenAI 兼容接口。
企业信息补全相关代码已随 Company 字段精简移除。
"""
from __future__ import annotations

from typing import Any, Optional

import httpx


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