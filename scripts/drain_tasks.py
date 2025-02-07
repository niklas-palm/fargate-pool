import boto3
import json

# Load stack outputs
with open(".stack-outputs.json", "r") as f:
    outputs = json.load(f)

# Extract necessary values from stack outputs
table_name = next(item["Value"] for item in outputs if item["Key"] == "TasksTableName")
cluster_name = next(item["Value"] for item in outputs if item["Key"] == "ClusterName")

# Initialize AWS clients
ecs = boto3.client("ecs")
dynamodb = boto3.resource("dynamodb")
table = dynamodb.Table(table_name)


def drain_tasks():
    # Get all tasks from DynamoDB
    response = table.scan()
    tasks = response["Items"]

    # Stop all ECS tasks
    for task in tasks:
        if "EcsTaskArn" in task:  # Only try to stop if we have the ECS task ARN
            task_arn = task["EcsTaskArn"]
            try:
                # Extract just the task ID from the ARN if needed
                # task_arn format: arn:aws:ecs:region:account:task/cluster-name/task-id
                task_id = task_arn.split("/")[-1]
                ecs.stop_task(cluster=cluster_name, task=task_id)
                print(f"Stopped ECS task: {task_id}")
            except Exception as e:
                print(f"Error stopping ECS task {task_id}: {str(e)}")
        else:
            print(
                f"No ECS task ARN found for task with SK: {task.get('SK', 'unknown')}"
            )

    # Delete all items from DynamoDB
    with table.batch_writer() as batch:
        for task in tasks:
            batch.delete_item(Key={"PK": task["PK"], "SK": task["SK"]})

    print(f"Deleted {len(tasks)} items from DynamoDB")


if __name__ == "__main__":
    drain_tasks()
    print("Task pool drained successfully.")
