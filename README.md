# discord-bot-template

Template for Discord bot run via Lambda, exposed to Discord via API Gateway webhook. Bot is set up with command handling template and DynamoDB permissions for bots needing a database resource.

## Configuration

This is what must be configured for each bot using this template:

- Repo Variables:
  - `DISCORD_APP_ID_DEV/PROD`: Discord Application ID for each environment
- Repo Secrets:
  - `DISCORD_BOT_TOKEN_DEV/PROD`: Discord Bot Token for each environment
- config.env vars:
  - `APP_NAME`: Name for your bot (should match or resemble repo name as it is used for naming resources)
  - `HCP_TERRAFORM_*`: Names of respective places for created HCP Terraform Workspace for your bot

## Bot Commands

Commands are ultimately defined in [src/commands/command_map.py](./src/commands/command_map.py), and this file is used in the CICD pipeline to automate registration of commands as Slash Commands for the Discord bot.

**Note that commands may take some time before they are viewable/usable in Discord.** Global commands take longer to sync up with Discord for use in the client, and this setup does not cover setting up Guild/Server commands.

### Command Mapping and Organization

[src/commands/command_map.py](./src/commands/command_map.py) defines a `dict` mapping mapping a command name to...

- A function that returns a message
- Command description
- List of parameters for the resulting Discord Slash Command.

Commands can be grouped in subdirectories like the example [check_in](./src/check_in/). **Good practice is having groups of commands use a [mapping.py](./src/check_in/mapping.py) file to share a dictionary with command_map.py.** Notice how the `check_in` mapping is consumed in command_map.py.

The full `CommandMapping` and `CommandEntry` types are defined using Python `TypedDict` to simplify inline definition. However, `CommandParam` and `ParamChoice` are defined as dataclasses both to simplify their initialization and to ensure they are always defined with their full sets of properties. This enforces full command definition.

### Command Management

While command creation is automated in the deployment pipeline, command deletion must be done manually. If you have changed/removed a command and need to delete it, you must do this manually.

Discord's API makes this simple but requires the following parameters:

- Bot Token (secret, but can be stored securely locally for this purpose)
- Application ID (should be stored in Repo Variables anyways)

_This template does not support guild/server-specific commands._

## CI/CD

- **Dev:** Triggers on push to anything but main or a tag
- **Prod:** Triggers on push to main with version tag

### General Workflow

1. Register bot commands via Discord API, reading from src/commands/command_map.py
2. Read env-independent config vars from config.env
3. Deploy via HCP Terraform

### Infrastructure Resources

The Terraform config and deployment pipeline manage the following resources to facilitate the bot:

- Ensure HCP Terraform Workspace exists for bot for each environment
- Builds Lambda Layer for the bot with pure-Python (architecture-independent) packages listed in requirements.txt
- Creates Lambda and API Gateway for the bot, exposing an API resource with a route using the app's environment and name

## Shared Organization Variables

- `AWS_TF_ROLE_VARSET_LAMB_APIGW_DDB` - Name for HCP Terraform Variable Set referencing an ARN granting permissions for Terraform runs to provision the necessary resources for this Lambda
  - This follows [Hashicorp's recommendation for sharing auth across an org](https://www.hashicorp.com/en/blog/access-aws-from-hcp-terraform-with-oidc-federation)
  - This value can be replaced by the name of any Varset that grants necessary permissions

### Secrets

- `AWS_S3_ARTIFACT_UPLOAD_ROLE_ARN` - ARN of manually configured AWS IAM role with permissions for uploading .zip artifacts to S3 for the Lambda and Layers
- `TF_API_TOKEN` - API token from HCP Terraform used for managing HCP Terraform resources mainly around the workspace where runs will occur
