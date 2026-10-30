from discord import AppCommandOptionType

from commands.models.command_mapping import CommandMapping
from commands.models.command_param import CommandParam
import commands.notes.notes_commands as notes_commands
import commands.notes.autocomplete_handlers as autocomplete_handlers

# Example group showing DynamoDB usage and autocomplete. Delete this group (and
# its line in command_map.py) when you start your own bot.
notes_commands_mapping: CommandMapping = {
    "note-set": {
        "function": notes_commands.note_set,
        "description": "Save a note for this server (requires Manage Server)",
        "params": [
            CommandParam(
                name="name",
                description="Name of the note",
                param_type=AppCommandOptionType.string,
                required=True,
                choices=None,
            ),
            CommandParam(
                name="content",
                description="What the note says",
                param_type=AppCommandOptionType.string,
                required=True,
                choices=None,
            ),
        ]
    },
    "note-get": {
        "function": notes_commands.note_get,
        "description": "Show a saved note",
        "params": [
            CommandParam(
                name="name",
                description="Name of the note",
                param_type=AppCommandOptionType.string,
                required=True,
                choices=None,
                autocomplete=True,
                autocomplete_handler=autocomplete_handlers.note_name_autocomplete,
            ),
        ]
    },
}
