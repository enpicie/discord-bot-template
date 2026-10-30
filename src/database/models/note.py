from dataclasses import dataclass, field
from typing import Any, Dict

from database.models.subscriptable_mixin import SubscriptableMixin

@dataclass
class Note(SubscriptableMixin):
    """Example record: a named text note scoped to one Discord server.

    Stored as PK = "SERVER#<server_id>", SK = "NOTE#<normalized name>" in the
    single table. Replace with your own models; keep the Keys/from_dynamodb shape.
    """
    class Keys:
        SK_NOTE_PREFIX = "NOTE#"

        SERVER_ID = "server_id"
        NOTE_NAME = "note_name"
        CONTENT = "content"
        AUTHOR_ID = "author_id"

    server_id: str = field(metadata={'db_key': Keys.SERVER_ID})
    note_name: str = field(metadata={'db_key': Keys.NOTE_NAME})
    content: str = field(metadata={'db_key': Keys.CONTENT})
    author_id: str = field(metadata={'db_key': Keys.AUTHOR_ID})

    @staticmethod
    def normalize_name(name: str) -> str:
        """Key form of a note name, so lookups are case- and whitespace-insensitive."""
        return " ".join(name.split()).lower()

    @classmethod
    def from_dynamodb(cls, record: Dict[str, Any]) -> 'Note':
        return cls(
            server_id=record[cls.Keys.SERVER_ID],
            note_name=record.get(cls.Keys.NOTE_NAME),
            content=record.get(cls.Keys.CONTENT),
            author_id=record.get(cls.Keys.AUTHOR_ID),
        )
