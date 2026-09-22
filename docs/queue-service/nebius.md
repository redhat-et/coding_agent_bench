# Nebius Setup

The queue service supports starting and stopping vLLM server instances automatically using [Nebius](https://nebius.com/).
When enabled, the queue service will create a Nebius VM, SSH into the instance, start the vLLM server for the next model in the queue, run the benchmark job against that model, swap the running model for the next model in the queue, then spin down the Nebius VM when the queue is empty.

To connect the queue service to Nebius, first [set up an AI Cloud account](https://docs.nebius.com/signup-billing/sign-up).

After setting up the account, [install the CLI](https://docs.nebius.com/cli/install) and [login to your account](https://docs.nebius.com/cli/configure).

Then run the following commands to create a service account in your project:

```sh
# Create a service account
export SA_ID=$(nebius iam service-account create \
  --name <service_account_name> \
  --format json | jq -r '.metadata.id')

# Create and attach an authorized key to the service account
nebius iam auth-public-key generate \
  --service-account-id $SA_ID \
  --output ~/.nebius/$SA_ID-credentials.json
```

## Setup

### Openshift

Once the service account is created, you can update your job queue secret with the following environment variables needed for Nebius:

```yaml
apiVersion: v1
kind: Secret
metadata:
  name:  job-queue-secret
stringData:
  API_KEY: <your-api-key>
  NEBIUS_ENABLED: '1'
  NEBIUS_SERVICE_ACCOUNT_CREDS: |
    <service-account-file-content>
  NEBIUS_PARENT_ID: <project-id>
  NEBIUS_TENANT_ID: <tenant-id>
  NEBIUS_SERVICE_ACCOUNT_ID: <service-account-id>
  NEBIUS_SUBNET_ID: <subnet-id>
  NEBIUS_INSTANCE_NAME_PREFIX: job-queue-worker
  NEBIUS_IDLE_TIMEOUT_SECONDS: '600'
  HF_TOKEN: <optional-huggingface-token>
type: Opaque
```

### Local

Set the following environment variables in your `.env`:

```
NEBIUS_ENABLED=1
NEBIUS_SERVICE_ACCOUNT_CREDS_PATH=
NEBIUS_USER=
NEBIUS_SSH_PUBLIC_KEY_PATH=
NEBIUS_SSH_PRIVATE_KEY_PATH=
NEBIUS_PARENT_ID=
NEBIUS_TENANT_ID=
NEBIUS_SERVICE_ACCOUNT_ID=
NEBIUS_SUBNET_ID=
NEBIUS_INSTANCE_NAME_PREFIX=cab-worker
NEBIUS_IDLE_TIMEOUT_SECONDS=600
HF_TOKEN=<optional>
```

## Usage

When creating a job, set `server_url` to `nebius-<resource>` to use a managed Nebius instance with the specified GPU resource (e.g. `nebius-h200`, `nebius-b200`). 
Available resources are defined in `RESOURCE_CONFIG_REGISTRY`.
The options are listed below as well, but use the `RESOURCE_CONFIG_REGISTRY` as the source of truth.

When creating a job, set `model_name` to one of the options in `MODEL_REGISTRY`.
The options are listed below as well, but use the `MODEL_REGISTRY` as the source of truth.

For example:

```sh
curl -X POST $JOB_QUEUE_URL/jobs \
    -d '{"job_name": "test", "agent": "pi", "dataset": "swe-bench/swe-bench-verified", "model_name": "Qwen/Qwen3.6-27B", "server_url": "nebius-b200", "n_tasks": 1}' \
    -H "Content-Type: application/json" \
    -H "X-API-Key: <your-api-key>"
```

## Supported Resources

| Hardware       | Supported | Resource Key   |
| -------------- | --------- | -------------- |
| gpu-h200-sxm   | ✅         | `nebius-h200`  |
| gpu-b200-sxm   | ✅         | `nebius-b200`  |
| gpu-b200-sxm-a | ✅         | `nebius-b200a` |

## Supported Models

| Model                                            | Supported | Resource Key                                       |
| ------------------------------------------------ | --------- | -------------------------------------------------- |
| Qwen/Qwen3.8-27B                                 | ✅         | `Qwen/Qwen3.8-27B`                                 |
| Qwen/Qwen3.8-27B-FP8                             | ✅         | `Qwen/Qwen3.8-27B-FP8`                             |
| RedHatAI/gemma-4-31B-it-FP8-block                | ✅         | `RedHatAI/gemma-4-31B-it-FP8-block`                |
| RedHatAI/gpt-oss-120b                            | ✅         | `RedHatAI/gpt-oss-120b`                            |
| RedHatAI/Mistral-Small-4-119B-2603-NVFP4         | ✅         | `RedHatAI/Mistral-Small-4-119B-2603-NVFP4`         |
| RedHatAI/NVIDIA-Nemotron-3-Super-120B-A12B-NVFP4 | ✅         | `RedHatAI/NVIDIA-Nemotron-3-Super-120B-A12B-NVFP4` |
| RedHatAI/Qwen3.6-27B-FP8                         | ✅         | `RedHatAI/Qwen3.6-27B-FP8`                         |
