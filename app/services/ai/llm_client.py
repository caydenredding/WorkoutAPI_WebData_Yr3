# app/ai/llm_client.py
from __future__ import annotations

import os
from typing import Any, Dict, Optional

import httpx


class LLMClient:
    """
    Local LLM client using Ollama (free, runs on your machine).

    Env vars (optional):
      - OLLAMA_BASE_URL (default: http://127.0.0.1:11434)
      - OLLAMA_MODEL (default: llama3.1:latest)
      - OLLAMA_TIMEOUT_SECONDS (default: 90)
      - OLLAMA_TEMPERATURE (default: 0.4)
      - OLLAMA_NUM_PREDICT (default: 350)  # caps output length
    """

    def __init__(
        self,
        base_url: Optional[str] = None,
        model: Optional[str] = None,
        timeout_seconds: Optional[float] = None,
        temperature: Optional[float] = None,
        num_predict: Optional[int] = None,
    ) -> None:
        self.base_url = (base_url or os.getenv("OLLAMA_BASE_URL", "http://127.0.0.1:11434")).rstrip("/")
        self.model = model or os.getenv("OLLAMA_MODEL", "llama3.1:latest")
        self.timeout = timeout_seconds or float(os.getenv("OLLAMA_TIMEOUT_SECONDS", "90"))

        # Generation options
        self.temperature = temperature if temperature is not None else float(os.getenv("OLLAMA_TEMPERATURE", "0.4"))
        self.num_predict = num_predict if num_predict is not None else int(os.getenv("OLLAMA_NUM_PREDICT", "350"))

    def generate_weekly_summary(self, facts: Dict[str, Any], tone: str = "friendly") -> str:
        tone = (tone or "friendly").strip().lower()

        system_instructions = f"""
You are a fitness coach writing a weekly recap inside a workout tracker.

CRITICAL RULES:
- Use ONLY numbers and dates in the provided JSON. Do NOT invent workouts, sets, PRs, weights, or weigh-ins.
- If a PR has "previous": null, treat it as a first recorded benchmark (do not claim improvement).
- If "previous" exists, you may say it improved and compute/mention the difference.
- All weigths are in KG, all distances in KM, all dates in YYYY-MM-DD format.
- Do NOT just recite the facts. Use them to write an engaging, insightful, and personalized story of the user's week in fitness.
- OALLAMA MUST RESPOND IN THE EXACT FORMAT BELOW, using the provided JSON data. DO NOT DEVIATE.

OUTPUT FORMAT (exactly):
Headline: <1 sentence>
Summary: <2 sentences max>

Highlights:
- <3–6 bullets>

Next week focus:
- <2–4 bullets>

Data notes:
- <1–3 bullets>
""".strip()

        user_content = f"""
Tone: {tone}

Weekly summary JSON:
{facts}

Write the weekly recap now.
""".strip()

        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system_instructions},
                {"role": "user", "content": user_content},
            ],
            "stream": False,
            "options": {
                "temperature": self.temperature,
                "num_predict": self.num_predict,
            },
        }

        url = f"{self.base_url}/api/chat"

        try:
            with httpx.Client(timeout=self.timeout) as client:
                r = client.post(url, json=payload)
                r.raise_for_status()
                data = r.json()

            content = (data.get("message") or {}).get("content")
            if not content:
                return f"[ollama] Unexpected response shape: {data}"
            return content.strip()

        except httpx.ConnectError:
            return (
                "Could not connect to Ollama. Make sure it's running:\n"
                "  OLLAMA_KEEP_ALIVE=30m ollama serve\n"
                f"and that OLLAMA_BASE_URL is correct (currently {self.base_url})."
            )
        except httpx.HTTPStatusError as e:
            return f"Ollama error ({e.response.status_code}): {e.response.text}"
        except Exception as e:
            return f"Unexpected error calling Ollama: {e}"
