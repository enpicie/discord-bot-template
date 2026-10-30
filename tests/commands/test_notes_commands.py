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
        "data": {"name": "note-set", "options": options},
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

    def _set(self, name: str, content: str):
        return notes_commands.note_set(_make_event([_option("name", name), _option("content", content)]), self.aws_services)

    def test_set_then_get_round_trips_the_note(self):
        self._set("Rules", "Be nice.")
        response = notes_commands.note_get(_make_event([_option("name", "Rules")]), self.aws_services)
        self.assertIn("Be nice.", response.content)

    def test_get_is_case_and_whitespace_insensitive(self):
        self._set("House Rules", "Be nice.")
        response = notes_commands.note_get(_make_event([_option("name", "  house   RULES ")]), self.aws_services)
        self.assertIn("Be nice.", response.content)

    def test_get_missing_note_returns_not_found_message(self):
        response = notes_commands.note_get(_make_event([_option("name", "nope")]), self.aws_services)
        self.assertEqual(response.content, bot_messages.NOTE_NOT_FOUND)

    def test_set_without_manage_server_is_refused_and_writes_nothing(self):
        event = _make_event([_option("name", "Rules"), _option("content", "x")], permissions="0")
        response = notes_commands.note_set(event, self.aws_services)
        self.assertEqual(response.content, bot_messages.REQUIRE_MANAGE_SERVER)
        self.assertEqual(self.aws_services.dynamodb_table.scan()["Count"], 0)

    def test_autocomplete_suggests_matching_note_names(self):
        self._set("Rules", "a")
        self._set("Schedule", "b")
        response = autocomplete_handlers.note_name_autocomplete(_make_event([_option("name", "ru")]), self.aws_services)
        self.assertEqual([c.name for c in response.choices], ["Rules"])


if __name__ == "__main__":
    unittest.main()
