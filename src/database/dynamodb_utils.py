"""DynamoDB access for the bot's single table.

Key scheme: every record for a Discord server shares PK = "SERVER#<server_id>";
the SK prefix says what the record is ("NOTE#<name>", ...). One Query on the PK
with an SK prefix returns every record of a kind for that server.
"""
from typing import List

from boto3.dynamodb.conditions import Key
from mypy_boto3_dynamodb.service_resource import Table

import utils.bot_messages as bot_messages
from commands.models.response_message import ResponseMessage
from database.models.note import Note

PK_SERVER_PREFIX = "SERVER#"
PK_ATTR = "PK"
SK_ATTR = "SK"

def build_server_pk(server_id: str) -> str:
    """Build the DynamoDB partition key value for a server's records."""
    return f"{PK_SERVER_PREFIX}{server_id}"

def build_note_key(server_id: str, note_name: str) -> dict:
    """Build the DynamoDB primary key dict for a NOTE record."""
    return {PK_ATTR: build_server_pk(server_id), SK_ATTR: Note.Keys.SK_NOTE_PREFIX + Note.normalize_name(note_name)}

def put_note(note: Note, table: Table) -> None:
    """Upsert a NOTE record, keyed by normalized note name."""
    item = {
        **build_note_key(note.server_id, note.note_name),
        Note.Keys.SERVER_ID: note.server_id,
        Note.Keys.NOTE_NAME: note.note_name,
        Note.Keys.CONTENT: note.content,
        Note.Keys.AUTHOR_ID: note.author_id,
    }
    print(f"[db] PUT NOTE server={note.server_id} note={note.note_name!r}")
    table.put_item(Item=item)
    print("[db] -> ok")

def get_note_or_fail(server_id: str, note_name: str, table: Table) -> Note | ResponseMessage:
    """Fetch a NOTE record. Returns a Note on success, or a user-facing
    ResponseMessage if it doesn't exist."""
    print(f"[db] GET NOTE server={server_id} note={note_name!r}")
    response = table.get_item(Key=build_note_key(server_id, note_name))
    record = response.get("Item")
    if not record:
        print(f"[db] -> not found NOTE server={server_id} note={note_name!r}")
        return ResponseMessage(content=bot_messages.NOTE_NOT_FOUND)
    print(f"[db] -> found NOTE server={server_id} note={note_name!r}")
    return Note.from_dynamodb(record)

def get_notes_for_server(server_id: str, table: Table) -> List[Note]:
    """Query all NOTE records for a server by PK + SK prefix."""
    print(f"[db] QUERY NOTES server={server_id}")
    response = table.query(
        KeyConditionExpression=Key(PK_ATTR).eq(build_server_pk(server_id)) & Key(SK_ATTR).begins_with(Note.Keys.SK_NOTE_PREFIX)
    )
    items = response.get("Items", [])
    print(f"[db] -> {len(items)} note(s) found for server={server_id}")
    return [Note.from_dynamodb(item) for item in items]
