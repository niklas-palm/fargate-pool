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

# Mark targets that don't create files as .PHONY
.PHONY: validate build deploy delete go outputs 

validate: ## Validates the SAM template
	@echo "Validating SAM template..."
	sam validate \
		--template $(TEMPLATE) \
		--region $(REGION)

build: ## Downloads all dependencies and builds resources
	@echo "Building SAM application..."
	sam build

build.container: ## Downloads all dependencies and builds resources
	@echo "Building SAM application..."
	sam build --use-container

deploy: ## Deploys the artifacts from the previous build
	@echo "Deploying stack $(STACKNAME) to region $(REGION)..."
	sam deploy \
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