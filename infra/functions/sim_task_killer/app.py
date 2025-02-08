import boto3
import random
import os
from boto3.dynamodb.conditions import Key
from aws_lambda_powertools import Logger, Metrics
from aws_lambda_powertools.metrics import MetricUnit
from aws_lambda_powertools.utilities.typing import LambdaContext

logger = Logger()
metrics = Metrics()

dynamodb = boto3.resource("dynamodb")
ecs = boto3.client("ecs")
table = dynamodb.Table(os.environ["TABLE_NAME"])
CLUSTER_NAME = os.environ["CLUSTER_NAME"]


def delete_single_task():
    """Attempt to delete a single assigned task"""
    try:
        # Query for an assigned task
        response = table.query(
            IndexName="StatusIndex",
            KeyConditionExpression=Key("Status").eq("ASSIGNED"),
            Limit=1,
        )

        if not response["Items"]:
            logger.info("No assigned tasks found to delete")
            return False

        task = response["Items"][0]
        task_id = task["TaskId"]
        ecs_task_arn = task.get("EcsTaskArn")

        logger.info(f"Found assigned task to delete: {task_id}")

        # Stop the ECS task
        if ecs_task_arn:
            try:
                ecs.stop_task(
                    cluster=CLUSTER_NAME,
                    task=ecs_task_arn.split("/")[-1],  # Extract task ID from ARN
                    reason="Task deletion by cleanup function",
                )
                logger.info(f"Stopped ECS task: {ecs_task_arn}")
            except Exception as e:
                logger.error(f"Error stopping ECS task {ecs_task_arn}: {str(e)}")
                # Continue with DynamoDB deletion even if ECS task stop fails

        # Delete the task from DynamoDB
        table.delete_item(
            Key={"PK": task["PK"], "SK": task["SK"]},
            ConditionExpression="attribute_exists(PK)",
        )

        metrics.add_metric(name="TaskKilled", unit=MetricUnit.Count, value=1)
        logger.info(f"Deleted task {task_id} from DynamoDB")
        return True

    except Exception as e:
        logger.error(f"Error deleting task: {str(e)}", exc_info=True)
        return False


@logger.inject_lambda_context
@metrics.log_metrics(capture_cold_start_metric=True)
def lambda_handler(event: dict, context: LambdaContext):
    # Generate random number of tasks to delete (5-15)
    num_tasks = random.randint(5, 15)
    logger.info(f"Attempting to delete {num_tasks} assigned tasks")

    # Try to delete the specified number of tasks
    for _ in range(num_tasks):
        delete_single_task()

    return {
        "statusCode": 200,
    }
