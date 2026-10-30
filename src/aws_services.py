# MIRROR: jobs/deferred_worker/worker_aws_services.py — keep in sync (independent Lambda packaging prevents imports)  # [feature:deferred_worker]
from dataclasses import dataclass

from mypy_boto3_dynamodb.service_resource import Table  # [feature:dynamodb]
from mypy_boto3_sqs.service_resource import Queue  # [feature:deferred_worker]

@dataclass
class AWSServices:
    """Container bundling the AWS resource clients the bot needs, so handlers
    receive one injectable dependency. Add a field per AWS resource."""
    dynamodb_table: Table  # [feature:dynamodb]
    deferred_worker_sqs_queue: Queue  # [feature:deferred_worker]
