# MIRROR: jobs/deferred_worker/worker_aws_client.py — keep in sync (independent Lambda packaging prevents imports)  # [feature:deferred_worker]
import boto3  # [feature:dynamodb|deferred_worker]

import constants  # [feature:dynamodb|deferred_worker]
from aws_services import AWSServices

_dynamodb = boto3.resource("dynamodb", region_name=constants.AWS_REGION)  # [feature:dynamodb]
_sqs = boto3.resource("sqs", region_name=constants.AWS_REGION)  # [feature:deferred_worker]

_aws_services: AWSServices | None = None


def get_aws_services() -> AWSServices:
    """Return the shared AWSServices instance, building it on first call
    and memoizing it for the lifetime of the Lambda container."""
    global _aws_services
    if _aws_services is None:
        _aws_services = AWSServices(
            dynamodb_table=_dynamodb.Table(constants.DYNAMODB_TABLE_NAME),  # [feature:dynamodb]
            deferred_worker_sqs_queue=_sqs.Queue(constants.SQS_DEFERRED_WORKER_QUEUE_URL),  # [feature:deferred_worker]
        )
    return _aws_services
