# MIRROR: src/aws_client.py — keep in sync (independent Lambda packaging prevents imports)
import boto3  # [feature:dynamodb]

import worker_constants as constants  # [feature:dynamodb]
from worker_aws_services import AWSServices

_dynamodb = boto3.resource("dynamodb", region_name=constants.AWS_REGION)  # [feature:dynamodb]

_aws_services: AWSServices | None = None


def get_aws_services() -> AWSServices:
    """Return the lazily created AWSServices singleton."""
    global _aws_services
    if _aws_services is None:
        _aws_services = AWSServices(
            dynamodb_table=_dynamodb.Table(constants.DYNAMODB_TABLE_NAME),  # [feature:dynamodb]
        )
    return _aws_services
