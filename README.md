# Fargate pool

Sample setting up a compute pool with ECS Fargate

The pool sets up x number of "hot" tasks, pre-launched and ready for assingment. A separate process monitors the number of hot tasts and ensures there's at least x host tasks at any given time.

### Prerequisites

- [AWS CLI](https://docs.aws.amazon.com/cli/latest/userguide/getting-started-install.html) installed
- [AWS SAM](https://docs.aws.amazon.com/serverless-application-model/latest/developerguide/install-sam-cli.html) installed
- [OIDC](https://docs.github.com/en/actions/security-for-github-actions/security-hardening-your-deployments/configuring-openid-connect-in-amazon-web-services) set up between your AWS acccount and Github (grants github access to assume a role in your account)

### Usage

1. Change the role you've cofigured Github to have access to in the `.github/workflows` files in the top of both files. This role will be assumed by the Github worker to perform actions in your AWS environment (push a container or deploy cloudformation)

2. Check in repo.

> [!NOTE]  
> During the first deployment there's a chance the output variables from the cloudformation stack aren't available. That means that ECR repository etc can't be resolved when pushing the container. This may occur during the first deployment.

3.

### Considerations

- With this approach, every task / container gets its own public IP. This is the simplest solution, not requiring any smart routing in the backend to route user requests to their respective container, but it comes with additional cost as AWS now charges per public IP.
-
