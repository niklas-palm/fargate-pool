.ONESHELL:
SHELL := /bin/bash

# Help function to display available commands
.PHONY: help
help:
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-30s\033[0m %s\n", $$1, $$2}'

# Default target when just running 'make'
.DEFAULT_GOAL := help

# Environment variables with default values
export STACKNAME ?= fargate-pool
export REGION ?= eu-west-1
export ENVIRONMENT ?= dev
export PROJECT ?= fargate-pool

export INFRA_DIR := infra


# Mark targets that don't create files as .PHONY
.PHONY: validate build deploy delete go outputs monitor-tasks grab-task logs

validate: ## Validates the SAM template
	@echo "Validating SAM template..."
	cd $(INFRA_DIR) && sam validate \
		--template $(TEMPLATE) \
		--region $(REGION)

build: ## Downloads all dependencies and builds resources
	@echo "Building SAM application..."
	cd $(INFRA_DIR) && sam build

build.container: ## Downloads all dependencies and builds resources
	@echo "Building SAM application..."
	cd $(INFRA_DIR) && sam build --use-container

deploy: ## Deploys the artifacts from the previous build
	@echo "Deploying stack $(STACKNAME) to region $(REGION)..."
	cd $(INFRA_DIR) && sam deploy \
		--stack-name $(STACKNAME)-$(ENVIRONMENT) \
		--resolve-s3 \
		--capabilities CAPABILITY_IAM \
		--region $(REGION) \
		--no-fail-on-empty-changeset \
		--no-confirm-changeset \
		--tags project=$(PROJECT) environment=$(ENVIRONMENT) \

delete: ## Deletes the CloudFormation stack
	@echo "Deleting stack $(STACKNAME)-$(ENVIRONMENT) from region $(REGION)..."
	sam delete \
		--stack-name $(STACKNAME)-$(ENVIRONMENT) \
		--region $(REGION) \
		--no-prompts

go: build deploy ## Build and deploys the stack

outputs: ## Fetch CloudFormation outputs and store them in output file, and then in GHA env
	@echo "Fetching CloudFormation outputs..."
	@aws cloudformation describe-stacks \
		--stack-name $(STACKNAME)-$(ENVIRONMENT) \
		--region $(REGION) \
		--query 'Stacks[0].Outputs[*].{Key:OutputKey,Value:OutputValue}' \
		--output json > .stack-outputs.json
	@./scripts/set-outputs.sh

outputs.local: ## Fetch CloudFormation outputs and store them in output file
	@echo "Fetching CloudFormation outputs..."
	@aws cloudformation describe-stacks \
		--stack-name $(STACKNAME)-$(ENVIRONMENT) \
		--region $(REGION) \
		--query 'Stacks[0].Outputs[*].{Key:OutputKey,Value:OutputValue}' \
		--output json > .stack-outputs.json


build-api: ## Build the API Docker image
	@echo "Building API Docker image..."
	docker build -t task-api ./frontend/api

run-api: outputs.local build-api
	@echo "Running API container..."
	$(eval DYNAMODB_TABLE_NAME := $(shell jq -r '.[] | select(.Key=="TasksTableName") | .Value' .stack-outputs.json))
	$(eval AWS_REGION := $(REGION))
	docker run --name task-api-container \
		-p 5001:5000 \
		-e DYNAMODB_TABLE_NAME=$(DYNAMODB_TABLE_NAME) \
		-e AWS_REGION=$(AWS_REGION) \
		-e AWS_ACCESS_KEY_ID=$(AWS_ACCESS_KEY_ID) \
		-e AWS_SECRET_ACCESS_KEY=$(AWS_SECRET_ACCESS_KEY) \
		-e AWS_SESSION_TOKEN=$(AWS_SESSION_TOKEN) \
		task-api

add-tasks: outputs.local ## Add specified number of tasks to the pools
	@echo "Adding tasks through EventBridge..."
	@read -p "Enter the number of tasks to add: " num_tasks; \
	python scripts/add_tasks.py $$num_tasks

drain: outputs.local ## Drain all tasks and related DynamoDB data
	@echo "Draining task pool..."
	@read -p "Are you sure you want to drain all tasks? This action cannot be undone. (y/N): " confirm; \
	if [ "$$confirm" = "y" ] || [ "$$confirm" = "Y" ]; then \
		python scripts/drain_tasks.py; \
	else \
		echo "Operation cancelled."; \
	fi

start-local: outputs.local stop-api build-api ## Start both the API container and frontend UI
	@echo "Starting local development environment..."
	@# Start the API container in the background
	$(eval DYNAMODB_TABLE_NAME := $(shell jq -r '.[] | select(.Key=="TasksTableName") | .Value' .stack-outputs.json))
	$(eval AWS_REGION := $(REGION))
	docker run -d --name task-api-container \
		-p 5001:5000 \
		-e DYNAMODB_TABLE_NAME=$(DYNAMODB_TABLE_NAME) \
		-e AWS_REGION=$(AWS_REGION) \
		-e AWS_ACCESS_KEY_ID=$(AWS_ACCESS_KEY_ID) \
		-e AWS_SECRET_ACCESS_KEY=$(AWS_SECRET_ACCESS_KEY) \
		-e AWS_SESSION_TOKEN=$(AWS_SESSION_TOKEN) \
		task-api
	@echo "API container started on http://localhost:5001"
	
	@# Start the frontend
	@echo "Starting frontend..."
	@cd frontend/ui && \
	npm install && \
	npm run dev

stop-local: stop-api ## Stop all local development services
	@echo "Stopping local development environment..."
	@# Additional cleanup if needed
	@echo "Local environment stopped."

stop-api: ## Stop and remove the API container
	@echo "Stopping and removing API container..."
	-docker stop task-api-container
	-docker rm task-api-container


logs: ## Fetches the latest logs
	@echo "Fetching latest logs from stack: $(STACKNAME)-$(ENVIRONMENT)"
	sam logs \
		--stack-name $(STACKNAME)-$(ENVIRONMENT) \
		--region $(REGION)

logs.error: ## Fetches the logs with ERROR
	@echo "Fetching latest logs from stack: $(STACKNAME)-$(ENVIRONMENT)"
	sam logs \
		--stack-name $(STACKNAME)-$(ENVIRONMENT) \
		--region $(REGION) \
		--filter ERROR 


logs.tail: ## Tails the logs in real-time
	@echo "Starting to tail the logs from stack: $(STACKNAME)-$(ENVIRONMENT))"
	sam logs \
		--stack-name $(STACKNAME)-$(ENVIRONMENT) \
		--region $(REGION) \
		--tail


logs.error.tail: ## Tails the logs, filering for ERROR
	@echo "Fetching latest logs from stack: $(STACKNAME)-$(ENVIRONMENT)"
	sam logs \
		--stack-name $(STACKNAME)-$(ENVIRONMENT) \
		--region $(REGION) \
		--filter ERROR \
		--tail
