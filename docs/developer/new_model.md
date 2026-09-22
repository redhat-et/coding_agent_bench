# Add a New Model

This will walk you through the two step process of adding a new model to the project: first validating the model and then registering it.

## Validate a New Model

Before a model can be added to the project, it must be validated to be able to run on at least one Nebius instances.

### Process Flow

1. Create GPU instance on Nebius (via CLI)  
2. SSH in and run setup commands  
3. Start vLLM model server  
4. Run benchmark(s)  
5. Delete Nebius instance when done

### Prerequisites

- [Install the Nebius CLI](https://docs.nebius.com/cli/install) and [log in](https://docs.nebius.com/cli/configure)  
- Join our Nebius organization (Reach out to Taylor Agarwal)  
- Create a service account and attach an authorized key

```shell
export SA_NAME=<name-for-new-sa>
export PROJECT_ID=project-i00hz9y8pr00mf5rzvw82k

# Create Service Account
export SA_ID=$(nebius iam service-account create \
  --name $SA_NAME \
  --format json | jq -r '.metadata.id')

# Create and attach an authorized key
nebius iam auth-public-key generate \
  --service-account-id $SA_ID \
  --output ~/.nebius/$SA_ID-credentials.json

# Configure the SA as an editor in the project
export EDITOR_GROUP_ID=$(nebius iam group get-by-name \
  --name editors --parent-id $PROJECT_ID \
  --format json | jq -r '.metadata.id')

nebius iam group-membership create \
  --parent-id $EDITOR_GROUP_ID \
  --member-id $SA_ID
```

### Step 1: Create an SSH Key Pair

```shell
ssh-keygen -t ed25519 -f ~/.ssh/nebius

export USER_DATA=$(jq -Rrs '.' <<EOF
#cloud-config
users:
  - name: $USER
    sudo: ALL=(ALL) NOPASSWD:ALL
    shell: /bin/bash
    ssh_authorized_keys:
      - $(cat ~/.ssh/nebius.pub)
EOF
)
```

### Step 2: Get/Create an Instance

```shell
export INSTANCE_NAME=<name-of-instance>
export SA_ID=<your-sa-id>
export PROJECT_ID=project-i00hz9y8pr00mf5rzvw82k

# Check if the instance already exists
nebius compute instance get-by-name --name $INSTANCE_NAME

# Create the instance if it does not exist
nebius compute v1 instance create \
  --parent-id $PROJECT_ID \
  --name $INSTANCE_NAME \
  --service-account-id $SA_ID \
  --resources-platform gpu-b200-sxm-a \
  --resources-preset 1gpu-20vcpu-224gb \
  --network-interfaces '[{"subnetId":"vpcsubnet-i00y73e2kyyjze510h","name":"eth0","ipAddress":{},"publicIpAddress":{}}]' \
  --boot-disk-attach-mode read_write \
  --boot-disk-managed-disk-name $INSTANCE_NAME-boot-disk \
  --boot-disk-managed-disk-size-bytes 1374389534720 \
  --boot-disk-managed-disk-block-size-bytes 4096 \
  --boot-disk-managed-disk-type network_ssd \
  --boot-disk-managed-disk-source-image-family-image-family ubuntu24.04-cuda13.0 \
  --boot-disk-device-id boot-disk \
  --cloud-init-user-data "$USER_DATA" \
  --reservation-policy-policy forbid \
  --preemptible-on-preemption stop

# Get the public IP Address for the instance
export PUBLIC_IP_ADDRESS=$(nebius compute instance get-by-name \
  --name $INSTANCE_NAME \
  --format json \                                                                   
  | jq -r '.status.network_interfaces[0].public_ip_address.address | split("/")[0]')

echo $PUBLIC_IP_ADDRESS
```

### Step 3: SSH into Instance

```shell
ssh -i ~/.ssh/nebius $USER@$PUBLIC_IP_ADDRESS
```

### Step 4: Set HF_TOKEN (optional, speeds up model downloads)

```shell
export HF_TOKEN=<your-token>
```

### Step 5: Run Your vLLM Command

Refer to the examples in the [Validated Models](../validated_models.md).

You can find the commands for many models in [vLLM's Recipes](https://recipes.vllm.ai/).

### Step 6: Connect to Running Instance

```shell
VLLM_SERVER_PUBLIC_URL=http://$PUBLIC_IP_ADDRESS:8000
echo "The vLLM server is located at $VLLM_SERVER_PUBLIC_URL"
```

## Register the Model in `coding_agent_bench`

Once the model has been validated, it can be added to `coding_agent_bench` to be used in benchmark runs on managed Nebius instances.

First, add a new child class of `ModelConfig` with the model-specific arguments to `src/coding_agent_bench/models/configs.py`.

Then register the new class in `MODEL_CONFIGS` and `MODEL_REGISTRY` in `src/coding_agent_bench/models/__init__.py`.

Please also add the model to the [Validated Models docs](../validated_models.md#validated-vllm-commands).
