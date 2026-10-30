from aws_services import AWSServices
import utils.discord_api_helper as discord_api_helper
from commands.models.discord_event import DiscordEvent
from commands.models.response_message import ResponseMessage


def ping(event: DiscordEvent, aws_services: AWSServices) -> ResponseMessage:
    """Smallest possible command: proves the endpoint, signature check and dispatch all work."""
    return ResponseMessage(content="Pong!")


def give_help(event: DiscordEvent, aws_services: AWSServices) -> ResponseMessage:
    """List every registered command with its description, straight from the command map."""
    # Imported here, not at module top: command_map imports this module's mapping.
    import commands.command_map as command_map

    lines = [f"`/{name}` — {entry['description']}" for name, entry in sorted(command_map.command_map.items())]
    return ResponseMessage(content="**Commands**\n" + "\n".join(lines)).with_silent_pings()


def server_info(event: DiscordEvent, aws_services: AWSServices) -> ResponseMessage:
    """Example of a call to the Discord REST API with the bot token (from Secrets Manager)."""
    server_id = event.get_server_id()
    guild_name = discord_api_helper.get_guild_name(server_id)
    if guild_name is None:
        return ResponseMessage(content="I couldn't look up this server — am I a member of it?")
    return ResponseMessage(content=f"This server is **{guild_name}** (ID `{server_id}`).")
