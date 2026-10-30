import database.dynamodb_utils as db_helper
import utils.permissions_helper as permissions_helper
from aws_services import AWSServices
from commands.models.discord_event import DiscordEvent
from commands.models.response_message import ResponseMessage
from database.models.note import Note


def note_set(event: DiscordEvent, aws_services: AWSServices) -> ResponseMessage:
    """Create or overwrite a server note. Requires 'Manage Server'."""
    permission_error = permissions_helper.require_manage_server_permission(event)
    if permission_error:
        return permission_error

    server_id = event.get_server_id()
    note = Note(
        server_id=server_id,
        note_name=event.get_command_input_value("name").strip(),
        content=event.get_command_input_value("content"),
        author_id=event.get_user_id(),
    )
    db_helper.put_note(note, aws_services.dynamodb_table)
    print(f"[notes] Saved note={note.note_name!r} server={server_id}")
    return ResponseMessage(content=f"Saved note **{note.note_name}**.")


def note_get(event: DiscordEvent, aws_services: AWSServices) -> ResponseMessage:
    """Show a server note by name."""
    result = db_helper.get_note_or_fail(
        event.get_server_id(), event.get_command_input_value("name"), aws_services.dynamodb_table
    )
    if isinstance(result, ResponseMessage):
        return result
    return ResponseMessage(content=f"**{result.note_name}**\n{result.content}").with_silent_pings()
