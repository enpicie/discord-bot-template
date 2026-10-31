import database.dynamodb_utils as db_helper
import utils.permissions_helper as permissions_helper
from aws_services import AWSServices
from commands.models.discord_event import DiscordEvent
from commands.models.response_message import ResponseMessage
from database.models.note import Note


def note(event: DiscordEvent, aws_services: AWSServices) -> ResponseMessage:
    """Example DynamoDB command. With `content`, saves the note (requires
    'Manage Server'); without it, shows the saved note."""
    server_id = event.get_server_id()
    note_name = event.get_command_input_value("name").strip()
    content = event.get_command_input_value("content")

    if content is None:
        result = db_helper.get_note_or_fail(server_id, note_name, aws_services.dynamodb_table)
        if isinstance(result, ResponseMessage):
            return result
        return ResponseMessage(content=f"**{result.note_name}**\n{result.content}").with_silent_pings()

    permission_error = permissions_helper.require_manage_server_permission(event)
    if permission_error:
        return permission_error

    saved = Note(server_id=server_id, note_name=note_name, content=content, author_id=event.get_user_id())
    db_helper.put_note(saved, aws_services.dynamodb_table)
    print(f"[notes] Saved note={saved.note_name!r} server={server_id}")
    return ResponseMessage(content=f"Saved note **{saved.note_name}**.")
