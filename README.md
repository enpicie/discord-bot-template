# discord-bot-template

Starting point for a serverless Discord bot on AWS Lambda. It's the same
foundation as [Adomi-san](https://github.com/enpicie/adomi-san-bot) with the
Adomi-specific features (start.gg, leagues, scheduling, Sheets) taken out.

Discord sends each slash command as an HTTP POST to API Gateway, which invokes
the bot Lambda. The Lambda checks Discord's signature, looks the command up in
the command map, runs it, and returns the reply.

```
Discord ──POST──▶ API Gateway ──▶ bot Lambda (src/) ──reply──▶ Discord
                                    │   │   │
                                    │   │   └─▶ Secrets Manager (bot token, for Discord REST calls)
                                    │   └─────▶ DynamoDB (state per Discord server)
                                    └─────────▶ SQS ──▶ deferred worker Lambda ──followup──▶ Discord
```

Every piece is included and deployed by default. The **base** (Lambda + API
Gateway + command discovery + pipelines) is required. The **three optional
features** (DynamoDB, deferred worker, bot token secret) each sit in their own
files and can be removed. See [Removing optional features](#removing-optional-features).

## Starting a new bot

1. **Create the repo.** Click "Use this template" on GitHub (or copy the files).
2. **Name it.** In [config.env](./config.env), set `APP_NAME` to your bot's name
   (lowercase, hyphens). Every AWS resource is named from it. **Nothing deploys
   while it's still `my-discord-bot`.**
3. **Make two Discord applications** in the
   [Developer Portal](https://discord.com/developers/applications), one for dev
   and one for prod. For each, copy:
   - **Public Key** → `DISCORD_PUBLIC_KEY_DEV` / `_PROD` in `config.env` (public, safe to commit)
   - **Application ID** → repo **variable** `DISCORD_APP_ID_DEV` / `_PROD`
   - **Bot Token** (Bot tab → Reset Token) → repo **secret** `DISCORD_BOT_TOKEN_DEV` / `_PROD`
4. **AWS access.** The pipelines use the org-level secrets
   `AWS_ROLE_ARN_LAMBDA_APIGW_DDB_SQS` (Terraform) and `AWS_ROLE_ARN_S3`
   (artifact upload). Repos in the `enpicie` org inherit them, so there's nothing to set.
5. **Deploy dev.** Push to any non-`main` branch. The Dev Pipeline runs tests,
   builds and uploads the Lambda zips and layers, and runs Terraform.
6. **Point Discord at it.** Copy the `interactions_endpoint_url` Terraform output
   (in the deploy job's log) into the dev app's **General Information →
   Interactions Endpoint URL**. It has the shape
   `https://<api-id>.execute-api.<region>.amazonaws.com/dev/<APP_NAME>`.
   Discord pings it to verify when you save, and the bot answers the ping.
7. **Register commands.** Run the Dev Pipeline from the Actions tab with
   *Run Discord command registration* checked, or run
   *Register Discord Bot Slash Commands* directly. Then invite the bot
   (OAuth2 → URL Generator → scopes `bot` + `applications.commands`) and try `/ping`.
8. **Make it yours.** Edit the Project line in [CLAUDE.md](./CLAUDE.md), and
   delete the example groups you don't want (`notes`, `deferred_example`).

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
"note-get": {
    "function": notes_commands.note_get,          # (DiscordEvent, AWSServices) -> ResponseMessage
    "description": "Show a saved note",           # ≤100 chars (Discord limit)
    "params": [
        CommandParam(
            name="name", description="Name of the note",
            param_type=AppCommandOptionType.string, required=True, choices=None,
            autocomplete=True,
            autocomplete_handler=autocomplete_handlers.note_name_autocomplete,
        ),
    ]
},
```

**To add a group:** create `src/commands/<group>/` with `__init__.py`,
`<group>_commands.py` and `mapping.py`, then add its mapping to `command_map.py`.

Error handling:
- Raise `ValueError("message")` from a command, and the user sees that message.
- Any other exception is logged, and the user gets `bot_messages.GENERAL_ERROR`.
- `tests/commands/test_command_map.py` checks every entry against Discord's
  registration rules, so a bad name or a description over 100 characters fails
  in CI, not at registration.

Command deletion isn't automated. If you rename or remove a command, delete the
old one through Discord's API.

## Example commands

| Command | Group | Shows |
|---|---|---|
| `/ping` | `general` | The minimum: endpoint, signature check, dispatch |
| `/help` | `general` | Reads the command map to list every command |
| `/server-info` | `general` | A Discord REST call using the bot token from Secrets Manager |
| `/note-set`, `/note-get` | `notes` | DynamoDB reads and writes, a permission check, autocomplete |
| `/slow-echo` | `deferred_example` | The deferred pattern: ⏳ placeholder, then a followup from the worker |

## Deferred commands (callbacks)

Discord drops any reply that takes longer than **3 seconds**. Commands that might
take longer (external APIs, bulk writes, file generation) are split in two:

1. **Bot Lambda** ([deferred_example_commands.py](./src/commands/deferred_example/deferred_example_commands.py)):
   validate the input (bad input still gets an instant reply), call
   `deferred_dispatch.dispatch("<command>", event, aws_services)`, and return a
   `⏳` placeholder.
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

## Database

There's one DynamoDB table (`<APP_NAME>-data-<env>`) with on-demand billing.
Every record for a Discord server shares `PK = SERVER#<server_id>`, and the
`SK` prefix says what kind of record it is (`NOTE#<name>`, …), so one Query can
return every record of a kind for a server.
[src/database/](./src/database/) holds the access functions and dataclass
models. `Note` is the pattern to copy: a `Keys` class, fields with `db_key`
metadata, and `from_dynamodb`.

To make a record expire automatically, set an `expires_at` attribute (epoch
seconds). [tests/commands/test_notes_commands.py](./tests/commands/test_notes_commands.py)
shows how to test against a fake table with `moto`.

## Bot token and secrets

Replying to a command and posting deferred followups don't need the bot token.
It's only needed for **Discord REST calls** like assigning roles, posting to
another channel, or reading guild info. For those:

- The token is stored in Secrets Manager (`<APP_NAME>-discord-bot-token-<env>`).
- The Lambdas get only the secret's **name** as an env var, and
  [discord_api_helper.py](./src/utils/discord_api_helper.py) fetches the value
  once per warm container.
- It's never a plaintext env var, and it's never logged.

Any other secret your bot needs should follow the same pattern.

## CI/CD

| Trigger | Pipeline | Does |
|---|---|---|
| Push to non-`main` branch | Dev Pipeline | tests + lint + `terraform validate` → deploy dev |
| Manual (Actions tab) | Dev Pipeline | same, optionally registers commands |
| Push tag `X.Y.Z` | Release Pipeline | tests → deploy prod → register all commands |
| Manual | Register Discord Bot Slash Commands | register one command, a prefix (`note` = `note-*`), or `all` |

Deploys run as one Terraform root (`terraform/infra`). State is stored in S3 at
`projects/<APP_NAME>/<env>/infra.tfstate`, managed by
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

## Removing optional features

Each feature's Terraform file also grants its IAM permissions, so deleting the
file removes them too. After removing a feature:

1. Run `make test`.
2. Run `make lint`. It flags imports the removal left unused, and
   `ruff check --fix .` removes them.
3. Push, and let `terraform validate` in CI catch any Terraform reference you missed.

> [!WARNING]
> Removing a feature from a bot that's **already deployed** destroys its AWS
> resources on the next deploy, including DynamoDB data.

### DynamoDB

- **Terraform:** delete `terraform/infra/dynamodb.tf`. Remove the
  `DYNAMODB_TABLE_NAME` env lines in `main.tf` and `deferred_worker.tf`, and the
  `dynamodb_table_name` output.
- **Bot:** delete `src/database/` and `src/commands/notes/` (plus its line in
  `command_map.py` and `NOTE_NOT_FOUND` in `bot_messages.py`). Remove
  `dynamodb_table` from `src/aws_services.py` and `src/aws_client.py`, and
  `DYNAMODB_TABLE_NAME` from `src/constants.py`.
- **Worker:** remove `dynamodb_table` and `DYNAMODB_TABLE_NAME` from
  `worker_aws_services.py`, `worker_aws_client.py` and `worker_constants.py`.
- **Tests and config:** delete `tests/commands/test_notes_commands.py`. Drop
  `mypy-boto3-dynamodb` from `requirements.txt` and the line in `.env.example`.

### Deferred worker

- **Terraform:** delete `terraform/infra/deferred_worker.tf`. Remove the
  `DEFERRED_WORKER_QUEUE_URL` env line in `main.tf`, the
  `deferred_worker_*_policy` blocks in `dynamodb.tf` and `secrets.tf`, the two
  `deferred_worker_*` outputs, and the two `deferred_worker_lambda_layer_*`
  variables.
- **Pipeline:** in `workflow-deploy.yml`, remove the `DEFERRED_WORKER_NAME` env,
  the two "Deferred Worker" steps, their log lines, and the two
  `TF_VAR_deferred_worker_*` lines.
- **Code:** delete `jobs/deferred_worker/`, `src/utils/deferred_dispatch.py` and
  `src/commands/deferred_example/` (plus its line in `command_map.py`). Remove
  `deferred_worker_sqs_queue` from `src/aws_services.py` and `src/aws_client.py`,
  and `SQS_DEFERRED_WORKER_QUEUE_URL` from `src/constants.py`.
- **Tests and config:** delete `tests/deferred_worker/`,
  `tests/commands/test_deferred_example_commands.py`,
  `tests/test_job_module_names.py` and `tests/job_imports.py` (restore the last
  two when you add a job). Drop `mypy-boto3-sqs` from `requirements.txt`, the
  worker lines in the `Makefile`, and the line in `.env.example`.

### Bot token secret

- **Terraform:** delete `terraform/infra/secrets.tf`. Remove the
  `DISCORD_BOT_TOKEN_SECRET_NAME` env lines in `main.tf` and
  `deferred_worker.tf`, and the `discord_bot_token` variable.
- **Pipeline:** in `workflow-deploy.yml`, remove `TF_VAR_discord_bot_token` and
  the `DISCORD_BOT_TOKEN` secret input, and remove the matching
  `DISCORD_BOT_TOKEN:` lines in `development.yml` and `release.yml`. Keep the
  `DISCORD_BOT_TOKEN_*` repo secrets: command registration still uses them.
- **Code:** delete `src/utils/discord_api_helper.py` and the `server-info`
  command (function and mapping entry). Remove `DISCORD_BOT_TOKEN_SECRET_NAME`
  from `src/constants.py`, and both it and `get_discord_bot_token` from
  `worker_constants.py`.
- **Tests and config:** delete `tests/utils/test_discord_api_helper.py` and the
  line in `.env.example`.

## Conventions

The code style is the same as Adomi's: imports through module aliases, mentions
through `message_helper`, a `[name]` prefix on every `print` in `src/`, and
`logger` in `jobs/`. The full rules are in [CLAUDE.md](./CLAUDE.md).
