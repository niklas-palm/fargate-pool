# scripts/add_tasks.py
import boto3
import sys
import json
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed

# Load stack outputs
with open(".stack-outputs.json", "r") as f:
    outputs = json.load(f)

# Extract necessary values from stack outputs
event_bus_name = next(
    item["Value"] for item in outputs if item["Key"] == "TaskEventBusName"
)

# Initialize AWS client
events = boto3.client("events")


def publish_task_event():
    try:
        response = events.put_events(
            Entries=[
                {
                    "Source": "com.fargate-pool",
                    "DetailType": "TaskGrabbed",
                    "Detail": json.dumps({"timestamp": datetime.utcnow().isoformat()}),
                    "EventBusName": event_bus_name,
                }
            ]
        )

        if response["FailedEntryCount"] > 0:
            return f"Failed to publish event: {response['Entries'][0]['ErrorMessage']}"
        return "Successfully published task event"
    except Exception as e:
        return f"Failed to publish event: {str(e)}"


def publish_events_parallel(num_events):
    with ThreadPoolExecutor(max_workers=10) as executor:
        futures = [executor.submit(publish_task_event) for _ in range(num_events)]
        for future in as_completed(futures):
            print(future.result())


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python add_tasks.py <number_of_tasks>")
        sys.exit(1)

    num_tasks = int(sys.argv[1])
    print(f"Publishing {num_tasks} task events to EventBus: {event_bus_name}")
    publish_events_parallel(num_tasks)
    print(f"Attempted to publish {num_tasks} task events.")
