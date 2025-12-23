\
from __future__ import annotations
import os
import requests
import json
import re
from typing import Any, Dict, List, Optional

DEFAULT_BASE = "https://generativelanguage.googleapis.com/v1beta"
DEFAULT_MODEL = "gemini-2.0-flash"

class GeminiError(RuntimeError):
    pass

def _extract_json(text: str) -> Dict[str, Any]:
    """
    Gemini đôi khi trả thêm chữ. Hàm này cố gắng lấy JSON object đầu tiên.
    """
    text = text.strip()
    try:
        return json.loads(text)
    except Exception:
        m = re.search(r"\{.*\}", text, flags=re.S)
        if not m:
            raise GeminiError("Không trích xuất được JSON từ phản hồi AI.")
        return json.loads(m.group(0))

def generate_json(
    prompt: str,
    api_key: str,
    model: str = DEFAULT_MODEL,
    api_base: str = DEFAULT_BASE,
    temperature: float = 0.7,
    max_output_tokens: int = 1024,
) -> Dict[str, Any]:
    """
    Gọi Gemini Developer API (AI Studio key) theo endpoint generateContent.
    """
    if not api_key:
        raise GeminiError("Thiếu GEMINI_API_KEY")

    url = f"{api_base.rstrip('/')}/models/{model}:generateContent"
    headers = {
        "Content-Type": "application/json",
        "x-goog-api-key": api_key,
    }

    payload = {
        "contents": [{"role": "user", "parts": [{"text": prompt}]}],
        "generationConfig": {
            "temperature": float(temperature),
            "maxOutputTokens": int(max_output_tokens),
            "responseMimeType": "application/json",
        },
    }

    r = requests.post(url, headers=headers, json=payload, timeout=90)
    if r.status_code >= 400:
        raise GeminiError(f"Lỗi gọi Gemini API ({r.status_code}): {r.text[:500]}")

    data = r.json()
    # Lấy text/json từ candidates
    try:
        parts = data["candidates"][0]["content"]["parts"]
        # parts có thể là [{"text": "..."}] hoặc [{"inlineData":...}]... ta ưu tiên text
        joined = "\n".join([p.get("text","") for p in parts if isinstance(p, dict)])
        if not joined.strip():
            # fallback: dump whole
            joined = json.dumps(data, ensure_ascii=False)
        return _extract_json(joined)
    except Exception as e:
        raise GeminiError(f"Không đọc được phản hồi Gemini: {e}")
