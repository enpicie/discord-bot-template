# MIRROR: src/aws_services.py — keep in sync (independent Lambda packaging prevents imports)
class AWSServices:
    """Bundle of pre-built AWS resource handles (DynamoDB table) passed into
    deferred command handlers."""

    def __init__(self, dynamodb_table):
        self.dynamodb_table = dynamodb_table
