import os

#######################################
# Environment Variables              #
#######################################
# All injected by Terraform (terraform/infra/main.tf). See .env.example.
AWS_REGION = os.environ.get("REGION")
BOT_PUBLIC_KEY = os.environ.get("PUBLIC_KEY")
DISCORD_BOT_TOKEN_SECRET_NAME = os.environ.get("DISCORD_BOT_TOKEN_SECRET_NAME")  # [feature:bot_token]
DYNAMODB_TABLE_NAME = os.environ.get("DYNAMODB_TABLE_NAME")  # [feature:dynamodb]
SQS_DEFERRED_WORKER_QUEUE_URL = os.environ.get("DEFERRED_WORKER_QUEUE_URL")  # [feature:deferred_worker]

########################################
# Discord Data Constants              #
########################################
# Discord expects to see this response to its "ping pong" verification request
PING_PONG_RESPONSE = { "type": 1 }
