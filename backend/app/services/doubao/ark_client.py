"""火山方舟（Ark）统一 REST 客户端：豆包大模型 / 翻译 / 视觉 / 向量 / 生图。

高内聚：方舟 v3（OpenAI 兼容）的全部请求细节——鉴权、endpoint、payload、错误处理——收敛于此。
低耦合：对外暴露语义方法（chat / chat_sync / vision / embed / generate_image），
       agent_service / translation_service / ai_photoshoot / retrieval_service 均只依赖本客户端。

说明：
  - 异步方法（httpx）供 async 业务使用；chat_sync（requests）供同步翻译提供商使用。
  - 未配置 Key 时 is_configured() 为 False，调用方据此走降级路径（Mock 引擎 / 回退原文 / 503）。
"""

import base64
import json
import logging
import time
from typing import AsyncIterator

import httpx
import requests

from app.config import settings

logger = logging.getLogger("ark")


class ArkError(RuntimeError):
    """方舟调用失败（网络 / 鉴权 / 业务错误）。"""


class ArkClient:
    """方舟 REST 客户端（模块级单例 ark_client）。"""

    def __init__(self):
        self._chat_endpoint = f"{settings.ark_base_url.rstrip('/')}/chat/completions"
        self._embeddings_endpoint = f"{settings.ark_base_url.rstrip('/')}/embeddings"
        self._images_endpoint = f"{settings.ark_base_url.rstrip('/')}/images/generations"

    # ── 配置探测 ────────────────────────────────────────────────

    def is_configured(self) -> bool:
        return bool(settings.ark_api_key)

    def _headers(self) -> dict:
        return {
            "Authorization": f"Bearer {settings.ark_api_key}",
            "Content-Type": "application/json",
        }

    def _chat_body(
        self,
        messages: list[dict],
        model: str,
        stream: bool,
        tools: list[dict] | None,
        temperature: float,
    ) -> dict:
        body: dict = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
            "stream": stream,
        }
        if tools:
            body["tools"] = tools
        return body

    # ── Chat（Agent / 翻译编排）─────────────────────────────────

    async def chat(
        self,
        messages: list[dict],
        *,
        model: str = "",
        stream: bool = False,
        tools: list[dict] | None = None,
        temperature: float = 0.7,
    ) -> str:
        """对话补全；stream=True 时聚合增量后返回完整文本。"""
        body = self._chat_body(messages, model or settings.ark_llm_model, stream, tools, temperature)
        async with httpx.AsyncClient(timeout=settings.ark_timeout) as client:
            resp = await client.post(self._chat_endpoint, headers=self._headers(), json=body)
            return self._handle_chat_response(resp, stream)

    async def chat_stream(
        self,
        messages: list[dict],
        *,
        model: str = "",
        tools: list[dict] | None = None,
        temperature: float = 0.7,
    ) -> AsyncIterator[str]:
        """流式对话：逐段产出文本增量（SSE）。"""
        body = self._chat_body(messages, model or settings.ark_llm_model, True, tools, temperature)
        async with httpx.AsyncClient(timeout=settings.ark_timeout) as client:
            async with client.stream("POST", self._chat_endpoint, headers=self._headers(), json=body) as resp:
                if resp.status_code != 200:
                    text = (await resp.aread()).decode("utf-8", errors="replace")
                    raise ArkError(f"Ark HTTP {resp.status_code}: {text[:300]}")
                async for line in resp.aiter_lines():
                    delta = self._parse_sse_line(line)
                    if delta:
                        yield delta

    def chat_sync(
        self,
        messages: list[dict],
        *,
        model: str = "",
        temperature: float = 0.3,
        timeout: float | None = None,
    ) -> str:
        """同步对话补全（翻译提供商等同步场景使用）。"""
        body = self._chat_body(messages, model or settings.ark_translate_model or settings.ark_llm_model, False, None, temperature)
        resp = requests.post(
            self._chat_endpoint,
            headers=self._headers(),
            json=body,
            timeout=timeout or settings.ark_timeout,
        )
        return self._handle_chat_response(resp, stream=False)

    # ── 视觉多模态（AI 旅拍）────────────────────────────────────

    async def vision(self, prompt: str, image_base64: str, mime: str = "image/jpeg") -> str:
        """图像理解：base64 data URI 走 OpenAI 兼容 image_url 格式。"""
        body = {
            "model": settings.ark_vision_model,
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt},
                        {"type": "image_url", "image_url": {"url": f"data:{mime};base64,{image_base64}"}},
                    ],
                }
            ],
        }
        async with httpx.AsyncClient(timeout=settings.ark_timeout) as client:
            resp = await client.post(self._chat_endpoint, headers=self._headers(), json=body)
            return self._handle_chat_response(resp, stream=False)

    # ── Embedding（知识库向量）──────────────────────────────────

    async def embed(self, texts: list[str]) -> list[list[float]]:
        """批量文本向量。返回与输入顺序一致的向量列表。"""
        async with httpx.AsyncClient(timeout=settings.ark_timeout) as client:
            resp = await client.post(
                self._embeddings_endpoint,
                headers=self._headers(),
                json={"model": settings.ark_embedding_model, "input": texts},
            )
            if resp.status_code != 200:
                raise ArkError(f"Ark embeddings HTTP {resp.status_code}: {resp.text[:300]}")
            data = resp.json()
        items = sorted(data.get("data", []), key=lambda d: d.get("index", 0))
        return [item["embedding"] for item in items]

    # ── 生图（旅拍增强，可选）───────────────────────────────────

    async def generate_image(self, prompt: str, size: str = "1024x1024") -> bytes:
        """文生图（doubao-seedream），返回 PNG/JPG 字节；未配置模型时抛 ArkError。"""
        if not settings.ark_image_model:
            raise ArkError("ark_image_model 未配置")
        async with httpx.AsyncClient(timeout=settings.ark_timeout * 2) as client:
            resp = await client.post(
                self._images_endpoint,
                headers=self._headers(),
                json={"model": settings.ark_image_model, "prompt": prompt, "size": size},
            )
            if resp.status_code != 200:
                raise ArkError(f"Ark images HTTP {resp.status_code}: {resp.text[:300]}")
            data = resp.json()
        items = data.get("data") or []
        if not items or not items[0].get("b64_json"):
            raise ArkError(f"生图响应缺少 b64_json: {json.dumps(data)[:200]}")
        return base64.b64decode(items[0]["b64_json"])

    # ── 响应解析 ────────────────────────────────────────────────

    @staticmethod
    def _handle_chat_response(resp: "httpx.Response | requests.Response", stream: bool) -> str:
        if resp.status_code != 200:
            raise ArkError(f"Ark HTTP {resp.status_code}: {resp.text[:300]}")
        data = resp.json()
        if stream:
            chunks = [
                choice.get("delta", {}).get("content", "")
                for choice in data.get("choices", [])
            ]
            return "".join(chunks).strip()
        choices = data.get("choices") or []
        if not choices:
            raise ArkError(f"Ark 响应缺少 choices: {json.dumps(data)[:200]}")
        return (choices[0].get("message", {}).get("content") or "").strip()

    @staticmethod
    def _parse_sse_line(line: str) -> str:
        line = line.strip()
        if not line.startswith("data:"):
            return ""
        payload = line[5:].strip()
        if payload == "[DONE]":
            return ""
        try:
            data = json.loads(payload)
        except Exception:  # noqa: BLE001 - 非 JSON 行忽略
            return ""
        chunks = [choice.get("delta", {}).get("content", "") for choice in data.get("choices", [])]
        return "".join(chunks)

    @staticmethod
    def elapsed_ms(start: float) -> int:
        return int((time.time() - start) * 1000)


ark_client = ArkClient()
