"""Example group tests against a moto-backed DynamoDB table — the pattern to
copy for your own database-backed commands."""
import os
import unittest

import boto3
from moto import mock_aws

os.environ.setdefault("AWS_DEFAULT_REGION", "us-east-1")

import commands.notes.autocomplete_handlers as autocomplete_handlers
import commands.notes.notes_commands as notes_commands
import utils.bot_messages as bot_messages
from commands.models.discord_event import DiscordEvent

_SERVER_ID = "123456789012345678"
_MANAGE_SERVER = str(0x20)


def _make_event(options: list, permissions: str = _MANAGE_SERVER) -> DiscordEvent:
    return DiscordEvent({
        "guild_id": _SERVER_ID,
        "channel_id": "222333444555666777",
        "data": {"name": "note", "options": options},
        "member": {
            "user": {"id": "111222333444555666", "username": "TestUser"},
            "permissions": permissions,
            "roles": [],
        },
    })


def _option(name: str, value: str) -> dict:
    return {"name": name, "type": 3, "value": value}


class _AWSServices:
    def __init__(self, table):
        self.dynamodb_table = table


@mock_aws
class TestNotesCommands(unittest.TestCase):
    def setUp(self):
        dynamodb = boto3.resource("dynamodb", region_name="us-east-1")
        # Mirrors terraform/infra/dynamodb.tf key schema.
        table = dynamodb.create_table(
            TableName="test-table",
            KeySchema=[{"AttributeName": "PK", "KeyType": "HASH"}, {"AttributeName": "SK", "KeyType": "RANGE"}],
            AttributeDefinitions=[{"AttributeName": "PK", "AttributeType": "S"}, {"AttributeName": "SK", "AttributeType": "S"}],
            BillingMode="PAY_PER_REQUEST",
        )
        self.aws_services = _AWSServices(table)

    def _save(self, name: str, content: str, permissions: str = _MANAGE_SERVER):
        event = _make_event([_option("name", name), _option("content", content)], permissions)
        return notes_commands.note(event, self.aws_services)

    def _show(self, name: str):
        return notes_commands.note(_make_event([_option("name", name)]), self.aws_services)

    def test_save_then_show_round_trips_the_note(self):
        self.assertIn("Saved", self._save("Rules", "Be nice.").content)
        self.assertIn("Be nice.", self._show("Rules").content)

    def test_show_is_case_and_whitespace_insensitive(self):
        self._save("House Rules", "Be nice.")
        self.assertIn("Be nice.", self._show("  house   RULES ").content)

    def test_show_missing_note_returns_not_found_message(self):
        self.assertEqual(self._show("nope").content, bot_messages.NOTE_NOT_FOUND)

    def test_save_without_manage_server_is_refused_and_writes_nothing(self):
        response = self._save("Rules", "x", permissions="0")
        self.assertEqual(response.content, bot_messages.REQUIRE_MANAGE_SERVER)
        self.assertEqual(self.aws_services.dynamodb_table.scan()["Count"], 0)

    def test_show_does_not_need_manage_server(self):
        self._save("Rules", "Be nice.")
        event = _make_event([_option("name", "Rules")], permissions="0")
        self.assertIn("Be nice.", notes_commands.note(event, self.aws_services).content)

    def test_autocomplete_suggests_matching_note_names(self):
        self._save("Rules", "a")
        self._save("Schedule", "b")
        response = autocomplete_handlers.note_name_autocomplete(_make_event([_option("name", "ru")]), self.aws_services)
        self.assertEqual([c.name for c in response.choices], ["Rules"])


if __name__ == "__main__":
    unittest.main()
