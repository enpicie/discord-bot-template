import database.dynamodb_utils as db_helper
from aws_services import AWSServices
from commands.models.autocomplete_response import AutocompleteResponse
from commands.models.command_param import ParamChoice
from commands.models.discord_event import DiscordEvent

# Discord accepts at most 25 autocomplete choices.
_MAX_CHOICES = 25


def note_name_autocomplete(event: DiscordEvent, aws_services: AWSServices) -> AutocompleteResponse:
    """Suggest this server's note names that contain what the user has typed so far."""
    typed = (event.get_command_input_value("name") or "").lower()
    notes = db_helper.get_notes_for_server(event.get_server_id(), aws_services.dynamodb_table)
    matches = [n.note_name for n in notes if typed in n.note_name.lower()]
    return AutocompleteResponse(
        choices=[ParamChoice(name=name, value=name) for name in sorted(matches)[:_MAX_CHOICES]]
    )
