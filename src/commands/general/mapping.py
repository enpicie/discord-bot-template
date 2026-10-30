from commands.models.command_mapping import CommandMapping
import commands.general.general_commands as general_commands

general_commands_mapping: CommandMapping = {
    "ping": {
        "function": general_commands.ping,
        "description": "Check that the bot is alive",
        "params": []
    },
    "help": {
        "function": general_commands.give_help,
        "description": "List all commands with descriptions",
        "params": []
    },
    # [feature:bot_token+examples]
    "server-info": {
        "function": general_commands.server_info,
        "description": "Show this server's name (example Discord API call using the bot token)",
        "params": []
    },
    # [/feature:bot_token+examples]
}
