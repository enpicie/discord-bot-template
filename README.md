<!-- [template-only] -->
# discord-bot-template

Starter for a serverless Discord bot on AWS Lambda. It's the same foundation as
[Adomi-san](https://github.com/enpicie/adomi-san-bot) with the Adomi-specific
features taken out.

## Start a new bot

```bash
gh repo create enpicie/<bot-name> --template enpicie/discord-bot-template --private --clone
```

```bash
cd <bot-name> && python init_bot.py
```

`init_bot.py` asks for the bot's name and which optional features to keep:

| Feature | Adds |
|---|---|
| DynamoDB | One table for bot state, keyed per Discord server |
| Deferred worker | SQS queue + worker Lambda for commands that take longer than Discord's 3s deadline |
| Bot token secret | Bot token in Secrets Manager, for Discord REST API calls (roles, channel posts) |
| Examples | `/note-set`, `/note-get`, `/slow-echo`, `/server-info` example commands (`/ping` and `/help` always stay) |

The script then:
1. Removes everything for the features you dropped: Terraform, Python, pipeline
   steps, tests and docs.
2. Sets the name everywhere, and deletes itself and the other template-only files.
3. Prints the remaining one-time setup (Discord apps, `gh` commands for repo
   secrets, the first push) as copyable commands.

What's left is a normal repo with no template machinery in it.

Run it without prompts by passing flags. `python init_bot.py --help` lists them:

```bash
python init_bot.py --name my-bot --no-deferred-worker --no-examples --yes
```

## How the template is built

Lines that belong to an optional feature carry a marker comment naming the
feature. A marker at the end of a line covers that line. A marker alone on its
line opens or closes a block. Files that belong entirely to one feature are
listed in `FEATURE_PATHS`. The format is documented at the top of
[init_bot.py](./init_bot.py).

When you change the template, mark any new feature-specific line. Two checks
keep the markers honest:

- `tests/test_init_bot.py` generates every feature combination, then checks that
  no markers remain and that every Python file still compiles.
- The **Template CI** workflow generates the combinations and runs the generated
  bot's own `make test`, `make lint` and `terraform validate` on each. It runs
  on pull requests and on demand. Nothing in this repo deploys: the bot
  pipelines skip themselves here.

Everything below this line becomes the new bot's README.

---
<!-- [/template-only] -->
# my-discord-bot

Serverless Discord bot on AWS Lambda, generated from
[discord-bot-template](https://github.com/enpicie/discord-bot-template).

Discord sends each slash command as an HTTP POST to API Gateway, which invokes
the bot Lambda. The Lambda checks Discord's signature, looks the command up in
the command map, runs it, and returns the reply.

```
Discord ──POST──▶ API Gateway ──▶ bot Lambda (src/) ──reply──▶ Discord
```
<!-- [feature:dynamodb|deferred_worker|bot_token] -->

The bot Lambda also uses:
<!-- [/feature:dynamodb|deferred_worker|bot_token] -->
- **DynamoDB** for state per Discord server ([Database](#database))  <!-- [feature:dynamodb] -->
- **SQS → deferred worker Lambda** for commands that take longer than 3s ([Deferred commands](#deferred-commands))  <!-- [feature:deferred_worker] -->
- **Secrets Manager** for the bot token, for Discord REST calls ([Bot token](#bot-token))  <!-- [feature:bot_token] -->

## One-time setup

1. **Discord apps.** Create a dev app and a prod app in the
   [Developer Portal](https://discord.com/developers/applications). For each:
   - **Public Key** → `DISCORD_PUBLIC_KEY_DEV` / `_PROD` in [config.env](./config.env) (public, safe to commit)
   - **Application ID** → repo **variable** `DISCORD_APP_ID_DEV` / `_PROD`
   - **Bot Token** (Bot tab → Reset Token) → repo **secret** `DISCORD_BOT_TOKEN_DEV` / `_PROD`
2. **AWS access.** The pipelines use the org-level secrets
   `AWS_ROLE_ARN_LAMBDA_APIGW_DDB_SQS` (Terraform) and `AWS_ROLE_ARN_S3`
   (artifact upload). Repos in the `enpicie` org inherit them.
3. **Deploy dev.** Push to any non-`main` branch.
4. **Point Discord at it.** Copy the `interactions_endpoint_url` Terraform output
   (in the deploy job's log) into the dev app's **General Information →
   Interactions Endpoint URL**. It has the shape
   `https://<api-id>.execute-api.<region>.amazonaws.com/dev/my-discord-bot`.
   Discord pings it to verify when you save, and the bot answers the ping.
5. **Register commands.** Run the Dev Pipeline from the Actions tab with
   *Run Discord command registration* checked. Invite the bot
   (OAuth2 → URL Generator → scopes `bot` + `applications.commands`) and try `/ping`.

Prod works the same way: push a version tag (`1.0.0`) to run the Release
Pipeline, which deploys prod and registers every command.

## How commands work

Commands are discovered from a single dict, `command_map`.

- Each group lives in `src/commands/<group>/` and exports a `CommandMapping` from
  its `mapping.py`.
- [src/commands/command_map.py](./src/commands/command_map.py) merges the groups.
- [src/bot.py](./src/bot.py) dispatches from that dict, and
  [scripts/register_commands.py](./scripts/register_commands.py) registers every
  entry with Discord. So adding an entry to a `mapping.py` is all it takes for a
  command to be dispatched and registered.

```python
"echo": {
    "function": my_commands.echo,                 # (DiscordEvent, AWSServices) -> ResponseMessage
    "description": "Repeat what you say",         # ≤100 chars (Discord limit)
    "params": [
        CommandParam(
            name="text", description="What to repeat",
            param_type=AppCommandOptionType.string, required=True, choices=None,
            # autocomplete=True, autocomplete_handler=my_handlers.text_autocomplete,
        ),
    ]
},
```

**To add a group:** create `src/commands/<group>/` with `__init__.py`,
`<group>_commands.py` and `mapping.py`, then add one line for it to
`command_map.py`.

Error handling:
- Raise `ValueError("message")` from a command, and the user sees that message.
- Any other exception is logged, and the user gets `bot_messages.GENERAL_ERROR`.
- `tests/commands/test_command_map.py` checks every entry against Discord's
  registration rules, so a bad name or a description over 100 characters fails
  in CI, not at registration.

Command deletion isn't automated. If you rename or remove a command, delete the
old one through Discord's API.
<!-- [feature:examples] -->

## Example commands

| Command | Shows |
|---|---|
| `/ping`, `/help` | The minimum: endpoint, signature check, dispatch; reading the command map |
| `/note-set`, `/note-get` | DynamoDB reads and writes, a permission check, autocomplete |  <!-- [feature:dynamodb] -->
| `/slow-echo` | The deferred pattern: ⏳ placeholder, then a followup from the worker |  <!-- [feature:deferred_worker] -->
| `/server-info` | A Discord REST call using the bot token from Secrets Manager |  <!-- [feature:bot_token] -->

Delete the example groups (and their line in `command_map.py`) once you've
built your own.
<!-- [/feature:examples] -->
<!-- [feature:deferred_worker] -->

## Deferred commands

Discord drops any reply that takes longer than **3 seconds**. Commands that might
take longer (external APIs, bulk writes, file generation) are split in two:

1. **Bot Lambda:** validate the input (bad input still gets an instant reply),
   call `deferred_dispatch.dispatch("<command>", event, aws_services)`, and
   return a `⏳` placeholder.
2. **Worker Lambda** ([jobs/deferred_worker/](./jobs/deferred_worker/)): SQS
   triggers it with the whole interaction. It looks up the handler in
   `_COMMAND_HANDLERS`, runs it, and posts the result as a followup to the
   original interaction.

Followups are authenticated by the interaction's own token, which is valid for
15 minutes, so the worker doesn't need the bot token for them. The worker is
packaged on its own and **cannot import `src/`**. Code needed on both sides is
copied, with a `MIRROR:` comment on each copy.

If a handler raises, the worker posts the general error instead of re-raising.
That stops SQS from re-running the command and posting a duplicate reply. A
message that still fails 3 times (e.g. the followup POST itself failed) moves
to the `-dlq` queue, where you can inspect it.
<!-- [/feature:deferred_worker] -->
<!-- [feature:dynamodb] -->

## Database

There's one DynamoDB table (`my-discord-bot-data-<env>`) with on-demand billing.
Every record for a Discord server shares `PK = SERVER#<server_id>`, and the
`SK` prefix says what kind of record it is, so one Query can return every record
of a kind for a server. [src/database/](./src/database/) holds the access
functions and dataclass models. Each model has a `Keys` class, fields with
`db_key` metadata, and `from_dynamodb`.

To make a record expire automatically, set an `expires_at` attribute (epoch
seconds). Test against a fake table with `moto` (`mock_aws`).
<!-- [/feature:dynamodb] -->
<!-- [feature:bot_token] -->

## Bot token

Replying to a command doesn't need the bot token. It's only needed for
**Discord REST calls** like assigning roles, posting to another channel, or
reading guild info. For those:

- The token is stored in Secrets Manager (`my-discord-bot-discord-bot-token-<env>`).
- The Lambdas get only the secret's **name** as an env var, and
  [discord_api_helper.py](./src/utils/discord_api_helper.py) fetches the value
  once per warm container.
- It's never a plaintext env var, and it's never logged.

Any other secret your bot needs should follow the same pattern.
<!-- [/feature:bot_token] -->

## CI/CD

| Trigger | Pipeline | Does |
|---|---|---|
| Push to non-`main` branch | Dev Pipeline | tests + lint + `terraform validate` → deploy dev |
| Manual (Actions tab) | Dev Pipeline | same, optionally registers commands |
| Push tag `X.Y.Z` | Release Pipeline | tests → deploy prod → register all commands |
| Manual | Register Discord Bot Slash Commands | register one command, a prefix (`note` = `note-*`), or `all` |

Deploys run as one Terraform root (`terraform/infra`). State is stored in S3 at
`projects/my-discord-bot/<env>/infra.tfstate`, managed by
`enpicie/gh-action-workflow-terraform-run`. Lambda layers are rebuilt only when a
`requirements.txt` changes. Use *force_rebuild_layer* to override.

Local checks:

```bash
make test
```

```bash
make lint
```

There is no local Discord stack. Interactions need the deployed endpoint, so test
end to end on dev.

## Conventions

The code style is the same as Adomi's: imports through module aliases, mentions
through `message_helper`, a `[name]` prefix on every `print` in `src/`, and
`logger` in `jobs/`. The full rules are in [CLAUDE.md](./CLAUDE.md).
