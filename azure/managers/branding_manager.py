from __future__ import annotations

from typing import Any, Dict


class BrandingManager:
    def __init__(self, template_name: str):
        self.template_name = template_name
        self.palette = {
            "primary": int("0xEFBF04", 16),
            "secondary": int("0x111111", 16),
            "background": int("0x090909", 16),
            "accent": int("0xFFFFFF", 16),
        }

    def get_embeds(self) -> Dict[str, Any]:
        return {
            "welcome": {
                "title": "AZOR AHAI",
                "description": "Welcome to the PvP community. Review the rules and complete onboarding.",
                "color": self.palette["primary"],
            },
            "rules": {
                "title": "Rules",
                "description": "Respect players, no toxicity, and follow staff direction.",
                "color": self.palette["secondary"],
            },
        }
