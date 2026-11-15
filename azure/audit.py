from dataclasses import dataclass, field
from datetime import datetime, timezone

from azure.database import log_event


@dataclass
class AuditEntry:
    guild_id: str
    event_type: str
    summary: str
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


def record_event(guild_id: str, event_type: str, summary: str):
    log_event(str(guild_id), event_type, summary)
    return AuditEntry(guild_id=str(guild_id), event_type=event_type, summary=summary)
