from flask import Flask, jsonify, request
from flask_cors import CORS
import boto3
from boto3.dynamodb.conditions import Key
import os
from datetime import datetime
import logging

app = Flask(__name__)
CORS(app)  # This will enable CORS for all routes

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Add a file handler
file_handler = logging.FileHandler("api.log")
file_handler.setLevel(logging.INFO)
file_formatter = logging.Formatter(
    "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
file_handler.setFormatter(file_formatter)
logger.addHandler(file_handler)

dynamodb = boto3.resource("dynamodb", region_name=os.environ.get("AWS_REGION"))
table_name = os.environ.get("DYNAMODB_TABLE_NAME")
table = dynamodb.Table(table_name)

logger.info(
    f"Initialized with table: {table_name} in region: {os.environ.get('AWS_REGION')}"
)


@app.route("/grab-task", methods=["POST"])
def grab_task():
    user_id = request.json.get("user_id")
    logger.info(f"Received grab-task request for user: {user_id}")

    if not user_id:
        logger.warning("Grab-task request received without user ID")
        return jsonify({"error": "User ID is required"}), 400

    try:
        response = table.query(
            IndexName="StatusIndex",
            KeyConditionExpression=Key("Status").eq("RUNNING"),
            Limit=1,
        )

        if not response["Items"]:
            logger.info("No available tasks found")
            return jsonify({"error": "No available tasks"}), 404

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
                ":now": datetime.utcnow().isoformat(),
            },
        )
        logger.info(f"Task {task['TaskId']} assigned to user {user_id}")

        return (
            jsonify(
                {
                    "message": "Task grabbed successfully",
                    "task_id": task["TaskId"],
                    "public_ip": task.get("PublicIp"),
                }
            ),
            200,
        )

    except Exception as e:
        logger.error(f"Error in grab_task: {str(e)}", exc_info=True)
        return jsonify({"error": str(e)}), 500


@app.route("/monitor", methods=["GET"])
def monitor_tasks():
    logger.info("Received monitor request")
    try:
        statuses = ["LAUNCHING", "RUNNING", "ASSIGNED"]
        counts = {}

        for status in statuses:
            response = table.query(
                IndexName="StatusIndex", KeyConditionExpression=Key("Status").eq(status)
            )
            counts[status.lower()] = response["Count"]

        logger.info(f"Current task counts: {counts}")
        return (
            jsonify(
                {
                    "launching": counts["launching"],
                    "available": counts["running"],
                    "occupied": counts["assigned"],
                }
            ),
            200,
        )

    except Exception as e:
        logger.error(f"Error in monitor_tasks: {str(e)}", exc_info=True)
        return jsonify({"error": str(e)}), 500


if __name__ == "__main__":
    logger.info("Starting the Flask application")
    app.run(host="0.0.0.0", port=5000)
