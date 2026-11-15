from __future__ import annotations

import json
from typing import Any


class LocalAIClient:
    def __init__(self, base_url: str = "http://localhost:11434"):
        self.base_url = base_url

    def is_available(self):
        return False

    def plan(self, prompt: str) -> dict[str, Any]:
        return {
            "prompt": prompt,
            "actions": [],
            "status": "preview_only",
        }

    def generate_preview(self, prompt: str):
        return {
            "summary": "Local AI is not running. A template-based action preview is shown instead.",
            "structured": {"intent": "template_setup", "prompt": prompt},
            "json": json.dumps({"intent": "template_setup", "prompt": prompt}, ensure_ascii=True),
        }
