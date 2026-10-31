<!-- [template-only] -->
# discord-bot-template

Starter for a serverless Discord bot on AWS Lambda + API Gateway, on the same
foundation as [Adomi-san](https://github.com/enpicie/adomi-san-bot) with the
Adomi-specific features taken out.

**Generator: https://enpicie.github.io/discord-bot-template/**

Tick the features you need, preview every file you'll get, and download a zip.
The zip is the new bot's repo, complete and with nothing template-specific left
in it. Don't use GitHub's "Use this template" button on this repo: the raw files
still contain the generator's feature markers.

## Start a new bot

1. **Generate it.** On the [generator page](https://enpicie.github.io/discord-bot-template/),
   enter the bot name, tick the features, review the preview, and click
   **Get template**.

   | Feature | Adds | Example command |
   |---|---|---|
   | *(always)* | Lambda + API Gateway, command discovery, pipelines, tests | `/ping` |
   | DynamoDB | One table for bot state, keyed per Discord server | `/note` |
   | Deferred worker (callbacks) | SQS queue + worker Lambda for commands that take longer than Discord's 3s deadline | `/slow-echo` |
   | Bot token in Secrets Manager | For Discord REST API calls (roles, channel posts). Replies and callbacks don't need it | — (`discord_api_helper.py` is ready to call) |

2. **Unzip it and make the first commit.**

   ```bash
   unzip <bot-name>.zip && cd <bot-name>
   ```
   ```bash
   git init -b main && git add -A && git commit -m "Initialize <bot-name>"
   ```

3. **Create the GitHub repo and push.**

   ```bash
   gh repo create enpicie/<bot-name> --private --source . --push
   ```

4. **Create the Discord apps.** Make a dev app and a prod app in the
   [Developer Portal](https://discord.com/developers/applications). Put each
   app's **Public Key** in `config.env` (`DISCORD_PUBLIC_KEY_DEV` / `_PROD`)
   unless you entered them on the page, then commit.

5. **Set the repo variables and secrets.** Each `gh secret set` prompts for the
   token (Bot tab → Reset Token).

   ```bash
   gh variable set DISCORD_APP_ID_DEV --body <dev application id>
   ```
   ```bash
   gh variable set DISCORD_APP_ID_PROD --body <prod application id>
   ```
   ```bash
   gh secret set DISCORD_BOT_TOKEN_DEV
   ```
   ```bash
   gh secret set DISCORD_BOT_TOKEN_PROD
   ```

   The AWS role secrets (`AWS_ROLE_ARN_LAMBDA_APIGW_DDB_SQS`, `AWS_ROLE_ARN_S3`)
   are set at the org level, so the new repo inherits them.

6. **Deploy dev.** Any branch other than `main` deploys dev.

   ```bash
   git checkout -b dev && git push -u origin dev
   ```

7. **Point Discord at the bot.** Copy the `interactions_endpoint_url` output
   from the deploy job's log into the dev app's **General Information →
   Interactions Endpoint URL**. Discord pings it to verify when you save.

8. **Register the slash commands.** In the Actions tab, run **Dev Pipeline**
   with *Run Discord command registration* checked. Then invite the bot
   (OAuth2 → URL Generator → scopes `bot` + `applications.commands`) and try `/ping`.

9. **Go to prod.** Push a version tag. The Release Pipeline deploys prod and
   then registers every command automatically. Point the prod app's
   Interactions Endpoint URL at the prod output the same way as step 7.

   ```bash
   git tag 1.0.0 && git push origin 1.0.0
   ```

Command registration works the same way as Adomi's: automatic after every prod
release, opt-in on dev runs, and available any time from the standalone
workflow. The generated README's
[Command registration](#command-registration) section has the details.

## How the generator works

Nothing runs on a server. The **Publish Generator** workflow
([pages.yml](./.github/workflows/pages.yml)) runs
[generator/build_site.py](./generator/build_site.py) on every merge to `main`.
That script renders all 16 feature combinations with
[generator/engine.py](./generator/engine.py) and publishes them with the page in
[site/](./site/). In your browser, the page swaps in your bot name and keys and
writes the zip.

Lines that belong to an optional feature carry a marker comment naming the
feature. A marker at the end of a line covers that line. A marker alone on its
line opens or closes a block. Files that belong entirely to one feature are
listed in `FEATURE_PATHS`. The format is documented at the top of `engine.py`.

When you change the template, mark any new feature-specific line. Two checks
keep the markers honest:

- `tests/test_generator.py` renders every combination, then checks that no
  markers remain, that every Python file compiles, and that the site builds.
- **Template CI** ([template-ci.yml](./.github/workflows/template-ci.yml)) runs
  on pull requests. It builds the zips exactly as the page does, unzips them,
  and runs each generated bot's own `make test`, `make lint` and
  `terraform validate`.

To preview the page locally:

```bash
python generator/build_site.py && python -m http.server -d _site 8000
```

Nothing in this repo deploys a bot. The bot pipelines skip themselves here, and
the only thing published is the static generator page.

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
   *Run Discord command registration* checked (see
   [Command registration](#command-registration)). Invite the bot
   (OAuth2 → URL Generator → scopes `bot` + `applications.commands`) and try `/ping`.
6. **Go to prod.** Push a version tag (`git tag 1.0.0 && git push origin 1.0.0`).
   The Release Pipeline deploys prod and registers every command. Point the prod
   app's Interactions Endpoint URL at the prod output the same way as step 4.

## Command registration

Slash commands must be registered with Discord before they show up in the
client. [scripts/register_commands.py](./scripts/register_commands.py) reads
`command_map` and registers each entry through Discord's API, using the
`DISCORD_APP_ID_*` repo variable and `DISCORD_BOT_TOKEN_*` secret for the
environment.

| When | How | What gets registered |
|---|---|---|
| Every prod release (tag push) | Automatic: the Release Pipeline's `register-commands` job runs after deploy | All commands |
| A dev deploy | Opt-in: run **Dev Pipeline** manually with *Run Discord command registration* checked | All commands |
| Any time | Run **Register Discord Bot Slash Commands** from the Actions tab, picking `dev` or `prod` | One command (`ping`), a prefix (`admin` → every `admin-*` command), or `all` |

Dev registration is opt-in because a plain push already deploys dev, and
re-registering every command on every push is slow. The script waits 10s
between commands to stay under Discord's rate limit.

Run this to list every command name the map defines:

```bash
PYTHONPATH=src python scripts/list_commands.py
```

Registration creates and updates commands, but it never deletes them. If you
rename or remove a command, delete the old one through Discord's API.
Global commands can take a while to appear in the Discord client.

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

## Starter commands

| Command | Group | Shows |
|---|---|---|
| `/ping` | `general` | The minimum: endpoint, signature check, dispatch |
| `/note name [content]` | `notes` | DynamoDB reads and writes, a permission check (saving needs Manage Server), autocomplete |  <!-- [feature:dynamodb] -->
| `/slow-echo text` | `deferred_example` | The deferred pattern: ⏳ placeholder, then a followup from the worker |  <!-- [feature:deferred_worker] -->

<!-- [feature:dynamodb|deferred_worker] -->
Replace the example groups with your own (and update their lines in
`command_map.py`) once you've built your own commands.
<!-- [/feature:dynamodb|deferred_worker] -->
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
| Manual | Register Discord Bot Slash Commands | register one command, a prefix (`admin` = `admin-*`), or `all` |

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
