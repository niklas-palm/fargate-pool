import boto3
import os
import json
import time
from datetime import datetime
from aws_lambda_powertools import Logger, Metrics
from aws_lambda_powertools.metrics import MetricUnit
from aws_lambda_powertools.utilities.typing import LambdaContext

logger = Logger()
metrics = Metrics()

ecs = boto3.client("ecs")
ec2 = boto3.client("ec2")
dynamodb = boto3.resource("dynamodb")

CLUSTER_NAME = os.environ["CLUSTER_NAME"]
TASK_DEFINITION = os.environ["TASK_DEFINITION"]
TABLE_NAME = os.environ["TABLE_NAME"]
SUBNET_ID1 = os.environ["SUBNET_ID1"]
SUBNET_ID2 = os.environ["SUBNET_ID2"]
SECURITY_GROUP_ID = os.environ["SECURITY_GROUP_ID"]

table = dynamodb.Table(TABLE_NAME)


def get_task_failure_reason(task_details):
    """Extract failure reason from task details"""
    if not task_details.get("tasks"):
        return "No task details available"

    task = task_details["tasks"][0]

    # Check for stopped reason
    if "stoppedReason" in task:
        return task["stoppedReason"]

    # Check for failures array
    if "failures" in task:
        return "; ".join(
            failure.get("reason", "Unknown reason") for failure in task["failures"]
        )

    return "Unknown failure reason"


def launch_task():
    timestamp = datetime.utcnow().isoformat()
    task_id = f"task_{timestamp}"
    start_time = time.time()

    # Create initial entry in DynamoDB
    table.put_item(
        Item={
            "PK": "TASK#POOL",
            "SK": f"TASK#{task_id}",
            "TaskId": task_id,
            "Status": "LAUNCHING",
            "CreatedAt": timestamp,
            "UpdatedAt": timestamp,
        }
    )
    logger.info(f"Created initial task entry for {task_id}")

    try:
        # Launch the ECS task
        response = ecs.run_task(
            cluster=CLUSTER_NAME,
            taskDefinition=TASK_DEFINITION,
            launchType="FARGATE",
            networkConfiguration={
                "awsvpcConfiguration": {
                    "subnets": [SUBNET_ID1, SUBNET_ID2],
                    "securityGroups": [SECURITY_GROUP_ID],
                    "assignPublicIp": "ENABLED",
                }
            },
        )

        ecs_task = response["tasks"][0]
        ecs_task_arn = ecs_task["taskArn"]

        # Update DDB with ECS task info
        table.update_item(
            Key={"PK": "TASK#POOL", "SK": f"TASK#{task_id}"},
            UpdateExpression="SET EcsTaskArn = :arn, UpdatedAt = :now",
            ExpressionAttributeValues={
                ":arn": ecs_task_arn,
                ":now": datetime.utcnow().isoformat(),
            },
        )

        try:
            # Wait for task to be running and get IP
            waiter = ecs.get_waiter("tasks_running")

            time.sleep(
                0.25
            )  # To avoid a race condition with the waiter. boto3 should do this....

            waiter.wait(cluster=CLUSTER_NAME, tasks=[ecs_task_arn])

            # Get task details after waiter
            task_details = ecs.describe_tasks(
                cluster=CLUSTER_NAME, tasks=[ecs_task_arn]
            )

            # Check if task is actually running
            task_status = task_details["tasks"][0]["lastStatus"]
            if task_status != "RUNNING":
                failure_reason = get_task_failure_reason(task_details)
                raise Exception(
                    f"Task failed to reach RUNNING state. Status: {task_status}. Reason: {failure_reason}"
                )

            eni_id = task_details["tasks"][0]["attachments"][0]["details"][1]["value"]
            ec2_response = ec2.describe_network_interfaces(NetworkInterfaceIds=[eni_id])
            public_ip = ec2_response["NetworkInterfaces"][0]["Association"]["PublicIp"]

        except Exception as waiter_error:
            # Get the final task status to understand what went wrong
            try:
                task_details = ecs.describe_tasks(
                    cluster=CLUSTER_NAME, tasks=[ecs_task_arn]
                )
                failure_reason = get_task_failure_reason(task_details)
                logger.error(f"Task startup failed. Details: {failure_reason}")

                # Add specific metric for different failure types
                failure_type = (
                    "WaiterTimeout"
                    if "Waiter" in str(waiter_error)
                    else "TaskStartupFailure"
                )
                metrics.add_metric(name=failure_type, unit=MetricUnit.Count, value=1)

            except Exception as e:
                logger.error(f"Failed to get task failure details: {str(e)}")
                failure_reason = str(waiter_error)

            raise Exception(f"Task failed to start: {failure_reason}")

        # Calculate and record startup duration
        startup_duration = time.time() - start_time
        logger.info(
            f"Task {task_id} is now running with IP {public_ip}. Startup took {startup_duration:.2f} seconds"
        )

        # Add metrics for startup time and success
        metrics.add_metric(
            name="TaskStartupDuration", unit=MetricUnit.Seconds, value=startup_duration
        )
        metrics.add_metric(name="TasksLaunched", unit=MetricUnit.Count, value=1)

        # Update task as running
        table.update_item(
            Key={"PK": "TASK#POOL", "SK": f"TASK#{task_id}"},
            UpdateExpression="SET #status = :status, PublicIp = :ip, UpdatedAt = :now",
            ExpressionAttributeNames={"#status": "Status"},
            ExpressionAttributeValues={
                ":status": "RUNNING",
                ":ip": public_ip,
                ":now": datetime.utcnow().isoformat(),
            },
        )

    except Exception as e:
        # Calculate and record failure duration
        failure_duration = time.time() - start_time
        logger.exception(
            f"Error launching task {task_id} after {failure_duration:.2f} seconds"
        )

        metrics.add_metric(name="TaskLaunchErrors", unit=MetricUnit.Count, value=1)
        metrics.add_metric(
            name="TaskStartupFailureDuration",
            unit=MetricUnit.Seconds,
            value=failure_duration,
        )

        table.update_item(
            Key={"PK": "TASK#POOL", "SK": f"TASK#{task_id}"},
            UpdateExpression="SET #status = :status, ErrorMessage = :error, UpdatedAt = :now",
            ExpressionAttributeNames={"#status": "Status"},
            ExpressionAttributeValues={
                ":status": "ERROR",
                ":error": str(e),
                ":now": datetime.utcnow().isoformat(),
            },
        )
        raise


@logger.inject_lambda_context
@metrics.log_metrics(capture_cold_start_metric=True)
def lambda_handler(event: dict, context: LambdaContext):
    logger.info("Received TaskGrabbed event, launching new task")
    try:
        launch_task()
    except Exception as e:
        logger.error(f"Failed to launch new task: {str(e)}")
        metrics.add_metric(name="FailedTaskLaunches", unit=MetricUnit.Count, value=1)
        raise

    return {"statusCode": 200, "body": json.dumps("Task launch completed")}
