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
        task_id = task["TaskId"]
        try:
            ecs.stop_task(cluster=cluster_name, task=task_id)
            print(f"Stopped ECS task: {task_id}")
        except Exception as e:
            print(f"Error stopping ECS task {task_id}: {str(e)}")

    # Delete all items from DynamoDB
    with table.batch_writer() as batch:
        for task in tasks:
            batch.delete_item(Key={"PK": task["PK"], "SK": task["SK"]})

    print(f"Deleted {len(tasks)} items from DynamoDB")


if __name__ == "__main__":
    drain_tasks()
    print("Task pool drained successfully.")
