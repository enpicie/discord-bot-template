from discord import AppCommandOptionType

from commands.models.command_mapping import CommandMapping
from commands.models.command_param import CommandParam
import commands.notes.notes_commands as notes_commands
import commands.notes.autocomplete_handlers as autocomplete_handlers

# Example group showing DynamoDB reads/writes, a permission check and
# autocomplete. Replace it with your own (and its line in command_map.py).
notes_commands_mapping: CommandMapping = {
    "note": {
        "function": notes_commands.note,
        "description": "Show a saved note, or save one by adding content (saving needs Manage Server)",
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
            CommandParam(
                name="content",
                description="Text to save under this name (leave out to show the note)",
                param_type=AppCommandOptionType.string,
                required=False,
                choices=None,
            ),
        ]
    },
}
