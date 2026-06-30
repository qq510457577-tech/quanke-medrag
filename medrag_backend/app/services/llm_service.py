from __future__ import annotations

import json
from typing import Any, Dict, List, Optional

import httpx

from ..config import DEFAULT_MODEL, DEEPSEEK_API_KEY, DEEPSEEK_BASE_URL, DEEPSEEK_ENABLED


def _safe_json_extract(content: str) -> Dict[str, Any]:
    start = content.find("{")
    end = content.rfind("}") + 1
    if start < 0 or end <= start:
        raise ValueError("No JSON object found in model output")
    payload = content[start:end].replace("```json", "").replace("```", "").strip()
    payload = payload.replace(",}", "}").replace(",]", "]")
    return json.loads(payload)


class LLMService:
    def __init__(self) -> None:
        self.enabled = DEEPSEEK_ENABLED
        self.client = httpx.AsyncClient(timeout=60.0)

    async def refine_final_report(
        self,
        *,
        patient_summary: str,
        candidates: List[Dict],
        reasoning: str,
        references: List[Dict],
    ) -> Optional[Dict[str, Any]]:
        if not self.enabled:
            return None

        system_prompt = (
            "你是面向基层全科医生的辅助诊断系统。"
            "请根据给定候选诊断、追问结果和循证资料输出紧凑 JSON。"
            "不要编造检查结果。"
        )
        user_prompt = json.dumps(
            {
                "patient_summary": patient_summary,
                "candidates": candidates[:3],
                "reasoning": reasoning,
                "references": references[:3],
                "schema": {
                    "clinical_reasoning": "string",
                    "diagnoses": [
                        {
                            "name": "string",
                            "probability": 0,
                            "basis": ["string"],
                            "next_steps": ["string"],
                        }
                    ],
                },
            },
            ensure_ascii=False,
        )
        response = await self.client.post(
            f"{DEEPSEEK_BASE_URL}/v1/chat/completions",
            headers={"Authorization": f"Bearer {DEEPSEEK_API_KEY}"},
            json={
                "model": DEFAULT_MODEL,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                "temperature": 0.2,
                "max_tokens": 1400,
                "response_format": {"type": "json_object"},
            },
        )
        try:
            response.raise_for_status()
            content = response.json()["choices"][0]["message"]["content"]
            return _safe_json_extract(content)
        except (httpx.HTTPStatusError, KeyError, ValueError, json.JSONDecodeError):
            # DeepSeek key/model/network failures must not break the local RAG report.
            return None
