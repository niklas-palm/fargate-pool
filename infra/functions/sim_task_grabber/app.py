import boto3
import random
import os
import uuid
from datetime import datetime, timezone
from boto3.dynamodb.conditions import Key
from aws_lambda_powertools import Logger, Metrics
from aws_lambda_powertools.utilities.typing import LambdaContext

logger = Logger()
metrics = Metrics()

dynamodb = boto3.resource("dynamodb")
table = dynamodb.Table(os.environ["TABLE_NAME"])


def generate_user_id():
    """Generate a random user ID"""
    return f"user_{uuid.uuid4().hex[:8]}"


def grab_single_task(user_id):
    """Attempt to grab a single task"""
    try:
        response = table.query(
            IndexName="StatusIndex",
            KeyConditionExpression=Key("Status").eq("RUNNING"),
            Limit=1,
        )

        if not response["Items"]:
            logger.info("No available tasks found")
            return False

        task = response["Items"][0]
        logger.info(f"Found available task: {task['TaskId']}")

        table.update_item(
            Key={"PK": task["PK"], "SK": task["SK"]},
            UpdateExpression="SET #status = :new_status, AssignedTo = :user, UpdatedAt = :now",
            ConditionExpression="#status = :old_status",
            ExpressionAttributeNames={"#status": "Status"},
            ExpressionAttributeValues={
                ":new_status": "ASSIGNED",
                ":old_status": "RUNNING",
                ":user": user_id,
                ":now": datetime.now(timezone.utc).isoformat(),
            },
        )
        logger.info(f"Task {task['TaskId']} assigned to user {user_id}")
        return True

    except Exception as e:
        logger.error(f"Error grabbing task: {str(e)}", exc_info=True)
        return False


@logger.inject_lambda_context
@metrics.log_metrics(capture_cold_start_metric=True)
def lambda_handler(event: dict, context: LambdaContext):
    # Generate random number of tasks to grab (5-15)
    num_tasks = random.randint(5, 15)
    logger.info(f"Attempting to grab {num_tasks} tasks")

    # Try to grab the specified number of tasks
    for _ in range(num_tasks):
        user_id = generate_user_id()
        grab_single_task(user_id)

    return {
        "statusCode": 200,
    }
