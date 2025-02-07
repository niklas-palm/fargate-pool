from aws_lambda_powertools import Logger, Metrics
from aws_lambda_powertools.metrics import MetricUnit
from aws_lambda_powertools.utilities.typing import LambdaContext
import boto3
import json
import os

logger = Logger()
metrics = Metrics()
events_client = boto3.client("events")
event_bus_name = os.environ["EVENT_BUS_NAME"]


@logger.inject_lambda_context
@metrics.log_metrics(capture_cold_start_metric=True)
def lambda_handler(event: dict, context: LambdaContext):
    for record in event.get("Records", []):
        if record["eventName"] == "MODIFY":
            new_image = record["dynamodb"]["NewImage"]
            old_image = record["dynamodb"]["OldImage"]

            if (
                new_image.get("Status", {}).get("S") == "ASSIGNED"
                and old_image.get("Status", {}).get("S") == "RUNNING"
            ):
                logger.info("Task assigned, publishing event")
                try:
                    response = events_client.put_events(
                        Entries=[
                            {
                                "Source": "com.fargate-pool",
                                "DetailType": "TaskGrabbed",
                                "Detail": json.dumps(
                                    {
                                        "taskId": new_image.get("PK", {}).get("S"),
                                        "status": new_image.get("Status", {}).get("S"),
                                        "timestamp": new_image.get("UpdatedAt", {}).get(
                                            "S"
                                        ),
                                    }
                                ),
                                "EventBusName": event_bus_name,
                            }
                        ]
                    )

                    if response["FailedEntryCount"] > 0:
                        logger.error(f"Failed to publish event: {response}")
                        metrics.add_metric(
                            name="FailedEventPublish", unit=MetricUnit.Count, value=1
                        )
                    else:
                        logger.info("Successfully published event")
                        metrics.add_metric(
                            name="SuccessfulEventPublish",
                            unit=MetricUnit.Count,
                            value=1,
                        )

                except Exception as e:
                    logger.error(f"Failed to publish event: {str(e)}")
                    metrics.add_metric(
                        name="FailedEventPublish", unit=MetricUnit.Count, value=1
                    )

    return {"statusCode": 200, "body": json.dumps("Event publishing completed")}
