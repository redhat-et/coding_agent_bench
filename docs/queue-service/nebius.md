# Nebius Setup

The queue service supports starting and stopping vLLM server instances automatically using [Nebius](https://nebius.com/).
When enabled, the queue service will create a Nebius VM, SSH into the instance, start the vLLM server for the next model in the queue, run the benchmark job against that model, swap the running model for the next model in the queue, then spin down the Nebius VM when the queue is empty.

To connect the queue service to Nebius, first [set up an AI Cloud account](https://docs.nebius.com/signup-billing/sign-up).

After setting up the account, [install the CLI](https://docs.nebius.com/cli/install) and [login to your account](https://docs.nebius.com/cli/configure).

Then run the following commands to create a service account in your project:

```sh
export SA_NAME=<name-for-new-sa>
export PROJECT_ID=<project-id>

# Create Service Account
export SA_ID=$(nebius iam service-account create \
  --parent-id $PROJECT_ID \
  --name $SA_NAME \
  --format json | jq -r '.metadata.id')

# Create and attach an authorized key
nebius iam auth-public-key generate \
  --service-account-id $SA_ID \
  --output ~/.nebius/$SA_ID-credentials.json

# Configure the SA as an editor in the project
# If there is not an editors group, first create one in the console 
# and give it global editor permits
export EDITOR_GROUP_ID=$(nebius iam group get-by-name \
  --name editors --parent-id $PROJECT_ID \
  --format json | jq -r '.metadata.id')

nebius iam group-membership create \
  --parent-id $EDITOR_GROUP_ID \
  --member-id $SA_ID
```

## Setup

### Openshift

Once the service account is created, copy `deploy/job-queue/base/nebius-secret.example.yaml`. Do not commit the resulting file:

```sh
cp deploy/job-queue/base/nebius-secret.example.yaml deploy/job-queue/base/nebius-secret.yaml
```

Fill in the secret values using the values from the previous steps. You can find the tenant ID and subnet ID in the Nebius UI:

```yaml
kind: Secret
metadata:
  name: nebius-secret
type: Opaque
stringData:
  NEBIUS_ENABLED: "1"
  NEBIUS_SERVICE_ACCOUNT_CREDS: |
    <cat ~/.nebius/$SA_ID-credentials.json>
  NEBIUS_USER: <SA_NAME>
  NEBIUS_PARENT_ID: <PROJECT_ID>
  NEBIUS_TENANT_ID: <nebius-tenant-id>
  NEBIUS_SERVICE_ACCOUNT_ID: <SA_ID>
  NEBIUS_SUBNET_ID: <nebius-subnet-id>
  NEBIUS_INSTANCE_NAME_PREFIX: job-queue-worker
  NEBIUS_IDLE_TIMEOUT_SECONDS: "600"
  HF_TOKEN: <optional-hugging-face-token>
```

Apply the secret and restart the queue service:

```sh
oc apply -f deploy/job-queue/base/nebius-secret.yaml -n <project>
oc rollout restart deployment/job-queue -n <project>
```

When creating a job, set `server_url` to `nebius-<resource>` to use a managed Nebius instance with the specified GPU resource (e.g. `nebius-h200`, `nebius-b200`). Available resources are defined in `RESOURCE_CONFIG_REGISTRY`.

### Local

Create an SSH key for the Nebius VMs:

```sh
ssh-keygen -t ed25519 -f ~/.ssh/nebius
```

Set the following environment variables in your `.env` using the values from the previous steps. You can find the tenant ID and subnet ID in the Nebius UI:

```
NEBIUS_ENABLED=1
NEBIUS_SERVICE_ACCOUNT_CREDS=<cat ~/.nebius/$SA_ID-credentials.json>
NEBIUS_USER=<SA_NAME>
NEBIUS_SSH_PUBLIC_KEY_PATH=/path/to/.ssh/nebius.pub
NEBIUS_SSH_PRIVATE_KEY_PATH=/path/to/.ssh/nebius
NEBIUS_PARENT_ID=<PROJECT_ID>
NEBIUS_TENANT_ID=<nebius-tenant-id>
NEBIUS_SERVICE_ACCOUNT_ID=<SA_ID>
NEBIUS_SUBNET_ID=<nebius-subnet-id>
NEBIUS_INSTANCE_NAME_PREFIX=job-queue-worker
NEBIUS_IDLE_TIMEOUT_SECONDS=600
HF_TOKEN=<optional-hugging-face-token>
```

## Usage

When creating a job, set `server_url` to `nebius-<resource>` to use a managed Nebius instance with the specified GPU resource (e.g. `nebius-h200`, `nebius-b200`). 
Available configuration options can be found at `$JOB_QUEUE_URL/api/nebius-configs`.

When creating a job, set `model_name` to one of the available models in the queue service.
Available models can be found at `$JOB_QUEUE_URL/api/models`.

For example:

```sh
curl -X POST $JOB_QUEUE_URL/jobs \
    -d '{"job_name": "test", "agent": "pi", "dataset": "swe-bench/swe-bench-verified", "model_name": "Qwen/Qwen3.6-27B", "server_url": "nebius-b200", "n_tasks": 1}' \
    -H "Content-Type: application/json" \
    -H "X-API-Key: <your-api-key>"
```

### Supported GPU configurations

Fetch supported GPU configurations from the queue service:

```sh
curl $JOB_QUEUE_URL/api/nebius-configs
```

### Supported Models

Fetch supported models from the queue service:

```sh
curl $JOB_QUEUE_URL/api/models
```
