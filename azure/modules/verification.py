from __future__ import annotations


class VerificationModule:
    def __init__(self, guild):
        self.guild = guild

    def verify_actions(self, actions):
        return {"status": "approved", "actions": actions}
