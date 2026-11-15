from __future__ import annotations


class FiveMModule:
    def __init__(self, guild):
        self.guild = guild

    def server_summary(self):
        return {"guild": str(self.guild.id), "status": "ready"}
