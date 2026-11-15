from __future__ import annotations


class WelcomeModule:
    def __init__(self, guild):
        self.guild = guild

    def build_message(self, member_name: str):
        return (
            f"Welcome to AZOR AHAI, {member_name}!\n"
            "Review the rules, introduce yourself, and apply for whitelist if required."
        )
